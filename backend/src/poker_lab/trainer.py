"""Isolated in-memory sessions and public views over the independent rules engine."""

import random
import secrets
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from threading import RLock

from poker_lab.engine import Holdem
from poker_lab.models import Action, Street
from poker_lab.policy import OpponentPolicy, ProfilePolicy, RandomPolicy
from poker_lab.profiles import OpponentProfile, ProfileConfig, resolve_profile
from poker_lab.schemas import (
    GameView,
    HeroAction,
    HistoryEntry,
    LegalView,
    Outcome,
    PlayerView,
)

NAMES = ("You", "Alex", "Morgan", "Sam", "Jordan", "Casey")
POSITIONS = ("BTN", "SB", "BB", "UTG", "HJ", "CO")


class MissingSession(Exception):
    pass


class StaleHand(Exception):
    pass


class CapacityReached(Exception):
    pass


@dataclass
class Session:
    game: Holdem
    rng: random.Random
    hand_id: str
    hand_number: int
    revision: int
    history: list[HistoryEntry]
    updated: float
    opponents: tuple[OpponentProfile, ...] = ()


def record(
    session: Session,
    seat: int | None,
    action: str,
    chips: int = 0,
    raise_to: int | None = None,
    street: Street | None = None,
) -> None:
    session.history.append(
        HistoryEntry(
            sequence=len(session.history) + 1,
            street=street or session.game.street,
            seat=seat,
            name=NAMES[seat] if seat is not None else "Dealer",
            action=action,
            chips=chips,
            raise_to=raise_to,
        )
    )


def apply_action(session: Session, seat: int, action: Action, amount: int | None) -> None:
    game = session.game
    old_street, old_board = game.street, len(game.board)
    player = game.players[seat]
    chips = 0
    if action == Action.CALL:
        chips = game.legal_actions().to_call
    elif action == Action.ALL_IN:
        chips = player.stack
    elif action in (Action.BET, Action.RAISE) and amount is not None:
        chips = amount - player.street_bet
    target = player.street_bet + chips
    game.act(seat, action, amount)
    record(
        session,
        seat,
        action,
        chips,
        target if action in (Action.BET, Action.RAISE, Action.ALL_IN) else None,
        old_street,
    )
    for street, length in ((Street.FLOP, 3), (Street.TURN, 4), (Street.RIVER, 5)):
        if old_board < length <= len(game.board):
            record(session, None, "deal", street=street)
    if game.street == Street.COMPLETE:
        record(
            session,
            None,
            "showdown" if sum(not p.folded for p in game.players) > 1 else "uncontested",
        )


def view(session: Session) -> GameView:
    g = session.game
    showdown = g.street == Street.COMPLETE and sum(not p.folded for p in g.players) > 1
    hero = g.players[0]
    legal = g.legal_actions()
    actions = list(legal.actions) if g.actor == 0 else []
    presets: dict[str, int] = {}
    if actions and legal.min_raise_to is not None:
        # A pot-sized raise adds the pot AFTER calling to the current wager.
        call = legal.to_call
        for percent in (33, 50, 75, 100):
            target = g.current_bet + (g.pot + call) * percent // 100
            presets[str(percent)] = min(legal.max_raise_to, max(legal.min_raise_to, target))
    players = []
    for p in g.players:
        status = (
            "folded"
            if p.folded
            else "settled"
            if g.street == Street.COMPLETE
            else "all-in"
            if p.stack == 0
            else "acting"
            if p.seat == g.actor
            else "waiting"
        )
        players.append(
            PlayerView(
                seat=p.seat,
                name=NAMES[p.seat],
                position=POSITIONS[(p.seat - g.button) % 6],
                stack=p.stack,
                bet=p.street_bet,
                status=status,
                cards=list(p.hole) if p.seat == 0 or (showdown and not p.folded) else None,
                effective_stack=min(hero.stack, p.stack),
            )
        )
    return GameView(
        hand_id=session.hand_id,
        hand_number=session.hand_number,
        revision=session.revision,
        street=g.street,
        button=g.button,
        hero=0,
        actor=g.actor,
        board=list(g.board),
        pot=g.pot,
        settled_pot=sum(a.pot.amount for a in g.awards),
        big_blind=g.big_blind,
        effective_stack=min(
            hero.stack, max((p.stack for p in g.players[1:] if not p.folded), default=0)
        ),
        players=players,
        legal=LegalView(
            actions=actions,
            to_call=legal.to_call,
            min_raise_to=legal.min_raise_to,
            max_raise_to=legal.max_raise_to,
            presets=presets,
        ),
        history=list(session.history),
        outcomes=[
            Outcome(pot=a.pot.amount, winners=list(a.winners), payouts=dict(a.payouts))
            for a in g.awards
        ],
        showdown=showdown,
        opponents=list(session.opponents),
    )


class SessionStore:
    def __init__(
        self,
        *,
        policy: OpponentPolicy | None = None,
        seed_factory: Callable[[], int] | None = None,
        clock: Callable[[], float] = time.monotonic,
        ttl: float = 7200,
        capacity: int = 512,
    ) -> None:
        self.sessions: dict[str, Session] = {}
        self.lock = RLock()
        self.policy = policy or RandomPolicy()
        self.seed_factory = seed_factory or (lambda: secrets.randbits(128))
        self.clock, self.ttl, self.capacity = clock, ttl, capacity

    def _lookup(self, token: str | None) -> Session:
        now = self.clock()
        for key in list(self.sessions):
            if now - self.sessions[key].updated >= self.ttl:
                del self.sessions[key]
        if token is None or token not in self.sessions:
            raise MissingSession
        return self.sessions[token]

    def _opponents(self, session: Session) -> None:
        while session.game.actor is not None:
            seat = session.game.actor
            if seat == 0 and not session.game.players[0].folded:
                break
            policy = (
                ProfilePolicy(session.opponents[seat - 1]) if session.opponents else self.policy
            )
            decision = policy.choose(session.game, session.rng)
            apply_action(session, seat, decision.action, decision.amount)

    def create(
        self, token: str | None, configs: list[ProfileConfig] | None = None
    ) -> tuple[str, GameView]:
        with self.lock:
            try:
                previous = self._lookup(token)
            except MissingSession:
                previous = None
            if previous is not None and previous.game.street != Street.COMPLETE:
                raise StaleHand("Finish the current hand before starting another")
            if previous is None and len(self.sessions) >= self.capacity:
                raise CapacityReached
            hand_number = previous.hand_number + 1 if previous else 1
            button = (previous.game.button + 1) % 6 if previous else 0
            session = Session(
                game=Holdem(seed=self.seed_factory(), button=button),
                rng=random.Random(self.seed_factory()),
                hand_id=secrets.token_urlsafe(16),
                hand_number=hand_number,
                revision=0,
                history=[],
                updated=self.clock(),
                opponents=tuple(resolve_profile(c) for c in configs)
                if configs is not None
                else previous.opponents
                if previous
                else (),
            )
            record(session, (button + 1) % 6, "small_blind", 50, street=Street.PREFLOP)
            record(session, (button + 2) % 6, "big_blind", 100, street=Street.PREFLOP)
            self._opponents(session)
            new_token = (
                token if previous is not None and token is not None else secrets.token_urlsafe(32)
            )
            self.sessions[new_token] = session
            return new_token, view(session)

    def get(self, token: str | None) -> GameView:
        with self.lock:
            session = self._lookup(token)
            session.updated = self.clock()
            return view(session)

    def act(self, token: str | None, request: HeroAction) -> GameView:
        with self.lock:
            original = self._lookup(token)
            if (
                request.hand_id != original.hand_id
                or request.revision != original.revision
                or original.game.actor != 0
            ):
                raise StaleHand("Hand has changed; refresh before acting")
            # Commit only after both the hero and all automatic actions succeed.
            session = deepcopy(original)
            apply_action(session, 0, request.action, request.amount)
            self._opponents(session)
            session.revision += 1
            session.updated = self.clock()
            assert token is not None
            self.sessions[token] = session
            return view(session)
