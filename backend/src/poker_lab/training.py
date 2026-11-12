"""Grade conditional chip utilities from exact, reviewed decision records."""

from collections import defaultdict
from math import fsum, isfinite
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictBool

from poker_lab import multistreet
from poker_lab.strategy_catalog import SolutionCatalog
from poker_lab.strategy_models import Identifier, StrictModel

EPS = 1e-8


class Exercise(StrictModel):
    solution_id: Identifier
    scenario_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    version: str = Field(pattern=r"^[0-9a-f]{64}$")
    combo: str = Field(pattern=r"^(?:[2-9TJQKA][cdhs]){2}$")


class Prompt(Exercise):
    position: str
    street: str
    board: list[str]
    pot: int
    blind: int
    actions: list[str]
    history: list[str]
    assumptions: list[str]
    solver: str
    accuracy: str


def exercises(catalog: SolutionCatalog) -> list[Prompt]:
    prompts = []
    for entry in catalog.visible("validated_gto"):
        doc = entry.document
        s = doc.scenario
        version, identity = doc.content_hash, s.scenario_id
        for row in doc.combinations:
            if row.reach_weight > 0 and row.action_ev:
                prompts.append(
                    Prompt(
                        solution_id=doc.solution_id,
                        scenario_id=identity,
                        version=version,
                        combo="".join(row.cards),
                        position=s.hero_position,
                        street=s.street,
                        board=s.board,
                        pot=s.pot,
                        blind=s.big_blind,
                        actions=[a.key for a in s.legal_actions],
                        history=[f"{a.street} {a.position} {a.key}" for a in s.history],
                        solver=f"{doc.solver_identifier} {doc.solver_version}",
                        assumptions=s.abstraction.assumptions,
                        accuracy=doc.validation.methodology,
                    )
                )
    return prompts


class Submission(Exercise):
    action: str = Field(min_length=1, max_length=32)
    hypothesis: multistreet.Hypothesis | None = None


class Feedback(StrictModel):
    status: Literal["graded", "ungraded"] = "ungraded"
    reason: str
    frequencies: dict[str, float] | None = None
    action_ev: dict[str, float] | None = None
    best: list[str] = Field(default_factory=list)
    loss: float | None = None
    loss_bb: float | None = None
    response: dict[str, float] | None = None
    model_gain: float | None = None
    equilibrium_cost: float | None = None


def compare(
    actions: set[str],
    values: dict[str, float] | None,
    chosen: str,
    frequencies: dict[str, float],
    blind: int,
) -> Feedback:
    if not values or set(values) != actions or not all(map(isfinite, values.values())):
        return Feedback(reason="Incomplete conditional action EVs")
    if chosen not in actions:
        return Feedback(reason="Selected sizing or action outside the validated tree")
    highest = max(values.values())
    loss = highest - values[chosen]
    loss = 0.0 if loss <= EPS else loss
    return Feedback(
        status="graded",
        reason="Conditional acting-player EV in this restricted tree",
        frequencies=frequencies,
        action_ev=values,
        loss=loss,
        loss_bb=loss / blind,
        best=[key for key in values if highest - values[key] <= EPS],
    )


def grade(catalog: SolutionCatalog, req: Submission) -> Feedback:
    entry = catalog.source(req.solution_id, "validated_gto")
    if not entry or entry.document.content_hash != req.version:
        return Feedback(reason="Reviewed solution version unavailable")
    doc = entry.document
    s = doc.scenario
    if s.scenario_id != req.scenario_id:
        return Feedback(reason="Public scenario mismatch")
    row = next((c for c in doc.combinations if "".join(c.cards) == req.combo), None)
    if row is None or row.reach_weight <= 0:
        return Feedback(reason="Combination outside reached solution coverage")
    if req.hypothesis is None:
        return compare(
            {a.key for a in s.legal_actions},
            row.action_ev,
            req.action,
            row.frequencies,
            s.big_blind,
        )
    if s.opponent_position not in ("BTN", "BB"):
        return Feedback(reason="Unsupported opponent position")
    try:
        model = multistreet.analyze(
            multistreet.Request(
                solution_id=req.solution_id,
                scenario=s,
                opponent=s.opponent_position,
                reference_version="ts009-average-1500-v1",
                hypotheses=[req.hypothesis],
            ),
            catalog,
        )
    except ValueError as exc:
        return Feedback(reason=str(exc))
    decision = next((d for d in model.results[0].decisions if d.combo == req.combo), None)
    if not decision or not decision.response_model:
        return Feedback(reason="Zero response reach under the selected hypothesis")
    choice = decision.response_model
    feedback = compare(
        set(choice.frequencies), choice.action_ev, req.action, row.frequencies, s.big_blind
    )
    feedback.response = choice.frequencies
    feedback.model_gain = decision.gain
    feedback.equilibrium_cost = decision.equilibrium_cost
    return feedback


class Attempt(StrictModel):
    id: UUID
    session: UUID
    retry: StrictBool
    origin: Literal["practice", "review"]
    time: AwareDatetime
    submission: Submission
    feedback: Feedback
    street: str = Field(max_length=12)
    position: str = Field(max_length=4)


class Archive(StrictModel):
    version: Literal["1"]
    attempts: list[Attempt] = Field(max_length=64)


class Metric(StrictModel):
    count: int
    graded: int
    total_bb: float | None
    average_bb: float | None


class VerifiedArchive(StrictModel):
    archive: Archive
    report: dict[str, Metric]


def summarize(archive: Archive) -> dict[str, Metric]:
    groups: dict[str, list[float | None]] = defaultdict(list)
    ids = set()
    for a in sorted(archive.attempts, key=lambda a: (a.time, str(a.id))):
        if a.id in ids:
            raise ValueError("Duplicate attempt ID")
        ids.add(a.id)
        r = a.submission
        mode = "Model" if r.hypothesis else "GTO"
        for key in (
            mode,
            f"{mode} · {a.street}",
            f"{mode} · {a.position}",
            f"{mode} · {r.solution_id}",
            f"{mode} · session {a.session}",
            f"{mode} · {'retry' if a.retry else 'first attempt'}",
        ):
            groups[key].append(a.feedback.loss_bb)
        if a.feedback.loss_bb is not None and a.feedback.loss_bb > 0:
            groups[f"{mode} · weakness {r.solution_id} {r.combo}"].append(a.feedback.loss_bb)
    result = {}
    for name, group in groups.items():
        losses = [loss for loss in group if loss is not None]
        result[name] = Metric(
            count=len(group),
            graded=len(losses),
            total_bb=fsum(losses) if losses else None,
            average_bb=fsum(losses) / len(losses) if losses else None,
        )
    return result
