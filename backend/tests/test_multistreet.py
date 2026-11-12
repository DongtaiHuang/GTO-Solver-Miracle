import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from poker_lab import multistreet as ms
from poker_lab.api import create_app
from poker_lab.strategy_catalog import configured_catalog

catalog = configured_catalog(None)


def request(sid="ts-root-v1", profile="tag", **extra):
    s = catalog.source(sid, "validated_gto").document.scenario
    return ms.Request(
        solution_id=sid,
        scenario=s,
        reference_version=ms.VERSION,
        opponent=s.opponent_position,
        hypotheses=[ms.Hypothesis(name="Base", profile=profile, **extra)],
    )


@pytest.mark.parametrize("sid", ["ts-root-v1", "ts-check-v1"])
def test_both_roles_equilibrium_and_model(sid):
    req = request(sid, "standard_gto")
    reference = ms.reference()
    hero = 0 if req.opponent == "BB" else 1
    result = ms.analyze(req, catalog).results[0]
    assert not result.changes
    assert result.root.response_model_ev == pytest.approx(reference["best"][hero], abs=1e-8)
    assert result.root.equilibrium_ev == pytest.approx(
        reference["value"] if hero == 0 else 550 - reference["value"], abs=1e-8
    )
    assert -1e-9 <= result.root.gain <= 0.022492
    modeled = ms.analyze(request(sid), catalog).results[0]
    assert modeled.root.gain >= 0 and len(modeled.changes) == 8
    assert modeled.root.equilibrium_cost == pytest.approx(
        modeled.root.equilibrium_ev - modeled.root.response_equilibrium_ev
    )
    for row in modeled.decisions:
        if row.response_model:
            assert sum(row.response_model.frequencies.values()) == pytest.approx(1)


def test_unreachable_and_hidden_combo_boundaries():
    result = ms.analyze(request("ts-bet275-v1", "tag", opening_bet=0), catalog).results[0]
    assert all(
        row.response_model is None and row.baseline_model is None for row in result.decisions
    )
    ref = ms.reference()
    target = "turn/check/check/Ac"
    eq = ms.evaluate(ref, 1, target, {}, {})
    for hand, row in zip(ref["hands"][1], eq.decisions, strict=True):
        if "Ac" in hand:
            assert row is None
        else:
            assert row is not None


def test_sparse_river_edit_and_sensitivity():
    ctx = request("ts-root-v1")
    rows = ms.policy_rows(ctx, catalog)
    node = "turn/check/check/Kh/check"
    assert all("Kh" not in h for h in rows[node])
    combo = next(iter(rows[node]))
    edit = ms.Override(node=node, combo=combo, probabilities={"check": 0.0, "bet@275": 1.0})
    ctx.hypotheses = [
        ms.Hypothesis(name=str(rate), profile="lag", opening_bet=rate, overrides=[edit])
        for rate in (0, 0.5, 1)
    ]
    results = ms.analyze(ctx, catalog).results
    assert len({round(r.root.response_model_ev, 6) for r in results}) == 3
    for r in results:
        assert r.root.response_model_ev >= r.root.baseline_model_ev - 1e-8
        assert any(change.node == node and change.combo == combo for change in r.changes)
    ctx.hypotheses[0].overrides.append(edit)
    with pytest.raises(ValueError, match="Repeated"):
        ms.analyze(ctx, catalog)


@pytest.mark.parametrize(
    "kind",
    [
        "seat",
        "board",
        "id",
        "tree",
        "stack",
        "version",
        "extra",
        "action",
        "blocked",
        "hidden",
        "total",
        "nan",
        "negative",
        "limit",
        "benchmark",
    ],
)
def test_invalid_inputs(kind):
    raw = request().model_dump(mode="json")
    override = {
        "node": "turn/check",
        "combo": "AcAd",
        "probabilities": {"check": 0.4, "bet@275": 0.6},
    }
    raw["hypotheses"][0]["overrides"] = [override]
    if kind == "seat":
        raw["opponent"] = "BB"
    elif kind == "board":
        raw["scenario"]["board"][0] = "3c"
    elif kind == "id":
        raw["solution_id"] = "river-550-btn-v1"
    elif kind == "tree":
        raw["scenario"]["abstraction"]["tree_id"] = "other-game"
    elif kind == "stack":
        raw["scenario"]["effective_stack"] = 8000
    elif kind == "version":
        raw["reference_version"] = "v2"
    elif kind == "extra":
        override["hero_cards"] = ["Kh", "Qh"]
    elif kind == "action":
        override["probabilities"] = {"check": 0.4, "raise@550": 0.6}
    elif kind == "blocked":
        override["node"] = "turn/check/check/Ac/check"
    elif kind == "hidden":
        override["node"] = "turn"
    elif kind == "total":
        override["probabilities"]["check"] = 0.6
    elif kind == "nan":
        override["probabilities"]["check"] = float("nan")
    elif kind == "negative":
        override["probabilities"]["check"] = -1.0
    elif kind == "limit":
        raw["hypotheses"] *= 4
    else:
        raw["hypotheses"][0]["profile"] = "standard_gto"
    with pytest.raises((ValidationError, ValueError)):
        ms.analyze(ms.Request.model_validate(raw), catalog)


def test_request_limits_and_no_shared_edits():
    app = create_app()
    first, second = TestClient(app), TestClient(app)
    raw = request().model_dump(mode="json")
    assert first.post("/api/strategy/multistreet", json=raw).status_code == 200
    r = second.post(
        "/api/strategy/multistreet", json=request(profile="standard_gto").model_dump(mode="json")
    )
    assert r.status_code == 200 and not r.json()["results"][0]["changes"]
    context = {k: v for k, v in raw.items() if k != "hypotheses"}
    assert first.post("/api/strategy/multistreet-policy", json=context).status_code == 200
    assert (
        first.post(
            "/api/strategy/multistreet",
            content=" " * 65537 + "{}",
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )


def test_known_overfolding_bluff():
    # One bluff facing two possible hidden callers; hero sees the same row for both deals.
    nodes = {
        "turn": {
            "seat": 0,
            "river": None,
            "invested": 0,
            "actions": ["check", "bet@550"],
            "children": ["x", "b"],
            "policy": [[0.5, 0.5]],
        },
        "x": {"river": None, "payoff": [[0.0, 0.0]]},
        "b": {
            "seat": 1,
            "river": None,
            "invested": 0,
            "actions": ["fold", "call@550"],
            "children": ["f", "c"],
            "policy": [[0.5, 0.5], [0.5, 0.5]],
        },
        "f": {"river": None, "payoff": [[550.0, 550.0]]},
        "c": {"river": None, "payoff": [[-550.0, -550.0]]},
    }
    ref = {"nodes": nodes, "hands": [["5c4c"], ["KhQh", "JsKs"]], "joint": [[0.5, 0.5]]}
    folds = {"b": [[1, 0], [1, 0]]}
    assert ms.evaluate(ref, 0, "turn", folds, {}).value == 275
    assert ms.evaluate(ref, 0, "turn", folds, {}, optimize=True).value == 550
    # Perfectly opposite hidden responses: averaging before maximization yields zero.
    mixed = ms.evaluate(ref, 0, "turn", {"b": [[1, 0], [0, 1]]}, {}, optimize=True)
    assert mixed.value == 0 and mixed.strategy["turn"] == [[0.5, 0.5]]
