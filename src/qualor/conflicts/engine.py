"""Pure checks of supplied projects, active submissions and reviewed rules."""

from datetime import datetime

from pydantic import TypeAdapter

from qualor.domain.base import UtcInstant
from qualor.domain.enums import CodeProvenance, ExtractionState, FreshnessStatus
from qualor.domain.evidence import EvidenceRecord
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.profiles import ProjectProfile
from qualor.eligibility.freshness import evaluate_freshness

from .model import (
    ActiveSubmission,
    ConflictAssessment,
    ConflictCategory,
    ConflictRule,
    ConflictStatus,
)
from .policy import ACCEPTABLE_SOURCES, CONFLICT_POLICY_VERSION, EVIDENCE_CATEGORY


def _unique(values, label):
    if len(set(values)) != len(values):
        raise ValueError(f"Duplicate {label}")


def _violation(rule, project, submissions):
    """True is an explicit violation; None preserves unresolved facts."""
    category = rule.category
    if category == ConflictCategory.NEW_PROJECT:
        new = project.is_new_project.value
        origin = project.code_provenance.value
        lineage = project.project_lineage.value
        reused = project.reused_components.value
        if (
            new is False
            or origin in {CodeProvenance.REUSED, CodeProvenance.MIXED}
            or lineage
            or reused
        ):
            return True
        return None if None in (new, origin, lineage, reused) else False
    if category == ConflictCategory.EXCLUSIVE_SUBMISSION:
        return bool(submissions)
    if category == ConflictCategory.LICENSE:
        actual, allowed = project.license_intent.value, rule.allowed_licenses.value
        return None if actual is None or allowed is None else actual not in allowed
    if category == ConflictCategory.SPONSOR_SUPPORT:
        return project.has_sponsor_support.value
    if category == ConflictCategory.EXISTING_PROJECT:
        new = project.is_new_project.value
        return None if new is None else not new
    if category == ConflictCategory.DISCLOSURE:
        reused, disclosed = project.reused_components.value, project.reuse_disclosed.value
        if reused is None:
            return None
        return False if not reused else (None if disclosed is None else not disclosed)
    unknown = False
    for submission in submissions:
        left, right = project.project_lineage.value, submission.project_lineage.value
        if project.id == submission.project_id:
            return True
        # An explicitly listed ancestor ID can also match the other project itself.
        if set(left or ()).intersection({submission.project_id, *(right or ())}):
            return True
        if project.id in (right or ()):
            return True
        unknown |= left is None or right is None
    return None if unknown else False


def _disagreement(category, project, submissions):
    fields = {
        ConflictCategory.NEW_PROJECT: (
            ("code_provenance", "code_origin"),
            ("reused_components", "reused_components"),
        ),
        ConflictCategory.LICENSE: (("license_intent", "license"),),
        ConflictCategory.SPONSOR_SUPPORT: (("has_sponsor_support", "sponsor_support"),),
        ConflictCategory.DISCLOSURE: (("reused_components", "reused_components"),),
    }.get(category, ())
    for submission in submissions:
        if submission.project_id != project.id:
            continue
        for project_field, submission_field in fields:
            left = getattr(project, project_field).value
            right = getattr(submission, submission_field).value
            if left is not None and right is not None and left != right:
                return True
    return False


def assess_conflicts(
    project: ProjectProfile,
    opportunity: OpportunityRecord,
    rules: tuple[ConflictRule, ...],
    submissions: tuple[ActiveSubmission, ...],
    evidence: tuple[EvidenceRecord, ...],
    evaluated_at: datetime,
) -> ConflictAssessment:
    project = ProjectProfile.model_validate(project)
    opportunity = OpportunityRecord.model_validate(opportunity)
    rules = tuple(ConflictRule.model_validate(r) for r in rules)
    submissions = tuple(ActiveSubmission.model_validate(s) for s in submissions)
    evidence = tuple(EvidenceRecord.model_validate(e) for e in evidence)
    evaluated_at = TypeAdapter(UtcInstant).validate_python(evaluated_at)
    _unique([s.id for s in submissions], "submission IDs")
    _unique([opportunity.id, *(s.contest for s in submissions)], "contest scopes")
    _unique([e.id for e in evidence], "evidence IDs")
    indexed = {e.id: e for e in evidence}
    external_refs = {s.contest: s.rules_evidence_refs for s in submissions}
    scopes = [(opportunity.id, rules, submissions, opportunity.deadlines)]
    scopes.extend((s.contest, s.conflict_rules, (s,), ()) for s in submissions)
    checked, missing, refs, reasons = [], [], [], []
    blocked = False
    for contest, scoped_rules, peers, deadlines in scopes:
        _unique([r.id for r in scoped_rules], "rule IDs within contest")
        _unique([r.category for r in scoped_rules], "rule categories within contest")
        for rule in scoped_rules:
            _unique(rule.evidence_ids, "evidence IDs within rule")
        by_category = {r.category: r for r in scoped_rules}
        for category in ConflictCategory:
            key = (contest, category)
            rule = by_category.get(category)
            problem = None
            if rule is None:
                problem = "Missing explicit category rule"
            elif not rule.supported or rule.applies.value is None:
                problem = "Unsupported interpretation or unknown applicability"
            elif contest in external_refs and not set(rule.evidence_ids).issubset(
                external_refs[contest]
            ):
                problem = "External rule is absent from submission evidence references"
            elif not rule.evidence_ids:
                problem = "Missing rule evidence"
            else:
                for ref in rule.evidence_ids:
                    record = indexed.get(ref)
                    if record is None:
                        problem = "Missing rule evidence"
                        break
                    if (
                        record.extraction_state != ExtractionState.REVIEWED
                        or record.source_type not in ACCEPTABLE_SOURCES
                        or record.normalized_field != EVIDENCE_CATEGORY[category]
                    ):
                        problem = "Unreviewed, mismatched or unacceptable evidence"
                        break
                    if any(
                        evaluate_freshness(
                            record.retrieved_at,
                            evaluated_at,
                            deadline,
                            unknown_deadline=not deadlines,
                        )
                        != FreshnessStatus.FRESH
                        for deadline in deadlines or (None,)
                    ):
                        problem = "Evidence freshness is stale or unknown"
                        break
            if problem:
                missing.append(key)
                reasons.append(f"{contest}/{category}: {problem}")
                continue
            refs.extend(rule.evidence_ids)
            violation = _violation(rule, project, peers) if rule.applies.value else False
            if (
                violation is False
                and rule.applies.value
                and _disagreement(category, project, peers)
            ):
                violation = None
            if violation is None:
                missing.append(key)
                reasons.append(
                    f"{contest}/{category}: Required explicit facts are unknown or disagree"
                )
            else:
                checked.append(key)
                blocked |= violation
                detail = "Explicit violation" if violation else "No violation in checked rule"
                reasons.append(f"{contest}/{category}: {detail}")
    status = (
        ConflictStatus.BLOCKED_BY_EXPLICIT_RULE
        if blocked
        else ConflictStatus.REVIEW_REQUIRED
        if missing
        else ConflictStatus.NO_CONFLICT_DETECTED_IN_CHECKED_RULES
    )
    return ConflictAssessment(
        status=status,
        checked_rule_categories=tuple(checked),
        missing_rule_categories=tuple(missing),
        evidence_ids=tuple(dict.fromkeys(refs)),
        reasons=tuple(reasons),
        evaluated_at=evaluated_at,
        policy_version=CONFLICT_POLICY_VERSION,
    )
