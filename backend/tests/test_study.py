import random
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from poker_lab.api import create_app
from poker_lab.engine import Holdem
from poker_lab.models import Action, Street
from poker_lab.policy import ProfilePolicy, RandomPolicy
from poker_lab.profiles import (
    ProfileConfig,
    ProfileId,
    ProfileParameters,
    default_profiles,
    resolve_profile,
)
from poker_lab.ranges import (
    CLASSES,
    COMBOS,
    MATRIX,
    HandRange,
    hand_class,
    modeled_range,
    summarize,
)
from poker_lab.study import (
    CustomCFRProvider,
    PrecomputedGTOProvider,
    ProviderContext,
    StatisticalOpponentModel,
    StrategyResponse,
    StudyRequest,
    StudySpot,
    analyze,
    board_texture,
)
from poker_lab.trainer import SessionStore


def profile(profile_id: str = "tag", **overrides: float):
    result = resolve_profile(ProfileConfig(id=profile_id))
    if overrides:
        values = result.parameters.model_dump()
        values.update(overrides)
        result = resolve_profile(
            ProfileConfig(id=profile_id, parameters=ProfileParameters(**values))
        )
    return result


def test_matrix_class_and_combo_construction() -> None:
    assert len(MATRIX) == 13 and all(len(row) == 13 for row in MATRIX)
    assert len(CLASSES) == len(set(CLASSES)) == 169
    assert MATRIX[0][0] == "AA" and MATRIX[0][1] == "AKs" and MATRIX[1][0] == "AKo"
    assert MATRIX[-1][-1] == "22"
    assert sum(len(combos) for combos in COMBOS.values()) == 1326
    for hand, combos in COMBOS.items():
        assert len(combos) == (6 if len(hand) == 2 else 4 if hand.endswith("s") else 12)
        assert all(hand_class(*combo) == hand for combo in combos)


def test_range_weights_and_exact_blocker_counts() -> None:
    result = summarize(HandRange(weights={"AA": 100, "AKs": 50, "AKo": 25}), ["As"], "manual")
    assert result.weighted_combos == 11
    assert result.available_weighted_combos == 6.75
    all_hands = HandRange(weights=dict.fromkeys(CLASSES, 100))
    assert summarize(all_hands, [], "manual").available_weighted_combos == 1326
    assert summarize(all_hands, ["As", "Kd", "Qc"], "manual").available_weighted_combos == 1176
    assert summarize(HandRange(), [], "manual").weighted_combos == 0


@pytest.mark.parametrize(
    "weights",
    [
        {"AK": 100},
        {"AA": -1},
        {"AA": 101},
        {"AA": 50.5},
        {"AA": True},
        {"ZZ": 10},
    ],
)
def test_rejects_invalid_range_weights(weights: dict) -> None:
    with pytest.raises(ValidationError):
        HandRange(weights=weights)


def test_profiles_have_explicit_assumptions_and_independent_defaults() -> None:
    profiles = default_profiles()
    assert [p.id for p in profiles] == list(ProfileId)
    assert all(not p.solver_backed for p in profiles)
    assert profiles[0].parameters is None and profiles[0].source == "unavailable"
    assert all(p.source == "initial_assumptions" for p in profiles[1:])
    for profile_id in ("tag", "lag", "tp", "lp"):
        assert profile(profile_id).parameters != profile("standard_gto").parameters
    assert len({modeled_range(p).model_dump_json() for p in profiles}) == 5
    assert not modeled_range(profiles[0]).weights
    assert modeled_range(profile(vpip=0, pfr=0)).weights == {}
    assert summarize(modeled_range(profile(vpip=100)), [], "model").weighted_combos == 1326


@pytest.mark.parametrize(
    "changes",
    [
        {"vpip": -1},
        {"vpip": 101},
        {"pfr": 50},
        {"calling_tendency": True},
        {"three_bet": "high"},
        {"unknown": 20},
    ],
)
def test_profile_parameter_validation(changes: dict) -> None:
    values = profile().parameters.model_dump()
    values.update(changes)
    with pytest.raises(ValidationError):
        ProfileParameters(**values)


def test_custom_parameters_update_model_and_gto_remains_unbacked() -> None:
    base = profile()
    custom = profile(vpip=50, pfr=30, bluffing_tendency=80)
    assert modeled_range(custom) != modeled_range(base)
    assert profile().parameters.vpip == 24
    with pytest.raises(ValidationError):
        ProfileConfig(id="standard_gto", parameters=custom.parameters)
    with pytest.raises(ValidationError):
        ProfileConfig(id="unknown")


@pytest.mark.parametrize(
    "changes",
    [
        {"hero_position": "BB"},
        {"hero_cards": ["As"]},
        {"hero_cards": ["As", "As"]},
        {"hero_cards": ["XX", "Ah"]},
        {"board": ["As", "Kd", "Qc"]},
        {"street": "flop"},
        {"pot": -1},
        {"pot": 100.5},
        {"bet_sizes": [True]},
        {"starting_stack_bb": 200},
        {"hero_cards": ["As", "Kd"], "board": ["As", "Qh", "Jc"], "street": "flop"},
    ],
)
def test_spot_validation(changes: dict) -> None:
    values = {"hero_position": "BTN", "opponent_position": "BB", **changes}
    with pytest.raises(ValidationError):
        StudySpot(**values)


def test_board_facts_and_availability() -> None:
    preflop = board_texture([])
    assert preflop.availability == "not_applicable" and preflop.paired is None
    board = board_texture(["As", "Ad", "2s"])
    assert board.availability == "calculated" and board.paired
    assert board.max_suit_count == 2 and board.rank_span == 12
    assert not board_texture(["As", "Kd", "2h"]).paired


def contract_base() -> dict:
    # Synthetic contract fixture only; this is not strategy data.
    return {
        "game_state_id": "synthetic-contract-fixture",
        "legal_actions": ["fold", "call"],
        "source": "test_fixture",
        "calculation_method": "contract test; not a poker calculation",
        "availability": "available",
        "confidence": "validated",
        "assumptions": ["Test only"],
        "explanation": "No production solver data",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"availability": "unavailable", "frequencies": {"fold": 1}},
        {"availability": "model_only", "ev_per_action": {"call": 0}},
        {"confidence": "unvalidated"},
        {"frequencies": {"raise": 1}},
        {"frequencies": {"fold": 0.2, "call": 0.2}},
        {"frequencies": {"fold": -1, "call": 2}},
        {"legal_actions": None, "frequencies": {"fold": 1}},
        {"ev_per_action": {"raise": 0}},
        {"legal_actions": None, "ev_per_action": {"call": 0}},
        {"ev_per_action": {"call": float("nan")}},
        {"hand_equity": 1.1},
    ],
)
def test_strategy_contract_rejects_misleading_results(changes: dict) -> None:
    values = contract_base()
    values.update(changes)
    with pytest.raises(ValidationError):
        StrategyResponse(**values)


def test_provider_interfaces_never_invent_solutions() -> None:
    context = ProviderContext(
        game_state_id="spot", legal_actions=[Action.FOLD, Action.CALL], profile=profile()
    )
    for provider in (PrecomputedGTOProvider(), StatisticalOpponentModel(), CustomCFRProvider()):
        response = provider.analyze(context)
        assert response.game_state_id == "spot"
        assert response.legal_actions == [Action.FOLD, Action.CALL]
        assert (
            response.frequencies is None
            and response.ev_per_action is None
            and response.hand_equity is None
        )
        assert response.assumptions and response.calculation_method
        assert response.availability != "available"
    context.profile = profile("standard_gto")
    assert StatisticalOpponentModel().analyze(context).availability == "unavailable"
    assert PrecomputedGTOProvider().analyze(context).explanation == "GTO solution unavailable"
    valid = StrategyResponse(
        **contract_base(),
        frequencies={"fold": 0.5, "call": 0.5},
        ev_per_action={"call": -2.5},
        hand_equity=0.5,
    )
    assert valid.frequencies[Action.CALL] == 0.5


def test_study_ids_sources_and_manual_ranges() -> None:
    request = StudyRequest()
    first = analyze(request)
    assert analyze(request).game_state_id == first.game_state_id
    assert first.context_source == "hypothetical"
    assert all(p.legal_actions is None for p in first.providers)
    other = StudyRequest(opponent=ProfileConfig(id="lag"))
    assert analyze(other).game_state_id != first.game_state_id
    manual = analyze(
        StudyRequest(
            hero_range=HandRange(weights={"AA": 100}), opponent_range=HandRange(weights={"KK": 50})
        )
    )
    assert manual.hero_range.weighted_combos == 6 and manual.opponent_range.weighted_combos == 3
    assert manual.opponent_range.source == "editable_manual"
    baseline = analyze(StudyRequest(opponent=ProfileConfig(id="standard_gto")))
    assert baseline.opponent_range.weights == {}
    assert baseline.opponent_range.source == "unspecified_no_gto_solution"


def test_api_catalog_study_and_payload_boundaries() -> None:
    client = TestClient(create_app())
    profiles = client.get("/api/profiles")
    assert profiles.status_code == 200 and len(profiles.json()) == 5
    response = client.post("/api/study", json={})
    assert response.status_code == 200
    assert response.json()["providers"][0]["explanation"] == "GTO solution unavailable"
    assert "no-store" in response.headers["cache-control"]
    assert client.post("/api/study", json={"legal_actions": ["raise"]}).status_code == 422
    assert client.post("/api/study", json={"opponent": {"id": "fake"}}).status_code == 422
    assert client.get("/api/study/current").status_code == 404


def test_trainer_configuration_import_and_session_isolation() -> None:
    store = SessionStore(seed_factory=lambda: 42)
    app = create_app(store)
    client, other = TestClient(app), TestClient(app)
    configs = [{"id": value} for value in ("tag", "lag", "tp", "lp", "standard_gto")]
    response = client.post("/api/games", json={"opponents": configs})
    assert response.status_code == 200
    state = response.json()
    assert [p["id"] for p in state["opponents"]] == [p["id"] for p in configs]
    imported = client.get("/api/study/current")
    assert imported.status_code == 200
    result = imported.json()
    assert result["context_source"] == "trainer_snapshot"
    assert result["trainer_hand_id"] == state["hand_id"]
    assert result["trainer_revision"] == state["revision"]
    assert result["spot"]["hero_cards"] == state["players"][0]["cards"]
    assert result["spot"]["board"] == state["board"] and result["spot"]["pot"] == state["pot"]
    assert result["providers"][0]["legal_actions"] == state["legal"]["actions"]
    assert "opponents" not in result and "cards" not in result["opponent"]
    assert other.get("/api/study/current").status_code == 404
    assert client.post("/api/games", json={"opponents": configs[:4]}).status_code == 422
    assert client.post("/api/games", json={"opponents": [{"id": "bogus"}] * 5}).status_code == 422
    assert (
        client.post(
            "/api/games", json={"opponents": [{"id": "standard_gto", "parameters": {}}] * 5}
        ).status_code
        == 422
    )
    # Import is read-only.
    assert client.get("/api/game").json() == state


def test_completed_and_legacy_trainer_hands_can_be_imported() -> None:
    from test_trainer import FoldPolicy, PassivePolicy, finish

    for policy in (FoldPolicy(), PassivePolicy()):
        client = TestClient(create_app(SessionStore(seed_factory=lambda: 42, policy=policy)))
        state = client.post("/api/games", json={}).json()
        state = finish(client, state)
        imported = client.get("/api/study/current")
        assert imported.status_code == 200
        result = imported.json()
        assert result["spot"]["street"] == "complete"
        assert result["spot"]["pot"] == state["settled_pot"]
        assert result["providers"][0]["legal_actions"] == []
        assert result["opponent"]["id"] == "standard_gto"


def test_archetypes_have_distinct_legal_reproducible_behavior() -> None:
    observations = {}
    for profile_id in ("tag", "lag", "tp", "lp"):
        game = Holdem()
        rng, policy = random.Random(7), ProfilePolicy(profile(profile_id))
        samples = [policy.choose(game, rng) for _ in range(2000)]
        assert all(sample.action in game.legal_actions().actions for sample in samples)
        observations[profile_id] = Counter(sample.action for sample in samples)
    assert (
        observations["lag"][Action.RAISE]
        > observations["tag"][Action.RAISE]
        > observations["tp"][Action.RAISE]
    )
    assert observations["lp"][Action.CALL] > observations["tp"][Action.CALL]
    assert len({tuple(sorted(counts.items())) for counts in observations.values()}) == 4
    game = Holdem()
    assert ProfilePolicy(profile("standard_gto")).choose(
        game, random.Random(3)
    ) == RandomPolicy().choose(game, random.Random(3))
    # Full hands across all streets exercise every pressure parameter and preserve chips.
    for profile_id in ("tag", "lag", "tp", "lp"):
        rng, game, policy = random.Random(15), Holdem(seed=3), ProfilePolicy(profile(profile_id))
        while game.actor is not None:
            decision = policy.choose(game, rng)
            game.act(game.actor, decision.action, decision.amount)
        assert sum(p.stack for p in game.players) == 60000


def test_configured_sessions_apply_parameters_and_preserve_them_next_hand() -> None:
    from poker_lab.schemas import HeroAction

    custom = profile("lag", vpip=100, pfr=100, three_bet=100, calling_tendency=100)
    configs = [ProfileConfig(id=custom.id, parameters=custom.parameters)] * 5
    store = SessionStore(seed_factory=lambda: 42)
    token, state = store.create(None, configs)
    assert state.opponents[0].parameters.vpip == 100
    assert any(h.action == Action.RAISE for h in state.history)
    initial_history = [h.model_dump() for h in state.history]
    clone = SessionStore(seed_factory=lambda: 42)
    _, clone_state = clone.create(None, configs)
    assert [h.model_dump() for h in clone_state.history] == initial_history
    while state.actor is not None:
        state = store.act(
            token,
            HeroAction(
                hand_id=state.hand_id,
                revision=state.revision,
                action=Action.CALL if state.legal.to_call else Action.CHECK,
            ),
        )
    _, new = store.create(token)
    assert new.opponents == state.opponents
    assert sum(p.stack for p in new.players) + new.pot == 60000


@pytest.mark.parametrize("street", [Street.FLOP, Street.TURN, Street.RIVER])
def test_profile_policy_postflop_uses_legal_check_bet_call_raise_fold(street: Street) -> None:
    for profile_id in ("tag", "lag", "tp", "lp"):
        game = Holdem()
        while game.street != street:
            game.act(game.actor, Action.CALL if game.legal_actions().to_call else Action.CHECK)
        policy, rng = ProfilePolicy(profile(profile_id)), random.Random(12)
        decisions = [policy.choose(game, rng) for _ in range(500)]
        assert {d.action for d in decisions} == {Action.BET, Action.CHECK}
        assert all(
            d.amount is None
            or game.legal_actions().min_raise_to <= d.amount <= game.legal_actions().max_raise_to
            for d in decisions
        )
        game.act(game.actor, Action.BET, 100)
        decisions = [policy.choose(game, rng) for _ in range(500)]
        assert {d.action for d in decisions} == {Action.CALL, Action.FOLD, Action.RAISE}
