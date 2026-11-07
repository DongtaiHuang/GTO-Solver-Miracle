import math
import random

import pytest

import poker_lab.equity as module
from poker_lab.equity import (
    PlayerInput,
    WorkLimit,
    calculate_equity,
    expand_range,
    pot_odds,
)
from poker_lab.evaluator import DECK
from poker_lab.ranges import CLASSES

BOARD = ("2c", "3d", "7h", "8c", "Jd")
AA = PlayerInput(cards=("As", "Ah"))
KK = PlayerInput(cards=("Ks", "Kh"))


@pytest.mark.parametrize(
    "hero,opponent,board",
    [
        (("As", "Ah"), ("Ks", "Kh"), BOARD),
        (("As", "Ks"), ("9s", "8s"), ("Qs", "Js", "Ts", "2d", "3c")),
        (("Ah", "4c"), ("Ks", "Kh"), ("As", "Ad", "Ac", "2h", "3d")),
        (("As", "Ah"), ("Ks", "Kh"), ("2c", "3d", "4h", "5s", "9c")),
    ],
)
def test_exact_river_winner_and_edge_cases(hero, opponent, board) -> None:
    result = calculate_equity([PlayerInput(cards=hero), PlayerInput(cards=opponent)], board=board)
    assert result.method == "exact" and result.evaluated_outcomes == 1
    assert result.players[0].win_probability == result.players[0].equity == 1
    assert result.players[1].loss_probability == 1
    assert (
        result.players[0].uncertainty is None
        and result.valid_samples is None
        and result.seed is None
    )


def test_exact_turn_and_flop_closed_form_fixture() -> None:
    # AA loses on the turn only to the two remaining kings (2 / 44).
    turn = calculate_equity([AA, KK], board=BOARD[:4], method="exact")
    assert turn.evaluated_outcomes == 44
    assert turn.players[0].equity == pytest.approx(42 / 44)
    # On this flop KK wins with at least one king and no ace: 87 - 4 = 83 of 990.
    flop = calculate_equity([AA, KK], board=BOARD[:3])
    assert flop.evaluated_outcomes == 990
    assert flop.players[0].win_probability == pytest.approx(907 / 990)
    assert flop.players[0].tie_probability == 0


@pytest.mark.parametrize("players", [2, 3, 6])
def test_shared_royal_flush_splits_fractionally(players: int) -> None:
    hands = [PlayerInput(cards=(rank + "c", rank + "d")) for rank in "234567"[:players]]
    result = calculate_equity(hands, board=("Ts", "Js", "Qs", "Ks", "As"))
    assert sum(p.equity for p in result.players) == pytest.approx(1)
    for player in result.players:
        assert player.win_probability == 0 and player.tie_probability == 1
        assert player.equity == pytest.approx(1 / players)


def test_exact_weighted_hand_range_and_weight_scaling() -> None:
    # With AsAh fixed, the range has 1 AA combo (tie) and 6 KK combos (hero wins).
    result = calculate_equity([AA, PlayerInput(weights={"AA": 100, "KK": 50})], board=BOARD)
    assert result.unblocked_combinations == (1, 7) and result.evaluated_outcomes == 7
    assert result.players[0].tie_probability == pytest.approx(0.25)
    assert result.players[0].win_probability == pytest.approx(0.75)
    assert result.players[0].equity == pytest.approx(0.875)
    scaled = calculate_equity([AA, PlayerInput(weights={"AA": 20, "KK": 10})], board=BOARD)
    assert scaled.players == result.players


def test_joint_range_distribution_conditions_product_weights_on_disjointness() -> None:
    players = [PlayerInput(weights={"AA": 100, "KK": 100}), PlayerInput(weights={"AA": 100})]
    exact = calculate_equity(players, board=BOARD)
    # Six disjoint AA-v-AA assignments tie; 36 KK-v-AA assignments lose.
    # Naive hero-first sampling would incorrectly make half the assignments ties.
    assert exact.evaluated_outcomes == 42
    assert exact.players[0].tie_probability == pytest.approx(1 / 7)
    assert exact.players[0].equity == pytest.approx(1 / 14)
    mc = calculate_equity(players, board=BOARD, method="monte_carlo", samples=4000, seed=18)
    assert (
        mc.players[0].uncertainty.lower
        <= exact.players[0].equity
        <= mc.players[0].uncertainty.upper
    )
    assert mc.proposals > mc.valid_samples == 4000
    tie = mc.players[0].tie_probability
    assert mc.players[0].uncertainty.standard_error == pytest.approx(
        0.5 * math.sqrt(tie * (1 - tie) / 3999)
    )


def test_blockers_remove_specific_combinations_without_renormalizing_class_weights() -> None:
    assert len(expand_range({"AA": 100})) == 6
    assert len(expand_range({"AKs": 100})) == 4
    assert len(expand_range({"AKo": 100})) == 12
    assert len(expand_range({"AA": 100}, ["As"])) == 3
    assert len(expand_range({"AKs": 100}, ["As"])) == 3
    assert len(expand_range({"AKo": 100}, ["As"])) == 9
    result = calculate_equity(
        [PlayerInput(weights={"AA": 100}), PlayerInput(weights={"KK": 100})],
        board=BOARD,
        dead=("As",),
    )
    assert result.unblocked_combinations == (3, 6)
    assert result.players[0].equity == 1


def test_preflop_sampling_is_reproducible_and_does_not_touch_global_rng() -> None:
    before = random.getstate()
    first = calculate_equity([AA, KK], samples=1000, seed=923)
    second = calculate_equity([AA, KK], samples=1000, seed=923)
    assert first == second and random.getstate() == before
    assert first.method == "monte_carlo" and first.valid_samples == first.evaluated_outcomes == 1000
    assert first.seed == 923
    for player in first.players:
        assert (
            player.win_probability + player.tie_probability + player.loss_probability
            == pytest.approx(1)
        )
        assert 0 <= player.uncertainty.lower <= player.equity <= player.uncertainty.upper <= 1
    assert sum(p.equity for p in first.players) == pytest.approx(1)
    assert calculate_equity([AA, KK], samples=1000, seed=924).players != first.players


def test_mc_matches_exact_and_keeps_boundary_uncertainty_nonzero() -> None:
    exact = calculate_equity([AA, KK], board=BOARD[:3])
    estimate = calculate_equity([AA, KK], board=BOARD[:3], method="monte_carlo", samples=3000)
    assert abs(estimate.players[0].equity - exact.players[0].equity) < 0.025
    u = estimate.players[0].uncertainty
    assert u.lower <= exact.players[0].equity <= u.upper
    guaranteed = calculate_equity([AA, KK], board=BOARD, method="monte_carlo", samples=100)
    assert guaranteed.players[0].equity == 1
    assert guaranteed.players[0].uncertainty.standard_error == 0
    assert guaranteed.players[0].uncertainty.lower < 1


def test_exact_preflop_when_dead_cards_make_enumeration_small() -> None:
    keep = set(BOARD + AA.cards + KK.cards)
    dead = tuple(card for card in DECK if card not in keep)
    result = calculate_equity([AA, KK], dead=dead)
    assert result.method == "exact" and result.evaluated_outcomes == 1
    assert result.players[0].equity == 1


@pytest.mark.parametrize(
    "players,board,dead",
    [
        ([AA], BOARD, ()),
        ([AA] * 7, BOARD, ()),
        ([AA, AA], BOARD, ()),
        ([AA, KK], ("2c",), ()),
        ([AA, KK], ("2c", "2c", "3d"), ()),
        ([AA, KK], ("As", "2c", "3d"), ()),
        ([AA, KK], BOARD, ("As",)),
        ([PlayerInput(cards=("XX", "Ah")), KK], BOARD, ()),
        ([PlayerInput(cards=("As",)), KK], BOARD, ()),
        ([PlayerInput(), KK], BOARD, ()),
        ([PlayerInput(cards=("As", "Ah"), weights={"AA": 100}), KK], BOARD, ()),
        ([AA, PlayerInput(weights={})], BOARD, ()),
        ([AA, PlayerInput(weights={"AA": 100})], BOARD, ("Ac", "Ad")),
        ([PlayerInput(weights={"AA": 100})] * 3, BOARD, ()),
    ],
)
def test_invalid_inputs_and_impossible_joint_ranges(players, board, dead) -> None:
    with pytest.raises(ValueError):
        calculate_equity(players, board=board, dead=dead)


@pytest.mark.parametrize(
    "weights", [{"AA": -1}, {"AA": 101}, {"AA": 1.5}, {"AA": True}, {"ZZ": 10}, {"AA": 0}]
)
def test_invalid_range_weights(weights: dict) -> None:
    with pytest.raises(ValueError):
        expand_range(weights)


@pytest.mark.parametrize(
    "settings",
    [
        {"method": "unknown"},
        {"samples": 0},
        {"samples": 10001},
        {"samples": True},
        {"seed": -1},
        {"seed": 2**32},
        {"seed": True},
        {"method": "exact"},
    ],
)
def test_invalid_options_and_exact_work_limits(settings: dict) -> None:
    with pytest.raises(ValueError):
        calculate_equity([AA, KK], **settings)


def test_all_work_limits_fail_cleanly(monkeypatch) -> None:
    with pytest.raises(WorkLimit, match="player count"):
        calculate_equity(
            [PlayerInput(weights=dict.fromkeys(CLASSES, 100))] * 6,
            samples=10000,
            method="monte_carlo",
        )
    monkeypatch.setattr(module, "MAX_SEARCH_NODES", 0)
    with pytest.raises(WorkLimit, match="Compatibility"):
        calculate_equity([AA, KK], board=BOARD)
    monkeypatch.setattr(module, "MAX_SEARCH_NODES", 50000)
    monkeypatch.setattr(module, "MAX_PROPOSALS", 0)
    with pytest.raises(WorkLimit, match="rejection"):
        calculate_equity([AA, KK], method="monte_carlo")
    dead = tuple(card for card in DECK if card not in set(AA.cards + KK.cards))[:44]
    with pytest.raises(ValueError, match="remaining"):
        calculate_equity([AA, KK], dead=dead)


@pytest.mark.parametrize(
    "pot,call,equity,required,ev",
    [
        (300, 100, 0.4, 0.25, 60),
        (100, 50, 1 / 3, 1 / 3, 0),
        (200, 100, 0.2, 1 / 3, -40),
        (100, 0, 0.5, 0, 50),
    ],
)
def test_pot_odds_closed_form(pot, call, equity, required, ev) -> None:
    result = pot_odds(pot, call, equity)
    assert result.required_equity == pytest.approx(required)
    assert result.call_ev == pytest.approx(ev)
    assert result.call_ev_interval is None
    assert "no future betting" in result.explanation and "side pots" in result.explanation


def test_pot_odds_interval_propagates_sampling_uncertainty() -> None:
    result = pot_odds(300, 100, 0.4, (0.3, 0.5))
    assert result.call_ev_interval == pytest.approx((20, 100))


@pytest.mark.parametrize(
    "pot,call,equity,interval",
    [
        (-1, 10, 0.5, None),
        (100, 10.5, 0.5, None),
        (True, 10, 0.5, None),
        (0, 0, 0.5, None),
        (100000001, 10, 0.5, None),
        (100, 10, True, None),
        (100, 10, float("nan"), None),
        (100, 10, 1.1, None),
        (100, 10, 0.5, (0.7, 0.9)),
        (100, 10, 0.5, (-0.1, 0.6)),
    ],
)
def test_invalid_pot_odds(pot, call, equity, interval) -> None:
    with pytest.raises(ValueError):
        pot_odds(pot, call, equity, interval)


def test_only_the_tied_winners_share_a_multiway_pot() -> None:
    result = calculate_equity([AA, PlayerInput(cards=("Ac", "Ad")), KK], board=BOARD)
    assert [p.equity for p in result.players] == [0.5, 0.5, 0]
    assert [p.tie_probability for p in result.players] == [1, 1, 0]
    sampled = calculate_equity(
        [AA, PlayerInput(cards=("Ac", "Ad")), KK], board=BOARD, method="monte_carlo", samples=100
    )
    assert [p.equity for p in sampled.players] == [0.5, 0.5, 0]


def test_six_player_monte_carlo_splits_a_shared_board() -> None:
    hands = [PlayerInput(cards=(rank + "c", rank + "d")) for rank in "234567"]
    result = calculate_equity(
        hands, board=("Ts", "Js", "Qs", "Ks", "As"), method="monte_carlo", samples=100
    )
    assert result.valid_samples == 100
    assert all(p.equity == pytest.approx(1 / 6) for p in result.players)
    assert sum(p.equity for p in result.players) == pytest.approx(1)


@pytest.mark.parametrize("value", ["0.5", 10**1000, float("inf")])
def test_nonfinite_or_nonnumeric_equity_rejected(value) -> None:
    with pytest.raises(ValueError):
        pot_odds(100, 10, value)


def test_boolean_interval_endpoint_is_not_a_probability() -> None:
    with pytest.raises(ValueError):
        pot_odds(100, 10, 0.5, (False, 1))
