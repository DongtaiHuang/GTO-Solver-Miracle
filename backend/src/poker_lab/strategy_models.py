"""Version 1 strategy exports. Structural validation is not proof of equilibrium."""

import hashlib
import json
from typing import Annotated, Literal, Self, cast

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from poker_lab.engine import Holdem
from poker_lab.evaluator import DECK, validate_cards
from poker_lab.models import Action

POSITIONS = ("BTN", "SB", "BB", "UTG", "HJ", "CO")
Position = Literal["BTN", "SB", "BB", "UTG", "HJ", "CO"]
Chips = Annotated[StrictInt, Field(ge=0, le=100000000)]
PositiveChips = Annotated[StrictInt, Field(gt=0, le=100000000)]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=3, max_length=3000)]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{3,80}$")]
DECK_ORDER = {card: i for i, card in enumerate(DECK)}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SizedAction(StrictModel):
    action: Action
    amount: Chips | None = None

    @property
    def key(self) -> str:
        return self.action.value + (f"@{self.amount}" if self.amount is not None else "")


class BettingEvent(SizedAction):
    street: Literal["preflop", "flop", "turn", "river"]
    position: Position


class Abstraction(StrictModel):
    tree_id: Identifier
    range_model_id: Identifier
    card_model: Literal["exact_cards"]
    rake_model: Literal["none"]
    action_semantics: Literal["total_street_bet_for_aggression"]
    assumptions: list[Text] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_assumptions(self) -> Self:
        if len(set(self.assumptions)) != len(self.assumptions):
            raise ValueError("Duplicate abstraction assumptions")
        return self


def validate_action(game: Holdem, definition: SizedAction) -> None:
    legal = game.legal_actions()
    if definition.action not in legal.actions:
        raise ValueError(f"Action {definition.key} is not engine-legal at this node")
    if definition.action in (Action.FOLD, Action.CHECK):
        valid = definition.amount is None
    elif definition.action == Action.CALL:
        valid = definition.amount == legal.to_call
    elif definition.action == Action.ALL_IN:
        valid = definition.amount == legal.max_raise_to
    else:
        valid = (
            definition.amount is not None
            and legal.min_raise_to is not None
            and legal.min_raise_to <= definition.amount <= legal.max_raise_to
        )
    if not valid:
        raise ValueError(f"Invalid exact action size for {definition.key}")


class StrategyScenario(StrictModel):
    schema_version: Literal["1.0"]
    game_format: Literal["6-max NLHE cash"]
    players: Literal[6]
    starting_stacks: dict[Position, PositiveChips]
    small_blind: PositiveChips
    big_blind: PositiveChips
    ante: Literal[0]
    hero_position: Position
    opponent_position: Position
    effective_stack: Chips
    pot: Chips
    street: Literal["preflop", "flop", "turn", "river"]
    board: list[str] = Field(max_length=5)
    dead_cards: list[str] = Field(max_length=20)
    history: list[BettingEvent] = Field(max_length=2000)
    legal_actions: list[SizedAction] = Field(min_length=2, max_length=12)
    abstraction: Abstraction

    @field_validator("players", "ante", mode="before")
    @classmethod
    def integer_literals(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Player count and ante must be integers")
        return value

    def replay(self) -> Holdem:
        if set(self.starting_stacks) != set(POSITIONS):
            raise ValueError("All six starting positions must be defined exactly once")
        if self.small_blind * 2 != self.big_blind:
            raise ValueError("Version 1 supports a half-big-blind small blind and zero antes")
        game = Holdem(
            button=0,
            big_blind=self.big_blind,
            stacks=[self.starting_stacks[cast(Position, p)] for p in POSITIONS],
        )
        for event in self.history:
            if game.actor != POSITIONS.index(event.position) or game.street != event.street:
                raise ValueError("History is incomplete, out of turn, or on the wrong street")
            validate_action(game, event)
            amount = event.amount if event.action in (Action.BET, Action.RAISE) else None
            game.act(game.actor, event.action, amount)
        return game

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.hero_position == self.opponent_position:
            raise ValueError("Hero and opponent positions must differ")
        cards = self.board + self.dead_cards
        validate_cards(cards, len(cards))
        expected = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
        if len(self.board) != expected[self.street]:
            raise ValueError("Board length does not match street")
        game = self.replay()
        hero = game.players[POSITIONS.index(self.hero_position)]
        opponent = game.players[POSITIONS.index(self.opponent_position)]
        if (
            game.street != self.street
            or game.actor != hero.seat
            or opponent.folded
            or self.pot != game.pot
            or self.effective_stack != min(hero.stack, opponent.stack)
        ):
            raise ValueError("Scenario conflicts with the replayed decision node")
        keys = [a.key for a in self.legal_actions]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate or ambiguous action definitions")
        for action in self.legal_actions:
            validate_action(game, action)
        effects = [
            (a.action.value, None)
            if a.action in (Action.FOLD, Action.CHECK)
            else (
                "commit",
                hero.street_bet + game.legal_actions().to_call
                if a.action == Action.CALL
                else a.amount,
            )
            for a in self.legal_actions
        ]
        if len(set(effects)) != len(effects):
            raise ValueError("Action definitions contain equivalent duplicate chip commitments")
        required = {Action.FOLD, Action.CALL if game.legal_actions().to_call else Action.CHECK}
        if not required <= {a.action for a in self.legal_actions}:
            raise ValueError("Abstraction must retain fold and the legal passive action")
        return self

    def canonical(self) -> dict[str, object]:
        result = self.model_dump(mode="json")
        # Flop order is irrelevant; turn/river identity and history order are preserved.
        result["board"] = sorted(self.board[:3], key=DECK_ORDER.__getitem__) + self.board[3:]
        result["dead_cards"] = sorted(self.dead_cards, key=DECK_ORDER.__getitem__)
        result["legal_actions"] = [
            a.model_dump(mode="json") for a in sorted(self.legal_actions, key=lambda a: a.key)
        ]
        result["abstraction"]["assumptions"] = sorted(self.abstraction.assumptions)
        return result

    @property
    def scenario_id(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class Provenance(StrictModel):
    source_name: Text
    source_url: Annotated[str, Field(pattern=r"^https://[^\s]+$", max_length=2000)]
    license_name: Text
    license_url: Annotated[str, Field(pattern=r"^https://[^\s]+$", max_length=2000)]
    usage_granted: StrictBool
    usage_evidence: Text
    redistribution: Literal["permitted", "private_only"]
    publish: StrictBool

    @field_validator("source_url", "license_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        url = HttpUrl(value)
        if url.username or url.password:
            raise ValueError("Provenance URLs must not contain credentials")
        return str(url)

    @model_validator(mode="after")
    def permission(self) -> Self:
        if not self.usage_granted or (self.publish and self.redistribution != "permitted"):
            raise ValueError(
                "Explicit usage permission and appropriate publication permission are required"
            )
        return self


class ValidationInfo(StrictModel):
    status: Literal["synthetic_only", "unverified", "reviewed_gto"]
    checked_at: AwareDatetime
    methodology: Text
    evidence_reference: Text
    limitations: list[Text] = Field(min_length=1, max_length=20)
    ev_verified: StrictBool


class ComboStrategy(StrictModel):
    cards: tuple[str, str]
    reach_weight: Annotated[float, Field(strict=True, gt=0, le=1, allow_inf_nan=False)]
    frequencies: dict[str, Probability]
    action_ev: dict[str, Annotated[float, Field(strict=True, allow_inf_nan=False)]] | None = None


class StrategySolution(StrictModel):
    schema_version: Literal["1.0"]
    solution_id: Identifier
    kind: Literal["synthetic_fixture", "solver_solution"]
    scenario: StrategyScenario
    solver_identifier: Text
    solver_version: Text
    exported_at: AwareDatetime
    provenance: Provenance
    validation: ValidationInfo
    combinations: list[ComboStrategy] = Field(min_length=1, max_length=1326)

    @model_validator(mode="after")
    def validate_records(self) -> Self:
        synthetic = self.kind == "synthetic_fixture"
        if synthetic != (self.validation.status == "synthetic_only"):
            raise ValueError("Synthetic fixtures must remain labeled synthetic_only")
        if synthetic and (
            self.validation.ev_verified or any(c.action_ev is not None for c in self.combinations)
        ):
            raise ValueError("Synthetic fixtures cannot provide validated action EV")
        actions = {a.key for a in self.scenario.legal_actions}
        seen = set()
        blocked = set(self.scenario.board + self.scenario.dead_cards)
        for combo in self.combinations:
            validate_cards(combo.cards, 2)
            key = tuple(sorted(combo.cards, key=DECK_ORDER.__getitem__))
            if key in seen or blocked.intersection(key):
                raise ValueError("Duplicate combination or combination blocked by board/dead cards")
            seen.add(key)
            if set(combo.frequencies) != actions or abs(sum(combo.frequencies.values()) - 1) > 1e-6:
                raise ValueError(
                    "Each combination must define normalized frequencies for every legal action"
                )
            if combo.action_ev is not None and (
                not self.validation.ev_verified
                or self.validation.status != "reviewed_gto"
                or not set(combo.action_ev) <= actions
            ):
                raise ValueError("Action EV requires reviewed EV evidence and legal action keys")
        return self

    @property
    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class Dataset(StrictModel):
    schema_version: Literal["1.0"]
    dataset_id: Identifier
    solutions: list[StrategySolution] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def no_conflicts(self) -> Self:
        ids = [s.solution_id for s in self.solutions]
        scenarios = [(s.kind, s.scenario.scenario_id) for s in self.solutions]
        if len(set(ids)) != len(ids) or len(set(scenarios)) != len(scenarios):
            raise ValueError("Duplicate solution identifier or conflicting scenario definitions")
        return self


class Approval(StrictModel):
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    reviewer: Text
    evidence_reference: Text
    approved_at: AwareDatetime
    confirmed_source_and_rights: Literal[True]


class ImportedSolution(StrictModel):
    document: StrategySolution
    imported_at: AwareDatetime
    approval: Approval | None = None

    @model_validator(mode="after")
    def verify_approval(self) -> Self:
        if self.approval is not None and (
            self.document.kind != "solver_solution"
            or self.document.validation.status != "reviewed_gto"
            or self.approval.content_hash != self.document.content_hash
        ):
            raise ValueError("Approval is not bound to the reviewed solver document")
        return self

    @property
    def public_baseline(self) -> bool:
        p = self.document.provenance
        return (
            self.document.kind == "solver_solution"
            and self.approval is not None
            and self.document.validation.status == "reviewed_gto"
            and self.approval.content_hash == self.document.content_hash
            and p.publish
            and p.redistribution == "permitted"
        )

    @property
    def public_demo(self) -> bool:
        p = self.document.provenance
        return (
            self.document.kind == "synthetic_fixture"
            and p.publish
            and p.redistribution == "permitted"
        )
