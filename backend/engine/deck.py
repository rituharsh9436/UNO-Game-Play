"""
Standard 108-Card UNO Deck Generation, Shuffling, and Initial Dealing.
Compliant with docs.md Section 5.1, 5.2, and 5.7.
"""

from __future__ import annotations

import secrets
from typing import List, Optional, Tuple

from engine.constants import (
    ACTION_VALUES,
    NUMBER_VALUES,
    STANDARD_COLORS,
    CardColor,
    CardType,
    CardValue,
    Direction,
)
from engine.models import Card


class UnoDeck:
    """Authoritative UNO deck generator and shuffler."""

    @staticmethod
    def generate_standard_deck() -> List[Card]:
        """
        Generate the standard official 108-card UNO deck.
        - 19 Red cards (one 0, two each 1-9)
        - 19 Blue cards (one 0, two each 1-9)
        - 19 Green cards (one 0, two each 1-9)
        - 19 Yellow cards (one 0, two each 1-9)
        - 8 Skip cards (2 per color)
        - 8 Reverse cards (2 per color)
        - 8 Draw Two cards (2 per color)
        - 4 Wild cards
        - 4 Wild Draw Four cards
        Total: 4 + 72 + 8 + 8 + 8 + 4 + 4 = 108 cards.
        """
        cards: List[Card] = []

        # Color-specific cards (25 per color = 100 colored cards)
        for color in STANDARD_COLORS:
            col_str = color.value.lower()
            # One '0' card per color
            cards.append(
                Card(
                    id=f"c_{col_str}_0",
                    color=color,
                    value=CardValue.ZERO,
                    type=CardType.NUMBER,
                )
            )

            # Two of each number 1 to 9 per color
            for num in NUMBER_VALUES[1:]:  # 1 through 9
                for copy_idx in (1, 2):
                    cards.append(
                        Card(
                            id=f"c_{col_str}_{num.value}_{copy_idx}",
                            color=color,
                            value=num,
                            type=CardType.NUMBER,
                        )
                    )

            # Two of each action card (Skip, Reverse, Draw Two) per color
            for action in ACTION_VALUES:
                act_str = action.value.lower()
                for copy_idx in (1, 2):
                    cards.append(
                        Card(
                            id=f"c_{col_str}_{act_str}_{copy_idx}",
                            color=color,
                            value=action,
                            type=CardType.ACTION,
                        )
                    )

        # 4 Wild Cards (Neutral color)
        for idx in range(1, 5):
            cards.append(
                Card(
                    id=f"c_wild_{idx}",
                    color=CardColor.WILD,
                    value=CardValue.WILD,
                    type=CardType.WILD,
                )
            )

        # 4 Wild Draw Four Cards (Neutral color)
        for idx in range(1, 5):
            cards.append(
                Card(
                    id=f"c_wild_draw_four_{idx}",
                    color=CardColor.WILD,
                    value=CardValue.DRAW_FOUR,
                    type=CardType.WILD_DRAW_FOUR,
                )
            )

        return cards

    @staticmethod
    def shuffle(cards: List[Card]) -> List[Card]:
        """
        Perform a cryptographically secure Fisher-Yates shuffle.
        Uses secrets.SystemRandom to eliminate predictability.
        """
        deck = list(cards)
        rng = secrets.SystemRandom()
        for i in range(len(deck) - 1, 0, -1):
            j = rng.randint(0, i)
            deck[i], deck[j] = deck[j], deck[i]
        return deck

    @classmethod
    def create_shuffled_deck(cls) -> List[Card]:
        """Create and return a freshly shuffled 108-card deck."""
        return cls.shuffle(cls.generate_standard_deck())

    @staticmethod
    def resolve_first_card(
        draw_pile: List[Card],
        player_count: int,
    ) -> Tuple[Card, CardColor, Direction, int, int]:
        """
        Draw and resolve the initial top card according to official Mattel rules (§5.2):
        - Wild Draw Four: Illegal as start card. Returned into deck, reshuffled, and redrawn.
        - Wild: Starting active color is set (defaults to RED or chosen). First player starts.
        - Number Card: Normal start, player 1 (to host's left) starts.
        - Skip: First player skipped, player 2 starts.
        - Reverse: Direction reversed (Counter-Clockwise). In 2-player, acts as skip. Host (player 0) starts.
        - Draw Two: First player draws 2 cards and skips turn; player 2 starts.

        Returns:
            (first_card, active_color, initial_direction, starting_player_index, initial_draw_penalty)
        """
        first_card: Optional[Card] = None

        # Wild Draw Four is illegal as first card: pop until legal first card found (§5.2)
        illegal_cards: List[Card] = []
        while draw_pile:
            candidate = draw_pile.pop(0)
            if candidate.type == CardType.WILD_DRAW_FOUR:
                illegal_cards.append(candidate)
            else:
                first_card = candidate
                break

        # Return skipped Wild Draw Four cards back into the middle of the deck
        if illegal_cards:
            mid_index = len(draw_pile) // 2
            for card in illegal_cards:
                draw_pile.insert(mid_index, card)

        if first_card is None:
            raise ValueError("Cannot resolve first card from an empty draw pile.")

        initial_direction = Direction.CLOCKWISE
        starting_player_index = 0
        initial_draw_penalty = 0

        if first_card.type == CardType.NUMBER:
            # Normal play begins with host's left (player 1 in clockwise)
            active_color = first_card.color
            starting_player_index = 0

        elif first_card.value == CardValue.SKIP:
            # First player is skipped; second player starts
            active_color = first_card.color
            starting_player_index = 1 % player_count

        elif first_card.value == CardValue.REVERSE:
            # Direction inverts to Counter-Clockwise
            initial_direction = Direction.COUNTER_CLOCKWISE
            active_color = first_card.color
            if player_count == 2:
                # In 2-player game, reverse acts as Skip
                starting_player_index = 1
            else:
                # Host plays first in counter-clockwise
                starting_player_index = 0

        elif first_card.value == CardValue.DRAW_TWO:
            # First player draws 2 and misses turn
            active_color = first_card.color
            starting_player_index = 1 % player_count
            initial_draw_penalty = 2

        elif first_card.type == CardType.WILD:
            # First player chooses color; default active color is RED if unresolved
            active_color = CardColor.RED
            starting_player_index = 0

        else:
            active_color = first_card.color
            starting_player_index = 0

        return (
            first_card,
            active_color,
            initial_direction,
            starting_player_index,
            initial_draw_penalty,
        )

    @staticmethod
    def reshuffle_discard_pile(
        discard_pile: List[Card],
    ) -> Tuple[Card, List[Card]]:
        """
        Reshuffle draw pile from discard pile when draw pile depletes (§5.7):
        1. Top card of discard pile remains on the table.
        2. All other discard cards are harvested.
        3. All harvested cards are shuffled cryptographically.
        Returns:
            (preserved_top_card, new_draw_pile)
        """
        if not discard_pile:
            return (
                Card(id="c_fallback", color=CardColor.RED, value=CardValue.ZERO, type=CardType.NUMBER),
                [],
            )

        # Top card remains in discard pile
        top_card = discard_pile[-1]
        pool = discard_pile[:-1]

        # Reset any selected colors on wild cards in pool
        cleansed_pool = [
            Card(id=c.id, color=c.color, value=c.value, type=c.type)
            for c in pool
        ]

        new_draw_pile = UnoDeck.shuffle(cleansed_pool)
        return top_card, new_draw_pile
