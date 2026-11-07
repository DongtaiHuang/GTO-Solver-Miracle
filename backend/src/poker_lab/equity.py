"""Bounded showdown equity over explicit hands/ranges; no strategy or betting solver."""

import math
import random
from bisect import bisect_right
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from typing import Literal

from poker_lab.evaluator import DECK, HandRank, evaluate, validate_cards
from poker_lab.ranges import COMBOS

MAX_SAMPLES = 10000
MAX_EXACT_OUTCOMES = 5000
MAX_RANK_EVALUATIONS = 20000
MAX_PROPOSALS = 200000
MAX_SEARCH_NODES = 50000
CARD_BITS = {card: 1 << index for index, card in enumerate(DECK)}


class WorkLimit(ValueError):
    """The requested deterministic work budget cannot be satisfied."""


@dataclass(frozen=True)
class PlayerInput:
    cards: tuple[str, ...] | None = None
    weights: Mapping[str, int] | None = None


@dataclass(frozen=True)
class Combo:
    cards: tuple[str, ...]
    mask: int
    weight: int


@dataclass(frozen=True)
class Uncertainty:
    standard_error: float
    lower: float
    upper: float
    confidence_level: float = 0.95
    interval_method: str = "hoeffding_95_simultaneous"


@dataclass(frozen=True)
class PlayerEquity:
    win_probability: float
    tie_probability: float
    loss_probability: float
    equity: float
    uncertainty: Uncertainty | None


@dataclass(frozen=True)
class EquityResult:
    method: Literal["exact", "monte_carlo"]
    players: tuple[PlayerEquity, ...]
    evaluated_outcomes: int
    valid_samples: int | None
    proposals: int
    seed: int | None
    unblocked_combinations: tuple[int, ...]
    work_upper_bound: str
    distribution: str
    assumptions: tuple[str, ...]


def mask(cards: Sequence[str]) -> int:
    return sum(CARD_BITS[card] for card in cards)


def expand_range(weights: Mapping[str, int], blocked: Sequence[str] = ()) -> list[Combo]:
    """One class weight applies to each of its individual card combinations."""
    validate_cards(tuple(blocked), len(blocked))
    if not set(weights) <= set(COMBOS):
        raise ValueError("Unknown starting hand class in range")
    if any(type(w) is not int or not 0 <= w <= 100 for w in weights.values()):
        raise ValueError("Range weights must be integer percentages from 0 to 100")
    dead = set(blocked)
    result = [
        Combo(combo, mask(combo), weight)
        for hand in COMBOS
        for weight in [weights.get(hand, 0)]
        if weight
        for combo in COMBOS[hand]
        if not dead.intersection(combo)
    ]
    if not result:
        raise ValueError("Range is empty or impossible after removing known-card blockers")
    return result


def _prepare(
    players: Sequence[PlayerInput], board: tuple[str, ...], dead: tuple[str, ...]
) -> list[list[Combo]]:
    if not 2 <= len(players) <= 6:
        raise ValueError("Equity supports two to six players")
    if len(board) not in (0, 3, 4, 5):
        raise ValueError("Board must contain zero, three, four, or five cards")
    fixed: list[str] = []
    for player in players:
        if (player.cards is None) == (player.weights is None):
            raise ValueError("Each player needs exactly one specific hand or weighted range")
        if player.cards is not None:
            validate_cards(player.cards, 2)
            fixed.extend(player.cards)
    known = list(board + dead) + fixed
    validate_cards(known, len(known))
    if 52 - len(board) - len(dead) - 2 * len(players) < 5 - len(board):
        raise ValueError("Not enough remaining cards to complete the board")
    rows = []
    for player in players:
        if player.cards is not None:
            rows.append([Combo(player.cards, mask(player.cards), 100)])
        else:
            assert player.weights is not None
            rows.append(expand_range(player.weights, known))
    return rows


def _has_assignment(rows: list[list[Combo]]) -> bool:
    ordered = sorted(rows, key=len)
    visited = 0

    def search(index: int, occupied: int) -> bool:
        nonlocal visited
        if index == len(ordered):
            return True
        for combo in ordered[index]:
            visited += 1
            if visited > MAX_SEARCH_NODES:
                raise WorkLimit(
                    "Compatibility search budget exceeded; narrow or simplify the ranges"
                )
            if not occupied & combo.mask and search(index + 1, occupied | combo.mask):
                return True
        return False

    return search(0, 0)


def _assignments(
    rows: list[list[Combo]],
    index: int = 0,
    occupied: int = 0,
    weight: int = 1,
    chosen: tuple[Combo, ...] = (),
) -> Iterator[tuple[tuple[Combo, ...], int]]:
    if index == len(rows):
        yield chosen, weight
    else:
        for combo in rows[index]:
            if not occupied & combo.mask:
                yield from _assignments(
                    rows, index + 1, occupied | combo.mask, weight * combo.weight, (*chosen, combo)
                )


def calculate_equity(
    players: Sequence[PlayerInput],
    *,
    board: tuple[str, ...] = (),
    dead: tuple[str, ...] = (),
    method: str = "auto",
    samples: int = 2000,
    seed: int = 42,
) -> EquityResult:
    """Product of per-combo weights conditioned on disjoint hands; uniform legal runouts."""
    if method not in ("auto", "exact", "monte_carlo"):
        raise ValueError("Unknown equity calculation method")
    if type(samples) is not int or not 100 <= samples <= MAX_SAMPLES:
        raise ValueError(f"Samples must be an integer between 100 and {MAX_SAMPLES}")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed must be an integer between zero and 2^32 - 1")
    rows = _prepare(players, board, dead)
    if not _has_assignment(rows):
        raise ValueError("Ranges have no mutually card-disjoint joint assignment")
    player_count = len(rows)
    unseen_count = 52 - len(board) - len(dead) - 2 * player_count
    runout_count = math.comb(unseen_count, 5 - len(board))
    upper = math.prod(len(row) for row in rows) * runout_count
    exact_limit = min(MAX_EXACT_OUTCOMES, MAX_RANK_EVALUATIONS // player_count)
    use_exact = upper <= exact_limit if method == "auto" else method == "exact"
    if use_exact and upper > exact_limit:
        raise WorkLimit(
            f"Exact enumeration upper bound {upper} exceeds {exact_limit}; use Monte Carlo"
        )
    if not use_exact and samples * player_count > MAX_RANK_EVALUATIONS:
        raise WorkLimit(f"Samples times player count must not exceed {MAX_RANK_EVALUATIONS}")

    @lru_cache(maxsize=4096)
    def rank(hand: tuple[str, ...], river: tuple[str, ...]) -> HandRank:
        return evaluate(hand + river)

    wins = [0.0] * player_count
    ties = [0.0] * player_count
    shares = [0.0] * player_count
    squares = [0.0] * player_count
    total_weight = 0
    evaluated = 0

    def observe(hands: tuple[Combo, ...], runout: tuple[str, ...], weight: int) -> None:
        nonlocal total_weight, evaluated
        river = tuple(sorted(board + runout, key=CARD_BITS.__getitem__))
        ranks = [rank(hand.cards, river) for hand in hands]
        best = max(ranks)
        winners = [i for i, value in enumerate(ranks) if value == best]
        for i in winners:
            reward = 1 / len(winners)
            shares[i] += weight * reward
            squares[i] += weight * reward * reward
            if len(winners) == 1:
                wins[i] += weight
            else:
                ties[i] += weight
        total_weight += weight
        evaluated += 1

    known_mask = mask(board + dead)

    def remaining(hands: tuple[Combo, ...]) -> tuple[str, ...]:
        occupied = known_mask
        for combo in hands:
            occupied |= combo.mask
        return tuple(card for card in DECK if not CARD_BITS[card] & occupied)

    proposals = 0
    if use_exact:
        for hands, weight in _assignments(rows):
            for runout in combinations(remaining(hands), 5 - len(board)):
                observe(hands, runout, weight)
    else:
        rng = random.Random(seed)
        cumulative = []
        for row in rows:
            running = 0
            cdf = []
            for combo in row:
                running += combo.weight
                cdf.append(running)
            cumulative.append(cdf)
        while evaluated < samples:
            proposals += 1
            if proposals > MAX_PROPOSALS:
                raise WorkLimit(
                    "Collision rejection budget exceeded; narrow or simplify the ranges"
                )
            chosen = []
            occupied = 0
            for row, cdf in zip(rows, cumulative):
                combo = row[0] if len(row) == 1 else row[bisect_right(cdf, rng.randrange(cdf[-1]))]
                if occupied & combo.mask:
                    break
                chosen.append(combo)
                occupied |= combo.mask
            if len(chosen) == player_count:
                hands = tuple(chosen)
                observe(hands, tuple(rng.sample(remaining(hands), 5 - len(board))), 1)
    result = []
    for i in range(player_count):
        equity = shares[i] / total_weight
        uncertainty = None
        if not use_exact:
            variance = max(0.0, (squares[i] - shares[i] ** 2 / samples) / (samples - 1))
            # Union-bound Hoeffding intervals for all bounded fractional shares.
            margin = math.sqrt(math.log(2 * player_count / 0.05) / (2 * samples))
            uncertainty = Uncertainty(
                math.sqrt(variance / samples), max(0.0, equity - margin), min(1.0, equity + margin)
            )
        win, tie = wins[i] / total_weight, ties[i] / total_weight
        result.append(PlayerEquity(win, tie, max(0.0, 1 - win - tie), equity, uncertainty))
    return EquityResult(
        method="exact" if use_exact else "monte_carlo",
        players=tuple(result),
        evaluated_outcomes=evaluated,
        valid_samples=None if use_exact else evaluated,
        proposals=proposals,
        seed=None if use_exact else seed,
        unblocked_combinations=tuple(len(row) for row in rows),
        work_upper_bound=str(upper),
        distribution="Product of explicit per-combination weights, conditioned on pairwise card disjointness",
        assumptions=(
            "All players reach one common showdown; no folds or future betting are modeled.",
            "Community runouts are uniform over remaining cards; burns are marginalized out.",
            "Tied winners receive equal fractional pot shares; side pots and rake are excluded.",
            "Probabilities are conditional on the supplied ranges, not their calibration.",
            "Exact means enumeration without sampling uncertainty, using floating-point probabilities.",
        ),
    )


@dataclass(frozen=True)
class PotOddsResult:
    required_equity: float
    call_ev: float
    call_ev_interval: tuple[float, float] | None
    explanation: str


def _probability(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def pot_odds(
    pot: int, call: int, equity: float, equity_interval: tuple[float, float] | None = None
) -> PotOddsResult:
    if any(type(value) is not int or not 0 <= value <= 100000000 for value in (pot, call)):
        raise ValueError("Pot and call must be nonnegative integer chips, at most 100000000 each")
    if pot + call == 0:
        raise ValueError("Pot plus call must be greater than zero")
    if not _probability(equity):
        raise ValueError("Equity must be a finite probability between zero and one")
    interval = None
    if equity_interval is not None:
        low, high = equity_interval
        if not _probability(low) or not _probability(high) or not low <= equity <= high:
            raise ValueError("Equity interval must contain the equity and lie between zero and one")
        interval = (low * (pot + call) - call, high * (pot + call) - call)
    return PotOddsResult(
        call / (pot + call),
        equity * (pot + call) - call,
        interval,
        "Pot includes the opponent bet, before hero calls. Assumes full showdown realization, "
        "no future betting, no rake, no additional contributions, and no separate side pots. "
        "This is a simplified call-EV calculation, not a postflop action solver or GTO recommendation.",
    )
