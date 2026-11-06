"""Exact best-five-of-seven evaluation. Larger tuples are stronger hands."""

from collections import Counter
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK = tuple(rank + suit for suit in SUITS for rank in RANKS)
HandRank = tuple[int, ...]


def validate_cards(cards: list[str] | tuple[str, ...], count: int) -> None:
    if len(cards) != count or len(set(cards)) != count or any(c not in DECK for c in cards):
        raise ValueError(f"Expected {count} distinct valid cards")


def _five(cards: tuple[str, ...]) -> HandRank:
    values = sorted((RANKS.index(c[0]) + 2 for c in cards), reverse=True)
    counts = Counter(values)
    groups = sorted(((count, value) for value, count in counts.items()), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    unique = sorted(counts, reverse=True)
    straight = 0
    if len(unique) == 5:
        if unique[0] - unique[4] == 4:
            straight = unique[0]
        elif unique == [14, 5, 4, 3, 2]:
            straight = 5
    if flush and straight:
        return (8, straight)
    if groups[0][0] == 4:
        return (7, groups[0][1], groups[1][1])
    if [g[0] for g in groups] == [3, 2]:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *values)
    if straight:
        return (4, straight)
    if groups[0][0] == 3:
        return (3, groups[0][1], *sorted((v for v in values if counts[v] == 1), reverse=True))
    pairs = sorted((v for v in counts if counts[v] == 2), reverse=True)
    if len(pairs) == 2:
        return (2, *pairs, next(v for v in values if counts[v] == 1))
    if pairs:
        return (1, pairs[0], *[v for v in values if counts[v] == 1])
    return (0, *values)


def evaluate(cards: list[str] | tuple[str, ...]) -> HandRank:
    validate_cards(cards, 7)
    return max(_five(hand) for hand in combinations(cards, 5))
