"""Offline exhaustive alternating CFR+ for fixed-board heads-up river games."""

import numpy as np
from poker_lab.evaluator import evaluate, validate_cards
from poker_lab.river_payoff import BOARD, POT, called_payoff


def normalize(rows):
    total = rows.sum(axis=1, keepdims=True)
    return np.divide(
        rows, total, out=np.full_like(rows, 1 / rows.shape[1]), where=total > 0
    )


class RiverGame:
    def __init__(self, ranges, bets=(275, 550), raise_to=1650):
        if (
            not bets
            or len(set(bets)) != len(bets)
            or any(type(b) is not int or not 100 <= b < 9750 for b in bets)
        ):
            raise ValueError("Invalid bet abstraction")
        if raise_to is not None and (
            type(raise_to) is not int or not 2 * max(bets) <= raise_to < 9750
        ):
            raise ValueError("Invalid raise-to")
        self.hands = []
        weights = []
        ranks = []
        for side in ranges:
            hands = [tuple(sorted(hand)) for hand, weight in side]
            w = np.array([weight for hand, weight in side], dtype=float)
            if (
                not hands
                or len(set(hands)) != len(hands)
                or not np.all(np.isfinite(w) & (w > 0))
            ):
                raise ValueError("Invalid weighted range")
            for hand in hands:
                validate_cards(list(hand) + BOARD, 7)
            self.hands.append(hands)
            weights.append(w / w.sum())
            ranks.append([evaluate(list(h) + BOARD) for h in hands])
        self.chance = np.outer(*weights)
        share = np.zeros_like(self.chance)
        for i, a in enumerate(self.hands[0]):
            for j, b in enumerate(self.hands[1]):
                if set(a) & set(b):
                    self.chance[i, j] = 0
                else:
                    share[i, j] = float(ranks[0][i] > ranks[1][j]) + 0.5 * (
                        ranks[0][i] == ranks[1][j]
                    )
        if self.chance.sum() == 0:
            raise ValueError("No compatible deals")
        self.chance /= self.chance.sum()
        self.actions = {(): ["check"] + [f"bet@{b}" for b in bets]}
        self.term = {("check",): share * POT}
        for b in bets:
            path = (f"bet@{b}",)
            self.actions[path] = ["fold", f"call@{b}"]
            self.term[path + ("fold",)] = np.full_like(share, POT)
            self.term[path + (f"call@{b}",)] = called_payoff(share, b)
            if raise_to is not None:
                raise_key = f"raise@{raise_to}"
                self.actions[path].append(raise_key)
                raised = path + (raise_key,)
                self.actions[raised] = ["fold", f"call@{raise_to - b}"]
                self.term[raised + ("fold",)] = np.full_like(share, -b)
                self.term[raised + (f"call@{raise_to - b}",)] = called_payoff(
                    share, raise_to
                )
        self.regret = {
            p: np.zeros((len(self.hands[len(p) % 2]), len(a)))
            for p, a in self.actions.items()
        }
        self.average = {p: np.zeros_like(r) for p, r in self.regret.items()}
        self.iterations = 0

    def traverse(self, policy, update=None, best=None, details=None):
        def visit(path, reach):
            if path in self.term:
                return self.term[path]
            seat = len(path) % 2
            probs = policy[path]
            children = []
            for k, action in enumerate(self.actions[path]):
                nxt = list(reach)
                nxt[seat] = reach[seat] * probs[:, k]
                children.append(visit(path + (action,), nxt))
            # Child arrays are BTN utilities indexed by the two private combos.
            pay = np.stack(children)
            opponent = reach[1 - seat]
            cf = self.chance * (opponent if seat == 0 else opponent[:, None])
            sign = 1 if seat == 0 else -1
            values = sign * (pay * cf).sum(axis=2 - seat).T
            if update == seat:
                delta = values - (values * probs).sum(axis=1, keepdims=True)
                self.regret[path] = np.maximum(0, self.regret[path] + delta)
                self.average[path] += self.iterations * reach[seat][:, None] * probs
            if details is not None:
                mass = cf.sum(axis=1 - seat)
                ev = np.divide(
                    values,
                    mass[:, None],
                    out=np.zeros_like(values),
                    where=mass[:, None] > 0,
                )
                if seat == 1:
                    ev += POT
                if len(path) == 2:
                    ev += int(path[0].split("@")[1])
                details[path] = (mass * reach[seat], ev)
            if best == seat:
                probs = np.eye(probs.shape[1])[values.argmax(axis=1)]
            mix = probs.T[:, :, None] if seat == 0 else probs.T[:, None, :]
            return (pay * mix).sum(axis=0)

        return float(
            (self.chance * visit((), [np.ones(n) for n in self.chance.shape])).sum()
        )

    def train(self, count):
        for _ in range(count):
            self.iterations += 1
            for seat in (0, 1):
                self.traverse(
                    {p: normalize(r) for p, r in self.regret.items()}, update=seat
                )

    def report(self):
        policy = {p: normalize(r) for p, r in self.average.items()}
        details = {}
        value = self.traverse(policy, details=details)
        gap = self.traverse(policy, best=0) - self.traverse(policy, best=1)
        return policy, details, value, gap
