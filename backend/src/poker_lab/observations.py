"""Replay-derived public action evidence and small-sample player statistics."""

import hashlib
import json
import math
from functools import lru_cache
from typing import Annotated, Literal, cast

from pydantic import Field

from poker_lab.analyzer import Hand, from_trainer, replay
from poker_lab.models import Action
from poker_lab.schemas import GameView
from poker_lab.strategy_models import Position, StrictModel

Id = Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")]
Label = Literal["tag", "lag", "tp", "lp"]
Source = Literal["trainer", "manual"]
METRICS = (
    "vpip",
    "pfr",
    "three_bet",
    "fold_to_three_bet",
    "flop_cbet",
    "fold_to_flop_cbet",
    "turn_aggression",
    "river_aggression",
    "postflop_call",
    "postflop_fold",
)


class Entry(StrictModel):
    hand_id: Id
    source: Source
    mapping: dict[Position, Id] = Field(min_length=1, max_length=6)
    hand: Hand


class Archive(StrictModel):
    version: Literal["1.0"]
    entries: list[Entry] = Field(max_length=128)
    overrides: dict[Id, Label] = Field(default_factory=dict, max_length=128)


class GameWithObservation(GameView):
    observation: Entry | None = None


def public_hand(hand: Hand) -> Hand:
    return hand.model_copy(
        update={
            "seats": {p: s.model_copy(update={"cards": None}) for p, s in hand.seats.items()},
            "payouts": None,
        }
    )


def trainer_game(game: GameView) -> GameWithObservation:
    entry = None
    if game.street == "complete":
        hand = public_hand(from_trainer(game))
        mapping = {
            cast(Position, p.position): f"bot-{p.seat}" if p.seat != game.hero else "trainer-hero"
            for p in game.players
        }
        entry = Entry(hand_id=game.hand_id, source="trainer", mapping=mapping, hand=hand)
    return GameWithObservation(**game.model_dump(), observation=entry)


def opportunities(hand: Hand) -> dict[Position, dict[str, list[bool]]]:
    states = replay(hand, [])
    facts: dict[Position, dict[str, list[bool]]] = {p: {k: [] for k in METRICS} for p in hand.seats}
    vpip = set()
    pfr = set()
    raises = 0
    aggressor = None
    opener = None
    three_pending = False
    flop_open = True
    facing_cbet = False
    for snapshot, event in zip(states, hand.actions, strict=False):
        p, a, street = event.position, event.action, event.street
        row = facts[p]
        passive_target = snapshot.players[p].bet + snapshot.legal.to_call
        aggressive = a in (Action.BET, Action.RAISE) or (
            a == Action.ALL_IN and (event.amount or 0) > passive_target
        )
        call = a == Action.CALL or (
            a == Action.ALL_IN and not aggressive and snapshot.legal.to_call > 0
        )
        full = (
            aggressive
            and snapshot.legal.min_raise_to is not None
            and (event.amount or 0) >= snapshot.legal.min_raise_to
        )
        if street == "preflop":
            if (
                raises == 1
                and snapshot.legal.min_raise_to is not None
                and Action.RAISE in snapshot.legal.actions
            ):
                row["three_bet"].append(full)
            if three_pending and p == opener:
                row["fold_to_three_bet"].append(a == Action.FOLD)
                three_pending = False
            if call or aggressive:
                vpip.add(p)
            if aggressive:
                pfr.add(p)
                if raises == 0:
                    opener = p
                three_pending = raises == 1 and full
                raises += 1
                aggressor = p
            continue
        if snapshot.legal.to_call:
            row["postflop_call"].append(call)
            row["postflop_fold"].append(a == Action.FOLD)
        may_aggress = bool({Action.RAISE, Action.BET}.intersection(snapshot.legal.actions)) or (
            Action.ALL_IN in snapshot.legal.actions and snapshot.legal.max_raise_to > passive_target
        )
        if street in ("turn", "river") and may_aggress:
            row[street + "_aggression"].append(aggressive)
        if street == "flop":
            can_bet = Action.BET in snapshot.legal.actions or (
                Action.ALL_IN in snapshot.legal.actions and not snapshot.legal.to_call
            )
            if facing_cbet:
                row["fold_to_flop_cbet"].append(a == Action.FOLD)
            if flop_open and p == aggressor and can_bet:
                row["flop_cbet"].append(aggressive)
                facing_cbet = aggressive
            elif aggressive:
                facing_cbet = False
            if aggressive:
                flop_open = False
    for p, player in states[-1].players.items():
        if states[-1].street != "preflop" or player.status in ("folded", "all-in"):
            facts[p]["vpip"].append(p in vpip)
            facts[p]["pfr"].append(p in pfr)
    return facts


def beta_cdf(x: float, a: int, b: int) -> float:
    # Integer-shape beta CDF equals the upper binomial tail starting at a.
    if x > a / (a + b):
        return 1 - beta_tail(1 - x, b, a)
    return beta_tail(x, a, b)


def beta_tail(x: float, a: int, b: int) -> float:
    n = a + b - 1
    term = math.exp(
        math.lgamma(n + 1)
        - math.lgamma(a + 1)
        - math.lgamma(b)
        + a * math.log(x)
        + (b - 1) * math.log1p(-x)
    )
    total = term
    for k in range(a, n):
        term *= ((n - k) / (k + 1)) * (x / (1 - x))
        total += term
        if term <= total * 1e-15:
            break
    return total


@lru_cache(maxsize=4096)
def interval(s: int, n: int) -> tuple[float, float]:
    def quantile(target: float) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if beta_cdf(mid, s + 1, n - s + 1) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    return quantile(0.025), quantile(0.975)


class Metric(StrictModel):
    successes: int
    opportunities: int
    observed: float | None
    estimate: float | None
    interval: tuple[float, float] | None
    sufficient: bool


def metric(s: int, n: int) -> Metric:
    return Metric(
        successes=s,
        opportunities=n,
        observed=s / n if n else None,
        estimate=(s + 1) / (n + 2) if n else None,
        interval=interval(s, n) if n else None,
        sufficient=n >= 20,
    )


class Rules(StrictModel):
    minimum_hands: int = Field(default=20, ge=1, le=128, strict=True)
    loose_threshold: float = Field(default=0.30, gt=0, lt=1)
    aggressive_threshold: float = Field(default=0.60, gt=0, lt=1)


def classify(metrics: dict[str, Metric], rules: Rules) -> tuple[Label | None, str]:
    v, r = metrics["vpip"], metrics["pfr"]
    if v.opportunities < rules.minimum_hands or v.successes < 5:
        return (
            None,
            f"Need {rules.minimum_hands} resolved preflops and 5 voluntary hands; observed {v.opportunities} and {v.successes}.",
        )
    loose = (v.estimate or 0) >= rules.loose_threshold
    participation = (r.successes + 1) / (v.successes + 2)
    aggressive = participation >= rules.aggressive_threshold
    label: Label = ("lag" if aggressive else "lp") if loose else ("tag" if aggressive else "tp")
    return (
        label,
        f"VPIP estimate {v.estimate:.1%} (loose at {rules.loose_threshold:.0%}); raise participation estimate {participation:.1%} (aggressive at {rules.aggressive_threshold:.0%}).",
    )


class Evidence(StrictModel):
    hand_id: str
    position: Position
    stack: int
    actions: list[str]
    counts: dict[str, tuple[int, int]]


class PlayerReport(StrictModel):
    id: str
    name: str
    source: Source
    hands: int
    metrics: dict[str, Metric]
    provisional: Label | None
    override: Label | None
    evidence: str
    history: list[Evidence]


class SummaryRequest(StrictModel):
    archive: Archive
    rules: Rules = Field(default_factory=Rules)


def report(request: SummaryRequest) -> list[PlayerReport]:
    archive = request.archive
    seen = set()
    fingerprints: dict[str, Source] = {}
    history: dict[str, list[Evidence]] = {}
    names: dict[str, tuple[str, Source]] = {}
    if sum(len(e.hand.actions) for e in archive.entries) > 4096:
        raise ValueError("Limit is 4096 recorded actions")
    for e in archive.entries:
        if e.hand_id in seen:
            raise ValueError("Duplicate hand ID")
        seen.add(e.hand_id)
        if e.hand.trainer_hand_id and (
            e.source != "trainer" or e.hand.trainer_hand_id != e.hand_id
        ):
            raise ValueError("Trainer provenance conflicts with entry")
        for identity in e.mapping.values():
            reserved = identity in {"trainer-hero", *(f"bot-{i}" for i in range(1, 6))}
            if reserved != (e.source == "trainer"):
                raise ValueError("Identity namespace conflicts with source")
        if any(s.cards is not None for s in e.hand.seats.values()) or e.hand.payouts is not None:
            raise ValueError("Observation archives must omit private cards and payouts")
        if len(set(e.mapping.values())) != len(e.mapping):
            raise ValueError("Each mapped seat needs a distinct identity")
        data = e.hand.model_dump(mode="json", exclude={"initial_pot", "hero", "trainer_hand_id"})
        for seat in data["seats"].values():
            seat.pop("name")
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        if digest in fingerprints and (e.source == "manual" or fingerprints[digest] != e.source):
            raise ValueError("Duplicate recorded hand content")
        fingerprints[digest] = e.source
        facts = opportunities(e.hand)
        for p, identity in e.mapping.items():
            if identity in names and names[identity][1] != e.source:
                raise ValueError("Identity source mismatch")
            names[identity] = (e.hand.seats[p].name, e.source)
            history.setdefault(identity, []).append(
                Evidence(
                    hand_id=e.hand_id,
                    position=p,
                    stack=e.hand.seats[p].stack,
                    actions=[
                        f"{a.street} {a.action.value}"
                        + (f" {a.amount}" if a.amount is not None else "")
                        for a in e.hand.actions
                        if a.position == p
                    ],
                    counts={k: (sum(v), len(v)) for k, v in facts[p].items() if v},
                )
            )
    if set(archive.overrides) - names.keys():
        raise ValueError("Override references unknown player")
    result = []
    for identity, rows in history.items():
        metrics = {
            k: metric(
                sum(r.counts.get(k, (0, 0))[0] for r in rows),
                sum(r.counts.get(k, (0, 0))[1] for r in rows),
            )
            for k in METRICS
        }
        label, reason = classify(metrics, request.rules)
        name, source = names[identity]
        result.append(
            PlayerReport(
                id=identity,
                name=name,
                source=source,
                hands=len(rows),
                metrics=metrics,
                provisional=label,
                override=archive.overrides.get(identity),
                evidence=reason,
                history=rows,
            )
        )
    return result
