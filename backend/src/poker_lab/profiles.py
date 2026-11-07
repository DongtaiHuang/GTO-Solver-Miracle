"""Editable modeling assumptions, not empirical population definitions or GTO data."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Rate = Annotated[float, Field(strict=True, ge=0, le=100)]


class ProfileId(StrEnum):
    STANDARD_GTO = "standard_gto"
    TAG = "tag"
    LAG = "lag"
    TP = "tp"
    LP = "lp"


class ProfileParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vpip: Rate
    pfr: Rate
    three_bet: Rate
    fold_to_three_bet: Rate
    flop_cbet: Rate
    fold_to_flop_cbet: Rate
    turn_aggression: Rate
    river_aggression: Rate
    calling_tendency: Rate
    bluffing_tendency: Rate

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.pfr > self.vpip:
            raise ValueError("PFR must not exceed VPIP")
        return self


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: ProfileId
    parameters: ProfileParameters | None = None

    @model_validator(mode="after")
    def baseline(self) -> Self:
        if self.id == ProfileId.STANDARD_GTO and self.parameters is not None:
            raise ValueError("Standard GTO has no validated parameters; choose a modeled archetype")
        return self


class OpponentProfile(ProfileConfig):
    name: str
    description: str
    source: Literal["initial_assumptions", "unavailable"]
    solver_backed: Literal[False] = False


DESCRIPTIONS = {
    ProfileId.STANDARD_GTO: (
        "Standard GTO",
        (
            "No validated solution is connected. No GTO ranges or statistical parameters are assumed. "
            "In Trainer only, this selection uses the original random heuristic fallback."
        ),
    ),
    ProfileId.TAG: (
        "Tight Aggressive (TAG)",
        "Selective participation with more raising than the tight-passive model.",
    ),
    ProfileId.LAG: (
        "Loose Aggressive (LAG)",
        "Wider participation with higher modeled raise and bluff tendencies.",
    ),
    ProfileId.TP: (
        "Tight Passive (TP)",
        "Selective participation, lower modeled aggression, and more folding to pressure.",
    ),
    ProfileId.LP: (
        "Loose Passive (LP)",
        "Wider participation and higher calling tendency, with restrained raising.",
    ),
}

# Percent scales: illustrative tuning defaults, not measured stats or universal labels.
DEFAULTS = {
    ProfileId.TAG: (24, 20, 7, 55, 60, 45, 45, 40, 45, 35),
    ProfileId.LAG: (38, 30, 12, 35, 72, 32, 70, 62, 62, 65),
    ProfileId.TP: (18, 9, 3, 70, 30, 62, 22, 15, 45, 12),
    ProfileId.LP: (45, 12, 4, 38, 40, 25, 28, 18, 85, 18),
}


def resolve_profile(config: ProfileConfig) -> OpponentProfile:
    parameters = config.parameters
    if config.id != ProfileId.STANDARD_GTO and parameters is None:
        parameters = ProfileParameters(
            **dict(zip(ProfileParameters.model_fields, DEFAULTS[config.id]))
        )
    name, description = DESCRIPTIONS[config.id]
    return OpponentProfile(
        id=config.id,
        parameters=parameters,
        name=name,
        description=description,
        source="initial_assumptions" if parameters else "unavailable",
    )


def default_profiles() -> list[OpponentProfile]:
    return [resolve_profile(ProfileConfig(id=profile_id)) for profile_id in ProfileId]
