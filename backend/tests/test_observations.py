import math

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_trainer import PassivePolicy, finish, make_store

from poker_lab.analyzer import Hand
from poker_lab.api import create_app
from poker_lab.observations import (
    Archive,
    Entry,
    Rules,
    SummaryRequest,
    classify,
    interval,
    metric,
    opportunities,
    report,
)


def hand(actions, board=(), stacks=None):
    return Hand.model_validate(
        {
            "version": "1.0",
            "hero": "BTN",
            "small_blind": 50,
            "big_blind": 100,
            "seats": {
                p: {"name": "Sam", "stack": (stacks or {}).get(p, 10000)}
                for p in ("UTG", "HJ", "CO", "BTN", "SB", "BB")
            },
            "board": board,
            "actions": [
                {"position": p, "action": a, "amount": amount, "street": street}
                for street, p, a, amount in actions
            ],
        }
    )


def pre(*actions):
    return [("preflop", *a) for a in actions]


def test_walk_and_unfinished_preflop():
    folds = pre(*[(p, "fold", None) for p in ("UTG", "HJ", "CO", "BTN", "SB")])
    stats = opportunities(hand(folds))
    assert all(
        s["vpip"] == [False] and s["pfr"] == [False] and not s["three_bet"] for s in stats.values()
    )
    partial = opportunities(hand(folds[:1]))
    assert partial["UTG"]["vpip"] == [False] and partial["BB"]["vpip"] == []


def test_threebet_opportunities_and_opener_fold():
    actions = pre(
        ("UTG", "raise", 250),
        ("HJ", "call", 250),
        ("CO", "raise", 750),
        ("BTN", "fold", None),
        ("SB", "fold", None),
        ("BB", "fold", None),
        ("UTG", "fold", None),
        ("HJ", "fold", None),
    )
    s = opportunities(hand(actions))
    assert s["HJ"]["vpip"] == [True] and s["HJ"]["pfr"] == [False]
    assert s["HJ"]["three_bet"] == [False] and s["CO"]["three_bet"] == [True]
    assert s["UTG"]["fold_to_three_bet"] == [True] and not s["HJ"]["fold_to_three_bet"]
    assert s["CO"]["pfr"] == [True] and not s["BTN"]["three_bet"]
    actions = actions[:3] + pre(
        ("BTN", "raise", 1800), ("SB", "fold", None), ("BB", "fold", None), ("UTG", "fold", None)
    )
    assert not opportunities(hand(actions))["UTG"]["fold_to_three_bet"]


def test_short_shove_is_not_full_threebet_and_short_call_is_passive():
    s = opportunities(
        hand(
            pre(("UTG", "raise", 250), ("HJ", "all_in", 300), ("CO", "all_in", 200)),
            stacks={"HJ": 300, "CO": 200},
        )
    )
    assert not s["HJ"]["three_bet"] and s["HJ"]["pfr"] == [True]
    assert s["CO"]["vpip"] == [True] and s["CO"]["pfr"] == [False]


def multi():
    return pre(
        ("UTG", "raise", 250),
        ("HJ", "fold", None),
        ("CO", "fold", None),
        ("BTN", "call", 250),
        ("SB", "fold", None),
        ("BB", "call", 150),
    )


def test_multiway_cbet_folds_and_later_opportunities():
    actions = multi() + [
        ("flop", "BB", "check", None),
        ("flop", "UTG", "bet", 350),
        ("flop", "BTN", "fold", None),
        ("flop", "BB", "call", 350),
        ("turn", "BB", "check", None),
        ("turn", "UTG", "check", None),
        ("river", "BB", "bet", 700),
        ("river", "UTG", "fold", None),
    ]
    s = opportunities(hand(actions, ["Kd", "2s", "7h", "Tc", "9d"]))
    assert s["UTG"]["flop_cbet"] == [True] and s["BTN"]["fold_to_flop_cbet"] == [True]
    assert s["BB"]["fold_to_flop_cbet"] == [False] and s["BB"]["postflop_call"] == [True]
    assert s["UTG"]["vpip"] == [True] and s["UTG"]["pfr"] == [True]
    assert s["BB"]["turn_aggression"] == [False] and s["BB"]["river_aggression"] == [True]
    assert s["UTG"]["postflop_fold"] == [True] and not s["BTN"]["turn_aggression"]
    assert not s["HJ"]["postflop_fold"]


def test_flop_lead_check_and_raise_boundaries():
    board = ["Kd", "2s", "7h"]
    s = opportunities(
        hand(multi() + [("flop", "BB", "bet", 350), ("flop", "UTG", "raise", 750)], board)
    )
    assert not s["UTG"]["flop_cbet"]
    s = opportunities(
        hand(multi() + [("flop", "BB", "check", None), ("flop", "UTG", "check", None)], board)
    )
    assert s["UTG"]["flop_cbet"] == [False]
    s = opportunities(
        hand(
            multi()
            + [
                ("flop", "BB", "check", None),
                ("flop", "UTG", "bet", 350),
                ("flop", "BTN", "raise", 800),
                ("flop", "BB", "fold", None),
            ],
            board,
        )
    )
    assert s["BTN"]["fold_to_flop_cbet"] == [False] and not s["BB"]["fold_to_flop_cbet"]


def test_beta_intervals_and_zero_sample():
    assert metric(0, 0).estimate is None and metric(0, 0).interval is None
    one = metric(1, 1)
    assert one.observed == 1 and one.estimate == pytest.approx(2 / 3) and not one.sufficient
    assert one.interval == pytest.approx((math.sqrt(0.025), math.sqrt(0.975)))
    assert interval(0, 1) == pytest.approx(tuple(1 - x for x in reversed(one.interval)))
    lo, hi = interval(2000, 4000)
    assert 0.48 < lo < 0.5 < hi < 0.52


@pytest.mark.parametrize(
    "v,r,label", [(10, 8, "tag"), (40, 35, "lag"), (10, 1, "tp"), (40, 10, "lp")]
)
def test_explainable_configurable_classification(v, r, label):
    stats = {"vpip": metric(v, 100), "pfr": metric(r, 100)}
    result, reason = classify(stats, Rules())
    assert result == label and "raise participation" in reason
    assert classify(stats, Rules(minimum_hands=120))[0] is None


def test_identity_across_positions_separate_names_and_override():
    h = hand(pre(("UTG", "fold", None)))
    a = Entry(hand_id="h1", source="manual", mapping={"UTG": "player-a", "BB": "player-b"}, hand=h)
    b = Entry(
        hand_id="h2",
        source="manual",
        mapping={"BB": "player-a"},
        hand=hand(multi(), ["Kh", "2s", "3c"]),
    )
    archive = Archive(version="1.0", entries=[a, b])
    result = report(SummaryRequest(archive=archive))
    assert len(result) == 2 and result[0].hands == 2 and result[1].hands == 1
    m = result[0].metrics["vpip"]
    assert m.opportunities == 2 and m.successes == 1
    archive.overrides["player-a"] = "lp"
    changed = report(SummaryRequest(archive=archive))[0]
    assert (
        changed.metrics == result[0].metrics
        and changed.override == "lp"
        and changed.provisional is None
    )
    for duplicate in (a, a.model_copy(update={"hand_id": "new-ref"})):
        archive.entries.append(duplicate)
        with pytest.raises(ValueError, match="Duplicate"):
            report(SummaryRequest(archive=archive))
        archive.entries.pop()


def test_invalid_import_and_no_cards():
    h = hand(pre(("UTG", "fold", None)))
    a = Entry(hand_id="h1", source="manual", mapping={"UTG": "p", "BB": "p"}, hand=h)

    def validate():
        report(SummaryRequest(archive=Archive(version="1.0", entries=[a])))

    with pytest.raises(ValueError, match="distinct"):
        validate()
    a.mapping.pop("BB")
    h.seats["BB"].cards = ("As", "Ad")
    with pytest.raises(ValueError, match="private cards"):
        validate()
    with pytest.raises(ValidationError):
        Archive.model_validate({"version": "2", "entries": []})
    with pytest.raises(ValidationError):
        Archive(version="1.0", entries=[a] * 129)


def test_completed_trainer_packet_is_stable_and_session_owned():
    app = create_app(make_store(policy=PassivePolicy()))
    owner, other = TestClient(app), TestClient(app)
    initial = owner.post("/api/games", json={}).json()
    assert initial["observation"] is None
    final = finish(owner, initial)
    packet = final["observation"]
    assert (
        packet == owner.get("/api/game").json()["observation"]
        and packet["hand_id"] == final["hand_id"]
    )
    assert all(s["cards"] is None for s in packet["hand"]["seats"].values())
    assert other.get("/api/game").status_code == 404
    archive = {"version": "1.0", "entries": [packet]}
    result = owner.post("/api/observations/report", json={"archive": archive}).json()
    assert len(result) == 6 and all(r["source"] == "trainer" and r["hands"] == 1 for r in result)
    assert (
        other.post(
            "/api/observations/report", json={"archive": {"version": "1.0", "entries": []}}
        ).json()
        == []
    )


def test_capped_shove_against_short_blinds_is_a_call():
    history = hand(pre(("UTG", "all_in", 75)), stacks={"BB": 40, "UTG": 75})
    facts = opportunities(history)["UTG"]
    assert facts["vpip"] == [True] and facts["pfr"] == [False]
