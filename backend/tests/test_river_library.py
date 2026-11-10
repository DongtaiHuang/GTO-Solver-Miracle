import pytest

from poker_lab.strategy_catalog import configured_catalog
from poker_lab.strategy_models import StrategyScenario
from poker_lab.strategy_provider import PrecomputedStrategyProvider, StrategyQuery


@pytest.mark.parametrize("size", [275, 550])
def test_river_equilibrium_and_exact_coverage(size):
    provider = PrecomputedStrategyProvider(configured_catalog(None))
    entries = {s.solution_id: s.scenario for s in provider.scenarios().scenarios}
    btn = entries[f"river-{size}-btn-v1"]
    result = provider.query(StrategyQuery(scenario=btn))
    assert result.is_gto_recommendation and result.source.approval_status == "trusted_local_review"
    assert "Best-response gap" in result.source.validation_methodology
    value, bluff = result.combinations
    assert value.frequencies[f"bet@{size}"] == pytest.approx(1)
    assert bluff.frequencies[f"bet@{size}"] == pytest.approx(size / (550 + size))
    assert bluff.action_ev["check"] == pytest.approx(bluff.action_ev[f"bet@{size}"])
    response = provider.query(StrategyQuery(scenario=entries[f"river-{size}-bb-v1"]))
    assert response.frequencies[f"call@{size}"] == pytest.approx(550 / (550 + size))
    assert response.action_ev[f"call@{size}"] == pytest.approx(0, abs=1e-8)
    raw = btn.model_dump(mode="json")
    raw["board"][4] = "8d"
    miss = provider.query(StrategyQuery(scenario=StrategyScenario.model_validate(raw)))
    assert miss.status == "unavailable" and miss.frequencies is None
