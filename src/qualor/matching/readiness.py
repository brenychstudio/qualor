"""Readiness needs explicit requirement coverage for every material category."""

from datetime import datetime

from pydantic import TypeAdapter

from qualor.domain.base import UtcInstant
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.planning import MaterialKind
from qualor.domain.profiles import ProjectProfile

from .model import FactorResult, ReadinessAssessment, ReadinessState
from .policy import MATCH_POLICY_VERSION


def assess_readiness(
    project: ProjectProfile, opportunity: OpportunityRecord, evaluated_at: datetime
) -> ReadinessAssessment:
    project = ProjectProfile.model_validate(project)
    opportunity = OpportunityRecord.model_validate(opportunity)
    evaluated_at = TypeAdapter(UtcInstant).validate_python(evaluated_at)
    requirements = (
        {r.kind: r for r in opportunity.matching_requirements.materials}
        if opportunity.matching_requirements
        else {}
    )
    materials = {m.kind: m for m in project.material_readiness}
    factors, gaps, missing = [], [], []
    for kind in MaterialKind:
        ref = f"opportunity.matching_requirements.materials.{kind}.required"
        fact_ref = f"project.material_readiness.{kind}"
        requirement, material = requirements.get(kind), materials.get(kind)
        rating = None
        reason = "Material requirement is unknown"
        used_refs = (fact_ref + ".ready",)
        if requirement is None or requirement.required.value is None:
            missing.append(ref)
        elif requirement.required.value is False:
            rating, reason = 4, "Material explicitly not required"
        elif material is None or material.ready.value is None:
            missing.append(fact_ref + ".ready")
            reason = "Required material readiness is unknown"
        elif material.ready.value:
            rating, reason = 4, "Required material is ready"
        else:
            gaps.append(kind)
            used_refs += (fact_ref + ".gap_executable",)
            if material.gap_executable.value is None:
                missing.append(fact_ref + ".gap_executable")
                reason = "Required material gap executability is unknown"
            elif material.gap_executable.value:
                rating, reason = 3, "Required material gap is executable"
            else:
                rating, reason = 0, "Required material gap is not executable"
            if material.reason:
                reason += ": " + material.reason
        factors.append(
            FactorResult(
                factor=kind.value,
                rating=rating,
                reasons=(reason,),
                requirement_refs=(ref,),
                fact_refs=used_refs,
            )
        )
    ratings = tuple(f.rating for f in factors)
    state = (
        ReadinessState.NOT_READY
        if 0 in ratings
        else ReadinessState.UNKNOWN
        if None in ratings
        else ReadinessState.GAPS_EXECUTABLE
        if 3 in ratings
        else ReadinessState.READY
    )
    return ReadinessAssessment(
        state=state,
        gaps=tuple(gaps),
        missing_information=tuple(missing),
        factor_results=tuple(factors),
        evaluated_at=evaluated_at,
        policy_version=MATCH_POLICY_VERSION,
    )
