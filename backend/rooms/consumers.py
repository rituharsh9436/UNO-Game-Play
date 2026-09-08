"""
WebSocket Consumers for Real-Time UNO Gameplay & Presence.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache

logger = logging.getLogger(__name__)


class UnoGameConsumer(AsyncJsonWebsocketConsumer):
    """
    ASGI Consumer handling real-time WebSocket communication for an UNO room.
    Enforces ticket-based authentication, group multicasting, and event dispatch.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.room_code: str = ""
        self.room_group_name: str = ""
        self.player_id: str = ""
        self.nickname: str = ""
        self.is_host: bool = False

    async def connect(self) -> None:
        """Handle incoming WebSocket connection with single-use ticket verification."""
        self.room_code = self.scope["url_route"]["kwargs"]["room_code"].upper()
        self.room_group_name = f"uno_room_{self.room_code}"

        # Parse query string to extract ticket
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        ticket = query_params.get("ticket", [None])[0]

        # In Sprint 1 baseline, validate ticket or allow dev connections if configured
        ticket_valid = False
        if ticket:
            cache_key = f"ws_ticket:{ticket}"
            cached_info = cache.get(cache_key)
            if cached_info and cached_info.get("room_code") == self.room_code:
                # Single-use: delete immediately
                cache.delete(cache_key)
                self.player_id = cached_info.get("player_id", "")
                self.nickname = cached_info.get("nickname", "Player")
                self.is_host = cached_info.get("is_host", False)
                ticket_valid = True

        # Close with 4003 (Unauthorized) if ticket invalid
        if not ticket_valid and not self.scope.get("dev_bypass", False):
            # If in local development or without ticket, permit connection if ticket param is "dev_guest"
            if ticket == "dev_guest":
                self.player_id = "dev_player"
                self.nickname = "Dev Guest"
                ticket_valid = True
            else:
                await self.close(code=4003)
                return

        # Join room broadcast group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        # Send initial connection confirmation
        await self.send_json(
            {
                "type": "connection_established",
                "payload": {
                    "room_code": self.room_code,
                    "player_id": self.player_id,
                    "nickname": self.nickname,
                    "is_host": self.is_host,
                    "message": "Connected to UNO room successfully.",
                },
            }
        )

    async def disconnect(self, close_code: int) -> None:
        """Handle connection termination and leave room group."""
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )
            # Broadcast disconnect event to other room participants
            if self.player_id:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "player_disconnected_event",
                        "player_id": self.player_id,
                        "nickname": self.nickname,
                    },
                )

    async def receive_json(self, content: Dict[str, Any], **kwargs: Any) -> None:
        """Handle incoming messages from the client."""
        msg_type = content.get("type", "")
        payload = content.get("payload", {})

        if msg_type == "ping":
            await self.send_json({"type": "pong", "payload": {"timestamp": payload.get("timestamp")}})
            return

        # Forward other message types to group broadcast for now
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "room_broadcast_message",
                "sender_channel": self.channel_name,
                "data": content,
            },
        )

    async def room_broadcast_message(self, event: Dict[str, Any]) -> None:
        """Send broadcast message to client."""
        await self.send_json(event["data"])

    async def player_disconnected_event(self, event: Dict[str, Any]) -> None:
        """Notify client that a peer disconnected."""
        await self.send_json(
            {
                "type": "player_disconnected",
                "payload": {
                    "player_id": event["player_id"],
                    "nickname": event["nickname"],
                },
            }
        )
