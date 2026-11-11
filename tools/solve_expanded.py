"""Compare against LP first, then export five hash-bound strategy records."""

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from poker_lab.strategy_models import Approval, Dataset, ImportedSolution
from river_cfr import RiverGame
from solve_river import BB, BTN, DATA, event, solve


def train(game, count):
    start = time.perf_counter()
    game.train(count)
    policy, details, value, gap = game.report()
    print(
        f"{game.chance.shape} {count} iterations, {time.perf_counter() - start:.3f}s, "
        f"{sum(len(r) for r in policy.values())} infosets, "
        f"{np.count_nonzero(game.chance) * len(game.term)} compatible deal-terminal pairs, "
        f"BTN value {value:.8f}, BR gap {gap:.8f} chips",
        flush=True,
    )
    return policy, details, value, gap


def reference(bet, count):
    g = RiverGame([[(h, 1) for h in hands] for hands in (BTN, BB)], (bet,), None)
    p, d, value, gap = train(g, count)
    betting, calling, check, bet_ev, call_ev, _ = solve(bet)
    path = (f"bet@{bet}",)
    freq = max(
        np.max(abs(betting - p[()][:, 1])), abs(calling.mean() - p[path][:, 1].mean())
    )
    error = max(
        np.max(abs(check - d[()][1][:, 0])),
        np.max(abs(bet_ev - d[()][1][:, 1])),
        np.max(abs(call_ev - d[path][1][:, 1])),
    )
    lp_value = np.mean(betting * bet_ev + (1 - betting) * check)
    print(
        f"HiGHS {bet}: value error {abs(lp_value - value):.8f}, frequency error {freq:.8f}, action EV error {error:.8f}"
    )
    if gap > 0.5 or abs(lp_value - value) > 0.25 or freq > 0.005 or error > 2:
        raise ValueError("Reference comparison outside tolerance")


def export(count, verify=False):
    for bet in (275, 550):
        reference(bet, count)
    raw = json.loads(Path(__file__).with_name("expanded_ranges.json").read_text())
    ranges = [
        [((k[:2], k[2:]), w) for k, w in raw[seat].items()]
        for seat in ("BTN", "BB")
    ]
    g = RiverGame(ranges)
    p, d, value, gap = train(g, count)
    if gap > 1:
        raise ValueError("Expanded BR gap exceeds 1 chip")
    target = DATA / "expanded_river.json"
    old = json.loads(target.read_text()) if verify else None
    stamp = old[0]["imported_at"] if old else datetime.now(UTC).isoformat()
    base = json.loads((DATA / "river_550.json").read_text())[0]["document"]
    docs = []
    range_id = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:20]
    for path, actions in g.actions.items():
        seat = len(path) % 2
        doc = json.loads(json.dumps(base))
        s = doc["scenario"]
        pos = ["BTN", "BB"]
        s.update(hero_position=pos[seat], opponent_position=pos[1 - seat])
        invested = [0, 0]
        for i, key in enumerate(path):
            action, amount = key.split("@")
            invested[i] = int(amount)
            s["history"].append(event("river", pos[i], action, int(amount)))
        s.update(pot=550 + sum(invested), effective_stack=9750 - max(invested))
        s["abstraction"].update(
            tree_id="river-b275-b550-r1650-v1",
            range_model_id="weighted-" + range_id,
            assumptions=[
                "Conditional range weights: " + json.dumps(raw, sort_keys=True),
                "BB checks. BTN checks or bets 275/550. BB folds, calls or raises to 1650. BTN folds or calls.",
            ],
        )
        keys = actions if path else ["fold", *actions]
        s["legal_actions"] = [
            {
                "action": k.partition("@")[0],
                "amount": int(k.split("@")[1]) if "@" in k else None,
            }
            for k in keys
        ]
        rows = []
        mass, ev = d[path]
        for i, h in enumerate(g.hands[seat]):
            if mass[i] <= 0:
                continue
            freq = dict(zip(actions, p[path][i], strict=True))
            vals = dict(zip(actions, ev[i], strict=True))
            if not path:
                freq["fold"] = vals["fold"] = 0.0
            rows.append(
                {"cards": h, "reach_weight": mass[i], "frequencies": freq, "action_ev": vals}
            )
        suffix = "-".join(path).replace("@", "") or "root"
        doc.update(
            solution_id="cfr-river-" + suffix + "-v1",
            combinations=rows,
            solver_identifier="Miracle exhaustive river CFR+",
            solver_version="1.0",
            exported_at=stamp,
        )
        doc["provenance"]["source_name"] = "Original weighted river CFR+ solve"
        doc["validation"].update(
            checked_at=stamp,
            methodology=f"Alternating CFR+, {count} iterations, linear average. Exact finite-tree BR gap {gap:.8f} chips; BTN value {value:.8f} chips.",
            evidence_reference="tools/solve_expanded.py and docs/TASK008.md",
            limitations=[
                "Restricted fixed river tree, conditioned ranges, incremental action EV in chips."
            ],
        )
        docs.append(doc)
    dataset = Dataset.model_validate(
        {"schema_version": "1.0", "dataset_id": "expanded-river-v1", "solutions": docs}
    )
    entries = [
        ImportedSolution(
            document=s,
            imported_at=stamp,
            approval=Approval(
                content_hash=s.content_hash,
                reviewer="Task 008 numerical verification",
                evidence_reference="LP comparison and full tree best responses; original project outputs.",
                approved_at=stamp,
                confirmed_source_and_rights=True,
            ),
        ).model_dump(mode="json")
        for s in dataset.solutions
    ]
    if verify:
        if entries != old:
            raise ValueError("Generated records differ")
    else:
        target.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    export(4000, args.verify)
