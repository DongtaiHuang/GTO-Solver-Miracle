"""Compile Task 009's exact deal masses, terminal payoffs and average policies offline."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from solve_turn import BUDGETS, TARGET, generate
from turn_cfr import TurnGame, best_response

DEST = TARGET.with_name("turn_reference_v1.json.gz")


def build():
    raw = json.loads(Path(__file__).with_name("expanded_ranges.json").read_text())
    game = TurnGame(
        [[((h[:2], h[2:]), w) for h, w in raw[pos].items()] for pos in ("BTN", "BB")]
    )
    game.train(BUDGETS[-1])
    policy = game.policy(game.average)
    for matrix in policy.values():
        if not np.all(
            np.isfinite(matrix) & (matrix >= 0) & (matrix <= 1)
        ) or not np.allclose(matrix.sum(axis=-1), 1, atol=1e-12, rtol=0):
            raise ValueError("Invalid full-reference probability rows")
    v = game.traverse(policy)
    br = [best_response(game, policy, s) for s in (0, 1)]
    if abs(v - 252.798053571) > 1e-8 or abs(sum(br) - 550 - 0.022491055) > 1e-8:
        raise ValueError("Reference differs from Task 009")
    nodes = {}

    def visit(path, key, r):
        if path in game.chance:
            children = [
                visit(path + ("deal",), key + "/" + c, j)
                for j, c in enumerate(game.cards)
            ]
            nodes[key] = {"chance": children}
        elif path in game.term:
            nodes[key] = {"payoff": game.term[path][r or 0].tolist(), "river": r}
        else:
            n = game.nodes[path]
            children = [visit(path + (a,), key + "/" + a, r) for a in n.actions]
            nodes[key] = {
                "seat": n.seat,
                "river": r,
                "invested": n.invested[n.seat],
                "actions": n.actions,
                "children": children,
                "policy": policy[path][r or 0].tolist(),
            }
        return key

    visit((), "turn", None)
    documents = {}
    for entry in json.loads(TARGET.read_text()):
        doc = entry["document"]
        s = doc["scenario"]
        key = "turn"
        for event in s["history"]:
            if event["street"] not in ("turn", "river"):
                continue
            if event["street"] == "river" and "chance" in nodes[key]:
                key += "/" + s["board"][-1]
            key += (
                "/"
                + event["action"]
                + (f"@{event['amount']}" if event["amount"] is not None else "")
            )
        if "chance" in nodes[key]:
            key += "/" + s["board"][-1]
        n = nodes[key]
        for combo in doc["combinations"]:
            i = game.hands[n["seat"]].index(tuple(combo["cards"]))
            np.testing.assert_allclose(
                n["policy"][i],
                [combo["frequencies"][a] for a in n["actions"]],
                rtol=0,
                atol=1e-12,
            )
        documents[doc["solution_id"]] = [key, entry["approval"]["content_hash"]]
    data = {
        "version": "ts009-average-1500-v1",
        "hands": [["".join(h) for h in side] for side in game.hands],
        "cards": game.cards,
        "joint": game.joint[0].tolist(),
        "river_joint": game.river_joint.tolist(),
        "nodes": nodes,
        "documents": documents,
        "value": v,
        "best": br,
    }
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    generate(verify=True)
    payload = build()
    if args.verify:
        if gzip.decompress(DEST.read_bytes()) != payload:
            raise ValueError("Full policy mismatch")
    else:
        DEST.write_bytes(gzip.compress(payload, mtime=0))
    print(
        "Uncompressed SHA-256",
        hashlib.sha256(payload).hexdigest(),
        "bytes",
        len(payload),
    )
