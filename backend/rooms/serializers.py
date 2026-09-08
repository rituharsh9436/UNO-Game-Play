"""
Django REST Framework serializers for Room, Player, and Match models.
"""

from typing import Any, Dict
from rest_framework import serializers
from rooms.models import Match, Room, RoomPlayer


class RoomPlayerSerializer(serializers.ModelSerializer):
    """Serializer for room players."""

    class Meta:
        model = RoomPlayer
        fields = [
            "id",
            "nickname",
            "seat_order",
            "is_host",
            "is_ready",
            "connected",
            "joined_at",
        ]
        read_only_fields = ["id", "is_host", "joined_at"]


class RoomSerializer(serializers.ModelSerializer):
    """Serializer for game rooms including active player list."""

    players = RoomPlayerSerializer(many=True, read_only=True)
    player_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Room
        fields = [
            "id",
            "room_code",
            "host_player_id",
            "status",
            "max_players",
            "house_rules",
            "player_count",
            "players",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "room_code", "host_player_id", "status", "created_at", "updated_at"]


class CreateRoomSerializer(serializers.Serializer):
    """Request payload for creating a new room."""

    nickname = serializers.CharField(max_length=30, min_length=1, trim_whitespace=True)
    house_rules = serializers.DictField(required=False, default=dict)


class JoinRoomSerializer(serializers.Serializer):
    """Request payload for joining an existing room."""

    nickname = serializers.CharField(max_length=30, min_length=1, trim_whitespace=True)


class TicketRequestSerializer(serializers.Serializer):
    """Request payload for issuing an ephemeral single-use WebSocket ticket."""

    session_token = serializers.CharField(max_length=128)


class MatchSerializer(serializers.ModelSerializer):
    """Serializer for match history and analytics."""

    class Meta:
        model = Match
        fields = [
            "id",
            "room",
            "winner_player",
            "total_turns",
            "duration_seconds",
            "started_at",
            "finished_at",
            "final_scoreboard",
        ]
        read_only_fields = fields
