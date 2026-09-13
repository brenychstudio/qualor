"""License intent is executable; actual licensing/publication needs separate facts."""

from qualor.domain.enums import Operator, SubjectReference
from qualor.domain.values import TextValue

from .base import Compiler, body, fullmatch, literal_values, split_condition


class LicenseAdapter:
    def compile(self, candidate, *, evaluated_at):
        c = Compiler(candidate, evaluated_at)
        if early := c.early():
            return early
        text, tail = split_condition(body(candidate))
        intent = fullmatch(r"Projects must intend to use (?:the )?(.+?) licenses?", text)
        actual = fullmatch(
            r"Projects must be licensed under (.+)|"
            r"The public repository must use (?:the )?(.+?) licenses?",
            text,
        )
        if intent:
            payload = intent[1]
        elif actual:
            payload = next(v for v in actual.groups() if v)
        else:
            return c.finish(c.unresolved("LICENSE_GRAMMAR_OR_CONDITION_UNRESOLVED"))
        parsed = literal_values(payload, candidate.candidate.proposed_value)
        if not parsed:
            return c.finish(c.unresolved("LICENSE_VALUES_OR_ALTERNATIVES_MISMATCH"))
        values, relation = parsed
        operands = tuple(TextValue(value=value) for value in values)
        if intent:
            rules = tuple(
                c.rule(Operator.IN, SubjectReference.LICENSE, (value,)) for value in operands
            )
        else:
            rules = tuple(
                c.unresolved("LICENSE_ACTUAL_COMPLIANCE_UNREPRESENTED", operands=(value,))
                for value in operands
            )
        rule = c.combine(rules, Operator.AND if relation == "and" else Operator.OR)
        if tail:
            rule = c.combine((rule, c.unresolved("LICENSE_ATTACHED_CONDITION_UNREPRESENTED")))
        return c.finish(
            rule,
            value=values[0] if len(values) == 1 else values,
            status="SUPPORTED" if intent else "UNSUPPORTED",
            conditional=bool(actual or tail),
            interpreted=True,
        )
