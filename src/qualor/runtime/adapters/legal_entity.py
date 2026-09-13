"""Explicit legal classifications and complete calendar incorporation intervals."""

from datetime import date

from qualor.domain.enums import Operator, SubjectReference
from qualor.domain.values import DateValue

from .base import fullmatch
from .entrant_type import compile_forms


def incorporation_condition(compiler, tail):
    match = fullmatch(r"incorporated between (\d{4}-\d{2}-\d{2}) and (\d{4}-\d{2}-\d{2})", tail)
    if match:
        try:
            start, end = date.fromisoformat(match[1]), date.fromisoformat(match[2])
        except ValueError:
            return None
        if start <= end:
            return compiler.rule(
                Operator.DATE_BETWEEN,
                SubjectReference.INCORPORATION_DATE,
                (DateValue(value=start), DateValue(value=end)),
            )
    return None


class LegalEntityAdapter:
    def compile(self, candidate, *, evaluated_at):
        return compile_forms(candidate, evaluated_at, legal=True)
