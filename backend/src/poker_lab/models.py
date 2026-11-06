from dataclasses import dataclass, field
from enum import StrEnum


class Street(StrEnum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    COMPLETE = "complete"


class Action(StrEnum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class Player:
    seat: int
    stack: int
    hole: list[str] = field(default_factory=list)
    folded: bool = False
    street_bet: int = 0
    contributed: int = 0

    @property
    def can_act(self) -> bool:
        return not self.folded and self.stack > 0


@dataclass(frozen=True)
class LegalActions:
    actions: tuple[Action, ...]
    to_call: int
    min_raise_to: int | None
    max_raise_to: int


@dataclass(frozen=True)
class Pot:
    amount: int
    eligible: tuple[int, ...]


@dataclass(frozen=True)
class Award:
    pot: Pot
    winners: tuple[int, ...]
    payouts: tuple[tuple[int, int], ...]
