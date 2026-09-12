"""Explicit shared planning inputs; no inferred requirements or durations."""

from enum import StrEnum
from typing import Self

from pydantic import StrictBool, model_validator

from .base import Contract, Fact, NonEmpty
from .enums import ProjectStage
from .money import NonNegativeDecimal


class HourRange(Contract):
    min_hours: NonNegativeDecimal
    max_hours: NonNegativeDecimal

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.min_hours > self.max_hours:
            raise ValueError("Hour range must be ordered")
        return self


class MaterialKind(StrEnum):
    REPOSITORY = "REPOSITORY"
    LICENSE = "LICENSE"
    DEMO = "DEMO"
    ARCHITECTURE_DIAGRAM = "ARCHITECTURE_DIAGRAM"
    TECHNICAL_INTEGRATION = "TECHNICAL_INTEGRATION"
    NARRATIVE = "NARRATIVE"
    PUBLIC_AVAILABILITY = "PUBLIC_AVAILABILITY"
    OTHER = "OTHER"


class MaterialRequirement(Contract):
    kind: MaterialKind
    required: Fact[StrictBool] = Fact()


class MaterialReadiness(Contract):
    kind: MaterialKind
    ready: Fact[StrictBool] = Fact()
    gap_executable: Fact[StrictBool] = Fact()
    reason: NonEmpty | None = None


class MatchingRequirements(Contract):
    problem_labels: Fact[tuple[NonEmpty, ...]] = Fact()
    audience_labels: Fact[tuple[NonEmpty, ...]] = Fact()
    technologies: Fact[tuple[NonEmpty, ...]] = Fact()
    features: Fact[tuple[NonEmpty, ...]] = Fact()
    stages: Fact[tuple[ProjectStage, ...]] = Fact()
    licenses: Fact[tuple[NonEmpty, ...]] = Fact()
    original_code_required: Fact[StrictBool] = Fact()
    max_adaptation_hours: Fact[NonNegativeDecimal] = Fact()
    #: Whether the source states outright that it sets no adaptation limit. An unread cap and
    #: an absent cap are different answers: the first is unknown, the second is satisfied by
    #: any finite adaptation. Absence of `max_adaptation_hours` never implies this.
    adaptation_unbounded: Fact[StrictBool] = Fact()
    materials: tuple[MaterialRequirement, ...] = ()

    @model_validator(mode="after")
    def unique_materials(self) -> Self:
        if len({m.kind for m in self.materials}) != len(self.materials):
            raise ValueError("Duplicate material requirements")
        return self

    @model_validator(mode="after")
    def one_adaptation_answer(self) -> Self:
        if self.adaptation_unbounded.value and self.max_adaptation_hours.value is not None:
            raise ValueError("An unbounded adaptation constraint cannot also state a finite limit")
        return self
