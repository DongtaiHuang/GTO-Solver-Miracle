"""Typed, bounded equity endpoints; calculations stay in poker_lab.equity."""

from dataclasses import asdict
from threading import BoundedSemaphore
from typing import Annotated, Literal, Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from poker_lab.equity import (
    MAX_SAMPLES,
    EquityResult,
    PlayerInput,
    WorkLimit,
    calculate_equity,
    pot_odds,
)
from poker_lab.ranges import HandRange

Chips = Annotated[StrictInt, Field(ge=0, le=100000000)]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
Cards = Annotated[list[str], Field(min_length=2, max_length=2)]


class EquityOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    board: list[str] = Field(default_factory=list, max_length=5)
    dead: list[str] = Field(default_factory=list, max_length=40)
    method: Literal["auto", "exact", "monte_carlo"] = "auto"
    samples: Annotated[StrictInt, Field(ge=100, le=MAX_SAMPLES)] = 2000
    seed: Annotated[StrictInt, Field(ge=0, le=2**32 - 1)] = 42


class PlayerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cards: Cards | None = None
    range: HandRange | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        if (self.cards is None) == (self.range is None):
            raise ValueError("Specify exactly one hand or range per player")
        return self

    def core(self) -> PlayerInput:
        return PlayerInput(
            tuple(self.cards) if self.cards is not None else None,
            self.range.weights if self.range is not None else None,
        )


class MultiwayRequest(EquityOptions):
    players: list[PlayerSpec] = Field(min_length=2, max_length=6)


class HandVsHandRequest(EquityOptions):
    hero_cards: Cards
    opponent_cards: Cards


class HandVsRangeRequest(EquityOptions):
    hero_cards: Cards
    opponent_range: HandRange


class RangeVsRangeRequest(EquityOptions):
    hero_range: HandRange
    opponent_range: HandRange


class UncertaintyView(BaseModel):
    standard_error: float
    lower: float
    upper: float
    confidence_level: float
    interval_method: str


class PlayerEquityView(BaseModel):
    win_probability: float
    tie_probability: float
    loss_probability: float
    equity: float
    uncertainty: UncertaintyView | None


class EquityView(BaseModel):
    method: Literal["exact", "monte_carlo"]
    players: list[PlayerEquityView]
    evaluated_outcomes: int
    valid_samples: int | None
    proposals: int
    seed: int | None
    unblocked_combinations: list[int]
    work_upper_bound: str
    distribution: str
    assumptions: list[str]


class PotOddsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pot: Chips
    call: Chips
    equity: Probability
    equity_interval: tuple[Probability, Probability] | None = None


class PotOddsView(BaseModel):
    required_equity: float
    call_ev: float
    call_ev_interval: tuple[float, float] | None
    explanation: str


def create_equity_router() -> APIRouter:
    router = APIRouter(prefix="/api/equity", tags=["equity"])
    gate = BoundedSemaphore(1)

    def run(options: EquityOptions, players: list[PlayerInput]) -> EquityResult:
        if not gate.acquire(blocking=False):
            raise HTTPException(
                429, "Equity calculator is busy; try again after the current calculation"
            )
        try:
            return calculate_equity(
                players,
                board=tuple(options.board),
                dead=tuple(options.dead),
                method=options.method,
                samples=options.samples,
                seed=options.seed,
            )
        except WorkLimit as exc:
            raise HTTPException(422, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        finally:
            gate.release()

    @router.post("/hand-vs-hand", response_model=EquityView)
    def hand_vs_hand(body: HandVsHandRequest) -> EquityView:
        return EquityView.model_validate(
            asdict(
                run(
                    body,
                    [
                        PlayerInput(cards=tuple(body.hero_cards)),
                        PlayerInput(cards=tuple(body.opponent_cards)),
                    ],
                )
            )
        )

    @router.post("/hand-vs-range", response_model=EquityView)
    def hand_vs_range(body: HandVsRangeRequest) -> EquityView:
        return EquityView.model_validate(
            asdict(
                run(
                    body,
                    [
                        PlayerInput(cards=tuple(body.hero_cards)),
                        PlayerInput(weights=body.opponent_range.weights),
                    ],
                )
            )
        )

    @router.post("/range-vs-range", response_model=EquityView)
    def range_vs_range(body: RangeVsRangeRequest) -> EquityView:
        return EquityView.model_validate(
            asdict(
                run(
                    body,
                    [
                        PlayerInput(weights=body.hero_range.weights),
                        PlayerInput(weights=body.opponent_range.weights),
                    ],
                )
            )
        )

    @router.post("/multiway", response_model=EquityView)
    def multiway(body: MultiwayRequest) -> EquityView:
        return EquityView.model_validate(asdict(run(body, [p.core() for p in body.players])))

    @router.post("/pot-odds", response_model=PotOddsView)
    def odds(body: PotOddsRequest) -> PotOddsView:
        try:
            result = pot_odds(body.pot, body.call, body.equity, body.equity_interval)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return PotOddsView.model_validate(asdict(result))

    return router
