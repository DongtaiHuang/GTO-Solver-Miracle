"""Study contracts and honest provider boundaries. No solver data is bundled."""

import hashlib
import json
import math
from collections import Counter
from typing import Annotated, Literal, Protocol, Self, cast

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from poker_lab.evaluator import RANKS, validate_cards
from poker_lab.models import Action, Street
from poker_lab.profiles import OpponentProfile, ProfileConfig, ProfileId, resolve_profile
from poker_lab.ranges import HandRange, RangeSummary, modeled_range, summarize
from poker_lab.schemas import GameView

Position = Literal["UTG", "HJ", "CO", "BTN", "SB", "BB"]
Chips = Annotated[StrictInt, Field(ge=0, le=100000000)]


class StudySpot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_format: Literal["6-max NLHE cash"] = "6-max NLHE cash"
    starting_stack_bb: Literal[100] = 100
    hero_position: Position = "BTN"
    opponent_position: Position = "BB"
    hero_cards: list[str] = Field(default_factory=list, max_length=2)
    board: list[str] = Field(default_factory=list, max_length=5)
    street: Street = Street.PREFLOP
    pot: Chips = 150
    bet_sizes: list[Chips] = Field(default_factory=list, max_length=8)
    history: str = Field(default="", max_length=100000)

    @model_validator(mode="after")
    def valid_spot(self) -> Self:
        if self.hero_position == self.opponent_position:
            raise ValueError("Hero and opponent positions must differ")
        if len(self.hero_cards) not in (0, 2):
            raise ValueError("Specify either zero or two hero cards")
        cards = self.hero_cards + self.board
        validate_cards(cards, len(cards))
        lengths = {
            Street.PREFLOP: (0,),
            Street.FLOP: (3,),
            Street.TURN: (4,),
            Street.RIVER: (5,),
            Street.COMPLETE: (0, 3, 4, 5),
        }
        if len(self.board) not in lengths[self.street]:
            raise ValueError("Board card count does not match the selected street")
        return self


class StudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spot: StudySpot = Field(default_factory=StudySpot)
    opponent: ProfileConfig = Field(default_factory=lambda: ProfileConfig(id=ProfileId.TAG))
    hero_range: HandRange = Field(default_factory=HandRange)
    opponent_range: HandRange | None = None


class StrategyResponse(BaseModel):
    game_state_id: str
    legal_actions: list[Action] | None
    frequencies: dict[Action, float] | None = None
    ev_per_action: dict[Action, float] | None = None
    hand_equity: float | None = None
    source: str
    calculation_method: str
    availability: Literal["unavailable", "model_only", "available"]
    confidence: Literal["not_applicable", "unvalidated", "validated"]
    assumptions: list[str]
    explanation: str

    @model_validator(mode="after")
    def consistent(self) -> Self:
        numeric = (
            self.frequencies is not None
            or self.ev_per_action is not None
            or self.hand_equity is not None
        )
        if self.availability != "available" and numeric:
            raise ValueError("Unavailable and modeled providers must not supply solver numbers")
        if self.availability == "available" and self.confidence != "validated":
            raise ValueError("Available solutions require validated provenance")
        if self.frequencies is not None and (
            self.legal_actions is None
            or not set(self.frequencies) <= set(self.legal_actions)
            or any(not 0 <= v <= 1 for v in self.frequencies.values())
            or abs(sum(self.frequencies.values()) - 1) > 0.000001
        ):
            raise ValueError("Frequencies must be normalized over legal actions")
        if self.ev_per_action is not None and (
            self.legal_actions is None
            or not set(self.ev_per_action) <= set(self.legal_actions)
            or any(not math.isfinite(v) for v in self.ev_per_action.values())
        ):
            raise ValueError("EV entries must reference legal actions")
        if self.hand_equity is not None and not 0 <= self.hand_equity <= 1:
            raise ValueError("Equity must be between zero and one")
        return self


class ProviderContext(BaseModel):
    spot: StudySpot = Field(default_factory=StudySpot)
    hero_range: HandRange = Field(default_factory=HandRange)
    opponent_range: HandRange = Field(default_factory=HandRange)
    trainer_state: GameView | None = None
    game_state_id: str
    legal_actions: list[Action] | None
    profile: OpponentProfile


class StrategyProvider(Protocol):
    def analyze(self, context: ProviderContext) -> StrategyResponse: ...


class PrecomputedGTOProvider:
    def analyze(self, context: ProviderContext) -> StrategyResponse:
        return StrategyResponse(
            game_state_id=context.game_state_id,
            legal_actions=context.legal_actions,
            source="precomputed_gto",
            calculation_method="No validated dataset configured",
            availability="unavailable",
            confidence="not_applicable",
            assumptions=["No strategy dataset or supported spot library has been loaded."],
            explanation="GTO solution unavailable",
        )


class StatisticalOpponentModel:
    def analyze(self, context: ProviderContext) -> StrategyResponse:
        return StrategyResponse(
            game_state_id=context.game_state_id,
            legal_actions=context.legal_actions,
            source="statistical_opponent_model",
            calculation_method="User-configurable archetype assumptions",
            availability="model_only" if context.profile.parameters else "unavailable",
            confidence="unvalidated" if context.profile.parameters else "not_applicable",
            assumptions=[
                "Profile values are tuning assumptions, not measured population statistics.",
                "VPIP sets range width; a documented rank/suitedness ordering fills classes.",
                "Range weights are inclusion weights, not action frequencies or hand equity.",
                "No best response, exploitative EV, or equilibrium has been calculated.",
            ],
            explanation=context.profile.description,
        )


class CustomCFRProvider:
    def analyze(self, context: ProviderContext) -> StrategyResponse:
        return StrategyResponse(
            game_state_id=context.game_state_id,
            legal_actions=context.legal_actions,
            source="custom_cfr",
            calculation_method="Solver interface reserved; no solver executed",
            availability="unavailable",
            confidence="not_applicable",
            assumptions=["A custom CFR solver is outside this milestone."],
            explanation="GTO solution unavailable",
        )


class BoardTexture(BaseModel):
    availability: Literal["calculated", "not_applicable"]
    paired: bool | None
    max_suit_count: int
    rank_span: int | None
    explanation: str


def board_texture(board: list[str]) -> BoardTexture:
    counts = Counter(card[0] for card in board)
    suits = Counter(card[1] for card in board)
    ranks = [RANKS.index(card[0]) + 2 for card in board]
    return BoardTexture(
        availability="calculated" if board else "not_applicable",
        paired=any(count > 1 for count in counts.values()) if board else None,
        max_suit_count=max(suits.values(), default=0),
        rank_span=max(ranks) - min(ranks) if ranks else None,
        explanation="Exact visible-card counts and high-ace rank span; no equity or strategic inference.",
    )


class StudyResult(BaseModel):
    game_state_id: str
    spot: StudySpot
    opponent: OpponentProfile
    hero_range: RangeSummary
    opponent_range: RangeSummary
    texture: BoardTexture
    providers: list[StrategyResponse]
    context_source: Literal["hypothetical", "trainer_snapshot"]
    trainer_hand_id: str | None = None
    trainer_revision: int | None = None


def analyze(request: StudyRequest, game: GameView | None = None) -> StudyResult:
    profile = resolve_profile(request.opponent)
    canonical = request.model_dump(mode="json")
    canonical["trainer"] = [game.hand_id, game.revision] if game else None
    state_id = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()[:24]
    providers: tuple[StrategyProvider, ...] = (
        PrecomputedGTOProvider(),
        StatisticalOpponentModel(),
        CustomCFRProvider(),
    )
    opponent_range = request.opponent_range
    if opponent_range is None:
        opponent_range = modeled_range(profile)
    context = ProviderContext(
        game_state_id=state_id,
        legal_actions=game.legal.actions if game else None,
        profile=profile,
        spot=request.spot,
        hero_range=request.hero_range,
        opponent_range=opponent_range,
        trainer_state=game,
    )
    dead = request.spot.hero_cards + request.spot.board
    return StudyResult(
        game_state_id=state_id,
        spot=request.spot,
        opponent=profile,
        hero_range=summarize(request.hero_range, request.spot.board, "editable_manual"),
        opponent_range=summarize(
            opponent_range,
            dead,
            "editable_manual"
            if request.opponent_range is not None
            else "modeled_assumption"
            if profile.parameters
            else "unspecified_no_gto_solution",
        ),
        texture=board_texture(request.spot.board),
        providers=[provider.analyze(context) for provider in providers],
        context_source="trainer_snapshot" if game else "hypothetical",
        trainer_hand_id=game.hand_id if game else None,
        trainer_revision=game.revision if game else None,
    )


def study_current(game: GameView) -> StudyResult:
    hero = game.players[game.hero]
    opponent = next(
        (p for p in game.players if p.seat != game.hero and p.status != "folded"), game.players[1]
    )
    profile = (
        game.opponents[opponent.seat - 1]
        if game.opponents
        else resolve_profile(ProfileConfig(id=ProfileId.STANDARD_GTO))
    )
    spot = StudySpot(
        hero_position=cast(Position, hero.position),
        opponent_position=cast(Position, opponent.position),
        hero_cards=hero.cards or [],
        board=game.board,
        street=game.street,
        pot=game.settled_pot if game.street == Street.COMPLETE else game.pot,
        bet_sizes=[p.bet for p in game.players if p.bet],
        history="\n".join(
            f"{h.sequence}. {h.street}: {h.name} {h.action} {h.chips}"
            + (f" to {h.raise_to}" if h.raise_to is not None else "")
            for h in game.history
        ),
    )
    return analyze(
        StudyRequest(
            spot=spot, opponent=ProfileConfig(id=profile.id, parameters=profile.parameters)
        ),
        game,
    )
