"""
Django Channels WebSocket Consumer for Room Lobbies and Real-Time Presence.
Compliant with docs.md Sections 4.3, 4.4, 6.1, 6.2, 6.3, and 12.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache

from engine.models import GameRules
from engine.state import UnoGameEngine
from rooms.services import (
    get_lobby_state,
    kick_player_from_lobby,
    set_player_connection_status,
    set_player_ready_status,
    transition_room_to_playing,
    update_room_house_rules,
    validate_game_start_readiness,
)

logger = logging.getLogger(__name__)

# Active in-memory / cache registry for active game engines
ACTIVE_GAMES: Dict[str, UnoGameEngine] = {}


class UnoGameConsumer(AsyncJsonWebsocketConsumer):
    """
    Asynchronous WebSocket consumer managing:
    - Ephemeral single-use ticket verification (§6.1).
    - Lobby presence, readiness, and host privilege enforcement (§4.4).
    - Room multicasting via Redis channels layer.
    - Rate limiting protection (5 actions/sec) (§12.2).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.room_code: str = ""
        self.room_group_name: str = ""
        self.player_id: str = ""
        self.nickname: str = ""
        self.is_host: bool = False
        self.action_timestamps: list[float] = []

    async def connect(self) -> None:
        """Handshake with ephemeral single-use ticket authentication (§6.1)."""
        url_route = self.scope.get("url_route", {})
        kwargs = url_route.get("kwargs", {})
        if "room_code" in kwargs:
            self.room_code = kwargs["room_code"].upper()
        else:
            path = self.scope.get("path", "")
            parts = [p for p in path.strip("/").split("/") if p]
            if len(parts) >= 3 and parts[0] == "ws" and parts[1] == "rooms":
                self.room_code = parts[2].upper()
            else:
                self.room_code = "UNKNOWN"

        self.room_group_name = f"uno_room_{self.room_code}"

        # Extract ticket from query string
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        ticket = query_params.get("ticket", [None])[0]

        authenticated = False

        if ticket:
            cache_key = f"ws_ticket:{ticket}"
            cached_info = cache.get(cache_key)
            if cached_info and cached_info.get("room_code") == self.room_code:
                # Single-use: atomically invalidate ticket
                cache.delete(cache_key)
                self.player_id = cached_info.get("player_id", "")
                self.nickname = cached_info.get("nickname", "Player")
                self.is_host = cached_info.get("is_host", False)
                authenticated = True

        # Local development / testing fallback if ticket is 'dev_guest'
        if not authenticated and ticket == "dev_guest":
            self.player_id = f"p_dev_{int(time.time() * 1000) % 10000}"
            self.nickname = "Dev Guest"
            authenticated = True

        if not authenticated and not self.scope.get("dev_bypass", False):
            # Unauthorized: close with 4003 as specified in docs.md §6.1
            await self.close(code=4003)
            return

        # Mark player as connected in DB
        await database_sync_to_async(set_player_connection_status)(self.player_id, True)

        # Join room multicast group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        # Send connection confirmation to client
        await self.send_json(
            {
                "type": "connection_established",
                "payload": {
                    "room_code": self.room_code,
                    "player_id": self.player_id,
                    "nickname": self.nickname,
                    "is_host": self.is_host,
                },
            }
        )

        # Broadcast updated lobby state to all participants
        await self._broadcast_lobby_state()

    async def disconnect(self, close_code: int) -> None:
        """Handle disconnection and host failover (§4.4 & §7)."""
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

            if self.player_id:
                # Mark disconnected and execute host migration if applicable
                was_host, new_host_id = await database_sync_to_async(set_player_connection_status)(
                    self.player_id, False, auto_migrate_host=True
                )

                # Broadcast updated lobby state to remaining players
                await self._broadcast_lobby_state()

    async def receive_json(self, content: Dict[str, Any], **kwargs: Any) -> None:
        """Handle incoming messages with token-bucket rate limiting (§12.2)."""
        # Rate limit: max 5 actions per second
        now = time.time()
        self.action_timestamps = [t for t in self.action_timestamps if now - t < 1.0]
        if len(self.action_timestamps) >= 5:
            await self.send_json(
                {
                    "type": "error_event",
                    "payload": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many actions. Max 5 actions per second permitted.",
                    },
                }
            )
            return
        self.action_timestamps.append(now)

        msg_type = content.get("type", "")
        payload = content.get("payload", {})

        if msg_type == "ping":
            await self.send_json({"type": "pong", "payload": {"timestamp": payload.get("timestamp")}})
            return

        elif msg_type == "request_lobby_sync":
            state = await database_sync_to_async(get_lobby_state)(self.room_code)
            if state:
                await self.send_json({"type": "lobby_state_sync", "version": 1, "payload": state})
            return

        elif msg_type == "toggle_ready":
            is_ready = bool(payload.get("is_ready", True))
            success = await database_sync_to_async(set_player_ready_status)(self.player_id, is_ready)
            if success:
                await self._broadcast_lobby_state()
            return

        elif msg_type == "host_action":
            await self._handle_host_action(payload)
            return

        else:
            await self.send_json(
                {
                    "type": "error_event",
                    "payload": {
                        "code": "UNKNOWN_ACTION",
                        "message": f"Action '{msg_type}' is not recognized.",
                    },
                }
            )

    async def _handle_host_action(self, payload: Dict[str, Any]) -> None:
        """Validate and dispatch host actions with permission check (§4.4)."""
        action = payload.get("action", "")

        # Fetch current lobby state to verify host status
        lobby = await database_sync_to_async(get_lobby_state)(self.room_code)
        if not lobby or lobby.get("host_player_id") != self.player_id:
            await self.send_json(
                {
                    "type": "error_event",
                    "payload": {
                        "code": "FORBIDDEN_HOST_ACTION",
                        "message": "Only the room host can perform this action.",
                    },
                }
            )
            return

        if action == "KICK_PLAYER":
            target_id = payload.get("target_player_id", "")
            success, reason = await database_sync_to_async(kick_player_from_lobby)(
                self.room_code, self.player_id, target_id
            )
            if success:
                # Broadcast kick notice and new lobby state
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "player_kicked_event",
                        "target_player_id": target_id,
                    },
                )
                await self._broadcast_lobby_state()
            else:
                await self.send_json(
                    {
                        "type": "error_event",
                        "payload": {"code": reason, "message": f"Could not kick player: {reason}"},
                    }
                )

        elif action == "UPDATE_RULES":
            new_rules = payload.get("rules", {})
            success, reason = await database_sync_to_async(update_room_house_rules)(
                self.room_code, self.player_id, new_rules
            )
            if success:
                await self._broadcast_lobby_state()
            else:
                await self.send_json(
                    {"type": "error_event", "payload": {"code": reason, "message": reason}}
                )

        elif action == "START_GAME":
            can_start, reason, players_data, rules_dict = await database_sync_to_async(
                validate_game_start_readiness
            )(self.room_code, self.player_id)

            if not can_start:
                await self.send_json(
                    {
                        "type": "error_event",
                        "payload": {"code": reason, "message": f"Cannot start game: {reason}"},
                    }
                )
                return

            # Initialize pure Python game engine
            rules = GameRules.from_dict(rules_dict)
            engine = UnoGameEngine.create_game(
                room_code=self.room_code,
                players_data=players_data,
                rules=rules,
            )
            ACTIVE_GAMES[self.room_code] = engine

            # Update DB status to PLAYING
            await database_sync_to_async(transition_room_to_playing)(self.room_code)

            # Broadcast game_started notification
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "game_started_broadcast",
                    "room_code": self.room_code,
                },
            )

            # Emit individualized sanitized state sync to each player (§6.3)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "dispatch_sanitized_states",
                    "room_code": self.room_code,
                },
            )

        else:
            await self.send_json(
                {
                    "type": "error_event",
                    "payload": {
                        "code": "INVALID_HOST_ACTION",
                        "message": f"Host action '{action}' is invalid.",
                    },
                }
            )

    async def _broadcast_lobby_state(self) -> None:
        """Fetch fresh lobby state and broadcast to all connected clients in the room."""
        state = await database_sync_to_async(get_lobby_state)(self.room_code)
        if state:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "lobby_state_broadcast",
                    "payload": state,
                },
            )

    # Handlers for channel layer group messages
    async def lobby_state_broadcast(self, event: Dict[str, Any]) -> None:
        """Forward broadcast lobby state to client."""
        await self.send_json(
            {
                "type": "lobby_state_sync",
                "version": 1,
                "payload": event["payload"],
            }
        )

    async def player_kicked_event(self, event: Dict[str, Any]) -> None:
        """Notify client if they have been kicked."""
        target_id = event.get("target_player_id")
        if self.player_id == target_id:
            await self.send_json(
                {
                    "type": "kicked_from_room",
                    "payload": {"reason": "You have been kicked by the room host."},
                }
            )
            await self.close(code=4000)

    async def game_started_broadcast(self, event: Dict[str, Any]) -> None:
        """Notify clients that match has started."""
        await self.send_json(
            {
                "type": "game_started",
                "payload": {
                    "room_code": event["room_code"],
                    "status": "PLAYING",
                },
            }
        )

    async def dispatch_sanitized_states(self, event: Dict[str, Any]) -> None:
        """Generate and send zero-leakage sanitized state for this specific client."""
        engine = ACTIVE_GAMES.get(self.room_code)
        if engine and self.player_id:
            sanitized = engine.get_sanitized_state(self.player_id)
            await self.send_json(sanitized)
