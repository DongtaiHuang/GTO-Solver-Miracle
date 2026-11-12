import numpy as np
import pytest
from turn_cfr import POT, TurnGame, best_response


def test_known_drawing_dead_game():
    g = TurnGame([[(("Kh", "Kc"), 1)], [(("4c", "5c"), 1)]])
    # BTN wins every showdown. Check/fold by BB and value play by BTN yield root value P.
    uniform = g.policy(g.average)
    start = best_response(g, uniform, 0) + best_response(g, uniform, 1) - POT
    g.train(100)
    p = g.policy(g.average)
    assert abs(g.traverse(p) - POT) < 1 and best_response(g, p, 0) + best_response(
        g, p, 1
    ) - POT < min(1, start)
    assert all((v >= 0).all() for v in g.regrets.values())
    assert all(np.allclose(v.sum(axis=-1), 1) for v in p.values())


def test_chance_tree_and_units():
    g = TurnGame(
        [[(("Ac", "Ad"), 2), (("5c", "4c"), 1)], [(("Ac", "Qc"), 3), (("Kh", "Qh"), 1)]]
    )
    assert np.allclose(g.joint, [[[0, 2 / 6], [3 / 6, 1 / 6]]])
    assert np.isclose(g.river_joint.sum(), 1)
    for i, h in enumerate(g.hands[0]):
        for j, k in enumerate(g.hands[1]):
            dist = g.conditional[:, i, j]
            assert np.count_nonzero(dist) == (0 if set(h) & set(k) else 44)
            assert all(
                v == 0 if c in h + k or set(h) & set(k) else v == 1 / 44
                for c, v in zip(g.cards, dist, strict=True)
            )
    assert g.nodes[()].seat == 1 and g.nodes[("check",)].seat == 0
    river = ("bet@275", "call@275", "deal")
    assert g.nodes[river].actions == ("check", "bet@550") and g.nodes[river].seat == 1
    assert np.all(g.term[river + ("bet@550", "fold")] == -275)
    assert g.regrets[()].shape == (1, 2, 2) and g.regrets[river].shape == (48, 2, 2)
    assert np.all(g.term[("check", "bet@275", "fold")] == 550)
    with pytest.raises(ValueError):
        g.train(4001)


def test_independent_response_and_first_average():
    g = TurnGame([[(("Kh", "Kc"), 1)], [(("4c", "5c"), 1)]])
    p = g.policy(g.average)
    # Drawing-dead BB plays uniformly. Winning BTN calls every lead and bets after checks.
    # Each reached river adds 3/4 of its half-pot bet to the check-through value.
    called_turn_value = 550 + 275 + 0.75 * 550
    after_bb_check = 0.5 * 550 + 0.5 * called_turn_value
    assert best_response(g, p, 0) == pytest.approx(
        0.5 * called_turn_value + 0.5 * after_bb_check
    )
    g.train(1)
    assert np.allclose(g.average[("check",)], 0.5)
    # BTN's own check on turn reaches the checked-through river with probability 1/2.
    assert np.allclose(g.average[("check", "check", "deal", "check")], 0.25)


def test_bb_best_response_against_uniform_drawing_dead_btn():
    game = TurnGame([[(("4c", "5c"), 1)], [(("Kh", "Kc"), 1)]])
    uniform = game.policy(game.average)
    # On the river the strong BB can earn half the river bet above its showdown value.
    # Check on the turn: half the time BTN bets (call), otherwise advance for free.
    assert best_response(game, uniform, 1) == pytest.approx((1100 + 687.5) / 2)
