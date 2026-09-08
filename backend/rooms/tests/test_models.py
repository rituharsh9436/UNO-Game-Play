"""
Unit tests for Room, RoomPlayer, and Match database models.
"""

import uuid
from django.test import TestCase
from django.utils import timezone
from rooms.models import Match, Room, RoomPlayer, RoomStatus, default_house_rules


class ModelTests(TestCase):
    def setUp(self) -> None:
        self.host_id = uuid.uuid4()
        self.room = Room.objects.create(
            room_code="ABC234",
            host_player_id=self.host_id,
            status=RoomStatus.WAITING,
            max_players=6,
            house_rules=default_house_rules(),
        )
        self.host_player = RoomPlayer.objects.create(
            id=self.host_id,
            room=self.room,
            session_token="test_token_host_123",
            nickname="HostPlayer",
            seat_order=0,
            is_host=True,
            is_ready=True,
            connected=True,
        )

    def test_room_creation_and_defaults(self) -> None:
        self.assertEqual(self.room.room_code, "ABC234")
        self.assertEqual(self.room.status, RoomStatus.WAITING)
        self.assertEqual(self.room.max_players, 6)
        self.assertEqual(self.room.house_rules["turn_time_seconds"], 25)
        self.assertFalse(self.room.house_rules["stack_draw_two"])
        self.assertEqual(self.room.player_count, 1)
        self.assertFalse(self.room.is_full)
        self.assertIn("ABC234", str(self.room))

    def test_room_player_association(self) -> None:
        guest_player = RoomPlayer.objects.create(
            room=self.room,
            session_token="test_token_guest_456",
            nickname="GuestPlayer",
            seat_order=1,
            is_host=False,
            is_ready=False,
            connected=True,
        )
        self.assertEqual(self.room.player_count, 2)
        self.assertIn("GuestPlayer", str(guest_player))
        self.assertIn("Host", str(self.host_player))

    def test_match_creation(self) -> None:
        match = Match.objects.create(
            room=self.room,
            winner_player=self.host_player,
            total_turns=24,
            duration_seconds=340,
            started_at=timezone.now(),
            finished_at=timezone.now(),
            final_scoreboard={"HostPlayer": 50, "GuestPlayer": 0},
        )
        self.assertEqual(match.winner_player, self.host_player)
        self.assertEqual(match.total_turns, 24)
        self.assertIn("HostPlayer", str(match))
