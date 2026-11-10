"""Exact lookup and reach-weighted aggregation, independent of HTTP and frontend code."""

from typing import Literal

from poker_lab.ranges import CLASSES, COMBOS, hand_class
from poker_lab.strategy_catalog import SolutionCatalog
from poker_lab.strategy_models import (
    Identifier,
    ImportedSolution,
    StrategyScenario,
    StrictModel,
)

Mode = Literal["validated_gto", "synthetic_demo"]


class StrategyQuery(StrictModel):
    scenario: StrategyScenario
    mode: Mode = "validated_gto"


class ActionView(StrictModel):
    key: str
    action: str
    amount: int | None


class ComboView(StrictModel):
    cards: tuple[str, str]
    hand_class: str
    reach_weight: float
    frequencies: dict[str, float]
    action_ev: dict[str, float] | None


class ClassStrategy(StrictModel):
    hand_class: str
    represented_combos: int
    unblocked_combos: int
    reach_mass: float
    frequencies: dict[str, float]
    action_ev: dict[str, float] | None


class SourceView(StrictModel):
    solution_id: str
    kind: str
    solver_identifier: str
    solver_version: str
    source_name: str
    source_url: str
    license_name: str
    license_url: str
    redistribution: str
    validation_status: str
    validation_methodology: str
    limitations: list[str]
    checked_at: str
    imported_at: str
    approval_status: str
    mathematical_verification: str


class QueryResult(StrictModel):
    scenario_id: str
    status: Literal["available", "synthetic_demo", "unavailable"]
    is_gto_recommendation: bool
    message: str
    scenario: StrategyScenario
    actions: list[ActionView]
    source: SourceView | None
    combinations: list[ComboView]
    classes: list[ClassStrategy]
    frequencies: dict[str, float] | None
    action_ev: dict[str, float] | None
    represented_combos: int
    unblocked_combos: int
    aggregation_method: str


class SourceRequest(StrictModel):
    solution_id: Identifier
    mode: Mode = "validated_gto"


class ScenarioSummary(StrictModel):
    solution_id: str
    scenario_id: str
    kind: str
    scenario: StrategyScenario
    label: str


class ScenarioIndex(StrictModel):
    scenarios: list[ScenarioSummary]
    message: str


def source_view(entry: ImportedSolution) -> SourceView:
    s = entry.document
    return SourceView(
        solution_id=s.solution_id,
        kind=s.kind,
        solver_identifier=s.solver_identifier,
        solver_version=s.solver_version,
        source_name=s.provenance.source_name,
        source_url=s.provenance.source_url,
        license_name=s.provenance.license_name,
        license_url=s.provenance.license_url,
        redistribution=s.provenance.redistribution,
        validation_status=s.validation.status,
        validation_methodology=s.validation.methodology,
        limitations=s.validation.limitations,
        checked_at=s.validation.checked_at.isoformat(),
        imported_at=entry.imported_at.isoformat(),
        approval_status="trusted_local_review" if entry.public_baseline else "synthetic_only",
        mathematical_verification="Mathematical correctness is not independently reproduced by this application.",
    )


def _aggregate(combos: list[ComboView]) -> tuple[dict[str, float] | None, dict[str, float] | None]:
    if not combos:
        return None, None
    mass = sum(c.reach_weight for c in combos)
    actions = combos[0].frequencies
    freq = {key: sum(c.reach_weight * c.frequencies[key] for c in combos) / mass for key in actions}
    ev = {
        key: sum(c.reach_weight * c.action_ev[key] for c in combos if c.action_ev is not None)
        / mass
        for key in actions
        if all(c.action_ev is not None and key in c.action_ev for c in combos)
    }
    return freq, ev or None


class PrecomputedStrategyProvider:
    def __init__(self, catalog: SolutionCatalog) -> None:
        self.catalog = catalog

    def scenarios(self, mode: Mode = "validated_gto") -> ScenarioIndex:
        return ScenarioIndex(
            scenarios=[
                ScenarioSummary(
                    solution_id=e.document.solution_id,
                    scenario_id=e.document.scenario.scenario_id,
                    kind=e.document.kind,
                    scenario=e.document.scenario,
                    label=f"{e.document.scenario.street} · {e.document.scenario.hero_position} vs "
                    f"{e.document.scenario.opponent_position} · {e.document.solution_id}",
                )
                for e in self.catalog.visible(mode)
            ],
            message="Synthetic UI examples, not GTO solutions."
            if mode == "synthetic_demo"
            else "Only permitted, explicitly reviewed exact scenarios are listed.",
        )

    def query(self, request: StrategyQuery) -> QueryResult:
        scenario = request.scenario
        blocked = set(scenario.board + scenario.dead_cards)
        unblocked = {
            hand: sum(not blocked.intersection(c) for c in COMBOS[hand]) for hand in CLASSES
        }
        entry = self.catalog.find(scenario.scenario_id, request.mode)
        actions = [
            ActionView(key=a.key, action=a.action.value, amount=a.amount)
            for a in sorted(scenario.legal_actions, key=lambda a: a.key)
        ]
        combos = (
            []
            if entry is None
            else [
                ComboView(
                    cards=c.cards,
                    hand_class=hand_class(*c.cards),
                    reach_weight=c.reach_weight,
                    frequencies=c.frequencies,
                    action_ev=c.action_ev,
                )
                for c in entry.document.combinations
            ]
        )
        classes = []
        for hand in CLASSES:
            represented = [c for c in combos if c.hand_class == hand]
            freq, ev = _aggregate(represented)
            if freq is not None:
                classes.append(
                    ClassStrategy(
                        hand_class=hand,
                        represented_combos=len(represented),
                        unblocked_combos=unblocked[hand],
                        reach_mass=sum(c.reach_weight for c in represented),
                        frequencies=freq,
                        action_ev=ev,
                    )
                )
        freq, ev = _aggregate(combos)
        real = entry is not None and request.mode == "validated_gto"
        return QueryResult(
            scenario_id=scenario.scenario_id,
            status="unavailable" if entry is None else "available" if real else "synthetic_demo",
            is_gto_recommendation=real,
            message="GTO solution unavailable"
            if entry is None
            else "Exact matched solver record; trusted review is not an independent equilibrium proof."
            if real
            else "SYNTHETIC UI FIXTURE — not a solver solution or poker recommendation.",
            scenario=scenario,
            actions=actions,
            source=source_view(entry) if entry else None,
            combinations=combos,
            classes=classes,
            frequencies=freq,
            action_ev=ev,
            represented_combos=len(combos),
            unblocked_combos=sum(unblocked.values()),
            aggregation_method="Reach-weighted means over represented unblocked combos only; missing combos are not folds.",
        )
