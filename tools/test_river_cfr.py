"""Offline numerical checks; run with the pinned generation environment."""

import itertools

import numpy as np
import pytest
from river_cfr import RiverGame, normalize
from solve_expanded import reference

RANGES = [
    [(("Ac", "Ad"), 2), (("5c", "4c"), 1)],
    [(("Ac", "Qc"), 3), (("Kh", "Qh"), 1)],
]


def test_chance_and_payoffs():
    g = RiverGame(RANGES)
    assert np.allclose(g.chance, [[0, 2 / 6], [3 / 6, 1 / 6]])
    raised = ("bet@275", "raise@1650")
    assert np.all(g.term[raised + ("fold",)] == -275)
    assert g.term[raised + ("call@1375",)][0, 1] == 2200
    assert g.term[raised + ("call@1375",)][1, 1] == -1650
    with pytest.raises(ValueError):
        RiverGame(RANGES, raise_to=600)


def test_regrets_average_and_determinism():
    g = RiverGame(RANGES)
    g.train(1)
    assert np.allclose(g.average[()], 1 / 3)
    assert all(np.all(r >= 0) for r in g.regret.values())
    assert np.all(g.regret[()][0] >= 0) and np.max(g.regret[()]) > 0
    g.train(20)
    another = RiverGame(RANGES)
    another.train(21)
    for path in g.actions:
        np.testing.assert_array_equal(g.average[path], another.average[path])
        p = normalize(g.average[path])
        assert p.shape == (2, len(g.actions[path])) and np.allclose(p.sum(axis=1), 1)


@pytest.mark.parametrize("seat", [0, 1])
def test_br_matches_exhaustive_own_hand_plans(seat):
    g = RiverGame(RANGES)
    g.train(20)
    policy = g.report()[0]
    nodes = [p for p in g.actions if len(p) % 2 == seat]
    # Explicitly enumerate each own combo's pure contingent plans. Each choice
    # must apply to every compatible opponent combo at that public history.
    bound = 0.0
    for h in range(2):
        scores = []
        for plan in itertools.product(*(g.actions[p] for p in nodes)):
            choices = dict(zip(nodes, plan, strict=True))

            def ev(path, i, j, choices=choices):
                if path in g.term:
                    return g.term[path][i, j]
                if path in choices:
                    return ev(path + (choices[path],), i, j)
                row = policy[path][j if seat == 0 else i]
                return sum(
                    prob * ev(path + (a,), i, j)
                    for prob, a in zip(row, g.actions[path], strict=True)
                )

            pairs = [(h, o) if seat == 0 else (o, h) for o in range(2)]
            scores.append(sum(g.chance[i, j] * ev((), i, j) for i, j in pairs))
        bound += (max if seat == 0 else min)(scores)
    assert g.traverse(policy, best=seat) == pytest.approx(bound)


@pytest.mark.parametrize("bet", [275, 550])
def test_matches_highs(bet):
    reference(bet, 4000)
