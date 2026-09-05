"""Enumerated subject resolution; no arbitrary attributes or inferred profile facts."""

from qualor.domain.enums import (
    Category,
    CodeProvenance,
    Operator,
    Provenance,
    ReasonCode,
    SubjectReference,
)
from qualor.domain.fixture import EvaluationContext
from qualor.domain.rules import RuleCandidate
from qualor.domain.values import BoolValue, DateValue, InstantValue, NumberValue, Scalar, TextValue

ALLOWED_SUBJECTS = {
    Category.DEADLINE: {SubjectReference.EVALUATED_AT},
    Category.ENTRANT_TYPE: {SubjectReference.TEAM_SIZE, SubjectReference.LEGAL_FORM},
    Category.GEOGRAPHY: {SubjectReference.RESIDENCE, SubjectReference.CITIZENSHIP},
    Category.LEGAL_ENTITY: {SubjectReference.LEGAL_FORM, SubjectReference.INCORPORATION_DATE},
    Category.PROJECT_POLICY: {SubjectReference.NEW_PROJECT},
    Category.LICENSE: {SubjectReference.LICENSE, SubjectReference.OPEN_SOURCE},
    Category.REQUIRED_TECHNOLOGY: {SubjectReference.REQUIRED_TECHNOLOGY},
    Category.FINANCIAL_SUPPORT: {SubjectReference.FINANCIAL_SUPPORT},
    Category.REWARD_CONDITIONS: {SubjectReference.REWARD_CONDITIONS},
}


def resolve_subject(
    rule: RuleCandidate, context: EvaluationContext
) -> tuple[Scalar | tuple[Scalar, ...] | None, ReasonCode]:
    subject = rule.subject_reference
    if subject not in ALLOWED_SUBJECTS[rule.rule_type]:
        return None, ReasonCode.UNSUPPORTED
    if subject == SubjectReference.EVALUATED_AT:
        # V1 deadline bounds must also participate in evidence freshness.
        # Other temporal shapes have no supported deadline-policy binding.
        if rule.operator != Operator.DATE_BETWEEN:
            return None, ReasonCode.UNSUPPORTED
        return InstantValue(value=context.evaluated_at), ReasonCode.MATCH
    founder, project = context.founder, context.project
    if subject == SubjectReference.NEW_PROJECT:
        if (
            project.code_provenance.provenance != Provenance.DOCUMENTED
            or project.code_provenance.value != CodeProvenance.ORIGINAL
            or project.is_new_project.provenance != Provenance.DOCUMENTED
        ):
            return None, ReasonCode.PROVENANCE_REQUIRED
    facts = {
        SubjectReference.RESIDENCE: founder.country_of_residence,
        SubjectReference.CITIZENSHIP: founder.citizenship,
        SubjectReference.LEGAL_FORM: founder.legal_form,
        SubjectReference.INCORPORATION_DATE: founder.incorporation_date,
        SubjectReference.TEAM_SIZE: founder.team_size,
        SubjectReference.OPEN_SOURCE: founder.open_source_willingness,
        SubjectReference.NEW_PROJECT: project.is_new_project,
        SubjectReference.LICENSE: project.license_intent,
        SubjectReference.REQUIRED_TECHNOLOGY: project.technology_stack,
        SubjectReference.FINANCIAL_SUPPORT: project.has_sponsor_support,
        SubjectReference.REWARD_CONDITIONS: project.reward_conditions_met,
    }
    fact = facts[subject]
    if fact.value is None or fact.provenance == Provenance.UNKNOWN:
        return None, ReasonCode.MISSING_FACT
    if subject == SubjectReference.REQUIRED_TECHNOLOGY:
        return tuple(TextValue(value=item) for item in fact.value), ReasonCode.MATCH
    if subject == SubjectReference.INCORPORATION_DATE:
        return DateValue(value=fact.value), ReasonCode.MATCH
    if subject == SubjectReference.TEAM_SIZE:
        return NumberValue(value=fact.value), ReasonCode.MATCH
    if subject in {
        SubjectReference.OPEN_SOURCE,
        SubjectReference.NEW_PROJECT,
        SubjectReference.FINANCIAL_SUPPORT,
        SubjectReference.REWARD_CONDITIONS,
    }:
        return BoolValue(value=fact.value), ReasonCode.MATCH
    return TextValue(value=fact.value), ReasonCode.MATCH
