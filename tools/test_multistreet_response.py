import json
from pathlib import Path

import numpy as np
import pytest
from poker_lab import multistreet as ms
from turn_cfr import TurnGame, best_response


@pytest.mark.parametrize("hero", [0, 1])
def test_independent_numpy_traversals_and_all_rivers(hero):
    raw = json.loads(Path(__file__).with_name("expanded_ranges.json").read_text())
    g = TurnGame(
        [[((k[:2], k[2:]), v) for k, v in raw[pos].items()] for pos in ("BTN", "BB")]
    )
    ref = ms.reference()
    target = "turn/check" if hero == 0 else "turn"
    fixed, _ = ms.modeled(ref, hero, ms.Hypothesis(name="Test", profile="lag"))
    br = ms.evaluate(ref, hero, target, fixed, {}, optimize=True)

    def to_vectors(overrides):
        policy = {}
        for path, node in g.nodes.items():
            rows = []
            for card in g.cards if node.river else [None]:
                key = "/".join(["turn", *(card if a == "deal" else a for a in path)])
                rows.append(overrides.get(key, ref["nodes"][key]["policy"]))
            policy[path] = np.array(rows)
        return policy

    assert best_response(g, to_vectors(fixed), hero) == pytest.approx(
        br.value, abs=1e-8
    )
    against_eq = g.traverse(to_vectors(br.strategy))
    assert ms.evaluate(ref, hero, target, {}, br.strategy).value == pytest.approx(
        against_eq if hero == 0 else 550 - against_eq, abs=1e-8
    )
