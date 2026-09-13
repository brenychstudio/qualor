"""Retain geographical source predicates without inventing jurisdiction authority."""

from typing import Annotated

from pydantic import Field, StrictBool, StringConstraints

from qualor.domain.base import Contract
from qualor.domain.enums import Operator
from qualor.domain.evidence import ClauseContext
from qualor.domain.values import TextValue

from .base import Compiler, body, fullmatch, literal_values

BoundedTexts = Annotated[
    tuple[Annotated[str, StringConstraints(strict=True, min_length=1, max_length=700)], ...],
    Field(max_length=12),
]


class GeographyCondition(Contract):
    """Source scopes, not a jurisdiction ontology or an applicant clearance record."""

    explicitly_allowed: BoundedTexts
    explicitly_excluded: BoundedTexts
    open_ended_legal_restriction: StrictBool
    requires_external_compliance_check: StrictBool
    qualifiers: BoundedTexts
    exceptions: BoundedTexts
    provenance: ClauseContext


class GeographyRuleAdapter:
    def compile(self, candidate, *, evaluated_at):
        c = Compiler(candidate, evaluated_at)
        if early := c.early():
            return early
        text = body(candidate)
        match = fullmatch(r"Entrants must (not )?(reside in|be citizens of) (.+)", text)
        excluded = fullmatch(r"(Residents|Citizens) of (.+) are excluded", text)
        if match:
            operator = Operator.NOT_IN if match[1] else Operator.IN
            scope = match[3]
        elif excluded:
            operator = Operator.NOT_IN
            scope = excluded[2]
        else:
            return c.finish(c.unresolved("GEOGRAPHY_SUBJECT_OR_GRAMMAR_UNRESOLVED"))
        catchall = fullmatch(
            r"(.+) or any jurisdiction where participation is prohibited by law", scope
        )
        open_ended = catchall is not None and operator == Operator.NOT_IN
        if open_ended:
            scope = catchall[1]
        parsed = literal_values(scope, candidate.candidate.proposed_value)
        if not parsed:
            return c.finish(c.unresolved("GEOGRAPHY_VALUE_OR_CONDITION_UNRESOLVED"))
        values, _ = parsed
        if len(values) > 12:
            raise ValueError("ADAPTER_GEOGRAPHY_SCOPE_LIMIT")
        condition = GeographyCondition(
            explicitly_allowed=values if operator == Operator.IN else (),
            explicitly_excluded=values if operator == Operator.NOT_IN else (),
            open_ended_legal_restriction=open_ended,
            requires_external_compliance_check=True,
            qualifiers=candidate.context.qualifiers,
            exceptions=candidate.context.exceptions,
            provenance=candidate.context,
        )
        operands = tuple(
            TextValue(value=value)
            for value in (*condition.explicitly_allowed, *condition.explicitly_excluded)
        )
        # No positive jurisdiction ontology is available in the approved contracts.
        # Literal agreement and capitalization do not authorize a membership test.
        reason = "GEOGRAPHY_EXTERNAL_COMPLIANCE_REQUIRED"
        c.reasons.append(reason)
        rule = c.rule(operator, operands=operands, supported=False, reason=reason)
        if open_ended:
            rule = c.combine((rule, c.unresolved(reason)), supported=False)
        return c.finish(
            rule,
            value=values[0] if len(values) == 1 else values,
            status="UNKNOWN",
            conditional=condition.requires_external_compliance_check,
            interpreted=True,
        )
