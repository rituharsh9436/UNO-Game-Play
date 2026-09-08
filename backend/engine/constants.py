"""
Constants and Enums for UNO Game Logic.
"""

from enum import Enum, IntEnum
from typing import List


class CardColor(str, Enum):
    RED = "RED"
    BLUE = "BLUE"
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    WILD = "WILD"


STANDARD_COLORS: List[CardColor] = [
    CardColor.RED,
    CardColor.BLUE,
    CardColor.GREEN,
    CardColor.YELLOW,
]


class CardType(str, Enum):
    NUMBER = "NUMBER"
    ACTION = "ACTION"
    WILD = "WILD"
    WILD_DRAW_FOUR = "WILD_DRAW_FOUR"


class CardValue(str, Enum):
    ZERO = "0"
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    SKIP = "SKIP"
    REVERSE = "REVERSE"
    DRAW_TWO = "DRAW_TWO"
    WILD = "WILD"
    DRAW_FOUR = "DRAW_FOUR"


NUMBER_VALUES: List[CardValue] = [
    CardValue.ZERO,
    CardValue.ONE,
    CardValue.TWO,
    CardValue.THREE,
    CardValue.FOUR,
    CardValue.FIVE,
    CardValue.SIX,
    CardValue.SEVEN,
    CardValue.EIGHT,
    CardValue.NINE,
]

ACTION_VALUES: List[CardValue] = [
    CardValue.SKIP,
    CardValue.REVERSE,
    CardValue.DRAW_TWO,
]


class Direction(IntEnum):
    CLOCKWISE = 1
    COUNTER_CLOCKWISE = -1

    def invert(self) -> "Direction":
        return Direction.COUNTER_CLOCKWISE if self == Direction.CLOCKWISE else Direction.CLOCKWISE


# Official Scoring Values for end-of-round tallying
CARD_POINT_VALUES = {
    CardValue.ZERO: 0,
    CardValue.ONE: 1,
    CardValue.TWO: 2,
    CardValue.THREE: 3,
    CardValue.FOUR: 4,
    CardValue.FIVE: 5,
    CardValue.SIX: 6,
    CardValue.SEVEN: 7,
    CardValue.EIGHT: 8,
    CardValue.NINE: 9,
    CardValue.SKIP: 20,
    CardValue.REVERSE: 20,
    CardValue.DRAW_TWO: 20,
    CardValue.WILD: 50,
    CardValue.DRAW_FOUR: 50,
}
