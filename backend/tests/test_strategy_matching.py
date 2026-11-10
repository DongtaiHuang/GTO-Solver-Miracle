"""Valid but different scenarios must never reuse a nearby solution."""

from datetime import UTC, datetime

import pytest
from test_strategy import example, review_candidate

from poker_lab.strategy_catalog import SolutionCatalog, demo_catalog
from poker_lab.strategy_models import Approval, ImportedSolution, StrategyScenario
from poker_lab.strategy_provider import PrecomputedStrategyProvider, StrategyQuery


@pytest.mark.parametrize(
    "difference", ["board", "opponent", "history", "stack", "dead_card", "tree"]
)
def test_valid_scenario_differences_cannot_match(difference: str) -> None:
    raw = example(1 if difference == "board" else 0).scenario.model_dump(mode="json")
    if difference == "board":
        raw["board"][0] = "3c"
    elif difference == "opponent":
        raw["opponent_position"] = "SB"
        raw["effective_stack"] = 9950
    elif difference == "history":
        raw["history"] = [{"street": "preflop", "position": "UTG", "action": "call", "amount": 100}]
        raw["hero_position"] = "HJ"
        raw["pot"] = 250
    elif difference == "stack":
        raw["starting_stacks"] = dict.fromkeys(raw["starting_stacks"], 20000)
        raw["effective_stack"] = 19900
        raw["legal_actions"][-1]["amount"] = 20000
    elif difference == "dead_card":
        raw["dead_cards"] = ["2c"]
    else:
        raw["abstraction"]["tree_id"] = "different-betting-tree"
    scenario = StrategyScenario.model_validate(raw)
    result = PrecomputedStrategyProvider(demo_catalog()).query(
        StrategyQuery(scenario=scenario, mode="synthetic_demo")
    )
    assert result.status == "unavailable"
    assert result.source is None and result.frequencies is None and result.action_ev is None
    assert not result.classes and not result.combinations


def test_aggregate_ev_requires_value_for_every_represented_combination() -> None:
    raw = review_candidate(ev=True).model_dump(mode="json")
    raw["combinations"][1]["action_ev"] = {"fold": 1.0}
    from poker_lab.strategy_models import StrategySolution

    candidate = StrategySolution.model_validate(raw)
    now = datetime.now(UTC)
    entry = ImportedSolution(
        document=candidate,
        imported_at=now,
        approval=Approval(
            content_hash=candidate.content_hash,
            reviewer="TEST reviewer",
            evidence_reference="TEST ONLY workflow fixture, not genuine solver output",
            approved_at=now,
            confirmed_source_and_rights=True,
        ),
    )
    result = PrecomputedStrategyProvider(SolutionCatalog([entry])).query(
        StrategyQuery(scenario=candidate.scenario)
    )
    aa = next(c for c in result.classes if c.hand_class == "AA")
    assert set(aa.action_ev) == {"fold"}
    assert set(result.action_ev) == {"fold"}
