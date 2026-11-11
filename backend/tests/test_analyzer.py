import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_trainer import PassivePolicy, finish, make_store

from poker_lab.analyzer import Hand, replay
from poker_lab.api import create_app
from poker_lab.strategy_catalog import configured_catalog

catalog = configured_catalog(None)
sources = [(e.document.solution_id, e.document.scenario) for e in catalog.visible("validated_gto")]
node = next(s for k, s in sources if k == "river-550-bb-v1")


def event(pos, action, amount=None, street="preflop"):
    return {"position": pos, "action": action, "amount": amount, "street": street}


def sample():
    return {
        "version": "1.0",
        "hero": "BTN",
        "small_blind": 50,
        "big_blind": 100,
        "initial_pot": 150,
        "seats": {
            p: {
                "name": p,
                "stack": stack,
                "cards": {"BTN": ["Ac", "Ad"], "BB": ["Kh", "Qh"]}.get(p),
            }
            for p, stack in node.starting_stacks.items()
        },
        "board": list(node.board),
        "actions": [e.model_dump(mode="json") for e in node.history]
        + [event("BB", "call", 550, "river")],
    }


def test_complete_replay_and_exact_decisions():
    hand = Hand.model_validate(sample())
    states = replay(hand, sources)
    assert states == replay(hand, sources)
    assert len(states) == len(hand.actions) + 1
    for s, e in zip(states, hand.actions, strict=False):
        assert s.actor == e.position and s.street == e.street and e.action in s.legal.actions
        assert s.players["BB"].cards is None
        assert len(s.board) == {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[s.street]
    assert states[-2].candidates == ["river-550-bb-v1"]
    assert states[-2].odds == pytest.approx(1 / 3)
    assert states[-1].payouts == {"BTN": 1650} and states[-1].players["BB"].cards == ("Kh", "Qh")
    changed = sample()
    changed["board"] = [*node.board[:-1], "8d"]
    assert not replay(Hand.model_validate(changed), sources)[-2].candidates


def test_unknown_cards_and_partial_history():
    raw = sample()
    raw["seats"]["BB"]["cards"] = None
    last = replay(Hand.model_validate(raw), [])[-1]
    assert last.pending_award and last.pot == 1650 and not last.payouts
    raw["actions"] = raw["actions"][:6]
    raw["board"] = []
    last = replay(Hand.model_validate(raw), [])[-1]
    assert last.street == "flop" and not last.board_complete and not last.board
    raw["actions"].append(event("BB", "check", street="flop"))
    with pytest.raises(ValueError):
        replay(Hand.model_validate(raw), [])


@pytest.mark.parametrize(
    "change", ["duplicate", "turn", "minimum", "pot", "payout", "unknown", "version"]
)
def test_reject_invalid(change):
    raw = sample()
    if change == "duplicate":
        raw["board"][0] = "Ac"
    elif change == "turn":
        raw["actions"][0]["position"] = "BTN"
    elif change == "minimum":
        raw["actions"][3]["amount"] = 150
    elif change == "pot":
        raw["initial_pot"] = 999
    elif change == "payout":
        raw["payouts"] = {"BB": 1650}
    elif change == "unknown":
        raw["seed"] = 1
    else:
        raw["version"] = "2"
    with pytest.raises((ValueError, ValidationError)):
        replay(Hand.model_validate(raw), [])


def test_split_side_pots_after_all_ins():
    raw = sample()
    raw["board"] = ["Ts", "Js", "Qs", "Ks", "As"]
    raw["seats"]["BTN"]["stack"] = 100
    raw["seats"]["SB"].update(stack=300, cards=["3h", "4h"])
    raw["seats"]["BB"]["stack"] = 200
    raw["actions"] = [event(p, "fold") for p in ("UTG", "HJ", "CO")] + [
        event("BTN", "all_in", 100),
        event("SB", "all_in", 300),
        event("BB", "all_in", 200),
    ]
    last = replay(Hand.model_validate(raw), [])[-1]
    assert last.payouts == {"BTN": 100, "SB": 300, "BB": 200}


def test_trainer_export_is_session_owned_and_replays():
    app = create_app(make_store(policy=PassivePolicy()))
    owner, other = TestClient(app), TestClient(app)
    state = owner.post("/api/games", json={}).json()
    assert owner.get("/api/analyzer/trainer").status_code == 400
    final = finish(owner, state)
    assert other.get("/api/analyzer/trainer").status_code == 404
    raw = owner.get("/api/analyzer/trainer").json()
    for player in final["players"]:
        assert raw["seats"][player["position"]]["cards"] == player["cards"]
    response = owner.post("/api/analyzer/replay", json=raw)
    assert response.status_code == 200, response.text
    for player in final["players"]:
        assert response.json()[-1]["players"][player["position"]]["stack"] == player["stack"]


def test_short_call_odds_exclude_ineligible_side_pot():
    raw = sample()
    raw["seats"]["HJ"]["stack"] = 100
    raw["actions"] = [event("UTG", "raise", 500)]
    decision = replay(Hand.model_validate(raw), [])[-1]
    assert decision.legal.to_call == 100
    assert decision.odds == pytest.approx(100 / 350)
