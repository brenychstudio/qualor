"""Immutable preparation and capacity contracts."""

from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from qualor.domain.base import Contract, NonEmpty, UtcInstant
from qualor.domain.money import NonNegativeDecimal
from qualor.domain.planning import HourRange


class EffortCategory(StrEnum):
    INTEGRATION = "INTEGRATION"
    EVIDENCE = "EVIDENCE"
    REPO_LICENSE_CLEANUP = "REPO_LICENSE_CLEANUP"
    DEMO = "DEMO"
    NARRATIVE = "NARRATIVE"
    SUBMISSION = "SUBMISSION"


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class EffortItem(Contract):
    category: EffortCategory
    hours: HourRange | None
    confidence: Confidence
    reason: NonEmpty


class EffortAssumptions(Contract):
    items: tuple[EffortItem, ...]

    @model_validator(mode="after")
    def unique_categories(self) -> Self:
        if len({i.category for i in self.items}) != len(self.items):
            raise ValueError("Duplicate effort categories")
        return self


class EffortEstimate(Contract):
    breakdown: tuple[EffortItem, ...]
    adaptation_range: HourRange | None
    min_total: NonNegativeDecimal | None
    max_total: NonNegativeDecimal | None
    reasons: tuple[NonEmpty, ...]
    missing_information: tuple[NonEmpty, ...]
    evaluated_at: UtcInstant
    policy_version: Literal[1] = 1

    @model_validator(mode="after")
    def consistent_totals(self) -> Self:
        assumptions = EffortAssumptions(items=self.breakdown)
        items = {i.category: i for i in assumptions.items}
        missing = tuple(
            f"effort.{c.value}" for c in EffortCategory if c not in items or items[c].hours is None
        )
        if self.adaptation_range is None:
            missing += ("project.estimated_adaptation_hours",)
        elif self.adaptation_range.min_hours != self.adaptation_range.max_hours:
            raise ValueError("Existing adaptation estimate must be an explicit point assumption")
        minimum = maximum = None
        if not missing:
            minimum = self.adaptation_range.min_hours + sum(
                (i.hours.min_hours for i in self.breakdown), Decimal(0)
            )
            maximum = self.adaptation_range.max_hours + sum(
                (i.hours.max_hours for i in self.breakdown), Decimal(0)
            )
        if (self.min_total, self.max_total, self.missing_information) != (
            minimum,
            maximum,
            missing,
        ):
            raise ValueError(
                "Effort totals and missing information must follow the supplied ranges"
            )
        return self


class CapacityState(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


class CapacityAssessment(Contract):
    state: CapacityState
    available_hours: NonNegativeDecimal | None
    remaining_wall_hours: NonNegativeDecimal | None
    usable_hours: NonNegativeDecimal | None
    required_hours: NonNegativeDecimal | None
    reasons: tuple[NonEmpty, ...]
    missing_information: tuple[NonEmpty, ...]
    evaluated_at: UtcInstant
    policy_version: Literal[1] = 1
