from pydantic import BaseModel, ConfigDict, Field, StrictInt

from poker_lab.models import Action, Street
from poker_lab.profiles import OpponentProfile, ProfileConfig


class EmptyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewHandRequest(EmptyRequest):
    opponents: list[ProfileConfig] | None = Field(default=None, min_length=5, max_length=5)


class HeroAction(EmptyRequest):
    hand_id: str = Field(min_length=1, max_length=64)
    revision: StrictInt = Field(ge=0)
    action: Action
    amount: StrictInt | None = None


class PlayerView(BaseModel):
    seat: int
    name: str
    position: str
    stack: int
    bet: int
    status: str
    cards: list[str] | None
    effective_stack: int


class HistoryEntry(BaseModel):
    sequence: int
    street: Street
    seat: int | None
    name: str
    action: str
    chips: int
    raise_to: int | None = None


class LegalView(BaseModel):
    actions: list[Action]
    to_call: int
    min_raise_to: int | None
    max_raise_to: int
    presets: dict[str, int]


class Outcome(BaseModel):
    pot: int
    winners: list[int]
    payouts: dict[int, int]


class GameView(BaseModel):
    hand_id: str
    hand_number: int
    revision: int
    street: Street
    button: int
    hero: int
    actor: int | None
    board: list[str]
    pot: int
    settled_pot: int
    big_blind: int
    effective_stack: int
    players: list[PlayerView]
    legal: LegalView
    history: list[HistoryEntry]
    outcomes: list[Outcome]
    showdown: bool
    opponents: list[OpponentProfile] = Field(default_factory=list)
