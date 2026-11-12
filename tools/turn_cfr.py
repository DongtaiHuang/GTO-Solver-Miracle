"""Exhaustive alternating CFR+. Axes are public river, BTN combo, BB combo."""

from dataclasses import dataclass

import numpy as np
from poker_lab.evaluator import DECK, evaluate, validate_cards
from poker_lab.river_payoff import BOARD, POT, called_payoff
from river_cfr import normalize

TURN = BOARD[:4]
MAX_HANDS = 16
MAX_ITERATIONS = 4000


@dataclass(frozen=True)
class Node:
    seat: int
    actions: tuple[str, str]
    invested: tuple[int, int]
    river: bool


class TurnGame:
    def __init__(self, ranges):
        self.hands = []
        weights = []
        self.cards = [c for c in DECK if c not in TURN]
        ranks = []
        for side in ranges:
            hands = [tuple(sorted(h)) for h, w in side]
            w = np.array([weight for _, weight in side], dtype=float)
            if (
                not 1 <= len(hands) <= MAX_HANDS
                or len(set(hands)) != len(hands)
                or not np.all(np.isfinite(w) & (w > 0))
            ):
                raise ValueError(
                    "Expected 1–16 unique positive-weight hands per player"
                )
            for h in hands:
                validate_cards(list(h) + TURN, 6)
            self.hands.append(hands)
            weights.append(w / w.sum())
            ranks.append(
                [
                    [
                        evaluate(list(h) + TURN + [r]) if r not in h else ()
                        for h in hands
                    ]
                    for r in self.cards
                ]
            )
        self.joint = np.outer(*weights)[None, :, :]
        self.conditional = np.zeros((48, *self.joint.shape[1:]))
        share = np.zeros_like(self.conditional)
        for i, h in enumerate(self.hands[0]):
            for j, k in enumerate(self.hands[1]):
                if set(h) & set(k):
                    self.joint[0, i, j] = 0
                    continue
                for r, c in enumerate(self.cards):
                    if c in h + k:
                        continue
                    self.conditional[r, i, j] = 1 / 44
                    left, right = ranks[0][r][i], ranks[1][r][j]
                    share[r, i, j] = float(left > right) + 0.5 * (left == right)
        if self.joint.sum() == 0:
            raise ValueError("No legal private deal")
        self.joint /= self.joint.sum()
        self.river_joint = self.joint * self.conditional
        self.nodes = {}
        self.term = {}
        self.chance = set()

        def street(prefix, prior, river):
            size = (POT + 2 * prior) // 2
            bet, call = f"bet@{size}", f"call@{size}"
            for lead, start in [(1, prefix), (0, prefix + ("check",))]:
                self.nodes[start] = Node(lead, ("check", bet), (prior, prior), river)
                investment = [prior, prior]
                investment[lead] += size
                facing = start + (bet,)
                self.nodes[facing] = Node(
                    1 - lead, ("fold", call), tuple(investment), river
                )
                self.term[facing + ("fold",)] = np.full_like(
                    self.river_joint if river else self.joint,
                    POT + prior if lead == 0 else -prior,
                )
            for line, matched in [
                (("check", "check"), prior),
                ((bet, call), prior + size),
                (("check", bet, call), prior + size),
            ]:
                end = prefix + line
                if river:
                    self.term[end] = called_payoff(share, matched)
                else:
                    self.chance.add(end)
                    street(end + ("deal",), matched, True)

        street((), 0, False)
        self.regrets = {
            path: np.zeros((48 if n.river else 1, len(self.hands[n.seat]), 2))
            for path, n in self.nodes.items()
        }
        self.average = {p: np.zeros_like(a) for p, a in self.regrets.items()}
        self.iterations = 0

    def policy(self, table):
        return {
            p: normalize(a.reshape(-1, 2)).reshape(a.shape) for p, a in table.items()
        }

    def traverse(self, policy, update=None, details=None):
        def visit(path, reach):
            if path in self.term:
                return self.term[path]
            if path in self.chance:
                return (visit(path + ("deal",), reach) * self.conditional).sum(
                    axis=0, keepdims=True
                )
            n = self.nodes[path]
            probs = policy[path]
            children = []
            for k, a in enumerate(n.actions):
                nxt = list(reach)
                nxt[n.seat] = reach[n.seat] * probs[:, :, k]
                children.append(visit(path + (a,), nxt))
            u = np.stack(children, axis=-1)
            opp = reach[1 - n.seat]
            cf = (self.river_joint if n.river else self.joint) * (
                opp[:, None, :] if n.seat == 0 else opp[:, :, None]
            )
            values = (u * cf[:, :, :, None]).sum(axis=2 - n.seat) * (
                1 if n.seat == 0 else -1
            )
            if update == n.seat:
                delta = values - (probs * values).sum(axis=-1, keepdims=True)
                self.regrets[path] = np.maximum(self.regrets[path] + delta, 0)
                self.average[path] += (
                    self.iterations * reach[n.seat][:, :, None] * probs
                )
            if details is not None:
                mass = cf.sum(axis=2 - n.seat)
                ev = np.divide(
                    values,
                    mass[:, :, None],
                    out=np.zeros_like(values),
                    where=mass[:, :, None] > 0,
                )
                details[path] = (
                    mass * reach[n.seat],
                    ev + n.invested[n.seat] + (POT if n.seat else 0),
                )
            mix = probs[:, :, None, :] if n.seat == 0 else probs[:, None, :, :]
            return (u * mix).sum(axis=-1)

        reach = [np.ones((1, len(h))) for h in self.hands]
        return float((visit((), reach) * self.joint).sum())

    def train(self, count):
        if count < 0 or count + self.iterations > MAX_ITERATIONS:
            raise ValueError("Iteration limit")
        for _ in range(count):
            self.iterations += 1
            for seat in (0, 1):
                self.traverse(self.policy(self.regrets), update=seat)


def best_response(game, policy, seat):
    """Counterfactual dynamic programming, independent of CFR traversal and regrets."""

    def walk(path, opponent_reach):
        if path in game.term:
            amount = game.term[path] if seat == 0 else POT - game.term[path]
            chance = game.river_joint if "deal" in path else game.joint
            weight = (
                opponent_reach[:, None, :] if seat == 0 else opponent_reach[:, :, None]
            )
            return (amount * chance * weight).sum(axis=2 - seat)
        if path in game.chance:
            return walk(path + ("deal",), opponent_reach).sum(axis=0, keepdims=True)
        node = game.nodes[path]
        if node.seat == seat:
            return np.maximum(
                *(walk(path + (a,), opponent_reach) for a in node.actions)
            )
        return sum(
            walk(path + (a,), opponent_reach * policy[path][:, :, k])
            for k, a in enumerate(node.actions)
        )

    return float(walk((), np.ones((1, len(game.hands[1 - seat])))).sum())
