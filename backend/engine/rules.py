"""
Authoritative Card Legality Validator & Rule Enforcer.
Compliant with docs.md Section 5.3 and 5.4.
"""

from __future__ import annotations

from typing import Optional

from engine.constants import CardColor, CardType, CardValue
from engine.models import Card, GameRules


def can_play_card(
    card: Card,
    top_card: Optional[Card],
    active_color: Optional[CardColor],
    rules: Optional[GameRules] = None,
    pending_draw_count: int = 0,
) -> bool:
    """
    Validate whether `card` is legal to play according to the official Legality Matrix (§5.3):
    1. If there is an active stacked draw attack (pending_draw_count > 0):
       - If stacking rule is enabled, ONLY a DRAW_TWO card can be stacked.
       - If stacking is not enabled, the player cannot play; they must draw the penalty.
    2. Otherwise, card C is legal to play on top card T with active color A_color iff:
       - C.color == A_color (or card matches current active color), OR
       - C.value == T.value (matching number or matching action name), OR
       - C.type == T.type (for action cards), OR
       - C.type == WILD, OR
       - C.type == WILD_DRAW_FOUR.
    """
    if rules is None:
        rules = GameRules()

    # If there is a pending stacked draw penalty
    if pending_draw_count > 0:
        if rules.stack_draw_two and card.value == CardValue.DRAW_TWO:
            return True
        return False

    # First turn edge case: if no top card, any card is valid
    if top_card is None:
        return True

    # Wild cards are always legal to play from hand
    if card.type in (CardType.WILD, CardType.WILD_DRAW_FOUR):
        return True

    # Color match with the active color (takes priority over top card printed color)
    effective_color = active_color if active_color else top_card.color
    if card.color == effective_color:
        return True

    # Value match (works for both Number cards 0-9 and Action cards like Skip, Reverse, Draw Two)
    if card.value == top_card.value:
        return True

    # Type match (e.g. Skip on Skip, Reverse on Reverse, Draw Two on Draw Two)
    if card.type == CardType.ACTION and card.type == top_card.type and card.value == top_card.value:
        return True

    return False


def get_playable_cards(
    hand: list[Card],
    top_card: Optional[Card],
    active_color: Optional[CardColor],
    rules: Optional[GameRules] = None,
    pending_draw_count: int = 0,
) -> list[Card]:
    """Filter and return the subset of cards in player's hand that are legal to play."""
    return [
        c
        for c in hand
        if can_play_card(
            card=c,
            top_card=top_card,
            active_color=active_color,
            rules=rules,
            pending_draw_count=pending_draw_count,
        )
    ]
