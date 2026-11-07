"""Replaceable heuristic opponents. These decisions are not GTO solutions."""

import random
from dataclasses import dataclass
from typing import Protocol

from poker_lab.engine import Holdem
from poker_lab.models import Action, Street
from poker_lab.profiles import OpponentProfile


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


class ProfilePolicy:
    """Directional tendencies only; supplied percentages are not realized action stats."""

    def __init__(self, profile: OpponentProfile) -> None:
        self.profile = profile

    def choose(self, game: Holdem, rng: random.Random) -> Decision:
        p = self.profile.parameters
        if p is None:
            return RandomPolicy().choose(game, rng)
        legal = game.legal_actions()
        aggression = next((a for a in (Action.BET, Action.RAISE) if a in legal.actions), None)
        if game.street == Street.PREFLOP:
            pressure = p.three_bet if game.current_bet > game.big_blind else p.pfr
            continuation = (0.6 * p.vpip + 0.4 * p.calling_tendency) / 100
            if game.current_bet > game.big_blind:
                continuation *= 1 - p.fold_to_three_bet / 200
        else:
            pressure = {
                Street.FLOP: p.flop_cbet,
                Street.TURN: p.turn_aggression,
                Street.RIVER: p.river_aggression,
            }[game.street]
            continuation = (0.65 * p.calling_tendency + 0.35 * (100 - p.fold_to_flop_cbet)) / 100
        raise_rate = (0.45 * pressure + 0.15 * p.bluffing_tendency) / 100
        roll = rng.random()
        if aggression is not None and roll < raise_rate:
            assert legal.min_raise_to is not None
            target = game.current_bet + round(game.pot * (0.33 + pressure / 150))
            return Decision(aggression, min(legal.max_raise_to, max(legal.min_raise_to, target)))
        if Action.CALL in legal.actions:
            return Decision(Action.CALL if roll < max(raise_rate, continuation) else Action.FOLD)
        return Decision(Action.CHECK)
