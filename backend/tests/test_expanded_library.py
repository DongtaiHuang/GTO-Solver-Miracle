import pytest

from poker_lab.exploit import Request, analyze
from poker_lab.strategy_catalog import configured_catalog
from poker_lab.strategy_models import StrategyScenario
from poker_lab.strategy_provider import PrecomputedStrategyProvider, StrategyQuery


def test_exact_expanded_nodes_and_exploit_boundary():
    catalog = configured_catalog(None)
    provider = PrecomputedStrategyProvider(catalog)
    nodes = [s for s in provider.scenarios().scenarios if s.solution_id.startswith("cfr-river-")]
    assert len(nodes) == 5
    for node in nodes:
        result = provider.query(StrategyQuery(scenario=node.scenario))
        assert result.status == "available" and result.represented_combos == 8
        assert "4000 iterations" in result.source.validation_methodology
        assert all(set(c.action_ev) == set(c.frequencies) for c in result.combinations)
        raw = node.scenario.model_dump(mode="json")
        raw["abstraction"]["range_model_id"] = "different-range"
        miss = provider.query(StrategyQuery(scenario=StrategyScenario.model_validate(raw)))
        assert miss.status == "unavailable"
        with pytest.raises(ValueError, match="Unsupported"):
            analyze(Request(scenario=node.scenario, profile="tag"), catalog)
