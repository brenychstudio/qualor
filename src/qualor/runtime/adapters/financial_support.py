"""Only the declared project's sponsor-support scope maps to its boolean fact."""

from qualor.domain.enums import Operator, SubjectReference
from qualor.domain.values import BoolValue

from .base import Compiler, body, fullmatch


class FinancialSupportAdapter:
    def compile(self, candidate, *, evaluated_at):
        c = Compiler(candidate, evaluated_at)
        if early := c.early():
            return early
        match = fullmatch(
            r"Projects must (not )?have sponsor support(?: and (.+))?", body(candidate)
        )
        if not match:
            return c.finish(c.unresolved("SUPPORT_ACTOR_TIME_OR_PREFERENCE_UNREPRESENTED"))
        required = not bool(match[1])
        value = "REQUIRED" if required else "PROHIBITED"
        if candidate.candidate.proposed_value != value:
            return c.finish(c.unresolved("SUPPORT_PROPOSAL_SOURCE_MISMATCH"))
        rule = c.rule(
            Operator.BOOL_IS, SubjectReference.FINANCIAL_SUPPORT, (BoolValue(value=required),)
        )
        if match[2]:
            rule = c.combine((rule, c.unresolved("SUPPORT_ADDITIONAL_CONDITION_UNREPRESENTED")))
        return c.finish(
            rule, value=value, status="SUPPORTED", conditional=bool(match[2]), interpreted=True
        )
