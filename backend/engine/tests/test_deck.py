"""
Unit tests for UNO deck generation, distribution, shuffling, first card resolution, and reshuffling.
Complies with docs.md Section 5.1, 5.2, and 5.7.
"""

from collections import Counter
import pytest

from engine.constants import CardColor, CardType, CardValue, Direction, STANDARD_COLORS
from engine.deck import UnoDeck
from engine.models import Card


class TestUnoDeck:
    def test_deck_total_count(self) -> None:
        """Deck must contain exactly 108 cards."""
        deck = UnoDeck.generate_standard_deck()
        assert len(deck) == 108

    def test_deck_color_distribution(self) -> None:
        """Deck must contain exactly 25 of each standard color and 8 wild cards."""
        deck = UnoDeck.generate_standard_deck()
        color_counts = Counter(c.color for c in deck)
        assert color_counts[CardColor.RED] == 25
        assert color_counts[CardColor.BLUE] == 25
        assert color_counts[CardColor.GREEN] == 25
        assert color_counts[CardColor.YELLOW] == 25
        assert color_counts[CardColor.WILD] == 8

    def test_zero_cards_count(self) -> None:
        """There must be exactly one 0 card per standard color (4 total)."""
        deck = UnoDeck.generate_standard_deck()
        zeros = [c for c in deck if c.value == CardValue.ZERO]
        assert len(zeros) == 4
        for color in STANDARD_COLORS:
            assert any(c.color == color and c.value == CardValue.ZERO for c in zeros)

    def test_number_cards_distribution(self) -> None:
        """There must be exactly two of each number 1-9 per color (72 total)."""
        deck = UnoDeck.generate_standard_deck()
        numbers = [c for c in deck if c.type == CardType.NUMBER and c.value != CardValue.ZERO]
        assert len(numbers) == 72

        for color in STANDARD_COLORS:
            color_numbers = [c for c in numbers if c.color == color]
            val_counts = Counter(c.value for c in color_numbers)
            for val_str in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                assert val_counts[CardValue(val_str)] == 2

    def test_action_cards_distribution(self) -> None:
        """There must be exactly two of each action card (Skip, Reverse, Draw Two) per color (24 total)."""
        deck = UnoDeck.generate_standard_deck()
        actions = [c for c in deck if c.type == CardType.ACTION]
        assert len(actions) == 24

        for color in STANDARD_COLORS:
            color_actions = [c for c in actions if c.color == color]
            act_counts = Counter(c.value for c in color_actions)
            assert act_counts[CardValue.SKIP] == 2
            assert act_counts[CardValue.REVERSE] == 2
            assert act_counts[CardValue.DRAW_TWO] == 2

    def test_wild_cards_distribution(self) -> None:
        """There must be exactly 4 Wild cards and 4 Wild Draw Four cards."""
        deck = UnoDeck.generate_standard_deck()
        wilds = [c for c in deck if c.type == CardType.WILD]
        draw_fours = [c for c in deck if c.type == CardType.WILD_DRAW_FOUR]
        assert len(wilds) == 4
        assert len(draw_fours) == 4

    def test_deck_card_ids_unique(self) -> None:
        """All 108 cards must have unique IDs."""
        deck = UnoDeck.generate_standard_deck()
        ids = [c.id for c in deck]
        assert len(ids) == len(set(ids))

    def test_shuffle_preserves_cards(self) -> None:
        """Shuffling must preserve all 108 cards while altering order."""
        deck = UnoDeck.generate_standard_deck()
        shuffled = UnoDeck.shuffle(deck)
        assert len(shuffled) == 108
        assert set(c.id for c in deck) == set(c.id for c in shuffled)

    def test_resolve_first_card_number(self) -> None:
        """A number card as first card starts clockwise with player 0."""
        number_card = Card(id="c_red_5_1", color=CardColor.RED, value=CardValue.FIVE, type=CardType.NUMBER)
        pile = [number_card]
        top, col, direction, start_idx, penalty = UnoDeck.resolve_first_card(pile, player_count=4)
        assert top == number_card
        assert col == CardColor.RED
        assert direction == Direction.CLOCKWISE
        assert start_idx == 0
        assert penalty == 0

    def test_resolve_first_card_skip(self) -> None:
        """Skip card as first card skips player 0 and starts player 1."""
        skip_card = Card(id="c_blue_skip_1", color=CardColor.BLUE, value=CardValue.SKIP, type=CardType.ACTION)
        pile = [skip_card]
        top, col, direction, start_idx, penalty = UnoDeck.resolve_first_card(pile, player_count=4)
        assert top == skip_card
        assert start_idx == 1
        assert penalty == 0

    def test_resolve_first_card_reverse_multiplayer(self) -> None:
        """Reverse card as first card in 4-player game switches direction to Counter-Clockwise."""
        rev_card = Card(id="c_green_rev_1", color=CardColor.GREEN, value=CardValue.REVERSE, type=CardType.ACTION)
        pile = [rev_card]
        top, col, direction, start_idx, penalty = UnoDeck.resolve_first_card(pile, player_count=4)
        assert top == rev_card
        assert direction == Direction.COUNTER_CLOCKWISE
        assert start_idx == 0

    def test_resolve_first_card_reverse_two_player(self) -> None:
        """Reverse card as first card in 2-player game acts like Skip."""
        rev_card = Card(id="c_green_rev_1", color=CardColor.GREEN, value=CardValue.REVERSE, type=CardType.ACTION)
        pile = [rev_card]
        top, col, direction, start_idx, penalty = UnoDeck.resolve_first_card(pile, player_count=2)
        assert top == rev_card
        assert start_idx == 1

    def test_resolve_first_card_draw_two(self) -> None:
        """Draw Two as first card gives player 0 a 2-card penalty and advances start to player 1."""
        draw2 = Card(id="c_yellow_d2_1", color=CardColor.YELLOW, value=CardValue.DRAW_TWO, type=CardType.ACTION)
        pile = [draw2]
        top, col, direction, start_idx, penalty = UnoDeck.resolve_first_card(pile, player_count=4)
        assert top == draw2
        assert start_idx == 1
        assert penalty == 2

    def test_resolve_first_card_wild(self) -> None:
        """Wild card as first card sets default active color."""
        wild_card = Card(id="c_wild_1", color=CardColor.WILD, value=CardValue.WILD, type=CardType.WILD)
        pile = [wild_card]
        top, col, direction, start_idx, penalty = UnoDeck.resolve_first_card(pile, player_count=4)
        assert top == wild_card
        assert col == CardColor.RED

    def test_resolve_first_card_wild_draw_four_redrawn(self) -> None:
        """Wild Draw Four is illegal as first card and must be returned into the deck (§5.2)."""
        wdf = Card(id="c_wdf_1", color=CardColor.WILD, value=CardValue.DRAW_FOUR, type=CardType.WILD_DRAW_FOUR)
        valid_card = Card(id="c_blue_7_1", color=CardColor.BLUE, value=CardValue.SEVEN, type=CardType.NUMBER)
        pile = [wdf, valid_card]

        top, col, direction, start_idx, penalty = UnoDeck.resolve_first_card(pile, player_count=4)
        # Should have skipped wdf and chosen valid_card
        assert top == valid_card
        assert col == CardColor.BLUE
        # wdf should have been returned into pile
        assert wdf in pile

    def test_reshuffle_discard_pile(self) -> None:
        """Discard pile reshuffle preserves top card and turns rest into new draw pile (§5.7)."""
        card1 = Card(id="c_red_1_1", color=CardColor.RED, value=CardValue.ONE, type=CardType.NUMBER)
        card2 = Card(id="c_blue_2_1", color=CardColor.BLUE, value=CardValue.TWO, type=CardType.NUMBER)
        card3 = Card(id="c_green_3_1", color=CardColor.GREEN, value=CardValue.THREE, type=CardType.NUMBER)
        discard = [card1, card2, card3]

        top, new_draw = UnoDeck.reshuffle_discard_pile(discard)
        assert top == card3
        assert len(new_draw) == 2
        assert set(c.id for c in new_draw) == {card1.id, card2.id}
