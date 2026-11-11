"""Replay versioned public histories with the betting engine. Unknown cards stay unknown."""

from typing import Annotated, Literal, Self, cast

from pydantic import Field, model_validator

from poker_lab.engine import Holdem
from poker_lab.evaluator import DECK, validate_cards
from poker_lab.models import Action, LegalActions, Street
from poker_lab.schemas import GameView
from poker_lab.strategy_models import (
    POSITIONS,
    BettingEvent,
    Chips,
    Position,
    PositiveChips,
    StrategyScenario,
    StrictModel,
    validate_action,
)
from poker_lab.study import BoardTexture, board_texture


class Seat(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    stack: PositiveChips
    cards: tuple[str, str] | None = None


class Hand(StrictModel):
    version: Literal["1.0"]
    seats: dict[Position, Seat]
    hero: Position
    small_blind: PositiveChips
    big_blind: PositiveChips
    initial_pot: Chips | None = None
    board: list[str] = Field(max_length=5)
    actions: list[BettingEvent] = Field(max_length=512)
    # Optional verified payout totals per winner, in chips.
    payouts: dict[Position, Chips] | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if set(self.seats) != set(POSITIONS) or self.small_blind * 2 != self.big_blind:
            raise ValueError("Enter all six seats and a big blind twice the small blind")
        if len(self.board) not in (0, 3, 4, 5):
            raise ValueError("Enter a complete flop before adding turn and river")
        known = self.board + [c for seat in self.seats.values() for c in seat.cards or ()]
        validate_cards(known, len(known))
        return self


class ReplayGame(Holdem):
    def __init__(self, hand: Hand):
        self.hand = hand
        self.pending_award = False
        slots: dict[int, str] = {}
        for i, pos in enumerate(POSITIONS):
            for round_no, card in enumerate(hand.seats[cast(Position, pos)].cards or ()):
                slots[(i - 1) % 6 + round_no * 6] = card
        slots.update(zip([13, 14, 15, 17, 19], hand.board, strict=False))
        remaining = iter(c for c in DECK if c not in slots.values())
        deck = [slots[i] if i in slots else next(remaining) for i in range(52)]
        super().__init__(
            big_blind=hand.big_blind,
            stacks=[hand.seats[cast(Position, p)].stack for p in POSITIONS],
            deck=deck,
        )

    def _settle(self) -> None:
        live = [p for p in self.players if not p.folded]
        if len(live) > 1 and (
            len(self.hand.board) < 5
            or any(self.hand.seats[cast(Position, POSITIONS[p.seat])].cards is None for p in live)
        ):
            self.pending_award = True
            self.street = Street.COMPLETE
            self.actor = None
            return
        super()._settle()


class Player(StrictModel):
    name: str
    stack: int
    bet: int
    contribution: int
    cards: tuple[str, str] | None
    status: str


class Snapshot(StrictModel):
    prior_action_count: int
    street: Street
    actor: Position | None
    board: list[str]
    board_complete: bool
    pot: int
    players: dict[Position, Player]
    legal: LegalActions
    texture: BoardTexture
    odds: float | None
    payouts: dict[Position, int]
    pending_award: bool
    candidates: list[str]


def replay(hand: Hand, scenarios: list[tuple[str, StrategyScenario]]) -> list[Snapshot]:
    game = ReplayGame(hand)
    if hand.initial_pot is not None and hand.initial_pot != game.pot:
        raise ValueError("Initial pot conflicts with posted blinds")
    states = []
    for i in range(len(hand.actions) + 1):
        board = hand.board[: len(game.board)]
        full = len(board) == len(game.board)
        actor = cast(Position, POSITIONS[game.actor]) if game.actor is not None else None
        legal = game.legal_actions()
        contested = sum(not p.folded for p in game.players) > 1
        players = {}
        payouts: dict[Position, int] = {}
        for award in game.awards:
            for seat, amount in award.payouts:
                pos = cast(Position, POSITIONS[seat])
                payouts[pos] = payouts.get(pos, 0) + amount
        for p in game.players:
            pos = cast(Position, POSITIONS[p.seat])
            visible = pos == hand.hero or (
                game.street == Street.COMPLETE and contested and not p.folded
            )
            players[pos] = Player(
                name=hand.seats[pos].name,
                stack=p.stack,
                bet=p.street_bet,
                contribution=p.contributed,
                cards=hand.seats[pos].cards if visible else None,
                status="folded"
                if p.folded
                else "settled"
                if game.awards
                else "all-in"
                if not p.stack
                else "acting"
                if pos == actor
                else "active",
            )
        odds = None
        if legal.to_call and game.actor is not None:
            cap = game.players[game.actor].contributed + legal.to_call
            eligible_after_call = legal.to_call + sum(min(p.contributed, cap) for p in game.players)
            odds = legal.to_call / eligible_after_call
        candidates = []
        for sid, s in scenarios:
            if (
                actor == s.hero_position
                and game.street == s.street
                and game.pot == s.pot
                and full
                and sorted(board[:3]) == sorted(s.board[:3])
                and board[3:] == s.board[3:]
                and not s.dead_cards
                and s.big_blind == hand.big_blind
                and s.history == hand.actions[:i]
                and all(s.starting_stacks[pos] == seat.stack for pos, seat in hand.seats.items())
            ):
                candidates.append(sid)
        states.append(
            Snapshot(
                prior_action_count=i,
                street=game.street,
                actor=actor,
                board=board,
                board_complete=full,
                pot=game.pot,
                players=players,
                legal=legal,
                texture=board_texture(board),
                odds=odds,
                payouts=payouts,
                pending_award=game.pending_award,
                candidates=candidates,
            )
        )
        if i < len(hand.actions):
            e = hand.actions[i]
            if not full or e.street != game.street or e.position != actor or game.actor is None:
                raise ValueError(f"Action {i + 1}: missing board, wrong street or wrong actor")
            validate_action(game, e)
            game.act(
                game.actor, e.action, e.amount if e.action in (Action.BET, Action.RAISE) else None
            )
    if game.street == Street.COMPLETE and len(hand.board) > len(game.board):
        raise ValueError("Board extends beyond the end of the hand")
    if hand.payouts is not None and (not game.awards or hand.payouts != states[-1].payouts):
        raise ValueError("Reported payouts cannot be verified from this history")
    return states


def from_trainer(view: GameView) -> Hand:
    if view.street != Street.COMPLETE:
        raise ValueError("Finish the trainer hand before reviewing")
    positions = [cast(Position, p.position) for p in view.players]
    events = []
    for e in view.history:
        if e.seat is not None and e.action in Action._value2member_map_:
            events.append(
                BettingEvent.model_validate(
                    {
                        "position": positions[e.seat],
                        "street": e.street,
                        "action": e.action,
                        "amount": e.chips if e.action == "call" else e.raise_to,
                    }
                )
            )
    totals: dict[Position, int] = {}
    for pot in view.outcomes:
        for seat, amount in pot.payouts.items():
            totals[positions[seat]] = totals.get(positions[seat], 0) + amount
    return Hand.model_validate(
        {
            "version": "1.0",
            "hero": positions[view.hero],
            "small_blind": view.big_blind // 2,
            "big_blind": view.big_blind,
            "seats": {
                p.position: {"name": p.name, "stack": 100 * view.big_blind, "cards": p.cards}
                for p in view.players
            },
            "board": view.board,
            "actions": events,
            "payouts": totals,
        }
    )
