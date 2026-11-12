import pytest

from poker_lab.analyzer import Hand, replay
from poker_lab.exploit import Request, analyze
from poker_lab.strategy_catalog import configured_catalog
from poker_lab.strategy_models import Dataset, StrategyScenario
from poker_lab.strategy_provider import PrecomputedStrategyProvider, StrategyQuery


def test_turn_catalog_exact_decision_replay_and_boundaries():
    catalog = configured_catalog(None)
    provider = PrecomputedStrategyProvider(catalog)
    entries = [
        e.document
        for e in catalog.visible("validated_gto")
        if e.document.solution_id.startswith("ts-")
    ]
    Dataset(schema_version="1.0", dataset_id="verified-turn-export", solutions=entries)
    assert len(entries) == 28
    candidates = [(e.solution_id, e.scenario) for e in entries]
    for doc in entries:
        s = doc.scenario
        hand = Hand.model_validate(
            {
                "version": "1.0",
                "hero": s.hero_position,
                "big_blind": 100,
                "small_blind": 50,
                "seats": {p: {"name": p, "stack": v} for p, v in s.starting_stacks.items()},
                "actions": s.history,
                "board": s.board,
            }
        )
        step = replay(hand, candidates)[-1]
        assert (
            step.candidates == [doc.solution_id]
            and step.pot == s.pot
            and step.actor == s.hero_position
        )
        response = provider.query(StrategyQuery(scenario=s))
        assert response.status == "available"
        for c in response.combinations:
            assert (
                sum(c.frequencies.values()) == pytest.approx(1)
                and c.action_ev.keys() == c.frequencies.keys()
            )
            assert not set(c.cards).intersection(s.board)
    s = entries[0].scenario
    with pytest.raises(ValueError, match="Unsupported"):
        analyze(Request(scenario=s, profile="lag"), catalog)
    raw = s.model_dump(mode="json")
    raw["abstraction"]["tree_id"] = "different-turn-tree"
    assert (
        provider.query(StrategyQuery(scenario=StrategyScenario.model_validate(raw))).status
        == "unavailable"
    )
