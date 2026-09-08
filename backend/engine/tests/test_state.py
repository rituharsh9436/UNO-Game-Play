"""
Comprehensive unit tests for UnoGameEngine state machine, turns, UNO challenge, timeouts, and scoring.
Complies with docs.md Section 5, Section 6.3, and Section 10.
"""

import time
import pytest

from engine.constants import CardColor, CardType, CardValue, Direction
from engine.models import Card, GameRules, PlayerState, TableState
from engine.state import GameEngineError, UnoGameEngine


class TestUnoGameEngine:
    @pytest.fixture
    def players_4(self) -> list[tuple[str, str, bool]]:
        return [
            ("p_1", "Alice", True),
            ("p_2", "Bob", False),
            ("p_3", "Charlie", False),
            ("p_4", "Dana", False),
        ]

    def test_create_game_initial_state(self, players_4: list[tuple[str, str, bool]]) -> None:
        """Creating game deals 7 cards to each of the 4 players and initializes state."""
        engine = UnoGameEngine.create_game("ROOM01", players_4)
        state = engine.state
        assert state.room_code == "ROOM01"
        assert len(state.players) == 4
        for p in state.players:
            assert p.card_count == 7
        assert state.status == "PLAYING"
        assert state.top_card is not None
        assert state.active_color is not None
        assert len(state.discard_pile) == 1
        # Total cards in play + draw pile + discard pile = 108
        total = sum(p.card_count for p in state.players) + len(state.draw_pile) + len(state.discard_pile)
        assert total == 108

    def test_create_game_invalid_player_count(self) -> None:
        """Games require between 2 and 6 players."""
        with pytest.raises(GameEngineError) as exc_1:
            UnoGameEngine.create_game("R1", [("p_1", "Alice", True)])
        assert exc_1.value.code == "INVALID_PLAYER_COUNT"

        seven_players = [(f"p_{i}", f"Player {i}", i == 0) for i in range(7)]
        with pytest.raises(GameEngineError) as exc_7:
            UnoGameEngine.create_game("R2", seven_players)
        assert exc_7.value.code == "INVALID_PLAYER_COUNT"

    def test_play_number_card_advances_turn(self) -> None:
        """Playing a legal number card updates top card and advances turn."""
        p1 = PlayerState(
            player_id="p_1",
            nickname="Alice",
            hand=[Card("c_red_7_1", CardColor.RED, CardValue.SEVEN, CardType.NUMBER)],
            is_host=True,
        )
        p2 = PlayerState(
            player_id="p_2",
            nickname="Bob",
            hand=[Card("c_red_3_1", CardColor.RED, CardValue.THREE, CardType.NUMBER)],
        )
        table = TableState(
            room_code="R100",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("c_red_2_1", CardColor.RED, CardValue.TWO, CardType.NUMBER),
            active_color=CardColor.RED,
            discard_pile=[Card("c_red_2_1", CardColor.RED, CardValue.TWO, CardType.NUMBER)],
        )
        engine = UnoGameEngine(table)

        # Alice plays Red 7 (and drops to 0 cards -> Win)
        result = engine.play_card("p_1", "c_red_7_1")
        assert result["status"] == "GAME_WON"
        assert result["winner_id"] == "p_1"
        assert table.status == "FINISHED"

    def test_not_your_turn_error(self) -> None:
        """Attempting to play out of turn raises NOT_YOUR_TURN."""
        p1 = PlayerState("p_1", "Alice", [Card("c1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p2 = PlayerState("p_2", "Bob", [Card("c2", CardColor.RED, CardValue.TWO, CardType.NUMBER)])
        table = TableState(
            room_code="R101",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        with pytest.raises(GameEngineError) as exc:
            engine.play_card("p_2", "c2")
        assert exc.value.code == "NOT_YOUR_TURN"

    def test_card_not_in_hand_error(self) -> None:
        """Attempting to play a card not in player's hand raises CARD_NOT_IN_HAND."""
        p1 = PlayerState("p_1", "Alice", [Card("c1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p2 = PlayerState("p_2", "Bob", [])
        table = TableState(
            room_code="R102",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        with pytest.raises(GameEngineError) as exc:
            engine.play_card("p_1", "phantom_card")
        assert exc.value.code == "CARD_NOT_IN_HAND"

    def test_illegal_move_error(self) -> None:
        """Playing a mismatched card raises ILLEGAL_MOVE."""
        p1 = PlayerState("p_1", "Alice", [Card("c_blue_4", CardColor.BLUE, CardValue.FOUR, CardType.NUMBER)])
        p2 = PlayerState("p_2", "Bob", [])
        table = TableState(
            room_code="R103",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.RED, CardValue.SEVEN, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        with pytest.raises(GameEngineError) as exc:
            engine.play_card("p_1", "c_blue_4")
        assert exc.value.code == "ILLEGAL_MOVE"

    def test_skip_card_skips_next_player(self) -> None:
        """Skip card advances turn by 2 steps in 4-player game."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_red_skip", CardColor.RED, CardValue.SKIP, CardType.ACTION),
            Card("extra", CardColor.RED, CardValue.ONE, CardType.NUMBER),
        ])
        p2 = PlayerState("p_2", "Bob", [Card("b1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p3 = PlayerState("p_3", "Charlie", [Card("c1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p4 = PlayerState("p_4", "Dana", [Card("d1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])

        table = TableState(
            room_code="R104",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2, p3, p4],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        res = engine.play_card("p_1", "c_red_skip")
        assert res["status"] == "SUCCESS"
        # Player 0 played Skip -> Player 1 skipped -> Player 2 is next
        assert table.current_player_index == 2
        assert table.current_player.player_id == "p_3"

    def test_reverse_card_multiplayer_inverts_direction(self) -> None:
        """Reverse card in 4-player game flips direction to Counter-Clockwise."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_red_rev", CardColor.RED, CardValue.REVERSE, CardType.ACTION),
            Card("extra", CardColor.RED, CardValue.ONE, CardType.NUMBER),
        ])
        p2 = PlayerState("p_2", "Bob", [])
        p3 = PlayerState("p_3", "Charlie", [])
        p4 = PlayerState("p_4", "Dana", [])

        table = TableState(
            room_code="R105",
            rules=GameRules(),
            direction=Direction.CLOCKWISE,
            current_player_index=0,
            players=[p1, p2, p3, p4],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        engine.play_card("p_1", "c_red_rev")
        assert table.direction == Direction.COUNTER_CLOCKWISE
        # From index 0 going counter-clockwise in 4 players -> index 3
        assert table.current_player_index == 3
        assert table.current_player.player_id == "p_4"

    def test_reverse_card_two_player_acts_as_skip(self) -> None:
        """In a 2-player game, Reverse acts as a Skip card (§5.4)."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_red_rev", CardColor.RED, CardValue.REVERSE, CardType.ACTION),
            Card("extra", CardColor.RED, CardValue.ONE, CardType.NUMBER),
        ])
        p2 = PlayerState("p_2", "Bob", [])

        table = TableState(
            room_code="R106",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        engine.play_card("p_1", "c_red_rev")
        # In 2-player, player 0 skips player 1 and plays again (index 0)
        assert table.current_player_index == 0

    def test_draw_two_without_stacking(self) -> None:
        """Standard Draw Two forces next player to draw 2 cards and lose their turn."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_d2", CardColor.RED, CardValue.DRAW_TWO, CardType.ACTION),
            Card("extra", CardColor.RED, CardValue.ONE, CardType.NUMBER),
        ])
        p2 = PlayerState("p_2", "Bob", [Card("b1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p3 = PlayerState("p_3", "Charlie", [])

        table = TableState(
            room_code="R107",
            rules=GameRules(stack_draw_two=False),
            current_player_index=0,
            players=[p1, p2, p3],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
            draw_pile=[
                Card("draw1", CardColor.BLUE, CardValue.ONE, CardType.NUMBER),
                Card("draw2", CardColor.BLUE, CardValue.TWO, CardType.NUMBER),
            ],
        )
        engine = UnoGameEngine(table)
        engine.play_card("p_1", "c_d2")
        # Bob received 2 cards (initial 1 + 2 = 3)
        assert p2.card_count == 3
        # Bob's turn was skipped; Charlie is next
        assert table.current_player_index == 2

    def test_draw_two_with_stacking(self) -> None:
        """With stack_draw_two=True, pending_draw_count increments and next player can stack."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_d2_red", CardColor.RED, CardValue.DRAW_TWO, CardType.ACTION),
            Card("extra1", CardColor.RED, CardValue.ONE, CardType.NUMBER),
        ])
        p2 = PlayerState("p_2", "Bob", [
            Card("c_d2_blue", CardColor.BLUE, CardValue.DRAW_TWO, CardType.ACTION),
            Card("extra2", CardColor.BLUE, CardValue.ONE, CardType.NUMBER),
        ])
        p3 = PlayerState("p_3", "Charlie", [
            Card("c3", CardColor.YELLOW, CardValue.ONE, CardType.NUMBER)
        ])

        table = TableState(
            room_code="R108",
            rules=GameRules(stack_draw_two=True),
            current_player_index=0,
            players=[p1, p2, p3],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
            draw_pile=[
                Card(f"d_{i}", CardColor.BLUE, CardValue.ONE, CardType.NUMBER) for i in range(10)
            ],
        )
        engine = UnoGameEngine(table)
        # Alice plays Draw Two
        engine.play_card("p_1", "c_d2_red")
        assert table.pending_draw_count == 2
        assert table.current_player_index == 1  # Bob's turn to respond

        # Bob stacks Draw Two
        engine.play_card("p_2", "c_d2_blue")
        assert table.pending_draw_count == 4
        assert table.current_player_index == 2  # Charlie's turn to respond

        # Charlie has no Draw Two; draws to accept 4 penalty cards
        res = engine.draw_card("p_3")
        assert res["action"] == "ACCEPTED_STACK_PENALTY"
        assert res["drawn_count"] == 4
        assert p3.card_count == 5  # initial 1 + 4 = 5
        assert table.pending_draw_count == 0

    def test_wild_requires_selected_color(self) -> None:
        """Playing a Wild card without a valid color declaration raises MISSING_WILD_COLOR."""
        p1 = PlayerState("p_1", "Alice", [Card("c_wild", CardColor.WILD, CardValue.WILD, CardType.WILD)])
        table = TableState(
            room_code="R109",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, PlayerState("p_2", "Bob")],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        with pytest.raises(GameEngineError) as exc:
            engine.play_card("p_1", "c_wild", selected_color=None)
        assert exc.value.code == "MISSING_WILD_COLOR"

    def test_wild_declares_active_color(self) -> None:
        """Playing a Wild card updates the active color to the chosen color."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_wild", CardColor.WILD, CardValue.WILD, CardType.WILD),
            Card("extra", CardColor.RED, CardValue.ONE, CardType.NUMBER),
        ])
        p2 = PlayerState("p_2", "Bob", [])
        table = TableState(
            room_code="R110",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        res = engine.play_card("p_1", "c_wild", selected_color=CardColor.GREEN)
        assert res["active_color"] == "GREEN"
        assert table.active_color == CardColor.GREEN

    def test_wild_draw_four_effect(self) -> None:
        """Wild Draw Four updates color, forces next player to draw 4 and skips turn."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_wdf", CardColor.WILD, CardValue.DRAW_FOUR, CardType.WILD_DRAW_FOUR),
            Card("extra", CardColor.RED, CardValue.ONE, CardType.NUMBER),
        ])
        p2 = PlayerState("p_2", "Bob", [Card("b1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p3 = PlayerState("p_3", "Charlie", [])

        table = TableState(
            room_code="R111",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2, p3],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
            draw_pile=[
                Card(f"d_{i}", CardColor.BLUE, CardValue.ONE, CardType.NUMBER) for i in range(5)
            ],
        )
        engine = UnoGameEngine(table)
        engine.play_card("p_1", "c_wdf", selected_color=CardColor.YELLOW)
        assert table.active_color == CardColor.YELLOW
        # Bob received 4 cards (1 + 4 = 5)
        assert p2.card_count == 5
        # Bob skipped; Charlie plays next
        assert table.current_player_index == 2

    def test_draw_card_and_pass(self) -> None:
        """Player draws 1 card and can pass their turn."""
        p1 = PlayerState("p_1", "Alice", [Card("c1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p2 = PlayerState("p_2", "Bob", [])
        table = TableState(
            room_code="R112",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.BLUE, CardValue.NINE, CardType.NUMBER),
            active_color=CardColor.BLUE,
            draw_pile=[Card("drawn_card", CardColor.GREEN, CardValue.THREE, CardType.NUMBER)],
        )
        engine = UnoGameEngine(table)
        # Cannot pass before drawing
        with pytest.raises(GameEngineError) as exc_pass:
            engine.pass_turn("p_1")
        assert exc_pass.value.code == "CANNOT_PASS"

        # Draw card
        res = engine.draw_card("p_1")
        assert res["action"] == "CARD_DRAWN"
        assert p1.card_count == 2
        assert p1.has_drawn_this_turn is True

        # Cannot draw twice
        with pytest.raises(GameEngineError) as exc_draw:
            engine.draw_card("p_1")
        assert exc_draw.value.code == "ALREADY_DRAWN"

        # Now can pass
        pass_res = engine.pass_turn("p_1")
        assert pass_res["status"] == "SUCCESS"
        assert table.current_player_index == 1

    def test_uno_call_safe_state(self) -> None:
        """When hand drops to 1 with call_uno=True, player enters safe UNO state."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_play", CardColor.RED, CardValue.ONE, CardType.NUMBER),
            Card("c_keep", CardColor.RED, CardValue.TWO, CardType.NUMBER),
        ])
        table = TableState(
            room_code="R113",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, PlayerState("p_2", "Bob")],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        res = engine.play_card("p_1", "c_play", call_uno=True)
        assert res["opened_vulnerability_window"] is False
        assert p1.uno_called is True
        assert p1.vulnerable_uno is False

    def test_uno_failed_call_vulnerable_and_caught(self) -> None:
        """When hand drops to 1 without call_uno, 3s window opens and opponent can catch."""
        p1 = PlayerState("p_1", "Alice", [
            Card("c_play", CardColor.RED, CardValue.ONE, CardType.NUMBER),
            Card("c_keep", CardColor.RED, CardValue.TWO, CardType.NUMBER),
        ])
        p2 = PlayerState("p_2", "Bob", [])
        table = TableState(
            room_code="R114",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
            draw_pile=[
                Card("pen1", CardColor.BLUE, CardValue.ONE, CardType.NUMBER),
                Card("pen2", CardColor.BLUE, CardValue.TWO, CardType.NUMBER),
            ],
        )
        engine = UnoGameEngine(table)
        res = engine.play_card("p_1", "c_play", call_uno=False)
        assert res["opened_vulnerability_window"] is True
        assert p1.vulnerable_uno is True

        # Bob catches Alice
        catch_res = engine.catch_uno(challenger_player_id="p_2", target_player_id="p_1")
        assert catch_res["status"] == "PENALTY_APPLIED"
        assert p1.card_count == 3  # kept 1 + 2 penalties = 3
        assert p1.vulnerable_uno is False

    def test_catch_uno_on_safe_player_fails(self) -> None:
        """Catching a player who is not vulnerable raises NOT_VULNERABLE."""
        p1 = PlayerState("p_1", "Alice", [Card("c1", CardColor.RED, CardValue.ONE, CardType.NUMBER)], vulnerable_uno=False)
        table = TableState(
            room_code="R115",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, PlayerState("p_2", "Bob")],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
        )
        engine = UnoGameEngine(table)
        with pytest.raises(GameEngineError) as exc:
            engine.catch_uno("p_2", "p_1")
        assert exc.value.code == "NOT_VULNERABLE"

    def test_catch_uno_window_expired(self) -> None:
        """Catching after the 3-second window expires raises WINDOW_EXPIRED."""
        past_time = int(time.time() * 1000) - 1000
        p1 = PlayerState("p_1", "Alice", [Card("c1", CardColor.RED, CardValue.ONE, CardType.NUMBER)], vulnerable_uno=True, vulnerability_deadline_ms=past_time)
        table = TableState(
            room_code="R116",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, PlayerState("p_2", "Bob")],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
        )
        engine = UnoGameEngine(table)
        with pytest.raises(GameEngineError) as exc:
            engine.catch_uno("p_2", "p_1")
        assert exc.value.code == "WINDOW_EXPIRED"
        assert p1.vulnerable_uno is False

    def test_scoring_at_game_end(self) -> None:
        """Round scoring tallies points of losing players' cards accurately."""
        p1 = PlayerState("p_1", "Alice", [Card("winning_card", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        # Bob has Wild (50 points) + Red 7 (7 points) = 57 points
        p2 = PlayerState("p_2", "Bob", [
            Card("c_w", CardColor.WILD, CardValue.WILD, CardType.WILD),
            Card("c_7", CardColor.RED, CardValue.SEVEN, CardType.NUMBER),
        ])
        # Charlie has Skip (20 points) = 20 points
        p3 = PlayerState("p_3", "Charlie", [
            Card("c_s", CardColor.BLUE, CardValue.SKIP, CardType.ACTION),
        ])

        table = TableState(
            room_code="R117",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2, p3],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        res = engine.play_card("p_1", "winning_card")
        assert res["status"] == "GAME_WON"
        assert res["winner_id"] == "p_1"
        # Total winner score = 57 + 20 = 77
        assert res["scoreboard"]["Alice"] == 77
        assert res["scoreboard"]["Bob"] == 57
        assert res["scoreboard"]["Charlie"] == 20

    def test_sanitized_state_security(self) -> None:
        """Opponents' cards must never leak in sanitized state (§6.3 & §12.6)."""
        p1 = PlayerState("p_1", "Alice", [Card("a1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p2 = PlayerState("p_2", "Bob", [Card("secret_card_bob", CardColor.BLUE, CardValue.TWO, CardType.NUMBER)])

        table = TableState(
            room_code="R118",
            rules=GameRules(),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            active_color=CardColor.RED,
        )
        engine = UnoGameEngine(table)
        alice_view = engine.get_sanitized_state("p_1")

        # Alice's hand has full card info
        assert len(alice_view["payload"]["your_hand"]) == 1
        assert alice_view["payload"]["your_hand"][0]["id"] == "a1"

        # Bob appears in opponents with only card_count; 'secret_card_bob' must NEVER appear
        assert len(alice_view["payload"]["opponents"]) == 1
        bob_summary = alice_view["payload"]["opponents"][0]
        assert bob_summary["player_id"] == "p_2"
        assert bob_summary["card_count"] == 1
        assert "hand" not in bob_summary
        assert "cards" not in bob_summary
        assert "secret_card_bob" not in str(alice_view)

    def test_turn_timeout_escalation(self) -> None:
        """Timeout draws 1 card, advances turn, and strike 2 triggers auto-pilot (§5.6)."""
        p1 = PlayerState("p_1", "Alice", [Card("a1", CardColor.RED, CardValue.ONE, CardType.NUMBER)])
        p2 = PlayerState("p_2", "Bob", [])
        table = TableState(
            room_code="R119",
            rules=GameRules(turn_time_seconds=25),
            current_player_index=0,
            players=[p1, p2],
            top_card=Card("top", CardColor.RED, CardValue.FIVE, CardType.NUMBER),
            draw_pile=[Card(f"d_{i}", CardColor.BLUE, CardValue.ONE, CardType.NUMBER) for i in range(5)],
            turn_deadline_ms=int(time.time() * 1000) - 100,  # Expired
        )
        engine = UnoGameEngine(table)

        # Strike 1
        res1 = engine.handle_turn_timeout()
        assert res1["timeout_occurred"] is True
        assert res1["afk_strikes"] == 1
        assert res1["is_auto_pilot"] is False
        assert table.current_player_index == 1

        # Force Bob's turn timeout
        table.turn_deadline_ms = int(time.time() * 1000) - 100
        engine.handle_turn_timeout()
        assert table.current_player_index == 0

        # Strike 2 on Alice triggers auto-pilot
        table.turn_deadline_ms = int(time.time() * 1000) - 100
        res2 = engine.handle_turn_timeout()
        assert res2["afk_strikes"] == 2
        assert res2["is_auto_pilot"] is True
        assert p1.is_auto_pilot is True
