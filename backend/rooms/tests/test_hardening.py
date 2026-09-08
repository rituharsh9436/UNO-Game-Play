"""
Unit & Integration Tests for Anti-DDoS Throttling, 45s Grace Disconnection, and Hardening.
Complies with docs.md Section 7, 12.2, and Section 11 (Sprint 6 DoD).
"""

import uuid
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from engine.constants import CardColor, CardType, CardValue
from engine.models import Card, GameRules, PlayerState, TableState
from engine.state import UnoGameEngine
from rooms.consumers import ACTIVE_GAMES, UnoGameConsumer
from rooms.models import Room, RoomPlayer, RoomStatus
from rooms.throttling import RoomCreationRateThrottle, RoomLookupRateThrottle


class HardeningRateLimitTests(APITestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_room_creation_throttled_to_five_per_hour(self) -> None:
        """Creating more than 5 rooms per IP within 1 hour triggers HTTP 429 (§12.2)."""
        url = reverse("create_room")
        for idx in range(5):
            res = self.client.post(url, data={"nickname": f"Tester{idx}"}, format="json")
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # 6th attempt from same IP must be throttled
        res_6 = self.client.post(url, data={"nickname": "OverLimit"}, format="json")
        self.assertEqual(res_6.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_room_lookup_backoff_after_repeated_failures(self) -> None:
        """More than 10 failed room lookups within 60s temporarily blocks the IP (§12.2)."""
        for _ in range(10):
            res = self.client.get(reverse("room_detail", kwargs={"room_code": "NONEX1"}))
            self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # 11th attempt is blocked with HTTP 429
        res_blocked = self.client.get(reverse("room_detail", kwargs={"room_code": "NONEX1"}))
        self.assertEqual(res_blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestDisconnectionGraceAndSyncThrottling:
    async def test_state_sync_throttling(self) -> None:
        """Full state sync calls are clamped to max 1 call per 3 seconds (§12.2)."""
        def setup_room():
            p_id = uuid.uuid4()
            room = Room.objects.create(room_code="SYNC01", host_player_id=p_id)
            player = RoomPlayer.objects.create(id=p_id, room=room, session_token="tok_sync", nickname="Syncer", is_host=True)
            return room, player

        room, player = await database_sync_to_async(setup_room)()
        tkt = "tkt_sync_test"
        cache.set(f"ws_ticket:{tkt}", {"player_id": str(player.id), "room_code": "SYNC01", "nickname": "Syncer", "is_host": True})

        comm = WebsocketCommunicator(UnoGameConsumer.as_asgi(), f"/ws/rooms/SYNC01/?ticket={tkt}")
        await comm.connect()
        await comm.receive_json_from()  # connection_established
        await comm.receive_json_from()  # lobby_state_sync

        # First sync call succeeds
        await comm.send_json_to({"type": "request_full_state_sync", "payload": {}})
        msg1 = await comm.receive_json_from()
        assert msg1["type"] == "lobby_state_sync"

        # Immediate second sync call is rate-limited (§12.2)
        await comm.send_json_to({"type": "request_full_state_sync", "payload": {}})
        msg2 = await comm.receive_json_from()
        assert msg2["type"] == "error_event"
        assert msg2["payload"]["code"] == "SYNC_RATE_LIMITED"

        await comm.disconnect()

    async def test_active_match_disconnection_45s_grace_period(self) -> None:
        """
        Disconnection during active match sets 45s grace period and notifies opponents.
        Reconnecting with fresh ticket clears grace period (§7).
        """
        def setup_active_room():
            h_id = uuid.uuid4()
            g_id = uuid.uuid4()
            room = Room.objects.create(room_code="GRACE1", host_player_id=h_id, status=RoomStatus.PLAYING)
            host = RoomPlayer.objects.create(id=h_id, room=room, session_token="tok_h_grace", nickname="Alice", is_host=True)
            guest = RoomPlayer.objects.create(id=g_id, room=room, session_token="tok_g_grace", nickname="Bob", is_host=False)
            return room, host, guest

        room, host, guest = await database_sync_to_async(setup_active_room)()

        # Setup active engine
        p1 = PlayerState(player_id=str(host.id), nickname="Alice", hand=[Card("c1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p2 = PlayerState(player_id=str(guest.id), nickname="Bob", hand=[Card("c2", CardColor.BLUE, CardValue.TWO, CardType.NUMBER)])
        table = TableState(room_code="GRACE1", rules=GameRules(), players=[p1, p2], status="PLAYING")
        engine = UnoGameEngine(table)
        ACTIVE_GAMES["GRACE1"] = engine

        tkt_h = "tkt_h_grace"
        tkt_g = "tkt_g_grace"
        cache.set(f"ws_ticket:{tkt_h}", {"player_id": str(host.id), "room_code": "GRACE1", "nickname": "Alice", "is_host": True})
        cache.set(f"ws_ticket:{tkt_g}", {"player_id": str(guest.id), "room_code": "GRACE1", "nickname": "Bob", "is_host": False})

        host_comm = WebsocketCommunicator(UnoGameConsumer.as_asgi(), f"/ws/rooms/GRACE1/?ticket={tkt_h}")
        guest_comm = WebsocketCommunicator(UnoGameConsumer.as_asgi(), f"/ws/rooms/GRACE1/?ticket={tkt_g}")

        await host_comm.connect()
        await host_comm.receive_json_from()
        await host_comm.receive_json_from()

        await guest_comm.connect()
        await guest_comm.receive_json_from()
        await guest_comm.receive_json_from()

        # Alice disconnects abruptly
        await host_comm.disconnect()

        # Bob receives player_disconnected event with 45s grace period (§7)
        disc_msg = await guest_comm.receive_json_from()
        assert disc_msg["type"] == "player_disconnected"
        assert disc_msg["payload"]["grace_window_seconds"] == 45

        # Verify grace timer was written to cache
        grace_key = f"grace_period:GRACE1:{host.id}"
        assert cache.get(grace_key) is True

        # Alice reconnects with a fresh ticket within 45s
        tkt_reconnect = "tkt_h_reconnect"
        cache.set(f"ws_ticket:{tkt_reconnect}", {"player_id": str(host.id), "room_code": "GRACE1", "nickname": "Alice", "is_host": True})

        reconnect_comm = WebsocketCommunicator(UnoGameConsumer.as_asgi(), f"/ws/rooms/GRACE1/?ticket={tkt_reconnect}")
        rec_ok, _ = await reconnect_comm.connect()
        assert rec_ok is True

        # Grace key must now be cleared!
        assert cache.get(grace_key) is None

        # Alice immediately receives fresh game state
        await reconnect_comm.receive_json_from()  # connection_established
        state_msg = await reconnect_comm.receive_json_from()  # game_state_sync
        assert state_msg["type"] == "game_state_sync"

        await reconnect_comm.disconnect()
        await guest_comm.disconnect()
