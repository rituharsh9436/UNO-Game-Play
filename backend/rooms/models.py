"""
Database Models for Real-Time UNO Platform.
Matches the PostgreSQL schema specified in docs.md Section 8.1.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict
from django.db import models
from django.utils import timezone


def default_house_rules() -> Dict[str, Any]:
    """Default house rules configuration."""
    return {
        "stack_draw_two": False,
        "turn_time_seconds": 25,
    }


class RoomStatus(models.TextChoices):
    WAITING = "WAITING", "Waiting in Lobby"
    PLAYING = "PLAYING", "Match In Progress"
    FINISHED = "FINISHED", "Match Finished"
    CLOSED = "CLOSED", "Room Closed"


class Room(models.Model):
    """
    Authoritative state record for an UNO game room.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_code = models.CharField(max_length=6, unique=True, db_index=True)
    host_player_id = models.UUIDField(help_text="UUID of the current room host")
    status = models.CharField(
        max_length=20,
        choices=RoomStatus.choices,
        default=RoomStatus.WAITING,
        db_index=True,
    )
    max_players = models.PositiveSmallIntegerField(default=6)
    house_rules = models.JSONField(default=default_house_rules)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rooms"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room_code", "status"], name="idx_rooms_code_status"),
        ]

    def __str__(self) -> str:
        return f"Room {self.room_code} [{self.status}]"

    @property
    def player_count(self) -> int:
        """Return the current number of registered players in this room."""
        return self.players.count()

    @property
    def is_full(self) -> bool:
        """Check if room has reached max capacity."""
        return self.player_count >= self.max_players


class RoomPlayer(models.Model):
    """
    Session and presence record for a participant in a room.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="players",
        db_index=True,
    )
    session_token = models.CharField(max_length=128, unique=True, db_index=True)
    nickname = models.CharField(max_length=30)
    seat_order = models.PositiveSmallIntegerField(null=True, blank=True)
    is_host = models.BooleanField(default=False)
    is_ready = models.BooleanField(default=False)
    connected = models.BooleanField(default=True)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "room_players"
        ordering = ["seat_order", "joined_at"]
        indexes = [
            models.Index(fields=["room", "session_token"], name="idx_players_room_session"),
        ]

    def __str__(self) -> str:
        host_tag = " (Host)" if self.is_host else ""
        return f"{self.nickname}{host_tag} in Room {self.room.room_code}"


class Match(models.Model):
    """
    Historical record and analytics for completed game matches.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matches",
    )
    winner_player = models.ForeignKey(
        RoomPlayer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="won_matches",
    )
    total_turns = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(default=timezone.now)
    final_scoreboard = models.JSONField(default=dict)

    class Meta:
        db_table = "matches"
        ordering = ["-finished_at"]

    def __str__(self) -> str:
        winner_nick = self.winner_player.nickname if self.winner_player else "N/A"
        return f"Match {self.id} - Winner: {winner_nick} ({self.duration_seconds}s)"
