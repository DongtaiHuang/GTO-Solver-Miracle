"""Boundary tests for local imports and strict public queries; no genuine solver data."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_strategy import dataset, example, review_candidate

from poker_lab.api import create_app
from poker_lab.strategy_catalog import (
    SolutionCatalog,
    configured_catalog,
    demo_catalog,
    import_dataset,
    read_dataset,
    strict_json,
)
from poker_lab.strategy_import import main
from poker_lab.strategy_models import StrategyScenario, StrategySolution


@pytest.mark.parametrize("payload", ['{"version":1,"version":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_import_rejects_duplicate_keys_and_nonfinite_json(tmp_path: Path, payload: str) -> None:
    source = tmp_path / "bad.json"
    source.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        read_dataset(source)


def test_public_queries_reject_duplicate_keys_and_oversized_json() -> None:
    client = TestClient(create_app())
    body = json.dumps({"scenario": example().scenario.model_dump(mode="json")})
    duplicate = body[:-1] + ', "mode":"validated_gto","mode":"synthetic_demo"}'
    response = client.post(
        "/api/strategy/query", content=duplicate, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422 and "Duplicate" in response.text
    response = client.post(
        "/api/strategy/source",
        content='{"solution_id":"abc","x":NaN}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    response = client.post(
        "/api/strategy/query",
        content=body + " " * (2 * 1024 * 1024),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_conflicting_action_aliases_and_unvalidated_ev_are_rejected() -> None:
    raw = example().scenario.model_dump(mode="json")
    raw["legal_actions"].append({"action": "raise", "amount": 10000})
    with pytest.raises(ValidationError, match="equivalent"):
        StrategyScenario.model_validate(raw)
    raw = review_candidate(ev=True).model_dump(mode="json")
    raw["combinations"][0]["action_ev"] = {"wrong": 3}
    with pytest.raises(ValidationError, match="Action EV"):
        StrategySolution.model_validate(raw)
    raw["combinations"][0]["action_ev"] = {"fold": 3}
    raw["validation"]["ev_verified"] = False
    with pytest.raises(ValidationError, match="Action EV"):
        StrategySolution.model_validate(raw)


def test_configured_catalog_does_not_publish_unapproved_import(tmp_path: Path) -> None:
    path = tmp_path / "catalog.db"
    import_dataset(dataset(review_candidate()), path)
    registry = configured_catalog(str(path))
    assert len(registry.entries) == 42
    assert all(e.document.solution_id.startswith(("river-", "cfr-river-", "ts-")) for e in registry.visible("validated_gto"))
    assert len(configured_catalog(None).entries) == 41
    with pytest.raises(ValueError, match="Duplicate"):
        SolutionCatalog(demo_catalog().entries * 2)


@pytest.mark.parametrize(
    "flags",
    [
        ["--approve-gto"],
        ["--reviewer", "Reviewer"],
        ["--review-evidence", "Evidence"],
        ["--confirm-source-and-rights"],
    ],
)
def test_cli_requires_explicit_complete_approval(
    monkeypatch, tmp_path: Path, flags: list[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["strategy_import", "unused.json", "--catalog", str(tmp_path / "catalog.db"), *flags],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2
    assert not (tmp_path / "catalog.db").exists()


def test_cli_transactional_success_and_rejection(monkeypatch, tmp_path: Path, capsys) -> None:
    source, catalog = tmp_path / "dataset.json", tmp_path / "catalog.db"
    source.write_text(dataset().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["strategy_import", str(source), "--catalog", str(catalog)])
    main()
    assert "Structural checks are not mathematical validation" in capsys.readouterr().out
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 1
    assert "Duplicate" in capsys.readouterr().err
    source.write_text("invalid", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 1


def test_cli_approval_is_explicit_and_content_bound(monkeypatch, tmp_path: Path) -> None:
    from poker_lab.strategy_catalog import load_catalog

    source, catalog = tmp_path / "dataset.json", tmp_path / "catalog.db"
    source.write_text(dataset(review_candidate()).model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "strategy_import",
            str(source),
            "--catalog",
            str(catalog),
            "--approve-gto",
            "--reviewer",
            "TEST REVIEWER",
            "--review-evidence",
            "TEST ONLY workflow, not real strategy",
            "--confirm-source-and-rights",
        ],
    )
    main()
    assert load_catalog(catalog).entries[0].approval is not None
    assert strict_json('{"number":1}') == {"number": 1}
