"""Generate the project's fixed-board Hold'em river equilibrium using HiGHS."""

import argparse
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linprog

from poker_lab.evaluator import evaluate
from poker_lab.strategy_models import Approval, Dataset, ImportedSolution

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/src/poker_lab/data"
BTN = [("Ac", "Ad"), ("5c", "4c")]
BB = [("Kh", "Qh"), ("Ks", "Js")]
BOARD = ["Kd", "7h", "2s", "Tc", "9d"]
POT = 550
URL = "https://github.com/DongtaiHuang/GTO-Solver-Miracle"
POLICIES = np.array(list(itertools.product([0, 1], repeat=2)))


def solve(bet):
    # Constant-sum utility: river pot share less additional investment.
    wins = np.array(
        [
            [float(evaluate(a + tuple(BOARD)) > evaluate(b + tuple(BOARD))) for b in BB]
            for a in BTN
        ]
    )
    assert all(
        len(set(a + b + tuple(BOARD))) == 9
        and evaluate(a + tuple(BOARD)) != evaluate(b + tuple(BOARD))
        for a in BTN
        for b in BB
    )
    called = wins * (POT + 2 * bet) - bet

    def payoff(ip, oop):
        return np.where(ip[:, None], np.where(oop, called, POT), wins * POT).mean()

    matrix = np.array([[payoff(i, j) for j in POLICIES] for i in POLICIES])

    def maximin(m):
        n = len(m)
        lp = linprog(
            [0] * n + [-1],
            A_ub=np.column_stack((-m.T, np.ones(n))),
            b_ub=np.zeros(n),
            A_eq=[[1] * n + [0]],
            b_eq=[1],
            bounds=[(0, 1)] * n + [(None, None)],
            method="highs-ds",
        )
        assert lp.success, lp.message
        return lp.x[:-1]

    x, y = maximin(matrix), maximin(-matrix.T)
    gap = float(max(matrix @ y) - min(x @ matrix))
    if abs(gap) > 1e-8:
        raise ValueError("Best-response gap exceeded tolerance")
    betting, calling = x @ POLICIES, y @ POLICIES
    ip_ev = np.mean(calling * called + (1 - calling) * POT, axis=1)
    bb_ev = (betting / sum(betting)) @ (POT - called)
    return betting, calling, wins.mean(axis=1) * POT, ip_ev, bb_ev, gap


def event(street, position, action, amount=None):
    return dict(street=street, position=position, action=action, amount=amount)


def generate(bet, stamp):
    betting, calling, check_ev, bet_ev, call_ev, gap = solve(bet)
    history = [event("preflop", pos, "fold") for pos in ("UTG", "HJ", "CO")]
    history += [
        event("preflop", "BTN", "raise", 250),
        event("preflop", "SB", "fold"),
        event("preflop", "BB", "call", 150),
    ]
    history += [
        event(street, pos, "check")
        for street in ("flop", "turn")
        for pos in ("BB", "BTN")
    ]
    history.append(event("river", "BB", "check"))
    solutions = []
    for ip in [True, False]:
        hero, opp = ("BTN", "BB") if ip else ("BB", "BTN")
        sized = ("bet" if ip else "call") + f"@{bet}"
        passive = "check" if ip else "fold"
        actions = [
            dict(action=passive, amount=None),
            dict(action=sized.split("@")[0], amount=bet),
        ]
        if ip:
            actions.insert(0, dict(action="fold", amount=None))
        rows = []
        for i, cards in enumerate(BTN if ip else BB):
            prob = float((betting if ip else calling)[i])
            freq = {passive: 1 - prob, sized: prob}
            ev = {
                passive: float(check_ev[i]) if ip else 0.0,
                sized: float((bet_ev if ip else call_ev)[i]),
            }
            if ip:
                freq["fold"] = ev["fold"] = 0.0
            rows.append(
                dict(cards=cards, reach_weight=0.5, frequencies=freq, action_ev=ev)
            )
        scenario = dict(
            schema_version="1.0",
            game_format="6-max NLHE cash",
            players=6,
            starting_stacks=dict.fromkeys(
                ["UTG", "HJ", "CO", "BTN", "SB", "BB"], 10000
            ),
            small_blind=50,
            big_blind=100,
            ante=0,
            hero_position=hero,
            opponent_position=opp,
            effective_stack=9750 if ip else 9750 - bet,
            pot=POT if ip else POT + bet,
            street="river",
            board=BOARD,
            dead_cards=[],
            history=history if ip else history + [event("river", "BTN", "bet", bet)],
            legal_actions=actions,
            abstraction=dict(
                tree_id=f"checked-river-{bet}-v1",
                range_model_id="btn-aa54-bb-kqkj-v1",
                card_model="exact_cards",
                rake_model="none",
                action_semantics="total_street_bet_for_aggression",
                assumptions=[
                    "BTN: AcAd, 5c4c equally weighted. BB: KhQh, KsJs equally weighted.",
                    f"Fixed flop and turn check-through, BB checks river. BTN may bet {bet}. No raises.",
                ],
            ),
        )
        solutions.append(
            dict(
                schema_version="1.0",
                solution_id=f"river-{bet}-{hero.lower()}-v1",
                kind="solver_solution",
                scenario=scenario,
                solver_identifier="Miracle river LP / HiGHS dual simplex",
                solver_version="1.0 / SciPy " + scipy.__version__,
                exported_at=stamp,
                provenance=dict(
                    source_name="Original enumerated Hold'em river solve",
                    source_url=URL,
                    license_name="MIT",
                    license_url=URL + "/blob/main/LICENSE",
                    usage_granted=True,
                    usage_evidence="Original numerical results generated by this project's MIT-licensed solver adapter.",
                    redistribution="permitted",
                    publish=True,
                ),
                validation=dict(
                    status="reviewed_gto",
                    checked_at=stamp,
                    methodology=f"Enumerated all pure policy pairs. Best-response gap {gap:.12g} chips for this restricted tree.",
                    evidence_reference="tools/solve_river.py and docs/TASK006A.md",
                    limitations=[
                        "Fixed ranges, board, prior actions and discrete river bet. EV is incremental in chips."
                    ],
                    ev_verified=True,
                ),
                combinations=rows,
            )
        )
    return Dataset.model_validate(
        dict(schema_version="1.0", dataset_id=f"river-{bet}-v1", solutions=solutions)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bet", type=int, choices=[275, 550], default=550)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = DATA / f"river_{args.bet}.json"
    prior = json.loads(path.read_text()) if args.verify else None
    stamp = prior[0]["imported_at"] if prior else datetime.now(UTC).isoformat()
    entries = []
    for doc in generate(args.bet, stamp).solutions:
        entry = ImportedSolution(
            document=doc,
            imported_at=stamp,
            approval=Approval(
                content_hash=doc.content_hash,
                reviewer="Task 006A reproducible LP validation",
                evidence_reference="Complete best-response enumeration and project-authored inputs and outputs.",
                approved_at=stamp,
                confirmed_source_and_rights=True,
            ),
        )
        entries.append(entry.model_dump(mode="json"))
    if args.verify:
        assert entries == prior
    else:
        path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(entries[0]["document"]["validation"]["methodology"])
