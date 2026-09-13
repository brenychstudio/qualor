"""Entrant forms and numeric team bounds, with branch-local residuals."""

import re

from qualor.domain.enums import Operator, SubjectReference
from qualor.domain.values import NumberValue, TextValue

from .base import Compiler, body, fullmatch

FORMS = {
    "individuals": "INDIVIDUAL",
    "natural persons": "INDIVIDUAL",
    "sole traders": "SOLE_TRADER",
    "incorporated companies": "INCORPORATED_COMPANY",
    "nonprofits": "NONPROFIT",
    "nonprofit organizations": "NONPROFIT",
    "teams": "TEAM",
    "universities": "UNIVERSITY",
}


def form_branch(c, text, proposed, *, legal=False):
    """Parse the form first; an attached predicate cannot change that form."""
    match = re.match(
        r"(" + "|".join(sorted(FORMS, key=len, reverse=True)) + r")(?: (.*))?$", text, re.I
    )
    if not match or FORMS[match[1].casefold()] != proposed:
        return c.unresolved("ENTITY_PROPOSAL_SOURCE_MISMATCH"), False
    form, tail = FORMS[match[1].casefold()], match[2] or ""
    if form in {"TEAM", "UNIVERSITY"}:
        if form == "TEAM" and not legal:
            numeric = fullmatch(
                r"(?:of|must have) (\d+) (?:to|through) (\d+) members(?: (.*))?", tail
            )
            limit = fullmatch(r"must have at (least|most) (\d+) members(?: (.*))?", tail)
            if numeric and 0 < int(numeric[1]) <= int(numeric[2]):
                rule = c.rule(
                    Operator.BETWEEN,
                    SubjectReference.TEAM_SIZE,
                    (NumberValue(value=numeric[1]), NumberValue(value=numeric[2])),
                )
                tail = numeric[3] or ""
            elif limit and int(limit[2]) > 0:
                rule = c.rule(
                    Operator.GTE if limit[1].casefold() == "least" else Operator.LTE,
                    SubjectReference.TEAM_SIZE,
                    (NumberValue(value=limit[2]),),
                )
                tail = limit[3] or ""
            else:
                return c.unresolved("TEAM_CONDITION_UNREPRESENTED"), True
        else:
            return c.unresolved("ORGANIZATION_CLASS_UNREPRESENTED"), True
    else:
        rule = c.rule(Operator.IN, SubjectReference.LEGAL_FORM, (TextValue(value=form),))
    if tail:
        if legal:
            from .legal_entity import incorporation_condition

            interval = incorporation_condition(c, tail)
            if interval is not None:
                return c.combine((rule, interval)), False
        applicability = bool(re.search(r"\b(?:unless|except|if|only|subject to)\b", tail, re.I))
        rule = c.combine(
            (rule, c.unresolved("ENTITY_ATTACHED_CONDITION_UNREPRESENTED")),
            supported=not applicability,
        )
        return rule, True
    return rule, False


def compile_forms(candidate, evaluated_at, *, legal=False):
    c = Compiler(candidate, evaluated_at)
    if early := c.early():
        return early
    text = body(candidate)
    permission = fullmatch(r"(?:Open to|Applicants must be|Entrants must be) (.+)", text)
    suffix = fullmatch(r"(.+) (?:may|can) (?:enter|participate)", text)
    team = fullmatch(r"Teams must have .+", text)
    if permission:
        payload = permission[1]
    elif suffix:
        payload = suffix[1]
    elif team and not legal:
        payload = text
    else:
        return c.finish(c.unresolved("ENTITY_GRAMMAR_UNSUPPORTED"))
    # OR attaches only complete named-form branches, never arbitrary tail words.
    alternatives = re.split(r"\s+or\s+(?=(?:" + "|".join(FORMS) + r")\b)", payload, flags=re.I)
    proposed = candidate.candidate.proposed_value
    values = proposed if isinstance(proposed, tuple) else (proposed,)
    if len(values) != len(alternatives):
        return c.finish(c.unresolved("ENTITY_ALTERNATIVES_MISMATCH"))
    branches = [
        form_branch(c, text, value, legal=legal)
        for text, value in zip(alternatives, values, strict=True)
    ]
    rule = c.combine((branch[0] for branch in branches), Operator.OR)
    has_supported = any(
        branch.supported and branch.subject_reference is not None for branch, _ in branches
    )
    # A composite may retain representable facts even with unresolved descendants.
    has_supported = has_supported or any(branch.children for branch, _ in branches)
    return c.finish(
        rule,
        value=proposed if has_supported else None,
        status="SUPPORTED" if has_supported else "UNSUPPORTED",
        conditional=any(conditional for _, conditional in branches),
        interpreted=has_supported,
    )


class EntrantTypeAdapter:
    def compile(self, candidate, *, evaluated_at):
        return compile_forms(candidate, evaluated_at)
