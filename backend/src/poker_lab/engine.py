"""Single-hand 6-max NLHE state machine. All amounts are integer chip units."""

import random

from poker_lab.evaluator import DECK, evaluate, validate_cards
from poker_lab.models import Action, Award, LegalActions, Player, Pot, Street


class Holdem:
    def __init__(
        self,
        *,
        seed: int = 0,
        button: int = 0,
        seats: int = 6,
        big_blind: int = 100,
        stacks: list[int] | None = None,
        deck: list[str] | None = None,
    ) -> None:
        if type(seats) is not int or not 2 <= seats <= 6:
            raise ValueError("Use two to six occupied seats")
        if type(button) is not int or not 0 <= button < seats:
            raise ValueError("Invalid button")
        if type(big_blind) is not int or big_blind < 2 or big_blind % 2:
            raise ValueError("Big blind must be a positive even integer")
        initial = [100 * big_blind] * seats if stacks is None else list(stacks)
        if len(initial) != seats or any(type(s) is not int or s <= 0 for s in initial):
            raise ValueError("Each occupied seat needs a positive integer stack")
        self.players = [Player(i, stack) for i, stack in enumerate(initial)]
        self.initial_chips = sum(initial)
        self.button = button
        self.big_blind = big_blind
        self.deck = list(DECK) if deck is None else list(deck)
        validate_cards(self.deck, 52)
        if deck is None:
            random.Random(seed).shuffle(self.deck)
        self.board: list[str] = []
        self.burned: list[str] = []
        self.street = Street.PREFLOP
        self.current_bet = big_blind
        self.last_full_raise = big_blind
        self.last_action: dict[int, int] = {}
        self.awards: list[Award] = []
        self.actor: int | None = None
        for _ in range(2):
            for offset in range(1, seats + 1):
                self.players[(button + offset) % seats].hole.append(self.deck.pop(0))
        small = button if seats == 2 else (button + 1) % seats
        big = (small + 1) % seats
        self._commit(small, min(big_blind // 2, self.players[small].stack))
        self._commit(big, min(big_blind, self.players[big].stack))
        self._advance(big)

    @property
    def pot(self) -> int:
        return sum(p.contributed for p in self.players)

    def _commit(self, seat: int, amount: int) -> None:
        p = self.players[seat]
        p.stack -= amount
        p.street_bet += amount
        p.contributed += amount

    def _raise_open(self, seat: int) -> bool:
        return (
            seat not in self.last_action
            or self.last_action[seat] == 0
            or self.current_bet - self.last_action[seat] >= self.last_full_raise
        )

    def legal_actions(self) -> LegalActions:
        if self.actor is None:
            return LegalActions((), 0, None, 0)
        p = self.players[self.actor]
        owed = max(0, self.current_bet - p.street_bet)
        maximum = p.street_bet + p.stack
        minimum = self.current_bet + self.last_full_raise
        actions = [Action.FOLD, Action.CALL if owed else Action.CHECK]
        opponents = any(q.can_act and q.seat != p.seat for q in self.players)
        may_raise = self._raise_open(p.seat) and opponents
        if may_raise and maximum >= minimum:
            actions.append(Action.BET if self.current_bet == 0 else Action.RAISE)
        if maximum <= self.current_bet or may_raise:
            actions.append(Action.ALL_IN)
        return LegalActions(
            tuple(actions),
            min(owed, p.stack),
            minimum if may_raise and maximum >= minimum else None,
            maximum,
        )

    def act(self, seat: int, action: Action | str, amount: int | None = None) -> None:
        """Bet/raise amount is the total street contribution (raise-to), never a delta."""
        if self.actor is None or type(seat) is not int or seat != self.actor:
            raise ValueError("Not this seat's turn")
        action = Action(action)
        legal = self.legal_actions()
        if action not in legal.actions:
            raise ValueError("Illegal action")
        if action in (Action.BET, Action.RAISE):
            if (
                type(amount) is not int
                or legal.min_raise_to is None
                or not legal.min_raise_to <= amount <= legal.max_raise_to
            ):
                raise ValueError("Invalid raise-to amount")
        elif amount is not None:
            raise ValueError("Only bet/raise accepts an amount")
        p = self.players[seat]
        if action == Action.FOLD:
            p.folded = True
        elif action == Action.CALL:
            self._commit(seat, legal.to_call)
        elif action in (Action.BET, Action.RAISE, Action.ALL_IN):
            target = legal.max_raise_to if action == Action.ALL_IN else amount
            assert target is not None
            old = self.current_bet
            self._commit(seat, target - p.street_bet)
            if target > old:
                if target - old >= self.last_full_raise:
                    self.last_full_raise = target - old
                    self.last_action.clear()
                self.current_bet = target
        self.last_action[seat] = self.current_bet
        self._advance(seat)

    def _advance(self, after: int) -> None:
        live = [p for p in self.players if not p.folded]
        if len(live) == 1:
            self._settle()
            return
        active = [p for p in live if p.can_act]
        pending = [
            p for p in active if p.street_bet < self.current_bet or p.seat not in self.last_action
        ]
        # A sole player with chips has no opponent who can answer a bet.
        if len(active) <= 1:
            pending = [p for p in active if p.street_bet < self.current_bet]
        if pending:
            self.actor = min(pending, key=lambda p: (p.seat - after - 1) % len(self.players)).seat
            return
        self.actor = None
        if self.street == Street.RIVER:
            self._settle()
            return
        self.street = {
            Street.PREFLOP: Street.FLOP,
            Street.FLOP: Street.TURN,
            Street.TURN: Street.RIVER,
        }[self.street]
        self.burned.append(self.deck.pop(0))
        count = 3 if self.street == Street.FLOP else 1
        self.board.extend(self.deck.pop(0) for _ in range(count))
        for p in self.players:
            p.street_bet = 0
        self.current_bet = 0
        self.last_full_raise = self.big_blind
        self.last_action.clear()
        self._advance(self.button)

    def side_pots(self) -> list[Pot]:
        pots: list[Pot] = []
        previous = 0
        for level in sorted({p.contributed for p in self.players if p.contributed}):
            contributors = [p for p in self.players if p.contributed >= level]
            pots.append(
                Pot(
                    (level - previous) * len(contributors),
                    tuple(p.seat for p in contributors if not p.folded),
                )
            )
            previous = level
        return pots

    def _settle(self) -> None:
        live = [p for p in self.players if not p.folded]
        ranks = {p.seat: evaluate(p.hole + self.board) for p in live} if len(live) > 1 else {}
        for pot in self.side_pots():
            best = max(ranks.get(s, ()) for s in pot.eligible)
            winners = tuple(
                sorted(
                    (s for s in pot.eligible if ranks.get(s, ()) == best),
                    key=lambda s: (s - self.button - 1) % len(self.players),
                )
            )
            share, extra = divmod(pot.amount, len(winners))
            payouts = tuple((s, share + (i < extra)) for i, s in enumerate(winners))
            for seat, chips in payouts:
                self.players[seat].stack += chips
            self.awards.append(Award(pot, winners, payouts))
        for p in self.players:
            p.contributed = 0
            p.street_bet = 0
        self.street = Street.COMPLETE
        self.actor = None
        self.current_bet = 0
