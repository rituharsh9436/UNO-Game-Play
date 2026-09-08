"""
Domain Services for Room Lifecycle, Host Privileges, and Lobby Management.
Compliant with docs.md Sections 4.3, 4.4, and 12.5.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone

from rooms.models import Room, RoomPlayer, RoomStatus

logger = logging.getLogger(__name__)


def get_lobby_state(room_code: str) -> Optional[Dict[str, Any]]:
    """Retrieve full sanitized lobby state for broadcast to all connected players."""
    try:
        room = Room.objects.prefetch_related("players").get(room_code=room_code.upper())
    except Room.DoesNotExist:
        return None

    players_data = []
    for p in room.players.all().order_by("seat_order", "joined_at"):
        players_data.append(
            {
                "player_id": str(p.id),
                "nickname": p.nickname,
                "is_host": p.is_host,
                "is_ready": p.is_ready,
                "connected": p.connected,
                "seat_order": p.seat_order,
            }
        )

    return {
        "room_code": room.room_code,
        "status": room.status,
        "host_player_id": str(room.host_player_id),
        "max_players": room.max_players,
        "house_rules": room.house_rules or {},
        "player_count": len(players_data),
        "players": players_data,
    }


def set_player_ready_status(player_id: str, is_ready: bool) -> bool:
    """Toggle ready status for a player."""
    try:
        player = RoomPlayer.objects.get(id=player_id)
        player.is_ready = is_ready
        player.save(update_fields=["is_ready"])
        return True
    except RoomPlayer.DoesNotExist:
        return False


def set_player_connection_status(
    player_id: str,
    connected: bool,
    auto_migrate_host: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Update player connectivity flag.
    If host disconnects during WAITING lobby, optionally migrates host to longest-standing connected player (§4.4).
    Returns (was_host, new_host_id).
    """
    try:
        player = RoomPlayer.objects.select_related("room").get(id=player_id)
    except Exception:
        return False, None

    player.connected = connected
    player.save(update_fields=["connected"])

    room = player.room
    if not player.is_host:
        return False, None

    # Host disconnected
    if not connected and auto_migrate_host and room.status == RoomStatus.WAITING:
        # Find next oldest player who is connected
        next_candidate = (
            room.players.filter(connected=True)
            .exclude(id=player.id)
            .order_by("joined_at")
            .first()
        )
        if next_candidate:
            with transaction.atomic():
                player.is_host = False
                player.save(update_fields=["is_host"])
                next_candidate.is_host = True
                next_candidate.is_ready = True
                next_candidate.save(update_fields=["is_host", "is_ready"])
                room.host_player_id = next_candidate.id
                room.save(update_fields=["host_player_id"])
                logger.info(f"Host migrated from {player.id} to {next_candidate.id} in room {room.room_code}")
                return True, str(next_candidate.id)

    return True, None


def kick_player_from_lobby(
    room_code: str,
    host_player_id: str,
    target_player_id: str,
) -> Tuple[bool, str]:
    """
    Host kicks player during WAITING lobby phase (§4.4 & §12.5).
    Guaranteed: Cannot kick during active play; only host can kick; host cannot kick self.
    """
    try:
        room = Room.objects.get(room_code=room_code.upper())
    except Room.DoesNotExist:
        return False, "ROOM_NOT_FOUND"

    if room.status != RoomStatus.WAITING:
        return False, "CANNOT_KICK_DURING_GAME"

    if str(room.host_player_id) != str(host_player_id):
        return False, "NOT_ROOM_HOST"

    if str(host_player_id) == str(target_player_id):
        return False, "CANNOT_KICK_SELF"

    try:
        target = RoomPlayer.objects.get(id=target_player_id, room=room)
        target.delete()
        # Re-index seat orders
        remaining = room.players.all().order_by("seat_order", "joined_at")
        for idx, p in enumerate(remaining):
            if p.seat_order != idx:
                p.seat_order = idx
                p.save(update_fields=["seat_order"])
        return True, "PLAYER_KICKED"
    except RoomPlayer.DoesNotExist:
        return False, "TARGET_NOT_FOUND"


def update_room_house_rules(
    room_code: str,
    host_player_id: str,
    new_rules: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Update house rules for the room while in WAITING lobby phase (§4.4).
    """
    try:
        room = Room.objects.get(room_code=room_code.upper())
    except Room.DoesNotExist:
        return False, "ROOM_NOT_FOUND"

    if room.status != RoomStatus.WAITING:
        return False, "CANNOT_UPDATE_RULES_DURING_GAME"

    if str(room.host_player_id) != str(host_player_id):
        return False, "NOT_ROOM_HOST"

    # Merge rules
    current_rules = room.house_rules or {}
    for k, v in new_rules.items():
        if k in ("stack_draw_two", "turn_time_seconds", "draw_to_match"):
            current_rules[k] = v

    room.house_rules = current_rules
    room.save(update_fields=["house_rules"])
    return True, "RULES_UPDATED"


def validate_game_start_readiness(
    room_code: str,
    host_player_id: str,
) -> Tuple[bool, str, List[Tuple[str, str, bool]], Dict[str, Any]]:
    """
    Validate conditions required to transition room from WAITING to PLAYING:
    - Must be WAITING state.
    - Requester must be Host.
    - Minimum 2 players, maximum 6 players.
    - All non-host participants must be marked is_ready=True.
    Returns (can_start, error_code, list_of_players, house_rules).
    """
    try:
        room = Room.objects.prefetch_related("players").get(room_code=room_code.upper())
    except Room.DoesNotExist:
        return False, "ROOM_NOT_FOUND", [], {}

    if room.status != RoomStatus.WAITING:
        return False, "MATCH_ALREADY_STARTED", [], {}

    if str(room.host_player_id) != str(host_player_id):
        return False, "NOT_ROOM_HOST", [], {}

    players = list(room.players.all().order_by("seat_order", "joined_at"))
    if len(players) < 2:
        return False, "NOT_ENOUGH_PLAYERS", [], {}

    if len(players) > room.max_players:
        return False, "ROOM_EXCEEDS_CAPACITY", [], {}

    # Verify all non-host participants are ready
    unready = [p.nickname for p in players if not p.is_host and not p.is_ready]
    if unready:
        return False, f"PLAYERS_NOT_READY: {', '.join(unready)}", [], {}

    players_data = [(str(p.id), p.nickname, p.is_host) for p in players]
    return True, "READY_TO_START", players_data, room.house_rules or {}


def transition_room_to_playing(room_code: str) -> bool:
    """Transition room status from WAITING to PLAYING in the database."""
    try:
        room = Room.objects.get(room_code=room_code.upper())
        room.status = RoomStatus.PLAYING
        room.save(update_fields=["status"])
        return True
    except Room.DoesNotExist:
        return False
