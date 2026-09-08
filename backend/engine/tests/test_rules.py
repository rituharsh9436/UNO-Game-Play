"""
Unit tests for UNO card legality matrix and house rule enforcement.
Complies with docs.md Section 5.3 and 5.4.
"""

import pytest

from engine.constants import CardColor, CardType, CardValue
from engine.models import Card, GameRules
from engine.rules import can_play_card, get_playable_cards


class TestRulesEngine:
    @pytest.fixture
    def red_five(self) -> Card:
        return Card(id="c_red_5_1", color=CardColor.RED, value=CardValue.FIVE, type=CardType.NUMBER)

    @pytest.fixture
    def red_nine(self) -> Card:
        return Card(id="c_red_9_1", color=CardColor.RED, value=CardValue.NINE, type=CardType.NUMBER)

    @pytest.fixture
    def blue_five(self) -> Card:
        return Card(id="c_blue_5_1", color=CardColor.BLUE, value=CardValue.FIVE, type=CardType.NUMBER)

    @pytest.fixture
    def yellow_two(self) -> Card:
        return Card(id="c_yellow_2_1", color=CardColor.YELLOW, value=CardValue.TWO, type=CardType.NUMBER)

    @pytest.fixture
    def red_skip(self) -> Card:
        return Card(id="c_red_skip_1", color=CardColor.RED, value=CardValue.SKIP, type=CardType.ACTION)

    @pytest.fixture
    def green_skip(self) -> Card:
        return Card(id="c_green_skip_1", color=CardColor.GREEN, value=CardValue.SKIP, type=CardType.ACTION)

    @pytest.fixture
    def blue_draw_two(self) -> Card:
        return Card(id="c_blue_d2_1", color=CardColor.BLUE, value=CardValue.DRAW_TWO, type=CardType.ACTION)

    @pytest.fixture
    def red_draw_two(self) -> Card:
        return Card(id="c_red_d2_1", color=CardColor.RED, value=CardValue.DRAW_TWO, type=CardType.ACTION)

    @pytest.fixture
    def wild_card(self) -> Card:
        return Card(id="c_wild_1", color=CardColor.WILD, value=CardValue.WILD, type=CardType.WILD)

    @pytest.fixture
    def wild_draw_four(self) -> Card:
        return Card(id="c_wdf_1", color=CardColor.WILD, value=CardValue.DRAW_FOUR, type=CardType.WILD_DRAW_FOUR)

    def test_matching_color(self, red_five: Card, red_nine: Card) -> None:
        """Card with matching color is legal."""
        assert can_play_card(red_nine, top_card=red_five, active_color=CardColor.RED) is True

    def test_matching_number_different_color(self, red_five: Card, blue_five: Card) -> None:
        """Card with matching number is legal regardless of color."""
        assert can_play_card(blue_five, top_card=red_five, active_color=CardColor.RED) is True

    def test_matching_action_type(self, red_skip: Card, green_skip: Card) -> None:
        """Skip can be played on Skip even with differing color."""
        assert can_play_card(green_skip, top_card=red_skip, active_color=CardColor.RED) is True

    def test_wild_always_legal(self, red_five: Card, wild_card: Card) -> None:
        """Wild card is always legal on any card."""
        assert can_play_card(wild_card, top_card=red_five, active_color=CardColor.RED) is True

    def test_wild_draw_four_always_legal(self, red_five: Card, wild_draw_four: Card) -> None:
        """Wild Draw Four is legal on standard plays."""
        assert can_play_card(wild_draw_four, top_card=red_five, active_color=CardColor.RED) is True

    def test_mismatched_card_illegal(self, red_five: Card, yellow_two: Card) -> None:
        """Card with neither matching color nor matching value is illegal."""
        assert can_play_card(yellow_two, top_card=red_five, active_color=CardColor.RED) is False

    def test_active_color_override(self, wild_card: Card, blue_five: Card, red_five: Card) -> None:
        """When top card is Wild and active color is BLUE, blue card is legal and red card is illegal."""
        assert can_play_card(blue_five, top_card=wild_card, active_color=CardColor.BLUE) is True
        assert can_play_card(red_five, top_card=wild_card, active_color=CardColor.BLUE) is False

    def test_draw_two_stacking_enabled(self, red_draw_two: Card, blue_draw_two: Card) -> None:
        """Under stacking house rule, Draw Two can be played on pending draw attack."""
        rules = GameRules(stack_draw_two=True)
        assert can_play_card(blue_draw_two, top_card=red_draw_two, active_color=CardColor.RED, rules=rules, pending_draw_count=2) is True

    def test_draw_two_stacking_disabled(self, red_draw_two: Card, blue_draw_two: Card) -> None:
        """When stacking is disabled, player cannot counter an active draw penalty."""
        rules = GameRules(stack_draw_two=False)
        assert can_play_card(blue_draw_two, top_card=red_draw_two, active_color=CardColor.RED, rules=rules, pending_draw_count=2) is False

    def test_non_draw_two_cannot_stack_on_draw_attack(self, red_draw_two: Card, red_five: Card) -> None:
        """Even with matching color, a number card cannot be played during pending draw attack."""
        rules = GameRules(stack_draw_two=True)
        assert can_play_card(red_five, top_card=red_draw_two, active_color=CardColor.RED, rules=rules, pending_draw_count=2) is False

    def test_get_playable_cards(self, red_five: Card, red_nine: Card, yellow_two: Card, wild_card: Card) -> None:
        """get_playable_cards filters hand correctly."""
        hand = [red_nine, yellow_two, wild_card]
        playable = get_playable_cards(hand, top_card=red_five, active_color=CardColor.RED)
        playable_ids = [c.id for c in playable]
        assert red_nine.id in playable_ids
        assert wild_card.id in playable_ids
        assert yellow_two.id not in playable_ids
