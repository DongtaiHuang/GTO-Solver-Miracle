from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from poker_lab.api import create_app
from poker_lab.training import compare

API = "/api/strategy/training/"


def test_numerical_tolerance_and_partial_evs():
    probabilities = {"call": 0.001, "fold": 0.999}
    actions = set(probabilities)
    assert compare(actions, {"call": -1e-9, "fold": 0}, "call", probabilities, 100).loss == 0
    assert compare(actions, {"call": -1, "fold": 0}, "call", probabilities, 100).loss_bb == 0.01
    assert compare(actions, {"call": 1}, "call", probabilities, 100).loss is None
    assert compare(actions, {"call": 1, "fold": 0}, "raise@4", probabilities, 100).loss is None


def test_training_catalog_submission_and_private_report():
    client = TestClient(create_app())
    prompts = client.get(API + "exercises").json()
    assert len({p["solution_id"] for p in prompts}) == 37
    p = next(p for p in prompts if p["solution_id"] == "ts-root-v1" and p["combo"] == "KhQh")
    assert len(p["board"]) == 4 and "action_ev" not in p
    req = {k: p[k] for k in ("solution_id", "scenario_id", "version", "combo")}
    req.update(action="bet@275", hypothesis={"name": "tag", "profile": "tag"})

    def grade(**updates):
        result = client.post(API + "grade", json=req | updates)
        assert result.status_code == 200
        return result.json()

    unreachable = next(p for p in prompts if p["solution_id"] == "ts-bet275-v1")
    other = {k: unreachable[k] for k in ("solution_id", "scenario_id", "version", "combo")}
    no_reach = grade(
        **other,
        action="fold",
        hypothesis={"name": "No opening bets", "profile": "tag", "opening_bet": 0},
    )
    assert no_reach["loss"] is None and "reach" in no_reach["reason"]
    model = grade()
    assert model["loss"] == pytest.approx(367.1819710806 - 246.6077945698)
    assert model["equilibrium_cost"] == pytest.approx(15.45863768)
    assert model["loss_bb"] == pytest.approx(model["loss"] / 100)
    assert grade(hypothesis={"name": "lp", "profile": "lp"}) != model
    assert grade(hypothesis=None)["loss"] == pytest.approx(0.007839243, abs=1e-6)
    for override in (
        {"combo": "KdKd"},
        {"version": "0" * 64},
        {"scenario_id": "0" * 64},
        {"action": "raise@999"},
    ):
        assert grade(**override)["status"] == "ungraded"
    attempt = {
        "id": str(uuid4()),
        "session": str(uuid4()),
        "time": "2026-01-02T00:00:00Z",
        "retry": False,
        "origin": "practice",
        "submission": req,
        "feedback": model,
        "street": "turn",
        "position": "BB",
    }

    def report(*attempts):
        return client.post(API + "report", json={"version": "1", "attempts": attempts})

    repeated = report(attempt, attempt | {"id": str(uuid4()), "retry": True}).json()["report"]
    assert repeated["Model · retry"]["graded"] == 1
    assert repeated["Model · turn"]["average_bb"] == pytest.approx(model["loss_bb"])
    assert report(attempt, attempt).status_code == 422
    fake = deepcopy(attempt)
    fake["feedback"]["loss"] = 30
    assert report(fake).status_code == 422
    assert report(attempt | {"position": "BTN"}).status_code == 422
    invalid = attempt | {
        "submission": req | {"action": "raise@999"},
        "feedback": grade(action="raise@999"),
    }
    assert report(invalid).json()["report"]["Model"]["average_bb"] is None
    assert report().json()["report"] == {}
