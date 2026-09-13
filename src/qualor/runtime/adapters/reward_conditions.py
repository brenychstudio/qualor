"""Declared condition scope, without invented awards or monetary conversions."""

import re

from qualor.domain.enums import Operator, SubjectReference
from qualor.domain.values import BoolValue

from .base import Compiler, body, fullmatch


class RewardConditionAdapter:
    def compile(self, candidate, *, evaluated_at):
        c = Compiler(candidate, evaluated_at)
        if early := c.early():
            return early
        text = body(candidate)
        if re.search(r"\b(?:total )?prize pool\b", text, re.I):
            return c.finish(c.unresolved("PRIZE_POOL_NOT_INDIVIDUAL_REWARD"))
        if re.search(r"\b(?:cloud )?credits\b", text, re.I):
            return c.finish(c.unresolved("CREDIT_NOT_CASH"))
        match = fullmatch(r"Projects must meet reward conditions(?: and (.+))?", text)
        if not match:
            return c.finish(c.unresolved("REWARD_VERIFICATION_TAX_OR_DISCRETION_UNREPRESENTED"))
        if candidate.candidate.proposed_value != "REQUIRED":
            return c.finish(c.unresolved("REWARD_PROPOSAL_SOURCE_MISMATCH"))
        rule = c.rule(
            Operator.BOOL_IS, SubjectReference.REWARD_CONDITIONS, (BoolValue(value=True),)
        )
        if match[1]:
            rule = c.combine((rule, c.unresolved("REWARD_ADDITIONAL_CONDITION_UNREPRESENTED")))
        return c.finish(
            rule, value="REQUIRED", status="SUPPORTED", conditional=bool(match[1]), interpreted=True
        )
