import random
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from poker_lab.api import COOKIE, create_app
from poker_lab.engine import Holdem
from poker_lab.models import Action, Street
from poker_lab.policy import Decision, RandomPolicy
from poker_lab.schemas import HeroAction
from poker_lab.trainer import MissingSession, SessionStore, StaleHand, view


class PassivePolicy:
    def choose(self, game: Holdem, rng: random.Random) -> Decision:
        return Decision(Action.CALL if game.legal_actions().to_call else Action.CHECK)


class FoldPolicy:
    def choose(self, game: Holdem, rng: random.Random) -> Decision:
        return Decision(Action.FOLD)


def make_store(**kwargs) -> SessionStore:
    return SessionStore(seed_factory=lambda: 42, **kwargs)


def action_payload(state: dict, action: str, **kwargs) -> dict:
    return {"hand_id": state["hand_id"], "revision": state["revision"], "action": action, **kwargs}


def finish(client: TestClient, state: dict) -> dict:
    for _ in range(100):
        if state["street"] == "complete":
            return state
        action = "call" if state["legal"]["to_call"] else "check"
        result = client.post("/api/game/actions", json=action_payload(state, action))
        assert result.status_code == 200, result.text
        state = result.json()
    pytest.fail("Hand failed to terminate")


def test_session_cookie_filtered_state_and_reload() -> None:
    store = make_store()
    client = TestClient(create_app(store))
    response = client.post("/api/games", json={})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api" in cookie
    assert "no-store" in response.headers["cache-control"]
    state = response.json()
    assert state["hero"] == 0 and state["actor"] == 0 and len(state["players"]) == 6
    assert len(state["players"][0]["cards"]) == 2
    assert all(p["cards"] is None for p in state["players"][1:])
    assert not {"deck", "seed", "rng", "burned", "hole"} & state.keys()
    assert client.get("/api/game").json() == state
    assert [h["sequence"] for h in state["history"]] == list(range(1, len(state["history"]) + 1))


def test_two_clients_cannot_access_each_others_state() -> None:
    app = create_app(make_store())
    alice, bob = TestClient(app), TestClient(app)
    state = alice.post("/api/games", json={}).json()
    assert bob.get("/api/game").status_code == 404
    assert bob.post("/api/game/actions", json=action_payload(state, "fold")).status_code == 404
    bob_state = bob.post("/api/games", json={}).json()
    assert state["hand_id"] != bob_state["hand_id"]
    assert alice.cookies.get(COOKIE) != bob.cookies.get(COOKIE)
    assert bob.post("/api/game/actions", json=action_payload(state, "fold")).status_code == 409
    assert alice.get("/api/game").json() == state
    bob.cookies.set(COOKIE, "forged")
    assert bob.get("/api/game").status_code == 404


@pytest.mark.parametrize(
    "extra",
    [
        {"seed": 42},
        {"stacks": [99999] * 6},
        {"cards": ["As", "Ah"]},
        {"pot": 9999},
    ],
)
def test_creation_rejects_client_controlled_state(extra: dict) -> None:
    client = TestClient(create_app(make_store()))
    assert client.post("/api/games", json=extra).status_code == 422


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"action": "raise", "amount": 1}, 400),
        ({"action": "raise", "amount": 10001}, 400),
        ({"action": "raise", "amount": 200.5}, 422),
        ({"action": "raise", "amount": True}, 422),
        ({"action": "raise"}, 400),
        ({"action": "call", "amount": 100}, 400),
        ({"action": "check"}, 400),
        ({"action": "invalid"}, 422),
        ({"action": "fold", "stack": 999999}, 422),
        ({"action": "fold", "revision": -1}, 422),
        ({"action": "fold", "hand_id": "old"}, 409),
    ],
)
def test_illegal_actions_leave_state_unchanged(changes: dict, status: int) -> None:
    client = TestClient(create_app(make_store(policy=PassivePolicy())))
    state = client.post("/api/games", json={}).json()
    payload = action_payload(state, "call")
    payload.update(changes)
    assert client.post("/api/game/actions", json=payload).status_code == status
    assert client.get("/api/game").json() == state


def test_complete_hand_showdown_and_rotating_new_hand() -> None:
    client = TestClient(create_app(make_store(policy=PassivePolicy())))
    initial = client.post("/api/games", json={}).json()
    assert client.post("/api/games", json={}).status_code == 409
    state = finish(client, initial)
    assert state["showdown"] and len(state["board"]) == 5
    assert state["actor"] is None and not state["legal"]["actions"]
    assert all(len(p["cards"]) == 2 for p in state["players"])
    assert sum(p["stack"] for p in state["players"]) == 60000
    assert sum(o["pot"] for o in state["outcomes"]) == state["settled_pot"] == 600
    assert [h["street"] for h in state["history"] if h["action"] == "deal"] == [
        "flop",
        "turn",
        "river",
    ]
    assert client.post("/api/game/actions", json=action_payload(state, "check")).status_code == 409
    new = client.post("/api/games", json={}).json()
    assert new["hand_id"] != initial["hand_id"] and new["hand_number"] == 2
    assert new["button"] == 1
    assert sum(p["stack"] for p in new["players"]) + new["pot"] == 60000
    assert all(p["cards"] is None for p in new["players"][1:])


def test_folded_cards_stay_hidden_at_showdown() -> None:
    client = TestClient(create_app(make_store(policy=PassivePolicy())))
    initial = client.post("/api/games", json={}).json()
    result = client.post("/api/game/actions", json=action_payload(initial, "fold")).json()
    assert result["street"] == "complete" and result["showdown"]
    assert result["players"][0]["status"] == "folded"
    assert all(p["cards"] for p in result["players"][1:])
    # Folded opponents are never revealed, even when other players reach showdown.
    store = make_store(policy=PassivePolicy())
    token, state = store.create(None)
    game = store.sessions[token].game
    game.players[3].folded = True
    client = TestClient(create_app(store))
    client.cookies.set(COOKIE, token)
    result = finish(client, state.model_dump())
    assert result["players"][3]["cards"] is None


def test_uncontested_pot_never_reveals_opponents() -> None:
    client = TestClient(create_app(make_store(policy=FoldPolicy())))
    initial = client.post("/api/games", json={}).json()
    result = client.post("/api/game/actions", json=action_payload(initial, "call")).json()
    assert result["street"] == "complete" and not result["showdown"]
    assert result["board"] == []
    assert all(p["cards"] is None for p in result["players"][1:])
    assert result["history"][-1]["action"] == "uncontested"
    assert result["outcomes"][0]["winners"] == [0]


def test_all_in_records_original_chips_and_runs_out() -> None:
    client = TestClient(create_app(make_store(policy=PassivePolicy())))
    state = client.post("/api/games", json={}).json()
    result = client.post("/api/game/actions", json=action_payload(state, "all_in")).json()
    assert result["street"] == "complete"
    assert len(result["board"]) == 5 and result["pot"] == 0
    hero_action = next(h for h in result["history"] if h["seat"] == 0)
    assert hero_action["chips"] == 10000 and hero_action["raise_to"] == 10000
    assert sum(p["stack"] for p in result["players"]) == 60000


def test_server_presets_match_engine_legal_ranges_and_pot_after_call() -> None:
    store = make_store(policy=PassivePolicy())
    token, state = store.create(None)
    assert state.pot == 450 and state.legal.to_call == 100
    assert state.legal.presets == {"33": 281, "50": 375, "75": 512, "100": 650}
    for target in state.legal.presets.values():
        assert state.legal.min_raise_to <= target <= state.legal.max_raise_to
    state = store.act(
        token, HeroAction(hand_id=state.hand_id, revision=state.revision, action=Action.CALL)
    )
    assert state.street == Street.FLOP
    assert state.legal.presets["100"] == state.pot
    for target in state.legal.presets.values():
        clone = make_store()
        clone.sessions[token] = deepcopy(store.sessions[token])
        clone.act(
            token,
            HeroAction(
                hand_id=state.hand_id, revision=state.revision, action=Action.BET, amount=target
            ),
        )


def test_stale_and_concurrent_requests_only_act_once() -> None:
    store = make_store(policy=PassivePolicy())
    token, state = store.create(None)
    request = HeroAction(hand_id=state.hand_id, revision=0, action=Action.CALL)

    def act_once() -> str:
        try:
            store.act(token, request)
            return "ok"
        except StaleHand:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: act_once(), range(2))) == ["ok", "stale"]
    assert store.get(token).revision == 1


def test_expiration_capacity_and_secure_cookie(monkeypatch) -> None:
    now = [0.0]
    store = make_store(clock=lambda: now[0], ttl=10, capacity=1, policy=FoldPolicy())
    app = create_app(store)
    first, second = TestClient(app), TestClient(app)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    first = TestClient(app, base_url="https://testserver")
    created = first.post("/api/games", json={})
    assert "Secure" in created.headers["set-cookie"]
    assert second.post("/api/games", json={}).status_code == 503
    now[0] = 11
    assert first.get("/api/game").status_code == 404
    assert second.post("/api/games", json={}).status_code == 200
    with pytest.raises(MissingSession):
        store.get("missing")


def test_csrf_and_content_type_guard(monkeypatch) -> None:
    client = TestClient(create_app(make_store()))
    assert (
        client.post("/api/games", json={}, headers={"origin": "https://evil.example"}).status_code
        == 403
    )
    assert client.post("/api/games", content="{}").status_code == 415
    assert (
        client.post("/api/games", json={}, headers={"origin": "http://localhost:3000"}).status_code
        == 200
    )
    monkeypatch.setenv("TRAINER_ORIGIN", "https://poker.example")
    assert (
        TestClient(create_app(make_store()))
        .post("/api/games", json={}, headers={"origin": "https://poker.example"})
        .status_code
        == 200
    )


def test_policy_seed_reproducibility_and_legal_actions() -> None:
    snapshots = []
    for _ in range(2):
        store = make_store()
        token, state = store.create(None)
        while state.actor is not None:
            action = Action.CALL if state.legal.to_call else Action.CHECK
            state = store.act(
                token, HeroAction(hand_id=state.hand_id, revision=state.revision, action=action)
            )
        snapshots.append(state.model_dump(exclude={"hand_id"}))
    assert snapshots[0] == snapshots[1]
    observed = set()
    for seed in range(50):
        rng, game, policy = random.Random(seed), Holdem(seed=seed), RandomPolicy()
        while game.actor is not None:
            decision = policy.choose(game, rng)
            assert decision.action in game.legal_actions().actions
            observed.add(decision.action)
            game.act(game.actor, decision.action, decision.amount)
        assert sum(p.stack for p in game.players) == 60000
    assert {Action.FOLD, Action.CALL, Action.CHECK, Action.BET, Action.RAISE} <= observed


def test_transaction_rolls_back_on_opponent_failure() -> None:
    class BrokenPolicy:
        def choose(self, game: Holdem, rng: random.Random) -> Decision:
            return Decision(Action.RAISE, 1)

    store = make_store(policy=PassivePolicy())
    token, state = store.create(None)
    store.policy = BrokenPolicy()
    with pytest.raises(ValueError):
        store.act(
            token, HeroAction(hand_id=state.hand_id, revision=0, action=Action.RAISE, amount=300)
        )
    assert store.get(token) == state


def test_snapshot_short_all_in_and_side_pots() -> None:
    store = make_store(policy=PassivePolicy())
    token, _ = store.create(None)
    session = store.sessions[token]
    session.game = Holdem(stacks=[100, 200, 300, 400, 500, 600])
    store._opponents(session)
    state = view(session)
    assert "all_in" in state.legal.actions and state.legal.min_raise_to is None
    state = store.act(token, HeroAction(hand_id=state.hand_id, revision=0, action=Action.ALL_IN))
    assert state.street == Street.COMPLETE
    assert sum(p.stack for p in state.players) == 2100
    assert len(state.outcomes) >= 1
