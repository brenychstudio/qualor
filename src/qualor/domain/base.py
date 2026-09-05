"""Shared validated record and fact contracts."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    model_validator,
)

from .enums import Provenance


def exact_input(value: object) -> object:
    if not isinstance(value, (str, datetime)):
        raise ValueError("Exact instant requires an aware datetime or ISO timestamp")
    return value


def calendar_input(value: object) -> object:
    if type(value) is date or (isinstance(value, str) and len(value) == 10):
        return value
    raise ValueError("Calendar date requires YYYY-MM-DD, not an inferred instant")


UtcInstant = Annotated[
    AwareDatetime, BeforeValidator(exact_input), AfterValidator(lambda x: x.astimezone(UTC))
]
CalendarDate = Annotated[date, BeforeValidator(calendar_input)]
NonEmpty = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
PositiveInt = Annotated[StrictInt, Field(ge=1)]


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        revalidate_instances="always",
        allow_inf_nan=False,
    )


class Record(Contract):
    schema_version: Literal["1"]
    id: NonEmpty
    version: PositiveInt
    created_at: UtcInstant
    updated_at: UtcInstant
    provenance: Provenance

    @model_validator(mode="after")
    def timestamps_ordered(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        return self


class Fact[T](Contract):
    value: T | None = None
    provenance: Provenance = Provenance.UNKNOWN
    evidence_refs: tuple[NonEmpty, ...] = ()

    @model_validator(mode="after")
    def provenance_matches_value(self) -> Self:
        if (self.value is None) != (self.provenance == Provenance.UNKNOWN):
            raise ValueError("Absent facts are UNKNOWN; known values require provenance")
        if self.value == "UNKNOWN" and self.provenance != Provenance.UNKNOWN:
            raise ValueError("Use a missing fact for unknown enum values")
        return self
