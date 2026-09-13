"""Mandatory stack membership and explicitly sufficient technology alternatives."""

from qualor.domain.enums import Operator, SubjectReference
from qualor.domain.values import TextValue

from .base import Compiler, body, fullmatch, literal_values, split_condition


class TechnologyRequirementAdapter:
    def compile(self, candidate, *, evaluated_at):
        c = Compiler(candidate, evaluated_at)
        if early := c.early():
            return early
        text = body(candidate)
        proposed = candidate.candidate.proposed_value
        optional = fullmatch(
            r"(?:Projects may optionally use (.+)|Using (.+) "
            r"(?:is optional(?: for deployment)?|earns bonus points))",
            text,
        )
        if optional and literal_values(next(v for v in optional.groups() if v), proposed):
            result = c.finish(value=proposed, status="SUPPORTED", interpreted=True)
            if result.normalization_status == "SUPPORTED":
                return result.model_copy(
                    update={"rules": (), "reason_codes": ("OPTIONAL_TECHNOLOGY",)}
                )
            return result
        match = fullmatch(
            r"(?:(?:Projects|Submissions|The project|The submission) "
            r"(?:must use|are required to use|must be built with|must be built using)|"
            r"Build (?:an?|the) (?:agent|tool|project|application|app) (?:with|using)) (.+)",
            text,
        )
        if not match:
            return c.finish(c.unresolved("TECHNOLOGY_GRAMMAR_UNSUPPORTED"))
        payload, tail = split_condition(match[1])
        parsed = literal_values(payload, proposed)
        if tail and not parsed and proposed == match[1]:
            # A proposal may quote the entire qualified value. Derive its exact
            # base literal from the source, retaining the tail as applicability.
            parsed = literal_values(payload, payload)
        if not parsed:
            return c.finish(c.unresolved("TECHNOLOGY_VALUE_OR_TAIL_UNRESOLVED"))
        values, relation = parsed
        operands = tuple(TextValue(value=v) for v in values)
        if relation == "and":
            rule = c.combine(
                c.rule(Operator.IN, SubjectReference.REQUIRED_TECHNOLOGY, (v,)) for v in operands
            )
        else:
            rule = c.rule(Operator.IN, SubjectReference.REQUIRED_TECHNOLOGY, operands)
        if tail:
            rule = c.combine((rule, c.unresolved("TECHNOLOGY_ATTACHED_CONDITION_UNREPRESENTED")))
        value = values[0] if len(values) == 1 else values
        return c.finish(
            rule, value=value, status="SUPPORTED", conditional=bool(tail), interpreted=True
        )
