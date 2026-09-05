"""Exact normalized label matching; no semantic inference or portfolio tie breaking."""

import unicodedata
from datetime import datetime

from qualor.domain.enums import CodeProvenance
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.planning import HourRange, MatchingRequirements
from qualor.domain.profiles import ProjectProfile

from .model import FactorResult, MatchStatus, ProjectMatch, ProjectSelection, ReadinessState
from .policy import MATCH_POLICY_VERSION, PARTIAL_THRESHOLD, STRONG_THRESHOLD, comparable_score
from .readiness import assess_readiness


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _coverage(
    actual: tuple[str, ...] | None, required: tuple[str, ...] | None, categorical: bool = False
) -> int | None:
    if required is None:
        return None
    expected = {_normalize(x) for x in required}
    if not expected:
        return 4
    if actual is None:
        return None
    overlap = expected.intersection(_normalize(x) for x in actual)
    return (4 if overlap else 0) if categorical else 4 * len(overlap) // len(expected)


def _minimum(*ratings: int | None) -> int | None:
    return None if None in ratings else min(ratings)


def match_project(
    project: ProjectProfile, opportunity: OpportunityRecord, evaluated_at: datetime
) -> ProjectMatch:
    project = ProjectProfile.model_validate(project)
    opportunity = OpportunityRecord.model_validate(opportunity)
    readiness = assess_readiness(project, opportunity, evaluated_at)
    requirements = opportunity.matching_requirements or MatchingRequirements()
    factors, missing, matched, blocking = [], [], [], []

    def add(name: str, rating: int | None, pairs: tuple[tuple[str, str], ...]) -> None:
        req_refs = tuple("opportunity.matching_requirements." + req for req, _ in pairs)
        fact_refs = tuple("project." + field for _, field in pairs)
        reason = (
            "Requirement evidence is incomplete"
            if rating is None
            else f"Explicit comparison rating {rating}/4"
        )
        factors.append(
            FactorResult(
                factor=name,
                rating=rating,
                reasons=(reason,),
                requirement_refs=req_refs,
                fact_refs=fact_refs,
            )
        )
        for req, field in pairs:
            required = getattr(requirements, req).value
            if (
                required is not None
                and required != ()
                and required is not False
                and getattr(project, field).value is None
            ):
                missing.append("project." + field)
        if rating == 4:
            matched.extend(req_refs)
        elif rating == 0:
            blocking.append(name)

    def category(field: str, required: str) -> int | None:
        value = getattr(project, field).value
        return _coverage(
            None if value is None else (value,), getattr(requirements, required).value, True
        )

    add(
        "problem_audience",
        _minimum(category("problem", "problem_labels"), category("audience", "audience_labels")),
        (("problem_labels", "problem"), ("audience_labels", "audience")),
    )
    add(
        "technology",
        _coverage(project.technology_stack.value, requirements.technologies.value),
        (("technologies", "technology_stack"),),
    )
    add(
        "features",
        _coverage(project.available_features.value, requirements.features.value),
        (("features", "available_features"),),
    )
    add("stage", category("stage", "stages"), (("stages", "stage"),))
    original = requirements.original_code_required.value
    code_rating = (
        4
        if original is False
        else None
        if original is None or project.code_provenance.value is None
        else 4
        if project.code_provenance.value == CodeProvenance.ORIGINAL
        else 0
    )
    add(
        "code_license",
        _minimum(code_rating, category("license_intent", "licenses")),
        (("original_code_required", "code_provenance"), ("licenses", "license_intent")),
    )
    actual, maximum = (
        project.estimated_adaptation_hours.value,
        requirements.max_adaptation_hours.value,
    )
    add(
        "adaptation",
        None if actual is None or maximum is None else 4 if actual <= maximum else 0,
        (("max_adaptation_hours", "estimated_adaptation_hours"),),
    )
    readiness_rating = {
        ReadinessState.READY: 4,
        ReadinessState.GAPS_EXECUTABLE: 3,
        ReadinessState.NOT_READY: 0,
        ReadinessState.UNKNOWN: None,
    }[readiness.state]
    factors.append(
        FactorResult(
            factor="readiness",
            rating=readiness_rating,
            reasons=(f"Material readiness: {readiness.state}",),
            requirement_refs=tuple(
                ref for f in readiness.factor_results for ref in f.requirement_refs
            ),
            fact_refs=tuple(ref for f in readiness.factor_results for ref in f.fact_refs),
        )
    )
    missing.extend(ref for ref in readiness.missing_information if ref.startswith("project."))
    matched.extend(
        ref for f in readiness.factor_results if f.rating == 4 for ref in f.requirement_refs
    )
    blocking.extend(f"material.{f.factor}" for f in readiness.factor_results if f.rating == 0)
    ratings = tuple(f.rating for f in factors)
    score = None if None in ratings else comparable_score(ratings)
    status = (
        MatchStatus.INSUFFICIENT_EVIDENCE
        if score is None
        else MatchStatus.STRONG
        if score >= STRONG_THRESHOLD
        else MatchStatus.PARTIAL
        if score >= PARTIAL_THRESHOLD
        else MatchStatus.WEAK
    )
    return ProjectMatch(
        project_id=project.id,
        opportunity_id=opportunity.id,
        factor_results=tuple(factors),
        missing_project_facts=tuple(dict.fromkeys(missing)),
        matched_requirements=tuple(matched),
        blocking_gaps=tuple(blocking),
        adaptation_hours=None if actual is None else HourRange(min_hours=actual, max_hours=actual),
        match_status=status,
        comparable_score=score,
        rating=None if score is None else sum(ratings) // len(ratings),
        evaluated_at=readiness.evaluated_at,
        policy_version=MATCH_POLICY_VERSION,
    )


def select_best_project(matches: tuple[ProjectMatch, ...]) -> ProjectSelection:
    candidates = ProjectSelection(best_project_id=None, candidates=matches, reasons=()).candidates
    best = None
    if not candidates:
        reason = "No project candidates supplied"
    elif any(m.comparable_score is None for m in candidates):
        reason = "At least one candidate lacks comparable evidence"
    else:
        highest = max(m.comparable_score for m in candidates)
        winners = tuple(m for m in candidates if m.comparable_score == highest)
        if len(winners) != 1:
            reason = "Top matching score is tied; selection remains unresolved"
        else:
            best, reason = winners[0].project_id, "Unique highest comparable matching score"
    return ProjectSelection(best_project_id=best, candidates=candidates, reasons=(reason,))
