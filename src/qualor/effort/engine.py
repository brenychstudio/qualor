"""Pure range totals and conservative deadline capacity."""

from datetime import datetime
from decimal import Decimal

from pydantic import TypeAdapter

from qualor.domain.base import UtcInstant
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.planning import HourRange
from qualor.domain.profiles import FounderProfile, ProjectProfile

from .model import (
    CapacityAssessment,
    CapacityState,
    EffortAssumptions,
    EffortCategory,
    EffortEstimate,
)
from .policy import EFFORT_POLICY_VERSION


def estimate_effort(
    project: ProjectProfile, assumptions: EffortAssumptions, evaluated_at: datetime
) -> EffortEstimate:
    project = ProjectProfile.model_validate(project)
    assumptions = EffortAssumptions.model_validate(assumptions)
    evaluated_at = TypeAdapter(UtcInstant).validate_python(evaluated_at)
    items = {i.category: i for i in assumptions.items}
    missing = [
        f"effort.{c.value}" for c in EffortCategory if c not in items or items[c].hours is None
    ]
    adaptation = project.estimated_adaptation_hours.value
    adaptation_range = (
        None if adaptation is None else HourRange(min_hours=adaptation, max_hours=adaptation)
    )
    if adaptation is None:
        missing.append("project.estimated_adaptation_hours")
    ranges = [i.hours for i in assumptions.items if i.hours is not None]
    return EffortEstimate(
        breakdown=tuple(items[c] for c in EffortCategory if c in items),
        adaptation_range=adaptation_range,
        min_total=None if missing else adaptation + sum((r.min_hours for r in ranges), Decimal(0)),
        max_total=None if missing else adaptation + sum((r.max_hours for r in ranges), Decimal(0)),
        reasons=("Totals require all six preparation categories and stated project adaptation.",),
        missing_information=tuple(missing),
        evaluated_at=evaluated_at,
        policy_version=EFFORT_POLICY_VERSION,
    )


def assess_capacity(
    founder: FounderProfile,
    effort: EffortEstimate,
    opportunity: OpportunityRecord,
    evaluated_at: datetime,
) -> CapacityAssessment:
    founder = FounderProfile.model_validate(founder)
    effort = EffortEstimate.model_validate(effort)
    opportunity = OpportunityRecord.model_validate(opportunity)
    evaluated_at = TypeAdapter(UtcInstant).validate_python(evaluated_at)
    missing = []
    available = founder.available_hours.value
    if available is None:
        missing.append("founder.available_hours")
    if effort.max_total is None or effort.missing_information:
        missing.append("effort.max_total")
    remaining = None
    if not opportunity.deadlines or any(not isinstance(d, datetime) for d in opportunity.deadlines):
        missing.append("opportunity.deadlines.exact_instant")
    else:
        delta = min(opportunity.deadlines) - evaluated_at
        microseconds = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
        remaining = max(Decimal(0), Decimal(microseconds) / Decimal(3600000000))
    usable = None if available is None or remaining is None else min(available, remaining)
    state = (
        CapacityState.UNKNOWN
        if missing
        else (
            CapacityState.SUFFICIENT if usable >= effort.max_total else CapacityState.INSUFFICIENT
        )
    )
    return CapacityAssessment(
        state=state,
        available_hours=available,
        remaining_wall_hours=remaining,
        usable_hours=usable,
        required_hours=effort.max_total,
        reasons=("Compare maximum effort with the lesser of available and remaining wall hours.",),
        missing_information=tuple(missing),
        evaluated_at=evaluated_at,
        policy_version=EFFORT_POLICY_VERSION,
    )
