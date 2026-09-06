"""Pure composition: every candidate is assessed from source facts afresh."""

import hashlib
from datetime import datetime

from qualor.conflicts import assess_conflicts
from qualor.domain.enums import FreshnessStatus, OpportunityStatus, Provenance
from qualor.domain.fixture import EvaluationInput
from qualor.domain.opportunity import OpportunityRecord
from qualor.effort import assess_affordability, assess_capacity, estimate_effort
from qualor.eligibility import aggregate_eligibility, evaluate_freshness
from qualor.eligibility.evidence import effective_deadlines
from qualor.matching import assess_readiness, match_project, select_best_project
from qualor.strategy import derive_strategy

from .fixture import DecisionFixture, DecisionInput
from .model import DecisionOutput, DecisionRecord, DecisionResult, PolicyVersions, Recommendation
from .policy import DECISION_POLICY_VERSION, PORTFOLIO_EXPLANATION, outcome, recommend


def decide_fixture(fixture: DecisionFixture) -> DecisionResult:
    fixture = DecisionFixture.model_validate(fixture)
    return DecisionResult.model_validate(decide(DecisionInput.model_validate(fixture)).model_dump())


def decide(fixture: DecisionInput) -> DecisionOutput:
    fixture = DecisionInput.model_validate(fixture)
    now, opportunity = fixture.evaluated_at, fixture.opportunity
    records = []
    digest = hashlib.sha256(fixture.model_dump_json().encode("utf-8")).hexdigest()
    for item in fixture.projects:
        project = item.project
        context = EvaluationInput(
            founder=fixture.founder,
            project=project,
            opportunity=opportunity,
            evidence=fixture.evidence,
            evaluated_at=now,
            mode=fixture.mode,
        )
        gate = aggregate_eligibility(fixture.eligibility_rules, context)
        deadlines = effective_deadlines(fixture.eligibility_rules, context)
        # Conservative raw rule bounds constrain capacity; only actual opportunity
        # instants establish expiry here. Confirmed critical rule expiry is a gate FAIL.
        capacity_opportunity = OpportunityRecord.model_validate(
            opportunity.model_copy(update={"deadlines": deadlines})
        )
        closed = opportunity.status == OpportunityStatus.CLOSED or any(
            isinstance(d, datetime) and d <= now for d in opportunity.deadlines
        )
        timing_known = bool(deadlines) and all(isinstance(d, datetime) for d in deadlines)
        opportunity_unknown = opportunity.status != OpportunityStatus.OPEN or not timing_known
        match = match_project(project, opportunity, now)
        readiness = assess_readiness(project, opportunity, now)
        effort = estimate_effort(project, item.effort, now)
        capacity = assess_capacity(fixture.founder, effort, capacity_opportunity, now)
        affordability = assess_affordability(fixture.founder, fixture.participation_costs, now)
        conflict = assess_conflicts(
            project,
            capacity_opportunity,
            fixture.conflict_rules,
            fixture.active_submissions,
            fixture.evidence,
            now,
        )
        strategy = derive_strategy(
            fixture.founder, opportunity, match, readiness, capacity, affordability, now
        )
        recommendation = recommend(
            gate.state,
            conflict.status,
            strategy.score,
            readiness.state,
            capacity.state,
            affordability.state,
            closed_or_expired=closed,
        )
        if opportunity_unknown and recommendation.recommendation in (
            Recommendation.APPLY,
            Recommendation.PREPARE,
        ):
            recommendation = outcome(Recommendation.WATCH, "OPPORTUNITY_STATUS_OR_TIMING_UNKNOWN")
        missing = list(gate.missing_information) + list(match.missing_project_facts)
        # Include requirement-side unknowns, which matching keeps in factor references.
        for factor in match.factor_results:
            if factor.rating is None:
                missing.extend(factor.requirement_refs)
        for assessment in (readiness, effort, capacity, affordability):
            missing.extend(assessment.missing_information)
        missing.extend("strategy." + f for f in strategy.missing_strategy_factors)
        missing.extend(
            f"conflict.{scope}.{category}" for scope, category in conflict.missing_rule_categories
        )
        if conflict.status == "REVIEW_REQUIRED":
            missing.append("conflict.review_required")
        if opportunity.status == OpportunityStatus.UNKNOWN:
            missing.append("opportunity.status")
        if not timing_known:
            missing.append("opportunity.deadlines.exact_instant")
        date = next((d for d in deadlines if not isinstance(d, datetime)), None)
        deadline = date if date is not None else min(deadlines, default=None)
        freshness = [
            evaluate_freshness(e.retrieved_at, now, deadline, unknown_deadline=not deadlines)
            for e in fixture.evidence
        ]
        fresh = (
            FreshnessStatus.STALE
            if FreshnessStatus.STALE in freshness
            else FreshnessStatus.UNKNOWN
            if not freshness or FreshnessStatus.UNKNOWN in freshness
            else FreshnessStatus.FRESH
        )
        records.append(
            DecisionRecord(
                schema_version="1",
                id=f"decision_{digest}_{project.id}",
                version=1,
                created_at=now,
                updated_at=now,
                provenance=Provenance.DOCUMENTED,
                opportunity_id=opportunity.id,
                opportunity_version=opportunity.version,
                project_id=project.id,
                project_version=project.version,
                profile_version=fixture.founder.version,
                eligibility_gate=gate,
                conflict_status=conflict.status,
                conflict=conflict,
                project_match=match,
                strategy_score=strategy.score,
                strategy_breakdown=strategy.breakdown,
                strategy=strategy,
                readiness=readiness,
                capacity=capacity,
                affordability=affordability,
                effort=effort,
                recommendation=recommendation.recommendation,
                explanation=recommendation.explanation,
                reason_codes=tuple(
                    dict.fromkeys(
                        (
                            *recommendation.reason_codes,
                            *(f"ELIGIBILITY_{code}" for code in gate.reason_codes),
                        )
                    )
                ),
                missing_information=tuple(dict.fromkeys(missing)),
                next_action=recommendation.next_action,
                freshness_status=fresh,
                policy_versions=PolicyVersions(
                    eligibility=gate.policy_version,
                    matching=match.policy_version,
                    effort=effort.policy_version,
                    conflicts=conflict.policy_version,
                    strategy=strategy.policy_version,
                    decisions=DECISION_POLICY_VERSION,
                ),
            )
        )
    selection = select_best_project(tuple(d.project_match for d in records))
    selected = next((d for d in records if d.project_id == selection.best_project_id), None)
    recommendation = (
        selected.recommendation
        if selected
        else (
            Recommendation.SKIP
            if all(d.recommendation == Recommendation.SKIP for d in records)
            else Recommendation.WATCH
        )
    )
    reasons = selected.reason_codes if selected else ("PORTFOLIO_SELECTION_UNRESOLVED",)
    missing = (
        selected.missing_information
        if selected
        else tuple(
            dict.fromkeys(
                ("portfolio.best_project", *(m for d in records for m in d.missing_information))
            )
        )
    )
    return DecisionOutput(
        mode=fixture.mode,
        best_project_id=selection.best_project_id,
        selection=selection,
        candidates=tuple(records),
        selected_decision=selected,
        recommendation=recommendation,
        reasons=reasons,
        missing_information=missing,
        explanation=selected.explanation if selected else PORTFOLIO_EXPLANATION,
        eligibility=selected.eligibility_gate.state if selected else None,
        **{
            field: getattr(selected, field) if selected else None
            for field in (
                "project_match",
                "strategy",
                "effort",
                "conflict",
                "readiness",
                "capacity",
                "affordability",
            )
        },
    )
