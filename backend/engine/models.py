"""
Data Models for UNO Game Engine.
Using dataclasses for high performance, immutability, and serialization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from engine.constants import CARD_POINT_VALUES, CardColor, CardType, CardValue, Direction


@dataclass(frozen=True)
class Card:
    """
    Immutable representation of an UNO card.
    """

    id: str
    color: CardColor
    value: CardValue
    type: CardType

    @property
    def points(self) -> int:
        """Return the official tournament point value for this card."""
        return CARD_POINT_VALUES.get(self.value, 0)

    @property
    def is_wild(self) -> bool:
        """Check if this card is a Wild or Wild Draw Four."""
        return self.type in (CardType.WILD, CardType.WILD_DRAW_FOUR)

    @property
    def is_action(self) -> bool:
        """Check if this card is an action card."""
        return self.type in (CardType.ACTION, CardType.WILD, CardType.WILD_DRAW_FOUR)

    def to_dict(self, is_playable: Optional[bool] = None) -> Dict[str, Any]:
        """Serialize card to dictionary matching schema in docs.md Section 6.3."""
        payload: Dict[str, Any] = {
            "id": self.id,
            "color": self.color.value,
            "value": self.value.value,
            "type": self.type.value,
        }
        if is_playable is not None:
            payload["is_playable"] = is_playable
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Card:
        """Construct a Card instance from dictionary."""
        return cls(
            id=data["id"],
            color=CardColor(data["color"]),
            value=CardValue(data["value"]),
            type=CardType(data["type"]),
        )


@dataclass
class GameRules:
    """Configurable House Rules."""

    stack_draw_two: bool = False
    turn_time_seconds: int = 25
    draw_to_match: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> GameRules:
        if not data:
            return cls()
        return cls(
            stack_draw_two=bool(data.get("stack_draw_two", False)),
            turn_time_seconds=int(data.get("turn_time_seconds", 25)),
            draw_to_match=bool(data.get("draw_to_match", False)),
        )


@dataclass
class PlayerState:
    """Player runtime state tracked by the engine."""

    player_id: str
    nickname: str
    hand: List[Card] = field(default_factory=list)
    uno_called: bool = False
    vulnerable_uno: bool = False
    vulnerability_deadline_ms: Optional[int] = None
    has_drawn_this_turn: bool = False
    is_auto_pilot: bool = False
    afk_strikes: int = 0
    connected: bool = True
    is_host: bool = False

    @property
    def card_count(self) -> int:
        return len(self.hand)

    def has_card(self, card_id: str) -> bool:
        return any(c.id == card_id for c in self.hand)

    def get_card(self, card_id: str) -> Optional[Card]:
        for c in self.hand:
            if c.id == card_id:
                return c
        return None

    def remove_card(self, card_id: str) -> Optional[Card]:
        for i, c in enumerate(self.hand):
            if c.id == card_id:
                return self.hand.pop(i)
        return None

    def add_card(self, card: Card) -> None:
        self.hand.append(card)


@dataclass
class TableState:
    """Complete authoritative table state."""

    room_code: str
    rules: GameRules
    direction: Direction = Direction.CLOCKWISE
    current_player_index: int = 0
    players: List[PlayerState] = field(default_factory=list)
    top_card: Optional[Card] = None
    active_color: Optional[CardColor] = None
    draw_pile: List[Card] = field(default_factory=list)
    discard_pile: List[Card] = field(default_factory=list)
    version: int = 1
    turn_deadline_ms: int = 0
    turn_count: int = 0
    status: str = "PLAYING"
    winner_id: Optional[str] = None
    pending_draw_count: int = 0

    @property
    def current_player(self) -> PlayerState:
        return self.players[self.current_player_index]

    def get_player(self, player_id: str) -> Optional[PlayerState]:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def get_player_index(self, player_id: str) -> int:
        for i, p in enumerate(self.players):
            if p.player_id == player_id:
                return i
        return -1
