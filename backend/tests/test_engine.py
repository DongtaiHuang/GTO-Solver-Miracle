import random

import pytest

from poker_lab.engine import Holdem
from poker_lab.evaluator import DECK
from poker_lab.models import Action, Street


def finish_checks(game: Holdem) -> None:
    while game.actor is not None:
        legal = game.legal_actions()
        game.act(game.actor, Action.CALL if legal.to_call else Action.CHECK)


def rig(prefix: str) -> list[str]:
    cards = prefix.split()
    return cards + [c for c in DECK if c not in cards]


def test_defaults_and_determinism() -> None:
    a, b = Holdem(seed=42), Holdem(seed=42)
    assert a.players == b.players
    assert a.players != Holdem(seed=43).players
    assert [p.stack for p in a.players] == [10000, 9950, 9900, 10000, 10000, 10000]
    assert a.actor == 3 and a.pot == 150
    assert len({c for p in a.players for c in p.hole}) == 12
    assert a.legal_actions().min_raise_to == 200


def test_progression_and_big_blind_option() -> None:
    g = Holdem()
    for seat in [3, 4, 5, 0, 1]:
        g.act(seat, "call")
    assert g.actor == 2
    g.act(2, "check")
    assert g.street == Street.FLOP and g.actor == 1 and len(g.board) == 3
    assert g.legal_actions().min_raise_to == 100
    g.act(1, "bet", 100)
    assert g.legal_actions().min_raise_to == 200
    finish_checks(g)
    assert len(g.board) == 5 and len(g.burned) == 3
    assert g.street == Street.COMPLETE and g.pot == 0
    assert sum(p.stack for p in g.players) == 60000
    assert not g.legal_actions().actions


def test_fold_win_without_board() -> None:
    g = Holdem()
    for seat in [3, 4, 5, 0, 1]:
        g.act(seat, "fold")
    assert g.street == Street.COMPLETE and not g.board
    assert g.players[2].stack == 10050
    assert sum(p.stack for p in g.players) == 60000


def test_heads_up_position_and_raise_size() -> None:
    g = Holdem(seats=2, button=1)
    assert g.actor == 1
    g.act(1, "raise", 300)
    assert g.legal_actions().min_raise_to == 500
    g.act(0, "call")
    assert g.actor == 0 and g.street == Street.FLOP
    finish_checks(g)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seats": 1},
        {"seats": 7},
        {"seats": True},
        {"button": 6},
        {"big_blind": 3},
        {"big_blind": True},
        {"stacks": [1]},
        {"stacks": [100, 100, 100, 100, 100, False]},
        {"deck": ["As"] * 52},
    ],
)
def test_invalid_setup(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        Holdem(**kwargs)


@pytest.mark.parametrize(
    "seat,action,amount",
    [
        (0, "call", None),
        (3, "check", None),
        (3, "bet", 200),
        (3, "raise", 199),
        (3, "raise", 10001),
        (3, "raise", 200.0),
        (3, "raise", None),
        (3, "call", 100),
        (3, "unknown", None),
    ],
)
def test_rejects_actions_atomically(seat: int, action: str, amount: int | None) -> None:
    g = Holdem()
    before = repr(g.__dict__)
    with pytest.raises(ValueError):
        g.act(seat, action, amount)
    assert repr(g.__dict__) == before


def test_short_all_in_does_not_reopen() -> None:
    g = Holdem(seats=3, stacks=[1000, 150, 1000])
    g.act(0, "call")
    g.act(1, "all_in")
    assert g.current_bet == 150 and g.last_full_raise == 100
    g.act(2, "call")
    assert g.actor == 0
    assert Action.RAISE not in g.legal_actions().actions
    assert Action.ALL_IN not in g.legal_actions().actions
    g.act(0, "call")
    assert g.street == Street.FLOP
    finish_checks(g)


def test_full_raise_reopens_and_unacted_player_can_raise() -> None:
    g = Holdem(seats=3, stacks=[1000, 150, 1000])
    g.act(0, "call")
    g.act(1, "all_in")
    assert g.legal_actions().min_raise_to == 250
    g.act(2, "raise", 250)
    assert Action.RAISE in g.legal_actions().actions
    g.act(0, "raise", 350)
    finish_checks(g)


def test_cumulative_short_raises_reopen() -> None:
    g = Holdem(seats=4, stacks=[150, 200, 1000, 1000])
    g.act(3, "call")
    g.act(0, "all_in")
    g.act(1, "all_in")
    g.act(2, "call")
    assert g.actor == 3 and Action.RAISE in g.legal_actions().actions
    g.act(3, "raise", 300)
    finish_checks(g)


def test_side_pots_and_uncalled_excess() -> None:
    # Seat 0 AA, seat 1 KK, seat 2 QQ; board cannot improve either loser.
    g = Holdem(
        seats=3, stacks=[100, 300, 200], deck=rig("Ks Qs As Kh Qh Ah 9c 2c 3d 7h 8c 8s Tc Jd")
    )
    g.act(0, "all_in")
    g.act(1, "all_in")
    g.act(2, "all_in")
    assert [a.pot.amount for a in g.awards] == [300, 200, 100]
    assert [p.stack for p in g.players] == [300, 300, 0]
    with pytest.raises(ValueError):
        g.act(0, "check")


def test_folded_money_and_odd_chips() -> None:
    # Royal flush on the board ties seats 1 and 2; seat 0's 101 stays in pot.
    g = Holdem(seats=3, deck=rig("2c 3c 4c 5c 6c 7c 8c Ts Js Qs 9c Ks 9d As"))
    g.act(0, "raise", 201)
    g.act(1, "call")
    g.act(2, "call")
    g.act(1, "bet", 100)
    g.act(2, "call")
    g.act(0, "fold")
    finish_checks(g)
    assert [p.stack for p in g.players] == [9799, 10101, 10100]
    assert g.awards[0].winners == (1, 2)
    assert g.awards[0].pot.amount == 603


def test_short_call_and_automatic_runout() -> None:
    g = Holdem(seats=2, stacks=[60, 1000])
    assert g.legal_actions().to_call == 10
    g.act(0, "call")
    assert g.street == Street.COMPLETE and len(g.board) == 5
    assert sum(p.stack for p in g.players) == 1060
    g = Holdem(seats=2, stacks=[10, 20])
    assert g.street == Street.COMPLETE


def test_all_in_call_below_current_bet() -> None:
    g = Holdem(seats=3, stacks=[80, 1000, 1000])
    g.act(0, "all_in")
    g.act(1, "call")
    g.act(2, "check")
    finish_checks(g)
    assert sum(p.stack for p in g.players) == 2080


def test_seeded_random_legal_games_conserve_chips() -> None:
    rng = random.Random(2026)
    for seed in range(150):
        g = Holdem(seed=seed, button=seed % 6, stacks=[rng.randint(1, 10000) for _ in range(6)])
        turns = 0
        while g.actor is not None:
            assert sum(p.stack for p in g.players) + g.pot == g.initial_chips
            assert all(p.stack >= 0 for p in g.players)
            legal = g.legal_actions()
            action = rng.choice(legal.actions)
            amount = None
            if action in (Action.BET, Action.RAISE):
                amount = rng.randint(legal.min_raise_to, legal.max_raise_to)
            g.act(g.actor, action, amount)
            turns += 1
            assert turns < 200
        assert sum(p.stack for p in g.players) == g.initial_chips
        assert sum(a.pot.amount for a in g.awards) == sum(
            chips for a in g.awards for _, chips in a.payouts
        )
