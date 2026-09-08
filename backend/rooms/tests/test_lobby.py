"""
Unit and Integration Tests for Room Lobby Management, Host Privileges, and WebSocket Handshake.
Complies with docs.md Section 4, Section 6, and Section 11 (Sprint 3 DoD).
"""

import uuid
import pytest
from django.core.cache import cache
from django.test import TestCase
from channels.testing import WebsocketCommunicator

from rooms.consumers import UnoGameConsumer
from rooms.models import Room, RoomPlayer, RoomStatus
from rooms.services import (
    get_lobby_state,
    kick_player_from_lobby,
    set_player_connection_status,
    set_player_ready_status,
    update_room_house_rules,
    validate_game_start_readiness,
)


class LobbyServiceTests(TestCase):
    def setUp(self) -> None:
        self.host_id = uuid.uuid4()
        self.room = Room.objects.create(
            room_code="LOBBY1",
            host_player_id=self.host_id,
            status=RoomStatus.WAITING,
            max_players=6,
            house_rules={"stack_draw_two": False, "turn_time_seconds": 25},
        )
        self.host_player = RoomPlayer.objects.create(
            id=self.host_id,
            room=self.room,
            session_token="token_host_1",
            nickname="HostAlice",
            seat_order=0,
            is_host=True,
            is_ready=True,
            connected=True,
        )
        self.guest_id = uuid.uuid4()
        self.guest_player = RoomPlayer.objects.create(
            id=self.guest_id,
            room=self.room,
            session_token="token_guest_1",
            nickname="GuestBob",
            seat_order=1,
            is_host=False,
            is_ready=False,
            connected=True,
        )

    def test_get_lobby_state(self) -> None:
        state = get_lobby_state("LOBBY1")
        assert state is not None
        assert state["room_code"] == "LOBBY1"
        assert state["status"] == "WAITING"
        assert state["player_count"] == 2
        assert len(state["players"]) == 2
        assert state["players"][0]["nickname"] == "HostAlice"
        assert state["players"][0]["is_host"] is True
        assert state["players"][1]["nickname"] == "GuestBob"
        assert state["players"][1]["is_ready"] is False

    def test_set_player_ready(self) -> None:
        success = set_player_ready_status(str(self.guest_id), True)
        assert success is True
        self.guest_player.refresh_from_db()
        assert self.guest_player.is_ready is True

    def test_update_house_rules(self) -> None:
        # Host updates rules
        success, reason = update_room_house_rules(
            "LOBBY1", str(self.host_id), {"stack_draw_two": True, "turn_time_seconds": 15}
        )
        assert success is True
        self.room.refresh_from_db()
        assert self.room.house_rules["stack_draw_two"] is True
        assert self.room.house_rules["turn_time_seconds"] == 15

        # Non-host cannot update rules
        success_bad, reason_bad = update_room_house_rules(
            "LOBBY1", str(self.guest_id), {"turn_time_seconds": 35}
        )
        assert success_bad is False
        assert reason_bad == "NOT_ROOM_HOST"

    def test_kick_player_permissions(self) -> None:
        # Non-host cannot kick
        bad_res, bad_reason = kick_player_from_lobby("LOBBY1", str(self.guest_id), str(self.host_id))
        assert bad_res is False
        assert bad_reason == "NOT_ROOM_HOST"

        # Host cannot kick self
        self_kick, self_reason = kick_player_from_lobby("LOBBY1", str(self.host_id), str(self.host_id))
        assert self_kick is False
        assert self_reason == "CANNOT_KICK_SELF"

        # Host kicks guest
        good_res, good_reason = kick_player_from_lobby("LOBBY1", str(self.host_id), str(self.guest_id))
        assert good_res is True
        assert good_reason == "PLAYER_KICKED"
        assert not RoomPlayer.objects.filter(id=self.guest_id).exists()

    def test_host_migration_on_disconnect(self) -> None:
        # Host disconnects during WAITING phase
        was_host, new_host = set_player_connection_status(str(self.host_id), False, auto_migrate_host=True)
        assert was_host is True
        assert new_host == str(self.guest_id)

        self.room.refresh_from_db()
        self.guest_player.refresh_from_db()
        assert self.room.host_player_id == self.guest_id
        assert self.guest_player.is_host is True

    def test_validate_game_start_readiness(self) -> None:
        # Fails when guest is not ready
        can_start, reason, _, _ = validate_game_start_readiness("LOBBY1", str(self.host_id))
        assert can_start is False
        assert "PLAYERS_NOT_READY" in reason

        # Guest marks ready
        self.guest_player.is_ready = True
        self.guest_player.save()

        can_start_now, reason_now, players_data, rules = validate_game_start_readiness(
            "LOBBY1", str(self.host_id)
        )
        assert can_start_now is True
        assert len(players_data) == 2


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestUnoGameConsumerAsync:
    async def test_websocket_rejects_missing_ticket(self) -> None:
        """Connecting without a ticket or with invalid ticket closes with code 4003 (§6.1)."""
        communicator = WebsocketCommunicator(
            UnoGameConsumer.as_asgi(),
            "/ws/rooms/TEST99/",
        )
        connected, close_code = await communicator.connect()
        assert connected is False
        assert close_code == 4003

    async def test_websocket_accepts_valid_ticket_and_invalidates_it(self) -> None:
        """A valid ticket authorizes the socket and is deleted (single-use) (§6.1)."""
        from channels.db import database_sync_to_async

        def setup_db_room():
            p_id = uuid.uuid4()
            room = Room.objects.create(
                room_code="WSROOM",
                host_player_id=p_id,
                status=RoomStatus.WAITING,
            )
            player = RoomPlayer.objects.create(
                id=p_id,
                room=room,
                session_token="token_ws_test",
                nickname="WSTester",
                is_host=True,
            )
            return room, player

        room, player = await database_sync_to_async(setup_db_room)()

        # Create ticket in cache
        ticket = "tkt_test_handshake_123"
        cache.set(
            f"ws_ticket:{ticket}",
            {
                "player_id": str(player.id),
                "room_code": "WSROOM",
                "nickname": "WSTester",
                "is_host": True,
            },
            timeout=30,
        )

        communicator = WebsocketCommunicator(
            UnoGameConsumer.as_asgi(),
            f"/ws/rooms/WSROOM/?ticket={ticket}",
        )
        connected, _ = await communicator.connect()
        assert connected is True

        # Initial message must be connection_established
        msg = await communicator.receive_json_from()
        assert msg["type"] == "connection_established"
        assert msg["payload"]["nickname"] == "WSTester"

        # Ticket must now be deleted from cache (single-use)
        assert cache.get(f"ws_ticket:{ticket}") is None

        # Disconnect cleanly
        await communicator.disconnect()

    async def test_websocket_toggle_ready_and_host_action(self) -> None:
        """Test toggling ready and host rule updates over WebSocket."""
        from channels.db import database_sync_to_async

        def setup_room_with_two_players():
            h_id = uuid.uuid4()
            g_id = uuid.uuid4()
            room = Room.objects.create(
                room_code="COMM99",
                host_player_id=h_id,
                status=RoomStatus.WAITING,
            )
            host = RoomPlayer.objects.create(
                id=h_id,
                room=room,
                session_token="token_host_comm",
                nickname="HostAlice",
                is_host=True,
                is_ready=True,
            )
            guest = RoomPlayer.objects.create(
                id=g_id,
                room=room,
                session_token="token_guest_comm",
                nickname="GuestBob",
                is_host=False,
                is_ready=False,
            )
            return room, host, guest

        room, host, guest = await database_sync_to_async(setup_room_with_two_players)()

        ticket_guest = "tkt_guest_comm_123"
        cache.set(
            f"ws_ticket:{ticket_guest}",
            {
                "player_id": str(guest.id),
                "room_code": "COMM99",
                "nickname": "GuestBob",
                "is_host": False,
            },
            timeout=30,
        )

        guest_comm = WebsocketCommunicator(
            UnoGameConsumer.as_asgi(),
            f"/ws/rooms/COMM99/?ticket={ticket_guest}",
        )
        connected, _ = await guest_comm.connect()
        assert connected is True

        # Read connection established
        msg_conn = await guest_comm.receive_json_from()
        assert msg_conn["type"] == "connection_established"

        # Read initial lobby broadcast
        msg_lobby = await guest_comm.receive_json_from()
        assert msg_lobby["type"] == "lobby_state_sync"

        # Guest toggles ready
        await guest_comm.send_json_to({"type": "toggle_ready", "payload": {"is_ready": True}})
        msg_ready = await guest_comm.receive_json_from()
        assert msg_ready["type"] == "lobby_state_sync"
        bob_entry = next(p for p in msg_ready["payload"]["players"] if p["player_id"] == str(guest.id))
        assert bob_entry["is_ready"] is True

        # Non-host attempts to start game (must be rejected)
        await guest_comm.send_json_to({"type": "host_action", "payload": {"action": "START_GAME"}})
        err_msg = await guest_comm.receive_json_from()
        assert err_msg["type"] == "error_event"
        assert err_msg["payload"]["code"] == "FORBIDDEN_HOST_ACTION"

        await guest_comm.disconnect()


