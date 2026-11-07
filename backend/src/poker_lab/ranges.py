"""169 hand classes, exact card combinations, and explicitly modeled range weights."""

from itertools import combinations
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from poker_lab.evaluator import DECK, RANKS
from poker_lab.profiles import OpponentProfile

ORDER = "AKQJT98765432"
MATRIX = tuple(
    tuple(a + b if i == j else a + b + "s" if i < j else b + a + "o" for j, b in enumerate(ORDER))
    for i, a in enumerate(ORDER)
)
CLASSES = tuple(hand for row in MATRIX for hand in row)


def hand_class(first: str, second: str) -> str:
    a, b = sorted((first, second), key=lambda c: RANKS.index(c[0]), reverse=True)
    return a[0] + b[0] + ("" if a[0] == b[0] else "s" if a[1] == b[1] else "o")


COMBOS: dict[str, list[tuple[str, str]]] = {hand: [] for hand in CLASSES}
for _first, _second in combinations(DECK, 2):
    COMBOS[hand_class(_first, _second)].append((_first, _second))

Weight = Annotated[int, Field(strict=True, ge=0, le=100)]


class HandRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weights: dict[str, Weight] = Field(default_factory=dict)

    @field_validator("weights")
    @classmethod
    def valid_classes(cls, weights: dict[str, int]) -> dict[str, int]:
        if not set(weights) <= set(CLASSES):
            raise ValueError("Range contains an unknown starting hand class")
        return weights


class RangeSummary(BaseModel):
    weights: dict[str, int]
    weighted_combos: float
    available_weighted_combos: float
    source: str


def summarize(hand_range: HandRange, dead: list[str], source: str) -> RangeSummary:
    blocked = set(dead)
    weighted = sum(len(COMBOS[hand]) * weight / 100 for hand, weight in hand_range.weights.items())
    available = sum(
        sum(not blocked.intersection(combo) for combo in COMBOS[hand]) * weight / 100
        for hand, weight in hand_range.weights.items()
    )
    return RangeSummary(
        weights=hand_range.weights,
        weighted_combos=round(weighted, 2),
        available_weighted_combos=round(available, 2),
        source=source,
    )


def modeled_range(profile: OpponentProfile) -> HandRange:
    if profile.parameters is None:
        return HandRange()
    p = profile.parameters

    def score(hand: str) -> tuple[float, str]:
        high, low = (RANKS.index(c) + 2 for c in hand[:2])
        value: float = high * 3 + 18 if high == low else high * 2 + low
        if hand.endswith("s"):
            value += 3 + p.bluffing_tendency / 25
        value += max(0, 4 - abs(high - low)) if high != low else 0
        return value, hand

    remaining = 1326 * p.vpip / 100
    weights = {}
    for hand in sorted(CLASSES, key=score, reverse=True):
        count = len(COMBOS[hand])
        weight = min(100, max(0, round(remaining / count * 100)))
        if weight:
            weights[hand] = weight
        remaining = max(0, remaining - count)
    return HandRange(weights=weights)
