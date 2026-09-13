"""New-work predicates; provenance and temporal compliance stay separate."""

import re

from qualor.domain.enums import Operator, SubjectReference
from qualor.domain.values import BoolValue

from .base import Compiler, body, fullmatch


class ProjectPolicyAdapter:
    def compile(self, candidate, *, evaluated_at):
        c = Compiler(candidate, evaluated_at)
        if early := c.early():
            return early
        match = fullmatch(
            r"(?:Projects|The project|Project) must (not )?be (?:newly created|new)(?: (.+))?",
            body(candidate),
        )
        if not match:
            return c.finish(c.unresolved("PROJECT_POLICY_GRAMMAR_UNSUPPORTED"))
        required = not bool(match[1])
        value = "NEW_ONLY" if required else "EXISTING_ONLY"
        if candidate.candidate.proposed_value != value:
            return c.finish(c.unresolved("PROJECT_POLICY_PROPOSAL_SOURCE_MISMATCH"))
        rule = c.rule(Operator.BOOL_IS, SubjectReference.NEW_PROJECT, (BoolValue(value=required),))
        tail = match[2] or ""
        if tail:
            # Only explicit conjunctive temporal/reuse/disclosure syntax preserves
            # the base requirement. Alternatives or applicability cannot hard-fail it.
            conjunct = bool(re.match(r"(?:during\b|and disclose\b|without reusing\b)", tail, re.I))
            rule = c.combine(
                (rule, c.unresolved("PROJECT_POLICY_TEMPORAL_REUSE_OR_DISCLOSURE_UNREPRESENTED")),
                supported=conjunct,
            )
        return c.finish(
            rule,
            value=value,
            status="SUPPORTED" if rule.supported else "UNKNOWN",
            conditional=bool(tail),
            interpreted=True,
        )
