"""Exact money and economically distinct rewards; no cross-kind aggregation."""

from decimal import Decimal
from typing import Annotated, Self

from pydantic import BeforeValidator, Field, StrictBool, StringConstraints, model_validator

from .base import CalendarDate, Contract, NonEmpty, Record, UtcInstant
from .enums import RewardKind


def reject_float(value: object) -> object:
    if isinstance(value, (float, bool)):
        raise ValueError("Use a decimal string, integer or Decimal; binary floats are forbidden")
    return value


ExactDecimal = Annotated[Decimal, BeforeValidator(reject_float), Field(allow_inf_nan=False)]
NonNegativeDecimal = Annotated[ExactDecimal, Field(ge=0)]


class Money(Contract):
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$", strict=True)]
    amount: NonNegativeDecimal


class Reward(Record):
    kind: RewardKind
    amount: Money | None = None
    amount_min: Money | None = None
    amount_max: Money | None = None
    conditions: tuple[NonEmpty, ...] = ()
    expiry: CalendarDate | UtcInstant | None = None
    eligibility_note: NonEmpty | None = None
    payment_timing: NonEmpty | None = None
    is_total_pool: StrictBool = False

    @model_validator(mode="after")
    def consistent_amount(self) -> Self:
        if (self.amount_min is None) != (self.amount_max is None):
            raise ValueError("A range requires both bounds")
        if self.amount_min is not None and self.amount_max is not None:
            if self.amount is not None:
                raise ValueError("Provide an exact amount or a range")
            if (
                self.amount_min.currency != self.amount_max.currency
                or self.amount_min.amount > self.amount_max.amount
            ):
                raise ValueError("Reward range must be ordered and use one currency")
        return self
