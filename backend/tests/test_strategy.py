from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from poker_lab.api import create_app
from poker_lab.strategy_catalog import (
    SolutionCatalog,
    demo_catalog,
    import_dataset,
    load_catalog,
    read_dataset,
)
from poker_lab.strategy_models import Dataset, ImportedSolution, StrategyScenario, StrategySolution
from poker_lab.strategy_provider import PrecomputedStrategyProvider, StrategyQuery


def example(index: int = 0) -> StrategySolution:
    return demo_catalog().entries[index].document.model_copy(deep=True)


def dataset(solution: StrategySolution | None = None) -> Dataset:
    return Dataset(
        schema_version="1.0", dataset_id="test-dataset-v1", solutions=[solution or example()]
    )


def review_candidate(*, public: bool = True, ev: bool = False) -> StrategySolution:
    # Fabricated metadata for testing the trusted approval boundary, NOT real solver data.
    raw = example().model_dump(mode="json")
    raw["solution_id"] = "test-only-admin-contract-v1"
    raw["kind"] = "solver_solution"
    raw["solver_identifier"] = "TEST ONLY: fabricated administrative contract, not a solver"
    raw["validation"]["status"] = "reviewed_gto"
    raw["validation"]["methodology"] = (
        "TEST-ONLY approval workflow; no genuine mathematical validation."
    )
    raw["provenance"]["publish"] = public
    if not public:
        raw["provenance"]["redistribution"] = "private_only"
    if ev:
        raw["validation"]["ev_verified"] = True
        for i, row in enumerate(raw["combinations"]):
            row["action_ev"] = {key: float(i) for key in row["frequencies"]}
    return StrategySolution.model_validate(raw)


def test_scenario_canonicalization_preserves_identity_and_critical_differences() -> None:
    original = example(1).scenario
    raw = original.model_dump(mode="json")
    raw["board"] = list(reversed(raw["board"]))
    raw["legal_actions"] = list(reversed(raw["legal_actions"]))
    raw["starting_stacks"] = dict(reversed(list(raw["starting_stacks"].items())))
    raw["abstraction"]["assumptions"].reverse()
    normalized = StrategyScenario.model_validate(raw)
    assert normalized.scenario_id == original.scenario_id
    raw["board"] = ["3c", "7h", "Jd"]
    assert StrategyScenario.model_validate(raw).scenario_id != original.scenario_id
    raw = example(3).scenario.model_dump(mode="json")
    raw["board"][-1], raw["board"][-2] = raw["board"][-2], raw["board"][-1]
    assert StrategyScenario.model_validate(raw).scenario_id != example(3).scenario.scenario_id
    raw = original.model_dump(mode="json")
    raw["legal_actions"][2]["amount"] = 350
    assert StrategyScenario.model_validate(raw).scenario_id != original.scenario_id
    raw = original.model_dump(mode="json")
    raw["abstraction"]["range_model_id"] = "different-range-model"
    assert StrategyScenario.model_validate(raw).scenario_id != original.scenario_id


@pytest.mark.parametrize(
    "field,value",
    [
        ("players", 2),
        ("players", 6.0),
        ("ante", False),
        ("ante", 10),
        ("small_blind", 25),
        ("pot", 999),
        ("effective_stack", 5000),
        ("hero_position", "HJ"),
        ("opponent_position", "UTG"),
        ("board", ["As"]),
        ("dead_cards", ["As", "As"]),
        ("starting_stacks", {"UTG": 10000}),
    ],
)
def test_rejects_ambiguous_or_conflicting_scenarios(field: str, value) -> None:
    raw = example().scenario.model_dump(mode="json")
    raw[field] = value
    with pytest.raises(ValidationError):
        StrategyScenario.model_validate(raw)


def test_history_and_exact_sizes_must_replay_against_engine() -> None:
    raw = example(1).scenario.model_dump(mode="json")
    raw["history"][0]["position"] = "HJ"
    with pytest.raises(ValidationError, match="History"):
        StrategyScenario.model_validate(raw)
    raw = example(1).scenario.model_dump(mode="json")
    raw["history"][0]["amount"] = 90
    with pytest.raises(ValidationError, match="size"):
        StrategyScenario.model_validate(raw)
    raw = example().scenario.model_dump(mode="json")
    raw["legal_actions"].append(raw["legal_actions"][0])
    with pytest.raises(ValidationError, match="Duplicate"):
        StrategyScenario.model_validate(raw)
    raw = example().scenario.model_dump(mode="json")
    raw["legal_actions"] = [{"action": "fold", "amount": None}, {"action": "raise", "amount": 200}]
    with pytest.raises(ValidationError, match="passive"):
        StrategyScenario.model_validate(raw)
    raw = example().scenario.model_dump(mode="json")
    raw["legal_actions"][1] = {"action": "check", "amount": None}
    with pytest.raises(ValidationError, match="engine-legal"):
        StrategyScenario.model_validate(raw)
    raw = example().scenario.model_dump(mode="json")
    raw["abstraction"]["assumptions"] *= 2
    with pytest.raises(ValidationError, match="Duplicate"):
        StrategyScenario.model_validate(raw)


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_combo",
        "invalid_card",
        "duplicate_cards",
        "wrong_keys",
        "not_normalized",
        "negative",
        "oversized",
        "nan",
        "zero_reach",
        "unknown_ev",
    ],
)
def test_combination_validation(mutation: str) -> None:
    raw = example().model_dump(mode="json")
    row = raw["combinations"][0]
    if mutation == "duplicate_combo":
        other = dict(row)
        other["cards"] = list(reversed(row["cards"]))
        raw["combinations"].append(other)
    elif mutation == "invalid_card":
        row["cards"] = ["ZZ", "Ad"]
    elif mutation == "duplicate_cards":
        row["cards"] = ["Ac", "Ac"]
    elif mutation == "wrong_keys":
        row["frequencies"]["raise@999"] = row["frequencies"].pop("raise@200")
    elif mutation == "not_normalized":
        row["frequencies"]["fold"] = 0.5
    elif mutation == "negative":
        row["frequencies"]["fold"] = -0.1
    elif mutation == "oversized":
        row["frequencies"]["fold"] = 1.1
    elif mutation == "nan":
        row["frequencies"]["fold"] = float("nan")
    elif mutation == "zero_reach":
        row["reach_weight"] = 0
    else:
        row["action_ev"] = {"not-legal": 5}
    with pytest.raises(ValidationError):
        StrategySolution.model_validate(raw)


def test_blocked_combinations_and_synthetic_label_integrity() -> None:
    raw = example(1).model_dump(mode="json")
    raw["combinations"][0]["cards"] = ["2c", "Ad"]
    with pytest.raises(ValidationError, match="blocked"):
        StrategySolution.model_validate(raw)
    raw = example().model_dump(mode="json")
    raw["validation"]["status"] = "reviewed_gto"
    with pytest.raises(ValidationError, match="Synthetic"):
        StrategySolution.model_validate(raw)
    raw = example().model_dump(mode="json")
    raw["validation"]["ev_verified"] = True
    with pytest.raises(ValidationError, match="Synthetic"):
        StrategySolution.model_validate(raw)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "no_usage",
        "no_publish_rights",
        "bad_url",
        "credentials",
        "missing_solver",
        "naive_time",
        "missing_version",
    ],
)
def test_metadata_and_provenance_validation(mutation: str) -> None:
    raw = example().model_dump(mode="json")
    if mutation == "missing":
        raw.pop("provenance")
    elif mutation == "no_usage":
        raw["provenance"]["usage_granted"] = False
    elif mutation == "no_publish_rights":
        raw["provenance"]["redistribution"] = "private_only"
    elif mutation == "bad_url":
        raw["provenance"]["source_url"] = "not-a-source"
    elif mutation == "credentials":
        raw["provenance"]["source_url"] = "https://secret:password@example.org"
    elif mutation == "missing_solver":
        raw.pop("solver_identifier")
    elif mutation == "naive_time":
        raw["validation"]["checked_at"] = "2026-11-09T00:00:00"
    else:
        raw.pop("schema_version")
    with pytest.raises(ValidationError):
        StrategySolution.model_validate(raw)


def test_reach_weighted_aggregation_partial_coverage_and_combo_ev() -> None:
    catalog = demo_catalog()
    provider = PrecomputedStrategyProvider(catalog)
    result = provider.query(StrategyQuery(scenario=example().scenario, mode="synthetic_demo"))
    aa = next(c for c in result.classes if c.hand_class == "AA")
    assert aa.represented_combos == 2 and aa.unblocked_combos == 6
    assert aa.frequencies["fold"] == pytest.approx((1 * 0.1 + 0.5 * 0.2) / 1.5)
    assert sum(aa.frequencies.values()) == pytest.approx(1)
    assert aa.action_ev is None
    assert result.represented_combos == 8 and result.unblocked_combos == 1326
    river = provider.query(StrategyQuery(scenario=example(3).scenario, mode="synthetic_demo"))
    assert next(c for c in river.classes if c.hand_class == "99").unblocked_combos == 3
    assert result.is_gto_recommendation is False and result.status == "synthetic_demo"
    assert all(c.action_ev is None for c in result.combinations)


def test_default_real_lookup_never_falls_back_to_synthetic_or_mismatched_state() -> None:
    provider = PrecomputedStrategyProvider(demo_catalog())
    scenario = example().scenario
    missing = provider.query(StrategyQuery(scenario=scenario))
    assert (
        missing.status == "unavailable" and missing.frequencies is None and missing.source is None
    )
    assert (
        not provider.scenarios().scenarios
        and len(provider.scenarios("synthetic_demo").scenarios) == 4
    )
    raw = scenario.model_dump(mode="json")
    raw["legal_actions"][2]["amount"] = 250
    mismatch = provider.query(
        StrategyQuery(scenario=StrategyScenario.model_validate(raw), mode="synthetic_demo")
    )
    assert mismatch.status == "unavailable" and not mismatch.combinations


def test_import_duplicates_are_transactional(tmp_path: Path) -> None:
    path = tmp_path / "catalog.db"
    assert import_dataset(dataset(), path) == 1
    with pytest.raises(ValueError, match="Duplicate"):
        import_dataset(dataset(), path)
    assert len(load_catalog(path).entries) == 1
    with pytest.raises(ValidationError, match="Duplicate"):
        Dataset(schema_version="1.0", dataset_id="duplicates", solutions=[example(), example()])
    first, second = example(), example()
    second.solution_id = "different-id"
    with pytest.raises(ValidationError, match="conflicting"):
        Dataset(schema_version="1.0", dataset_id="conflicts", solutions=[first, second])
    with pytest.raises(ValueError, match="Duplicate"):
        import_dataset(dataset(second), path)
    assert len(load_catalog(path).entries) == 1


def test_metadata_alone_cannot_publish_gto_and_private_data_stays_private(tmp_path: Path) -> None:
    path = tmp_path / "unreviewed.db"
    candidate = review_candidate()
    import_dataset(dataset(candidate), path)
    registry = load_catalog(path)
    result = PrecomputedStrategyProvider(registry).query(StrategyQuery(scenario=candidate.scenario))
    assert result.status == "unavailable" and not registry.visible("validated_gto")
    private = review_candidate(public=False)
    private_path = tmp_path / "private.db"
    import_dataset(
        dataset(private),
        private_path,
        reviewer="Test reviewer",
        evidence="Test-only administrative attestation, not mathematical proof",
        confirm_rights=True,
    )
    private_registry = load_catalog(private_path)
    assert not private_registry.visible("validated_gto")
    client = TestClient(create_app(strategy_catalog=private_registry))
    assert client.get("/api/strategy/scenarios").json()["scenarios"] == []
    assert (
        client.post("/api/strategy/source", json={"solution_id": private.solution_id}).status_code
        == 404
    )


def test_trusted_approval_is_content_bound_and_not_independent_math_proof(tmp_path: Path) -> None:
    candidate = review_candidate(ev=True)
    path = tmp_path / "reviewed.db"
    import_dataset(
        dataset(candidate),
        path,
        reviewer="Test reviewer",
        evidence="Test-only review mechanism; no genuine strategy validated",
        confirm_rights=True,
    )
    registry = load_catalog(path)
    provider = PrecomputedStrategyProvider(registry)
    result = provider.query(StrategyQuery(scenario=candidate.scenario))
    assert result.status == "available" and result.source.approval_status == "trusted_local_review"
    assert "not independently" in result.source.mathematical_verification
    aa = next(c for c in result.classes if c.hand_class == "AA")
    assert aa.action_ev["fold"] == pytest.approx(1 / 3)
    assert result.action_ev is not None
    entry = registry.entries[0].model_dump(mode="json")
    entry["document"]["combinations"][0]["reach_weight"] = 0.7
    with pytest.raises(ValidationError, match="Approval"):
        ImportedSolution.model_validate(entry)
    # No private reviewer identity or evidence paths are returned as public metadata.
    public = result.source.model_dump_json()
    assert "Test reviewer" not in public
    assert "content_hash" not in public


def test_approval_requires_real_review_and_explicit_rights(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="evidence"):
        import_dataset(dataset(review_candidate()), tmp_path / "a.db", reviewer="Reviewer")
    with pytest.raises(ValidationError, match="Approval"):
        import_dataset(
            dataset(),
            tmp_path / "b.db",
            reviewer="Reviewer",
            evidence="Cannot promote fabricated demo probabilities",
            confirm_rights=True,
        )


def test_local_dataset_limits_and_loading(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "input.json"
    source.write_text(dataset().model_dump_json(), encoding="utf-8")
    assert read_dataset(source).solutions[0].kind == "synthetic_fixture"
    import poker_lab.strategy_catalog as catalog_module

    monkeypatch.setattr(catalog_module, "MAX_IMPORT_BYTES", 1)
    with pytest.raises(ValueError, match="8 MiB"):
        read_dataset(source)
    monkeypatch.setattr(catalog_module, "MAX_CATALOG_SOLUTIONS", 4)
    with pytest.raises(ValueError, match="124"):
        import_dataset(dataset(), tmp_path / "limit.db")
    with pytest.raises(ValueError, match="165"):
        SolutionCatalog(demo_catalog().entries * 2)


def test_api_exact_lookup_source_metadata_and_no_public_import() -> None:
    client = TestClient(create_app())
    assert len(client.get("/api/strategy/scenarios").json()["scenarios"]) == 37
    samples = client.get("/api/strategy/examples").json()["scenarios"]
    assert len(samples) == 4
    for record in samples:
        payload = {"scenario": record["scenario"], "mode": "synthetic_demo"}
        response = client.post("/api/strategy/query", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "synthetic_demo" and not data["is_gto_recommendation"]
        assert data["source"]["validation_status"] == "synthetic_only"
        assert "no-store" in response.headers["cache-control"]
        assert client.post("/api/strategy/frequencies", json=payload).json() == data
        assert (
            client.post(
                "/api/strategy/source",
                json={"solution_id": record["solution_id"], "mode": "synthetic_demo"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/strategy/source", json={"solution_id": record["solution_id"]}
            ).status_code
            == 404
        )
        real = client.post("/api/strategy/query", json={"scenario": record["scenario"]}).json()
        assert real["status"] == "unavailable" and real["frequencies"] is None
    assert client.post("/api/strategy/import", json={}).status_code == 404
    assert client.post("/api/strategy/query", json={"scenario": {}}).status_code == 422
    assert (
        client.post(
            "/api/strategy/query", json={"scenario": samples[0]["scenario"], "mode": "guess"}
        ).status_code
        == 422
    )
