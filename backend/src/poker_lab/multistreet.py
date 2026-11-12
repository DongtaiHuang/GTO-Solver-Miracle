"""Bounded best responses to fixed, public-history/own-combo policies."""

import gzip
import hashlib
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
from typing import Literal, TypedDict, cast

from pydantic import Field

from poker_lab.profiles import ProfileId
from poker_lab.strategy_catalog import SolutionCatalog
from poker_lab.strategy_models import Identifier, Probability, StrategyScenario, StrictModel

VERSION = "ts009-average-1500-v1"
DIGEST = "45e43ff1f75f8b293c5f6ff6d9af219e797e79b77b44f09bba6a4e7348b5f014"
Matrix = list[list[float]]
Policy = dict[str, Matrix]
Seat = Literal["BTN", "BB"]
HYPOTHESES = {ProfileId.TAG: 0.4, ProfileId.LAG: 0.75, ProfileId.TP: 0.15, ProfileId.LP: 0.25}


class Node(TypedDict, total=False):
    seat: int
    chance: list[str]
    payoff: Matrix
    river: int | None
    invested: int
    actions: list[str]
    children: list[str]
    policy: Matrix


class Reference(TypedDict):
    version: str
    nodes: dict[str, Node]
    hands: list[list[str]]
    joint: Matrix
    river_joint: list[Matrix]
    cards: list[str]
    documents: dict[str, list[str]]
    value: float
    best: list[float]


@lru_cache(maxsize=1)
def reference() -> Reference:
    try:
        with (
            files("poker_lab").joinpath("data/turn_reference_v1.json.gz").open("rb") as f,
            gzip.GzipFile(fileobj=f) as z,
        ):
            raw = z.read(1024**2)
    except (OSError, EOFError) as exc:
        raise ValueError("Full equilibrium policy unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise ValueError("Incompatible full equilibrium policy")
    return cast(Reference, json.loads(raw))


class Context(StrictModel):
    solution_id: Identifier
    scenario: StrategyScenario
    reference_version: Literal["ts009-average-1500-v1"]
    opponent: Seat


class Override(StrictModel):
    node: str = Field(min_length=1, max_length=128)
    combo: str = Field(min_length=4, max_length=4)
    probabilities: dict[str, Probability] = Field(min_length=2, max_length=2)


class Hypothesis(StrictModel):
    name: str = Field(min_length=1, max_length=60)
    profile: ProfileId
    opening_bet: Probability | None = None
    overrides: list[Override] = Field(default_factory=list, max_length=32)


class Request(Context):
    hypotheses: list[Hypothesis] = Field(min_length=1, max_length=3)


class Row(StrictModel):
    node: str
    combo: str
    equilibrium: dict[str, float]
    modeled: dict[str, float]


class Root(StrictModel):
    equilibrium_ev: float
    baseline_model_ev: float
    response_model_ev: float
    gain: float
    response_equilibrium_ev: float
    equilibrium_cost: float


class Choice(StrictModel):
    reach: float
    frequencies: dict[str, float]
    action_ev: dict[str, float]
    ev: float


class Decision(StrictModel):
    combo: str
    baseline_model: Choice | None
    response_model: Choice | None
    baseline_equilibrium: Choice | None
    response_equilibrium: Choice | None
    gain: float | None
    equilibrium_cost: float | None


class Result(StrictModel):
    name: str
    profile: ProfileId
    changes: list[Row]
    root: Root
    decisions: list[Decision]


class Analysis(StrictModel):
    reference_version: str
    solution_id: str
    opponent: Seat
    assumptions: str
    results: list[Result]


def match(ctx: Context, catalog: SolutionCatalog) -> tuple[Reference, str, int]:
    ref = reference()
    identity = ref["documents"].get(ctx.solution_id)
    entry = catalog.source(ctx.solution_id, "validated_gto")
    if (
        not identity
        or not entry
        or entry.document.content_hash != identity[1]
        or entry.document.scenario.scenario_id != ctx.scenario.scenario_id
    ):
        raise ValueError("No exact reviewed multistreet policy for this solution and scenario")
    n = ref["nodes"][identity[0]]
    if ctx.opponent == ctx.scenario.hero_position:
        raise ValueError("Opponent seat conflicts with acting hero")
    return ref, identity[0], n["seat"]


def mass(ref: Reference, n: Node) -> Matrix:
    r = n["river"]
    return ref["joint"] if r is None else ref["river_joint"][r]


def possible(ref: Reference, n: Node, i: int) -> bool:
    chance = mass(ref, n)
    return any(chance[i]) if n["seat"] == 0 else any(row[i] for row in chance)


def row_dict(n: Node, values: list[float]) -> dict[str, float]:
    return dict(zip(n["actions"], values, strict=True))


def policy_rows(ctx: Context, catalog: SolutionCatalog) -> dict[str, dict[str, dict[str, float]]]:
    ref, _, hero = match(ctx, catalog)
    return {
        key: {
            h: row_dict(n, n["policy"][i])
            for i, h in enumerate(ref["hands"][1 - hero])
            if possible(ref, n, i)
        }
        for key, n in ref["nodes"].items()
        if n.get("seat") == 1 - hero
    }


def modeled(ref: Reference, hero: int, h: Hypothesis) -> tuple[Policy, list[Row]]:
    if h.profile == ProfileId.STANDARD_GTO and (h.overrides or h.opening_bet is not None):
        raise ValueError("Equilibrium benchmark cannot contain overrides")
    rows: dict[tuple[str, str], dict[str, float]] = {}
    opp = 1 - hero
    if h.profile != ProfileId.STANDARD_GTO:
        bet = h.opening_bet if h.opening_bet is not None else HYPOTHESES[h.profile]
        key = "turn" if opp == 1 else "turn/check"
        rows.update({(key, hand): {"check": 1 - bet, "bet@275": bet} for hand in ref["hands"][opp]})
    seen = set()
    for record in h.overrides:
        loc = (record.node, record.combo)
        if loc in seen:
            raise ValueError("Repeated policy override")
        seen.add(loc)
        rows[loc] = record.probabilities
    changed: Policy = {}
    audit = []
    for (key, combo), probs in rows.items():
        n = ref["nodes"].get(key)
        if not n or n.get("seat") != opp or combo not in ref["hands"][opp]:
            raise ValueError("Override must identify an opponent information set")
        i = ref["hands"][opp].index(combo)
        if (
            not possible(ref, n, i)
            or set(probs) != set(n["actions"])
            or abs(sum(probs.values()) - 1) > 1e-12
        ):
            raise ValueError("Blocked combo, illegal action or invalid probability total")
        if key not in changed:
            changed[key] = list(n["policy"])
        changed[key][i] = [probs[a] for a in n["actions"]]
        eq = row_dict(n, n["policy"][i])
        if eq != probs:
            audit.append(Row(node=key, combo=combo, equilibrium=eq, modeled=probs))
    return changed, audit


@dataclass
class Evaluation:
    value: float = 0.0
    decisions: list[Choice | None] = field(default_factory=list)
    strategy: Policy = field(default_factory=dict)


def evaluate(
    ref: Reference,
    hero: int,
    target: str,
    opponent: Policy,
    hero_policy: Policy,
    *,
    optimize: bool = False,
) -> Evaluation:
    """Return counterfactual chip values per hero combo, then recover joint reach at target."""
    result = Evaluation()
    conditionals: list[Choice | None] = []
    count = len(ref["hands"][hero])

    def visit(key: str, opp: list[float]) -> list[float]:
        n = ref["nodes"][key]
        if "payoff" in n:
            chance = mass(ref, n)
            if hero == 0:
                return [
                    sum(q * u * w for q, u, w in zip(qs, us, opp, strict=True))
                    for qs, us in zip(chance, n["payoff"], strict=True)
                ]
            return [
                sum(chance[i][j] * (550 - n["payoff"][i][j]) * w for i, w in enumerate(opp))
                for j in range(count)
            ]
        if "chance" in n:
            # River masses already include P(card | private deal).
            return [sum(col) for col in zip(*(visit(c, opp) for c in n["chance"]), strict=True)]
        if n["seat"] != hero:
            model = opponent.get(key, n["policy"])
            branches = [
                visit(child, [w * row[k] for w, row in zip(opp, model, strict=True)])
                for k, child in enumerate(n["children"])
            ]
            return [a + b for a, b in zip(*branches, strict=True)]
        branches = [visit(c, opp) for c in n["children"]]
        policy = hero_policy.get(key, n["policy"])
        chosen = []
        values = []
        for i, (a, b) in enumerate(zip(*branches, strict=True)):
            row = policy[i]
            if optimize and a != b:
                row = [1.0, 0.0] if a > b else [0.0, 1.0]
            chosen.append(row)
            v = row[0] * a + row[1] * b
            values.append(v)
            if key == target:
                chance = mass(ref, n)
                weights = chance[i] if hero == 0 else [q[i] for q in chance]
                m = math.sumprod(weights, opp)
                offset = n["invested"]
                conditionals.append(
                    Choice(
                        reach=m,
                        frequencies=row_dict(n, row),
                        action_ev=row_dict(n, [a / m + offset, b / m + offset]),
                        ev=v / m + offset,
                    )
                    if m
                    else None
                )
        if optimize:
            result.strategy[key] = chosen
        return values

    result.value = sum(visit("turn", [1.0] * len(ref["hands"][1 - hero])))
    own = [1.0] * count
    prefix = "turn"
    for token in target.split("/")[1:]:
        node = ref["nodes"][prefix]
        if node.get("seat") == hero:
            matrix = result.strategy.get(prefix, hero_policy.get(prefix, node["policy"]))
            k = node["actions"].index(token)
            own = [w * row[k] for w, row in zip(own, matrix, strict=True)]
        prefix += "/" + token
    for choice, w in zip(conditionals, own, strict=True):
        if choice is not None:
            choice.reach *= w
        result.decisions.append(choice if choice and choice.reach > 0 else None)
    return result


def analyze(body: Request, catalog: SolutionCatalog) -> Analysis:
    ref, key, hero = match(body, catalog)
    baseline = evaluate(ref, hero, key, {}, {})
    results = []
    for hypothesis in body.hypotheses:
        policy, changes = modeled(ref, hero, hypothesis)
        base_model = evaluate(ref, hero, key, policy, {})
        response = evaluate(ref, hero, key, policy, {}, optimize=True)
        cost = evaluate(ref, hero, key, {}, response.strategy)
        root = Root(
            equilibrium_ev=baseline.value,
            baseline_model_ev=base_model.value,
            response_model_ev=response.value,
            gain=response.value - base_model.value,
            response_equilibrium_ev=cost.value,
            equilibrium_cost=baseline.value - cost.value,
        )
        decisions = [
            Decision(
                combo=combo,
                baseline_model=b,
                response_model=r,
                baseline_equilibrium=e,
                response_equilibrium=c,
                gain=r.ev - b.ev if r and b else None,
                equilibrium_cost=e.ev - c.ev if e and c else None,
            )
            for combo, b, r, e, c in zip(
                ref["hands"][hero],
                base_model.decisions,
                response.decisions,
                baseline.decisions,
                cost.decisions,
                strict=True,
            )
        ]
        results.append(
            Result(
                name=hypothesis.name,
                profile=hypothesis.profile,
                changes=changes,
                root=root,
                decisions=decisions,
            )
        )
    return Analysis(
        reference_version=VERSION,
        solution_id=body.solution_id,
        opponent=body.opponent,
        results=results,
        assumptions="User-selected modeling hypotheses. Every unedited row inherits the full Task 009 equilibrium policy. Root values include all compatible deals and all legal river runouts.",
    )
