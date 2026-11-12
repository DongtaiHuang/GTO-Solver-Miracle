"""Offline generation and reproducibility check for the turn/river catalog."""

import argparse
import hashlib
import json
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from poker_lab.strategy_models import Approval, Dataset, ImportedSolution
from solve_river import DATA, event
from turn_cfr import POT, TURN, TurnGame, best_response

TARGET = DATA / "turn_river_v1.json"
RIVERS = ("9d", "As")
BUDGETS = (10, 100, 500, 1500)


def generate(verify=False):
    old = json.loads(TARGET.read_text()) if verify else None
    stamp = old[0]["imported_at"] if old else datetime.now(UTC).isoformat()
    raw = json.loads(Path(__file__).with_name("expanded_ranges.json").read_text())
    ranges = [
        [((k[:2], k[2:]), w) for k, w in raw[seat].items()] for seat in ("BTN", "BB")
    ]
    tracemalloc.start()
    probe = TurnGame(ranges)
    probe.train(1)
    pp = probe.policy(probe.average)
    probe.traverse(pp, details={})
    best_response(probe, pp, 0)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    del probe, pp
    if peak > 64 * 1024**2:
        raise ValueError("64 MiB traced working-set budget exceeded")
    start = time.perf_counter()
    g = TurnGame(ranges)
    for n in BUDGETS:
        g.train(n - g.iterations)
        p = g.policy(g.average)
        value = g.traverse(p)
        btn, bb = (best_response(g, p, i) for i in (0, 1))
        gap = btn + bb - POT
        print(
            f"{n} iterations: value {value:.9f}; BR BTN {btn:.9f}, BB {bb:.9f}; gap {gap:.9f}; {time.perf_counter() - start:.2f}s",
            flush=True,
        )
    if not (0 <= gap <= 1 and btn + 1e-8 >= value and bb + 1e-8 >= POT - value):
        raise ValueError("Accuracy gate failed")
    details = {}
    g.traverse(p, details=details)
    infos = sum(
        np.count_nonzero((g.river_joint if n.river else g.joint).sum(axis=2 - n.seat))
        for n in g.nodes.values()
    )
    terminals = sum(
        np.count_nonzero(g.river_joint if "deal" in path else g.joint)
        for path in g.term
    )
    print(
        f"{infos} legal infosets; {np.count_nonzero(g.joint)} deals; {np.count_nonzero(g.river_joint)} deal-rivers; {terminals} deal-terminals; traced peak {peak} bytes"
    )
    base = json.loads((DATA / "river_550.json").read_text())[0]["document"]
    prefix = [
        e for e in base["scenario"]["history"] if e["street"] in ("preflop", "flop")
    ]
    range_id = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:20]
    docs = []
    for path, node in g.nodes.items():
        for card in RIVERS if node.river else (None,):
            r = g.cards.index(card) if card else 0
            doc = json.loads(json.dumps(base))
            s = doc["scenario"]
            players = ["BTN", "BB"]
            history = list(prefix)
            for idx, a in enumerate(path):
                if a == "deal":
                    continue
                parent = g.nodes[path[:idx]]
                name, _, amount = a.partition("@")
                history.append(
                    event(
                        "river" if parent.river else "turn",
                        players[parent.seat],
                        name,
                        int(amount) if amount else None,
                    )
                )
            actions = list(node.actions)
            if "check" in actions:
                actions.insert(0, "fold")
            s.update(
                hero_position=players[node.seat],
                opponent_position=players[1 - node.seat],
                street="river" if card else "turn",
                history=history,
                board=TURN + ([card] if card else []),
                pot=POT + sum(node.invested),
                effective_stack=9750 - max(node.invested),
                legal_actions=[
                    {
                        "action": a.partition("@")[0],
                        "amount": int(a.partition("@")[2]) if "@" in a else None,
                    }
                    for a in actions
                ],
            )
            s["abstraction"].update(
                tree_id="turn-river-halfpot-v1",
                range_model_id="weighted-" + range_id,
                assumptions=[
                    "Turn EV includes all 44 equally likely legal rivers per private deal and subsequent betting.",
                    "BB first each street; check or half-pot bet; fold or call; no raises. Pot is 550 or 1100 on river.",
                    "Conditional range weights: " + json.dumps(raw, sort_keys=True),
                ],
            )
            rows = []
            mass, ev = details[path]
            for i, h in enumerate(g.hands[node.seat]):
                if mass[r, i] <= 0:
                    continue
                freq = dict(zip(node.actions, p[path][r, i], strict=True))
                vals = dict(zip(node.actions, ev[r, i], strict=True))
                if "check" in actions:
                    freq["fold"] = vals["fold"] = 0.0
                rows.append(
                    {
                        "cards": h,
                        "reach_weight": mass[r, i],
                        "frequencies": freq,
                        "action_ev": vals,
                    }
                )
            suffix = (
                "-".join(card if a == "deal" else a.replace("@", "") for a in path)
                or "root"
            )
            doc.update(
                solution_id="ts-" + suffix + "-v1",
                combinations=rows,
                solver_identifier="Miracle joint turn-river CFR+",
                solver_version="1.0",
                exported_at=stamp,
            )
            doc["provenance"]["source_name"] = "Original project turn-to-river solve"
            doc["validation"].update(
                checked_at=stamp,
                methodology=f"Alternating CFR+ {n} iterations; BTN average value {value:.9f}, BTN BR {btn:.9f}, BB BR {bb:.9f}, full BR gap {gap:.9f} chips.",
                evidence_reference="tools/solve_turn.py and docs/TASK009.md",
                limitations=[
                    "Restricted ranges and two-street half-pot tree; incremental action EV in chips."
                ],
            )
            docs.append(doc)
    dataset = Dataset.model_validate(
        {"schema_version": "1.0", "dataset_id": "turn-river-v1", "solutions": docs}
    )
    entries = [
        ImportedSolution(
            document=s,
            imported_at=stamp,
            approval=Approval(
                content_hash=s.content_hash,
                reviewer="Task 009 numerical verification",
                evidence_reference="Independent best responses, complete river enumeration, project-authored inputs and outputs.",
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
        TARGET.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    generate(parser.parse_args().verify)
