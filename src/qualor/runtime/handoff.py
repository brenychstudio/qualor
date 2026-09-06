"""Compile admitted observations, never model verdicts, into the established engines."""

from datetime import UTC, datetime

from qualor.decisions.engine import decide
from qualor.decisions.fixture import DecisionInput
from qualor.domain.base import Fact
from qualor.domain.enums import ExtractionState, Operator, SubjectReference
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.planning import MatchingRequirements
from qualor.domain.rules import RuleCandidate
from qualor.domain.values import BoolValue, TextValue
from qualor.effort import ParticipationCosts

from .claims import FIELD_CATEGORY, HARD_AUTHORITIES, normalize


def compute_decision(run):
    now = datetime.now(UTC)
    observed = {}
    for admitted in run.claims.values():
        if (
            admitted.evidence.source_type in HARD_AUTHORITIES
            and admitted.normalized_value is not None
        ):
            if admitted.claim.field == "required_technology":
                # Positive technology requirements are additive, not exclusive.
                continue
            value = admitted.normalized_value
            terms = value if isinstance(value, tuple) else (value,)
            observed.setdefault(admitted.claim.field, set()).add(
                tuple(sorted({normalize(term) for term in terms}))
            )
    run.contradictions = tuple(k for k, v in observed.items() if len(v) > 1)
    rules = []
    technologies = []
    technology_refs = []
    for admitted in run.claims.values():
        field = admitted.claim.field
        if field not in FIELD_CATEGORY:
            continue
        evidence = admitted.evidence
        base = dict(
            schema_version="1",
            id="rule_" + evidence.id,
            version=1,
            created_at=now,
            updated_at=now,
            provenance="DOCUMENTED",
            rule_type=FIELD_CATEGORY[field],
            criticality="CRITICAL",
            evidence_ids=(evidence.id,),
            supported=False,
            operator=Operator.EQ,
            source_text_summary="Quoted candidate; unsupported interpretation remains unknown",
            contradiction=bool(run.contradictions),
        )
        if evidence.extraction_state == ExtractionState.REVIEWED and not run.contradictions:
            if field == "required_technology":
                values = admitted.normalized_value
                values = values if isinstance(values, tuple) else (values,)
                for index, value in enumerate(values):
                    rules.append(
                        RuleCandidate(
                            **{
                                **base,
                                "id": base["id"] + "_" + str(index),
                                "supported": True,
                                "operator": Operator.IN,
                                "subject_reference": SubjectReference.REQUIRED_TECHNOLOGY,
                                "operands": (TextValue(value=value),),
                            }
                        )
                    )
                    technologies.append(value)
                    technology_refs.append(evidence.id)
                continue
            if field == "project_policy" and admitted.normalized_value == "NEW_ONLY":
                base.update(
                    supported=True,
                    operator=Operator.BOOL_IS,
                    subject_reference=SubjectReference.NEW_PROJECT,
                    operands=(BoolValue(value=True),),
                )
        rules.append(RuleCandidate(**base))
    sources = sorted(
        run.sources.values(), key=lambda s: (0 if s.authority == "OFFICIAL_RULES" else 1, s.id)
    )
    url = (
        sources[0].final_url
        if sources
        else (
            next(iter(run.candidates.values())).observation.url
            if run.candidates
            else "https://" + run.inputs.allowed_hosts[0] + "/"
        )
    )
    # Metadata, dates, rewards and costs are not promoted from merely valid extraction JSON.
    opportunity = OpportunityRecord(
        schema_version="1",
        id="unknown",
        version=1,
        created_at=now,
        updated_at=now,
        provenance="UNKNOWN",
        organizer="UNKNOWN",
        program_name="UNKNOWN",
        edition="UNKNOWN",
        canonical_rules_url=url,
        source_versions=tuple(s.content_hash for s in sources),
        matching_requirements=MatchingRequirements(
            technologies=Fact(
                value=tuple(dict.fromkeys(technologies)),
                provenance="DOCUMENTED",
                evidence_refs=tuple(technology_refs),
            )
        )
        if technologies
        else None,
    )
    return decide(
        DecisionInput(
            schema_version="1",
            mode=run.mode,
            founder=run.inputs.founder,
            opportunity=opportunity,
            projects=run.inputs.projects,
            eligibility_rules=tuple(rules),
            evidence=tuple(c.evidence for c in run.claims.values()),
            conflict_rules=(),
            active_submissions=(),
            participation_costs=ParticipationCosts(complete=Fact(), items=()),
            evaluated_at=now,
        )
    )
