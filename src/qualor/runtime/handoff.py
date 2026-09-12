"""Compile admitted observations, never model verdicts, into established engines."""

from datetime import UTC, datetime

from qualor.decisions.engine import decide
from qualor.decisions.fixture import DecisionInput
from qualor.domain.base import Fact
from qualor.domain.enums import ExtractionState, Operator, Provenance, SubjectReference
from qualor.domain.opportunity import OpportunityRecord, normalize_url, opportunity_identity
from qualor.domain.planning import MatchingRequirements
from qualor.domain.rules import RuleCandidate
from qualor.domain.values import BoolValue, TextValue
from qualor.effort import ParticipationCosts

from .claims import FIELD_CATEGORY, HARD_AUTHORITIES, normalize
from .normalization import parse_absolute_deadline
from .run_models import RuntimeDecisionBundle
from .sources import AUTHORITY_PRIORITY


def _authoritative_claims(run, field):
    return tuple(
        admitted
        for admitted in run.claims.values()
        if admitted.claim.field == field
        and admitted.evidence.source_type in HARD_AUTHORITIES
        and admitted.normalization_status == "SUPPORTED"
        and admitted.normalized_value is not None
    )


def _single_text_value(run, field):
    values = {
        normalize(admitted.normalized_value): admitted.normalized_value
        for admitted in _authoritative_claims(run, field)
        if isinstance(admitted.normalized_value, str)
    }
    return next(iter(values.values())) if len(values) == 1 else None


def _single_text_sequence(run, field):
    values = {}
    for admitted in _authoritative_claims(run, field):
        value = admitted.normalized_value
        items = value if isinstance(value, tuple) else (value,)
        values[tuple(normalize(item) for item in items)] = tuple(items)
    return next(iter(values.values())) if len(values) == 1 else ()


def _deadline_values(run):
    values = {
        parsed
        for admitted in _authoritative_claims(run, "deadline")
        if isinstance(admitted.normalized_value, str)
        and (parsed := parse_absolute_deadline(admitted.normalized_value)) is not None
    }
    return tuple(values) if len(values) == 1 else ()


def _compile_rules(run, now):
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
            contradiction=field in run.contradictions,
        )
        if (
            evidence.extraction_state == ExtractionState.REVIEWED
            and field not in run.contradictions
        ):
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
    requirements = (
        MatchingRequirements(
            technologies=Fact(
                value=tuple(dict.fromkeys(technologies)),
                provenance="DOCUMENTED",
                evidence_refs=tuple(technology_refs),
            )
        )
        if technologies
        else None
    )
    return tuple(rules), requirements


def compile_decision_bundle(run) -> RuntimeDecisionBundle:
    """Compile one source-grounded opportunity and evaluate it exactly once."""

    now = datetime.now(UTC)
    observed = {}
    for admitted in run.claims.values():
        if admitted.evidence.source_type in HARD_AUTHORITIES:
            if admitted.claim.field == "required_technology":
                continue
            value = admitted.normalized_value
            if value is None:
                value = admitted.claim.value
            if value is None:
                continue
            terms = value if isinstance(value, tuple) else (value,)
            observed.setdefault(admitted.claim.field, set()).add(
                tuple(sorted({normalize(term) for term in terms}))
            )
    run.contradictions = tuple(field for field, values in observed.items() if len(values) > 1)
    rules, requirements = _compile_rules(run, now)
    evidence = tuple(claim.evidence for claim in run.claims.values())
    authority_rank = {authority: index for index, authority in enumerate(AUTHORITY_PRIORITY)}
    admitted_sources = sorted(
        evidence,
        key=lambda item: (
            authority_rank[item.source_type],
            normalize_url(item.final_url),
            item.content_hash,
            item.id,
        ),
    )
    sources = sorted(
        run.sources.values(),
        key=lambda item: (
            authority_rank[item.authority],
            normalize_url(item.final_url),
            item.content_hash,
            item.id,
        ),
    )
    admitted_rules = [
        item for item in admitted_sources if item.source_type == "OFFICIAL_RULES"
    ]
    url = (
        admitted_rules[0].final_url
        if admitted_rules
        else sources[0].final_url
        if sources
        else (
            next(iter(run.candidates.values())).observation.url
            if run.candidates
            else "https://" + run.inputs.allowed_hosts[0] + "/"
        )
    )
    organizer = _single_text_value(run, "organizer") or "UNKNOWN"
    program = _single_text_value(run, "program") or "UNKNOWN"
    edition = _single_text_value(run, "edition") or "UNKNOWN"
    deadlines = _deadline_values(run)
    deliverables = _single_text_sequence(run, "deliverables")
    documented = any(
        (
            organizer != "UNKNOWN",
            program != "UNKNOWN",
            edition != "UNKNOWN",
            bool(deadlines),
            bool(deliverables),
            requirements is not None,
        )
    )
    opportunity = OpportunityRecord(
        schema_version="1",
        id=opportunity_identity(organizer, program, edition),
        version=1,
        created_at=now,
        updated_at=now,
        provenance=Provenance.DOCUMENTED if documented else Provenance.UNKNOWN,
        organizer=organizer,
        program_name=program,
        edition=edition,
        canonical_rules_url=url,
        deadlines=deadlines,
        deliverables=deliverables,
        source_versions=tuple(
            dict.fromkeys(source.content_hash for source in admitted_sources)
        ),
        matching_requirements=requirements,
    )
    resolver = getattr(run, "opportunity_version_resolver", None)
    if resolver is not None:
        opportunity = OpportunityRecord.model_validate(resolver(opportunity))
    decision_input = DecisionInput(
        schema_version="1",
        mode=run.mode,
        founder=run.inputs.founder,
        opportunity=opportunity,
        projects=run.inputs.projects,
        eligibility_rules=rules,
        evidence=evidence,
        conflict_rules=(),
        active_submissions=(),
        participation_costs=ParticipationCosts(complete=Fact(), items=()),
        evaluated_at=now,
    )
    return RuntimeDecisionBundle(
        opportunity=opportunity,
        evidence=evidence,
        decision_input=decision_input,
        decision=decide(decision_input),
    )


def compute_decision(run):
    """Backward-compatible decision-only view of the canonical runtime bundle."""

    return compile_decision_bundle(run).decision
