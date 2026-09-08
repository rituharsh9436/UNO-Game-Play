"""
Authoritative UNO Game Engine & State Machine.
Encapsulates all turn progressions, special card effects, UNO challenges, and state sanitization.
Compliant with docs.md Sections 5, 6.3, and 12.6.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from engine.constants import CardColor, CardType, CardValue, Direction
from engine.deck import UnoDeck
from engine.models import Card, GameRules, PlayerState, TableState
from engine.rules import can_play_card, get_playable_cards


class GameEngineError(Exception):
    """Base exception for all game engine rule violations."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class UnoGameEngine:
    """
    Pure Python authoritative state engine for a single UNO match.
    Zero external dependencies, completely deterministic and thread-safe per room.
    """

    def __init__(self, state: TableState) -> None:
        self.state = state

    @classmethod
    def create_game(
        cls,
        room_code: str,
        players_data: List[Tuple[str, str, bool]],  # (player_id, nickname, is_host)
        rules: Optional[GameRules] = None,
    ) -> UnoGameEngine:
        """
        Initialize and deal a brand new game match according to official Mattel setup (§5.2).
        Requires 2 to 6 players.
        """
        if len(players_data) < 2 or len(players_data) > 6:
            raise GameEngineError("INVALID_PLAYER_COUNT", "Game requires between 2 and 6 players.")

        if rules is None:
            rules = GameRules()

        # Generate and cryptographically shuffle 108 cards
        draw_pile = UnoDeck.create_shuffled_deck()

        # Deal 7 cards to each participant
        player_states: List[PlayerState] = []
        for p_id, nick, is_host in players_data:
            hand = [draw_pile.pop(0) for _ in range(7)]
            player_states.append(
                PlayerState(
                    player_id=p_id,
                    nickname=nick,
                    hand=hand,
                    is_host=is_host,
                    connected=True,
                )
            )

        # Resolve initial first card (§5.2)
        (
            first_card,
            active_color,
            direction,
            start_index,
            draw_penalty,
        ) = UnoDeck.resolve_first_card(draw_pile, len(player_states))

        discard_pile = [first_card]

        # Apply initial draw penalty if start card was Draw Two
        if draw_penalty > 0:
            penalized_player = player_states[0]
            for _ in range(draw_penalty):
                if draw_pile:
                    penalized_player.add_card(draw_pile.pop(0))

        now_ms = int(time.time() * 1000)
        deadline_ms = now_ms + (rules.turn_time_seconds * 1000)

        table_state = TableState(
            room_code=room_code,
            rules=rules,
            direction=direction,
            current_player_index=start_index,
            players=player_states,
            top_card=first_card,
            active_color=active_color,
            draw_pile=draw_pile,
            discard_pile=discard_pile,
            version=1,
            turn_deadline_ms=deadline_ms,
            turn_count=1,
            status="PLAYING",
            pending_draw_count=0,
        )

        return cls(table_state)

    def play_card(
        self,
        player_id: str,
        card_id: str,
        selected_color: Optional[CardColor] = None,
        call_uno: bool = False,
    ) -> Dict[str, Any]:
        """
        Authoritatively validate and execute a card play action (§5.3 - §5.5).
        """
        if self.state.status != "PLAYING":
            raise GameEngineError("GAME_NOT_IN_PROGRESS", "Cannot play cards when match is not active.")

        current_player = self.state.current_player
        if current_player.player_id != player_id:
            raise GameEngineError("NOT_YOUR_TURN", "It is not your turn to play.")

        card = current_player.get_card(card_id)
        if not card:
            raise GameEngineError("CARD_NOT_IN_HAND", f"Card {card_id} is not in your hand.")

        # Check card legality
        is_legal = can_play_card(
            card=card,
            top_card=self.state.top_card,
            active_color=self.state.active_color,
            rules=self.state.rules,
            pending_draw_count=self.state.pending_draw_count,
        )
        if not is_legal:
            raise GameEngineError("ILLEGAL_MOVE", f"Card {card.value.value} cannot be played now.")

        # Wild cards require an active color declaration
        if card.is_wild:
            if not selected_color or selected_color == CardColor.WILD:
                raise GameEngineError("MISSING_WILD_COLOR", "You must declare an active color for Wild cards.")
            chosen_active_color = selected_color
        else:
            chosen_active_color = card.color

        # Remove card from player hand
        current_player.remove_card(card_id)
        self.state.discard_pile.append(card)
        self.state.top_card = card
        self.state.active_color = chosen_active_color

        # Handle UNO Call & Vulnerability state (§5.5)
        new_hand_count = current_player.card_count
        opened_vulnerability_window = False

        if new_hand_count == 1:
            if call_uno:
                current_player.uno_called = True
                current_player.vulnerable_uno = False
                current_player.vulnerability_deadline_ms = None
            else:
                # Failed to call UNO: open 3.0-second vulnerability window
                current_player.uno_called = False
                current_player.vulnerable_uno = True
                current_player.vulnerability_deadline_ms = int(time.time() * 1000) + 3000
                opened_vulnerability_window = True
        elif new_hand_count == 0:
            # Player has placed their last card: VICTORY!
            return self._finalize_round(winner=current_player)
        else:
            # More than 1 card: reset uno state
            current_player.uno_called = False
            current_player.vulnerable_uno = False
            current_player.vulnerability_deadline_ms = None

        # Reset turn draw state
        current_player.has_drawn_this_turn = False

        # Execute Card Action Transitions (§5.4)
        advance_steps = 1
        cards_to_draw_next = 0

        if card.value == CardValue.SKIP:
            advance_steps = 2

        elif card.value == CardValue.REVERSE:
            if len(self.state.players) == 2:
                # 2-player game: Reverse acts identically to Skip
                advance_steps = 2
            else:
                self.state.direction = self.state.direction.invert()
                advance_steps = 1

        elif card.value == CardValue.DRAW_TWO:
            if self.state.rules.stack_draw_two:
                # Stacking house rule enabled
                self.state.pending_draw_count += 2
                advance_steps = 1
            else:
                # Standard rule: next player draws 2 and loses their turn
                cards_to_draw_next = 2
                advance_steps = 2

        elif card.value == CardValue.DRAW_FOUR:
            # Wild Draw 4: next player draws 4 and loses turn
            cards_to_draw_next = 4
            advance_steps = 2

        # Advance turn index
        next_index = self._calculate_next_index(self.state.current_player_index, advance_steps)
        self.state.current_player_index = next_index

        # If next player had to draw without stacking (+2 or +4)
        if cards_to_draw_next > 0:
            skipped_player_index = (
                self.state.current_player_index - (1 * self.state.direction.value)
            ) % len(self.state.players)
            self._draw_cards_for_player(self.state.players[skipped_player_index], cards_to_draw_next)

        # Increment version and update deadline
        self.state.version += 1
        self.state.turn_count += 1
        now_ms = int(time.time() * 1000)
        self.state.turn_deadline_ms = now_ms + (self.state.rules.turn_time_seconds * 1000)

        return {
            "status": "SUCCESS",
            "card_played": card.to_dict(),
            "active_color": self.state.active_color.value,
            "next_player_id": self.state.current_player.player_id,
            "opened_vulnerability_window": opened_vulnerability_window,
            "vulnerable_player_id": current_player.player_id if opened_vulnerability_window else None,
        }

    def draw_card(self, player_id: str) -> Dict[str, Any]:
        """
        Draw a card from the draw pile.
        - If stacked penalty active: draws all accumulated cards and skips turn.
        - Otherwise draws 1 card and marks `has_drawn_this_turn = True`.
        """
        if self.state.status != "PLAYING":
            raise GameEngineError("GAME_NOT_IN_PROGRESS", "Cannot draw card when match is not active.")

        current_player = self.state.current_player
        if current_player.player_id != player_id:
            raise GameEngineError("NOT_YOUR_TURN", "Cannot draw when it is not your turn.")

        # If resolving stacked draw penalties
        if self.state.pending_draw_count > 0:
            count = self.state.pending_draw_count
            self.state.pending_draw_count = 0
            drawn = self._draw_cards_for_player(current_player, count)
            # Player loses turn after accepting penalty
            self.state.current_player_index = self._calculate_next_index(self.state.current_player_index, 1)
            self.state.version += 1
            now_ms = int(time.time() * 1000)
            self.state.turn_deadline_ms = now_ms + (self.state.rules.turn_time_seconds * 1000)
            return {
                "action": "ACCEPTED_STACK_PENALTY",
                "drawn_count": count,
                "drawn_cards": [c.to_dict() for c in drawn],
                "turn_advanced": True,
                "next_player_id": self.state.current_player.player_id,
            }

        if current_player.has_drawn_this_turn:
            raise GameEngineError("ALREADY_DRAWN", "You have already drawn a card this turn. Pass or play.")

        drawn = self._draw_cards_for_player(current_player, 1)
        drawn_card = drawn[0] if drawn else None
        current_player.has_drawn_this_turn = True
        self.state.version += 1

        is_playable = False
        if drawn_card:
            is_playable = can_play_card(
                drawn_card,
                self.state.top_card,
                self.state.active_color,
                self.state.rules,
            )

        return {
            "action": "CARD_DRAWN",
            "drawn_card": drawn_card.to_dict() if drawn_card else None,
            "is_playable": is_playable,
        }

    def pass_turn(self, player_id: str) -> Dict[str, Any]:
        """
        Pass turn after drawing (§6.2).
        Valid only if player has already drawn during the current turn.
        """
        if self.state.status != "PLAYING":
            raise GameEngineError("GAME_NOT_IN_PROGRESS", "Match is not active.")

        current_player = self.state.current_player
        if current_player.player_id != player_id:
            raise GameEngineError("NOT_YOUR_TURN", "It is not your turn.")

        if not current_player.has_drawn_this_turn:
            raise GameEngineError("CANNOT_PASS", "You must draw a card before you can pass your turn.")

        current_player.has_drawn_this_turn = False
        self.state.current_player_index = self._calculate_next_index(self.state.current_player_index, 1)
        self.state.version += 1
        now_ms = int(time.time() * 1000)
        self.state.turn_deadline_ms = now_ms + (self.state.rules.turn_time_seconds * 1000)

        return {
            "status": "SUCCESS",
            "next_player_id": self.state.current_player.player_id,
            "version": self.state.version,
        }

    def catch_uno(self, challenger_player_id: str, target_player_id: str) -> Dict[str, Any]:
        """
        Opponent calls Catch UNO within the 3-second vulnerability window (§5.5).
        Penalizes target player by forcing 2 card draws.
        """
        target = self.state.get_player(target_player_id)
        if not target:
            raise GameEngineError("PLAYER_NOT_FOUND", "Target player does not exist.")

        if not target.vulnerable_uno:
            raise GameEngineError("NOT_VULNERABLE", "Target player is not vulnerable to an UNO catch.")

        now_ms = int(time.time() * 1000)
        if target.vulnerability_deadline_ms and now_ms > target.vulnerability_deadline_ms:
            target.vulnerable_uno = False
            target.vulnerability_deadline_ms = None
            raise GameEngineError("WINDOW_EXPIRED", "The 3.0-second Catch UNO window has already elapsed.")

        # Apply 2-card penalty
        target.vulnerable_uno = False
        target.vulnerability_deadline_ms = None
        drawn_cards = self._draw_cards_for_player(target, 2)
        self.state.version += 1

        return {
            "status": "PENALTY_APPLIED",
            "target_player_id": target_player_id,
            "challenger_player_id": challenger_player_id,
            "drawn_count": len(drawn_cards),
        }

    def handle_turn_timeout(self, force: bool = False) -> Dict[str, Any]:
        """
        Handle deadline expiration (§5.6).
        Draws 1 card for player, logs AFK strike, and advances turn.
        """
        now_ms = int(time.time() * 1000)
        if not force and now_ms < self.state.turn_deadline_ms:
            return {"timeout_occurred": False}

        current_player = self.state.current_player
        current_player.afk_strikes += 1

        if current_player.afk_strikes >= 2:
            current_player.is_auto_pilot = True

        # Draw penalty card
        self._draw_cards_for_player(current_player, 1)
        current_player.has_drawn_this_turn = False

        # Advance turn
        self.state.current_player_index = self._calculate_next_index(self.state.current_player_index, 1)
        self.state.version += 1
        self.state.turn_deadline_ms = now_ms + (self.state.rules.turn_time_seconds * 1000)

        return {
            "timeout_occurred": True,
            "timed_out_player_id": current_player.player_id,
            "afk_strikes": current_player.afk_strikes,
            "is_auto_pilot": current_player.is_auto_pilot,
            "next_player_id": self.state.current_player.player_id,
        }

    def get_sanitized_state(self, recipient_player_id: str) -> Dict[str, Any]:
        """
        Produce a zero-knowledge sanitized state payload for the specified recipient (§6.3 & §12.6).
        Ensures opponents' card hands and the draw pile sequence are NEVER exposed.
        """
        recipient = self.state.get_player(recipient_player_id)
        if not recipient:
            raise GameEngineError("PLAYER_NOT_FOUND", "Player not in this game.")

        # Compute playable flags for recipient's own hand
        your_hand_payload = []
        is_my_turn = self.state.current_player.player_id == recipient_player_id
        for card in recipient.hand:
            playable = is_my_turn and can_play_card(
                card,
                self.state.top_card,
                self.state.active_color,
                self.state.rules,
                self.state.pending_draw_count,
            )
            your_hand_payload.append(card.to_dict(is_playable=playable))

        # Build sanitized opponents list (card count only, zero card IDs)
        opponents_payload = []
        for p in self.state.players:
            if p.player_id == recipient_player_id:
                continue
            opponents_payload.append(
                {
                    "player_id": p.player_id,
                    "nickname": p.nickname,
                    "card_count": p.card_count,
                    "is_host": p.is_host,
                    "connected": p.connected,
                    "uno_called": p.uno_called,
                    "vulnerable_uno": p.vulnerable_uno,
                    "is_auto_pilot": p.is_auto_pilot,
                }
            )

        return {
            "type": "game_state_sync",
            "version": self.state.version,
            "payload": {
                "room_code": self.state.room_code,
                "status": self.state.status,
                "direction": self.state.direction.value,
                "current_player_id": self.state.current_player.player_id,
                "turn_deadline_ms": self.state.turn_deadline_ms,
                "top_card": self.state.top_card.to_dict() if self.state.top_card else None,
                "active_color": self.state.active_color.value if self.state.active_color else None,
                "draw_pile_count": len(self.state.draw_pile),
                "discard_pile_count": len(self.state.discard_pile),
                "pending_draw_count": self.state.pending_draw_count,
                "winner_id": self.state.winner_id,
                "opponents": opponents_payload,
                "your_hand": your_hand_payload,
            },
        }

    # Private internal helpers
    def _calculate_next_index(self, current_index: int, steps: int) -> int:
        direction_val = self.state.direction.value
        total = len(self.state.players)
        return (current_index + (steps * direction_val)) % total

    def _draw_cards_for_player(self, player: PlayerState, count: int) -> List[Card]:
        drawn: List[Card] = []
        for _ in range(count):
            if not self.state.draw_pile:
                # Reshuffle discard pile (§5.7)
                preserved_top, new_draw = UnoDeck.reshuffle_discard_pile(self.state.discard_pile)
                self.state.discard_pile = [preserved_top]
                self.state.draw_pile = new_draw

            if self.state.draw_pile:
                card = self.state.draw_pile.pop(0)
                player.add_card(card)
                drawn.append(card)
        return drawn

    def _finalize_round(self, winner: PlayerState) -> Dict[str, Any]:
        self.state.status = "FINISHED"
        self.state.winner_id = winner.player_id

        # Calculate scores from all losing players' remaining cards
        scoreboard: Dict[str, int] = {}
        total_winner_points = 0
        for p in self.state.players:
            player_points = sum(c.points for c in p.hand)
            scoreboard[p.nickname] = player_points
            if p.player_id != winner.player_id:
                total_winner_points += player_points

        scoreboard[winner.nickname] = total_winner_points

        return {
            "status": "GAME_WON",
            "winner_id": winner.player_id,
            "winner_nickname": winner.nickname,
            "scoreboard": scoreboard,
            "total_turns": self.state.turn_count,
        }
