"""
API Views for Room Lifecycle, Health Checks, and Ticket Authentication.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any, Dict
from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rooms.models import Room, RoomPlayer, RoomStatus
from rooms.serializers import (
    CreateRoomSerializer,
    JoinRoomSerializer,
    RoomSerializer,
    TicketRequestSerializer,
)

# 32-character unambiguous alphabet specified in docs.md Section 4.1
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_room_code(length: int = 6) -> str:
    """Generate a cryptographically secure unambiguous 6-character room code."""
    for _ in range(10):
        code = "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(length))
        if not Room.objects.filter(room_code=code, status__in=[RoomStatus.WAITING, RoomStatus.PLAYING]).exists():
            return code
    # Fallback to UUID-based string if collisions occur in dense namespace
    return uuid.uuid4().hex[:length].upper()


class HealthCheckView(APIView):
    """
    Service health check endpoint verifying database and Redis readiness.
    Complies with DoD for Sprint 1.
    """

    def get(self, request: Request) -> Response:
        db_healthy = False
        db_error = None
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                db_healthy = row is not None and row[0] == 1
        except Exception as exc:
            db_error = str(exc)

        # Redis connectivity check
        redis_healthy = False
        redis_status = "disabled_in_memory"
        if getattr(settings, "USE_REDIS_CHANNELS", False):
            try:
                import redis
                client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
                redis_healthy = client.ping()
                redis_status = "connected" if redis_healthy else "unresponsive"
            except Exception as exc:
                redis_status = f"unhealthy: {exc}"
        else:
            redis_healthy = True
            redis_status = "in_memory_layer_active"

        all_healthy = db_healthy and (redis_healthy or not getattr(settings, "USE_REDIS_CHANNELS", False))

        payload: Dict[str, Any] = {
            "status": "ok" if all_healthy else "degraded",
            "service": "uno-backend",
            "version": "2.1.0",
            "checks": {
                "database": "healthy" if db_healthy else f"unhealthy: {db_error}",
                "redis": redis_status,
            },
        }

        http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=http_status)


class CreateRoomView(APIView):
    """
    Create a new game room and register the creator as the Host.
    Returns the room details and secret host session token.
    """

    def post(self, request: Request) -> Response:
        serializer = CreateRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        nickname = serializer.validated_data["nickname"]
        house_rules = serializer.validated_data.get("house_rules", {})

        room_code = generate_room_code()
        host_player_id = uuid.uuid4()
        session_token = secrets.token_hex(32)

        room = Room.objects.create(
            room_code=room_code,
            host_player_id=host_player_id,
            status=RoomStatus.WAITING,
            house_rules=house_rules or None,
        )

        player = RoomPlayer.objects.create(
            id=host_player_id,
            room=room,
            session_token=session_token,
            nickname=nickname,
            seat_order=0,
            is_host=True,
            is_ready=True,
            connected=True,
        )

        room_data = RoomSerializer(room).data
        return Response(
            {
                "room": room_data,
                "player": {
                    "id": str(player.id),
                    "nickname": player.nickname,
                    "is_host": True,
                    "session_token": session_token,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class RoomDetailView(APIView):
    """
    Retrieve room state and participants by 6-character room code.
    """

    def get(self, request: Request, room_code: str) -> Response:
        code = room_code.upper().strip()
        try:
            room = Room.objects.prefetch_related("players").get(room_code=code)
        except Room.DoesNotExist:
            return Response(
                {"error": "Room not found or expired.", "code": "ROOM_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RoomSerializer(room)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JoinRoomView(APIView):
    """
    Join an existing room as a guest participant.
    """

    def post(self, request: Request, room_code: str) -> Response:
        code = room_code.upper().strip()
        try:
            room = Room.objects.get(room_code=code)
        except Room.DoesNotExist:
            return Response(
                {"error": "Room not found.", "code": "ROOM_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if room.status != RoomStatus.WAITING:
            return Response(
                {"error": "Cannot join a match that is already in progress or closed.", "code": "MATCH_IN_PROGRESS"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if room.is_full:
            return Response(
                {"error": "Room is full (max 6 players).", "code": "ROOM_FULL"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = JoinRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nickname = serializer.validated_data["nickname"]

        session_token = secrets.token_hex(32)
        current_count = room.players.count()
        player = RoomPlayer.objects.create(
            room=room,
            session_token=session_token,
            nickname=nickname,
            seat_order=current_count,
            is_host=False,
            is_ready=False,
            connected=True,
        )

        return Response(
            {
                "room": RoomSerializer(room).data,
                "player": {
                    "id": str(player.id),
                    "nickname": player.nickname,
                    "is_host": False,
                    "session_token": session_token,
                },
            },
            status=status.HTTP_200_OK,
        )


class TicketExchangeView(APIView):
    """
    Exchange a persistent session token for an ephemeral 30-second single-use ticket.
    Complies with docs.md Section 6.1 (Ticket Authentication Handshake).
    """

    def post(self, request: Request) -> Response:
        serializer = TicketRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_token = serializer.validated_data["session_token"]

        try:
            player = RoomPlayer.objects.select_related("room").get(session_token=session_token)
        except RoomPlayer.DoesNotExist:
            return Response(
                {"error": "Invalid session token.", "code": "INVALID_TOKEN"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Generate single-use ticket
        ticket = f"tkt_{secrets.token_hex(24)}"

        # Store ticket in cache or Redis with 30s TTL
        # In Sprint 1/3, we save in Django cache or Redis
        from django.core.cache import cache
        cache_key = f"ws_ticket:{ticket}"
        cache_payload = {
            "player_id": str(player.id),
            "room_code": player.room.room_code,
            "nickname": player.nickname,
            "is_host": player.is_host,
        }
        cache.set(cache_key, cache_payload, timeout=30)

        return Response(
            {
                "ticket": ticket,
                "expires_in": 30,
                "room_code": player.room.room_code,
                "player_id": str(player.id),
            },
            status=status.HTTP_200_OK,
        )
