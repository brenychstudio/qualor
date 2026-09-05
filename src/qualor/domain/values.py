"""Discriminated scalar operands preserve type across JSON round trips."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool

from .base import CalendarDate, Contract, NonEmpty, UtcInstant
from .money import ExactDecimal


class TextValue(Contract):
    kind: Literal["text"] = "text"
    value: NonEmpty


class NumberValue(Contract):
    kind: Literal["number"] = "number"
    value: ExactDecimal


class BoolValue(Contract):
    kind: Literal["bool"] = "bool"
    value: StrictBool


class DateValue(Contract):
    kind: Literal["date"] = "date"
    value: CalendarDate


class InstantValue(Contract):
    kind: Literal["instant"] = "instant"
    value: UtcInstant


Scalar = Annotated[
    TextValue | NumberValue | BoolValue | DateValue | InstantValue, Field(discriminator="kind")
]
