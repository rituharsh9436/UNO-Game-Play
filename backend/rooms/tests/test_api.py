"""
Unit tests for Room creation, retrieval, joining, and ticketing.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rooms.models import Room, RoomPlayer, RoomStatus


class RoomAPITests(APITestCase):
    def test_create_room(self) -> None:
        url = reverse("create_room")
        payload = {
            "nickname": "Alice",
            "house_rules": {"stack_draw_two": True, "turn_time_seconds": 20},
        }
        response = self.client.post(url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn("room", data)
        self.assertIn("player", data)
        self.assertEqual(len(data["room"]["room_code"]), 6)
        self.assertEqual(data["player"]["nickname"], "Alice")
        self.assertTrue(data["player"]["is_host"])
        self.assertTrue(bool(data["player"]["session_token"]))

    def test_get_room_detail(self) -> None:
        room = Room.objects.create(
            room_code="TEST99",
            host_player_id="00000000-0000-0000-0000-000000000001",
            status=RoomStatus.WAITING,
        )
        url = reverse("room_detail", kwargs={"room_code": "TEST99"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["room_code"], "TEST99")

    def test_join_room(self) -> None:
        room = Room.objects.create(
            room_code="JOIN12",
            host_player_id="00000000-0000-0000-0000-000000000002",
            status=RoomStatus.WAITING,
        )
        url = reverse("join_room", kwargs={"room_code": "JOIN12"})
        response = self.client.post(url, data={"nickname": "Bob"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["player"]["nickname"], "Bob")
        self.assertFalse(data["player"]["is_host"])
        self.assertTrue(bool(data["player"]["session_token"]))

    def test_ticket_exchange(self) -> None:
        room = Room.objects.create(
            room_code="TCKT88",
            host_player_id="00000000-0000-0000-0000-000000000003",
            status=RoomStatus.WAITING,
        )
        player = RoomPlayer.objects.create(
            room=room,
            session_token="secret_session_token_xyz",
            nickname="Charlie",
            is_host=True,
        )
        url = reverse("ticket_exchange")
        response = self.client.post(url, data={"session_token": player.session_token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["ticket"].startswith("tkt_"))
        self.assertEqual(data["expires_in"], 30)
        self.assertEqual(data["room_code"], "TCKT88")
