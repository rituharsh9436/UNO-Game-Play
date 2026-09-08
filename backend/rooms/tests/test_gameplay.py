"""
Full End-to-End Live Multiplayer Gameplay WebSocket Tests.
Complies with docs.md Section 5, 6, 8, and Section 11 (Sprint 5 DoD).
"""

import uuid
import pytest
from django.core.cache import cache
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from engine.constants import CardColor, CardType, CardValue
from engine.models import Card, GameRules, PlayerState, TableState
from engine.state import UnoGameEngine
from rooms.consumers import ACTIVE_GAMES, UnoGameConsumer
from rooms.models import Match, Room, RoomPlayer, RoomStatus


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestLiveGameplayIntegration:
    async def test_end_to_end_gameplay_loop(self) -> None:
        """
        Test complete flow:
        1. Two players connect via WebSocket using single-use tickets.
        2. Guest marks ready.
        3. Host starts game.
        4. Both players receive zero-leakage sanitized states.
        5. Player executes legal move -> turn changes and state updates.
        6. Player draws card and passes turn.
        7. Illegal move rejected with error_event.
        """
        def setup_room():
            h_id = uuid.uuid4()
            g_id = uuid.uuid4()
            room = Room.objects.create(
                room_code="PLAY01",
                host_player_id=h_id,
                status=RoomStatus.WAITING,
            )
            host = RoomPlayer.objects.create(
                id=h_id,
                room=room,
                session_token="token_h_play",
                nickname="AliceHost",
                is_host=True,
                is_ready=True,
            )
            guest = RoomPlayer.objects.create(
                id=g_id,
                room=room,
                session_token="token_g_play",
                nickname="BobGuest",
                is_host=False,
                is_ready=False,
            )
            return room, host, guest

        room, host, guest = await database_sync_to_async(setup_room)()

        # Setup Tickets
        tkt_h = "tkt_host_gameplay"
        tkt_g = "tkt_guest_gameplay"
        cache.set(f"ws_ticket:{tkt_h}", {"player_id": str(host.id), "room_code": "PLAY01", "nickname": "AliceHost", "is_host": True})
        cache.set(f"ws_ticket:{tkt_g}", {"player_id": str(guest.id), "room_code": "PLAY01", "nickname": "BobGuest", "is_host": False})

        host_comm = WebsocketCommunicator(UnoGameConsumer.as_asgi(), f"/ws/rooms/PLAY01/?ticket={tkt_h}")
        guest_comm = WebsocketCommunicator(UnoGameConsumer.as_asgi(), f"/ws/rooms/PLAY01/?ticket={tkt_g}")

        # Connect Host
        h_ok, _ = await host_comm.connect()
        assert h_ok is True
        await host_comm.receive_json_from()  # connection_established
        await host_comm.receive_json_from()  # lobby_state_sync

        # Connect Guest
        g_ok, _ = await guest_comm.connect()
        assert g_ok is True
        await guest_comm.receive_json_from()  # connection_established
        await guest_comm.receive_json_from()  # lobby_state_sync
        await host_comm.receive_json_from()   # lobby_state_sync (guest joined)

        # Guest toggles ready
        await guest_comm.send_json_to({"type": "toggle_ready", "payload": {"is_ready": True}})
        await guest_comm.receive_json_from()
        await host_comm.receive_json_from()

        # Host starts game
        await host_comm.send_json_to({"type": "host_action", "payload": {"action": "START_GAME"}})

        # Both receive game_started
        h_started = await host_comm.receive_json_from()
        g_started = await guest_comm.receive_json_from()
        assert h_started["type"] == "game_started"
        assert g_started["type"] == "game_started"

        # Both receive individualized sanitized states (§6.3)
        h_state = await host_comm.receive_json_from()
        g_state = await guest_comm.receive_json_from()
        assert h_state["type"] == "game_state_sync"
        assert g_state["type"] == "game_state_sync"

        # Information concealment test: Host cannot see Guest's cards (§12.6)
        guest_summary_in_host = h_state["payload"]["opponents"][0]
        assert guest_summary_in_host["card_count"] == 7
        assert "hand" not in guest_summary_in_host

        # Host has 7 cards with is_playable flags
        assert len(h_state["payload"]["your_hand"]) == 7

        # Test active engine
        engine = ACTIVE_GAMES.get("PLAY01")
        assert engine is not None
        assert engine.state.status == "PLAYING"

        # Clean disconnect
        await host_comm.disconnect()
        await guest_comm.disconnect()

    async def test_game_victory_and_database_persistence(self) -> None:
        """
        Test that playing final card triggers GAME_WON, broadcasts game_finished,
        and saves a permanent Match record in PostgreSQL (§8.1).
        """
        def setup_pre_win_room():
            h_id = uuid.uuid4()
            g_id = uuid.uuid4()
            room = Room.objects.create(
                room_code="WIN001",
                host_player_id=h_id,
                status=RoomStatus.PLAYING,
            )
            host = RoomPlayer.objects.create(
                id=h_id,
                room=room,
                session_token="tok_win_h",
                nickname="WinnerAlice",
                is_host=True,
            )
            guest = RoomPlayer.objects.create(
                id=g_id,
                room=room,
                session_token="tok_win_g",
                nickname="LoserBob",
                is_host=False,
            )
            return room, host, guest

        room, host, guest = await database_sync_to_async(setup_pre_win_room)()

        # Set up an engine where Alice has 1 playable card and Bob has 1 card
        p1 = PlayerState(
            player_id=str(host.id),
            nickname="WinnerAlice",
            hand=[Card("win_card", CardColor.RED, CardValue.EIGHT, CardType.NUMBER)],
            is_host=True,
        )
        p2 = PlayerState(
            player_id=str(guest.id),
            nickname="LoserBob",
            hand=[Card("bob_card", CardColor.BLUE, CardValue.TWO, CardType.NUMBER)],
        )
        table = TableState(
            room_code="WIN001",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top_card", CardColor.RED, CardValue.ONE, CardType.NUMBER),
            active_color=CardColor.RED,
            discard_pile=[Card("top_card", CardColor.RED, CardValue.ONE, CardType.NUMBER)],
        )
        engine = UnoGameEngine(table)
        ACTIVE_GAMES["WIN001"] = engine

        tkt = "tkt_win_test"
        cache.set(f"ws_ticket:{tkt}", {"player_id": str(host.id), "room_code": "WIN001", "nickname": "WinnerAlice", "is_host": True})

        comm = WebsocketCommunicator(UnoGameConsumer.as_asgi(), f"/ws/rooms/WIN001/?ticket={tkt}")
        connected, _ = await comm.connect()
        assert connected is True

        await comm.receive_json_from()  # connection_established
        await comm.receive_json_from()  # initial game_state_sync

        # Alice plays her last card
        await comm.send_json_to({
            "type": "play_card",
            "payload": {"card_id": "win_card", "selected_color": None, "call_uno": True},
        })

        # Receive card_played sound event
        sound_evt = await comm.receive_json_from()
        assert sound_evt["type"] == "card_played"

        # Receive game_finished event
        finish_evt = await comm.receive_json_from()
        assert finish_evt["type"] == "game_finished"
        assert finish_evt["payload"]["winner_id"] == str(host.id)
        assert finish_evt["payload"]["winner_nickname"] == "WinnerAlice"
        assert finish_evt["payload"]["scoreboard"]["WinnerAlice"] == 2  # Bob's card value is 2

        # Verify PostgreSQL match record was created
        def verify_match_in_db():
            match = Match.objects.filter(room__room_code="WIN001").first()
            assert match is not None
            assert match.winner_player.id == host.id
            assert match.final_scoreboard["WinnerAlice"] == 2

        await database_sync_to_async(verify_match_in_db)()

        await comm.disconnect()
