"""Replaceable heuristic opponents. These decisions are not GTO solutions."""

import random
from dataclasses import dataclass
from typing import Protocol

from poker_lab.engine import Holdem
from poker_lab.models import Action


@dataclass(frozen=True)
class Decision:
    action: Action
    amount: int | None = None


class OpponentPolicy(Protocol):
    def choose(self, game: Holdem, rng: random.Random) -> Decision: ...


class RandomPolicy:
    def choose(self, game: Holdem, rng: random.Random) -> Decision:
        legal = game.legal_actions()
        aggression = next((a for a in (Action.BET, Action.RAISE) if a in legal.actions), None)
        roll = rng.random()
        if aggression is not None and roll < 0.18:
            assert legal.min_raise_to is not None
            target = min(
                legal.max_raise_to,
                max(legal.min_raise_to, game.current_bet + max(game.big_blind, game.pot // 2)),
            )
            return Decision(aggression, target)
        if Action.CALL in legal.actions:
            if roll > 0.86:
                return Decision(Action.FOLD)
            return Decision(Action.CALL)
        return Decision(Action.CHECK)
