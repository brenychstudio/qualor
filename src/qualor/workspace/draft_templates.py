"""Offline drafting: quoted source data never supplies executable instructions.

Only the service assembles authoritative sections. The author returns visibly
labelled presentation prose, never facts, approval, destinations or tool calls.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import StringConstraints

from qualor.decisions import DecisionRecord
from qualor.domain import EvidenceRecord, FounderProfile, OpportunityRecord, ProjectProfile
from qualor.domain.base import Contract

from .models import DraftAuthoringFact, DraftPackSection, RunRecord


@dataclass(frozen=True)
class DraftInputSnapshot:
    founder: FounderProfile
    project: ProjectProfile
    opportunity: OpportunityRecord
    decision: DecisionRecord
    evidence: tuple[EvidenceRecord, ...]
    source_run: RunRecord
    authoring_facts: tuple[DraftAuthoringFact, ...]
    missing_fields: tuple[str, ...]
    decision_evidence_refs: tuple[str, ...]
    authoring_only_evidence_refs: tuple[str, ...]


class DraftProse(Contract):
    project_fit: Annotated[str, StringConstraints(strict=True, max_length=16_000)]
    suggested_answers: Annotated[str, StringConstraints(strict=True, max_length=16_000)]


class DraftAuthor(Protocol):
    """Trusted offline composer. Model implementations require separate authorization."""

    def compose(self, snapshot: DraftInputSnapshot) -> DraftProse: ...


def authoring_data(founder, project, opportunity, evidence, decision):
    """Explicit allowlist; unknowns never become facts or stringified object blobs."""
    facts = []
    missing = set(decision.missing_information) | set(decision.readiness.missing_information)

    def add(key, value, source, refs=()):
        if value is None:
            missing.add(key)
            return
        if isinstance(value, bool):
            tag = "BOOLEAN"
        elif isinstance(value, int):
            tag = "INTEGER"
        elif isinstance(value, Decimal):
            tag = "DECIMAL"
        elif isinstance(value, tuple):
            tag = "STRINGS"
        else:
            tag = "STRING"
            if isinstance(value, StrEnum):
                value = value.value
        facts.append(
            DraftAuthoringFact(
                key=key,
                value={"type": tag, "value": value},
                source=source,
                evidence_refs=refs,
            )
        )

    for field in (
        "country_of_residence",
        "citizenship",
        "legal_form",
        "team_size",
        "available_hours",
        "open_source_willingness",
        "strategic_goals",
    ):
        fact = getattr(founder, field)
        add(f"founder.{field}", fact.value, "FOUNDER_PROFILE", fact.evidence_refs)
    add("project.name", project.name, "PROJECT_PROFILE")
    for field in (
        "problem",
        "audience",
        "stage",
        "available_features",
        "technology_stack",
        "code_provenance",
        "is_new_project",
        "license_intent",
        "prior_submissions",
        "estimated_adaptation_hours",
        "has_sponsor_support",
        "reward_conditions_met",
    ):
        fact = getattr(project, field)
        add(f"project.{field}", fact.value, "PROJECT_PROFILE", fact.evidence_refs)
    for field in ("organizer", "program_name", "edition", "deliverables"):
        add(f"opportunity.{field}", getattr(opportunity, field), "OPPORTUNITY")
    if not opportunity.deliverables:
        missing.add("opportunity.deliverables")
    for item in evidence:
        add(f"evidence.{item.id}.excerpt", item.supporting_excerpt, "EVIDENCE", (item.id,))
    return tuple(facts), tuple(sorted(missing))


def _fact_text(snapshot: DraftInputSnapshot, key: str) -> str:
    item = next((f for f in snapshot.authoring_facts if f.key == key), None)
    if item is None:
        return f"MISSING: {key}"
    value = item.value.value
    return ", ".join(value) if isinstance(value, tuple) else str(value)


PROJECT_FIT_FIELDS = (
    ("Project", "project.name"),
    ("Problem", "project.problem"),
    ("Audience", "project.audience"),
)
ANSWER_FIELDS = (
    ("Project description", "project.problem"),
    ("Technology", "project.technology_stack"),
)


def _template_refs(snapshot: DraftInputSnapshot, fields) -> tuple[str, ...]:
    """Cite only the explicit facts rendered by this template; no semantic inference."""
    keys = {key for _, key in fields}
    return tuple(
        sorted(
            {
                ref
                for fact in snapshot.authoring_facts
                if fact.key in keys
                for ref in fact.evidence_refs
            }
        )
    )


class DeterministicDraftAuthor:
    def compose(self, snapshot: DraftInputSnapshot) -> DraftProse:
        return DraftProse(
            project_fit=(
                "\n".join(
                    f"{label}: {_fact_text(snapshot, key)}" for label, key in PROJECT_FIT_FIELDS
                )
                + "\nDeterministic project match: "
                + snapshot.decision.project_match.match_status.value
            ),
            suggested_answers=(
                "\n".join(f"{label}: {_fact_text(snapshot, key)}" for label, key in ANSWER_FIELDS)
                + "\n"
                + "\n".join(f"MISSING: {field}" for field in snapshot.missing_fields)
            ),
        )


def assemble_sections(
    snapshot: DraftInputSnapshot, prose: DraftProse
) -> tuple[DraftPackSection, ...]:
    refs = tuple(e.id for e in snapshot.evidence)
    decision = snapshot.decision
    opportunity = snapshot.opportunity
    entries = (
        (
            "SUBMISSION_SUMMARY",
            "01 Submission summary",
            f"Local draft for human review. No external submission.\n"
            f"{opportunity.program_name} / {opportunity.edition}\n"
            f"Project: {snapshot.project.name}\n"
            f"Deterministic recommendation: {decision.recommendation.value}",
            (),
        ),
        (
            "PROJECT_FIT_NARRATIVE",
            "02 Project fit narrative",
            f"Draft prose — review before use.\n{prose.project_fit}",
            _template_refs(snapshot, PROJECT_FIT_FIELDS),
        ),
        (
            "ELIGIBILITY_CHECKLIST",
            "03 Eligibility checklist",
            f"Deterministic eligibility: {decision.eligibility_gate.state.value}\n"
            + "\n".join(
                f"{e.rule_id}: {e.status.value}" for e in decision.eligibility_gate.evaluations
            ),
            snapshot.decision_evidence_refs,
        ),
        (
            "REQUIRED_DELIVERABLES",
            "04 Required deliverables",
            "\n".join(opportunity.deliverables) or "MISSING: opportunity.deliverables",
            (),
        ),
        (
            "EVIDENCE_REFERENCES",
            "05 Evidence references",
            "\n\n".join(
                f"{e.id} / version {e.version} / {e.source_type.value}\n"
                f"Exact source excerpt (untrusted quoted data):\n{e.supporting_excerpt}\n"
                f"Source: {e.final_url}\nRetrieved: {e.retrieved_at.isoformat()}"
                for e in snapshot.evidence
            ),
            refs,
        ),
        (
            "READINESS_GAPS",
            "06 Readiness gaps",
            f"Deterministic readiness: {decision.readiness.state.value}\n"
            + (
                "\n".join(str(g.value) for g in decision.readiness.gaps)
                or "No recorded readiness gaps."
            )
            + "\n"
            + "\n".join(f"MISSING: {field}" for field in snapshot.missing_fields),
            (),
        ),
        (
            "SUGGESTED_APPLICATION_ANSWERS",
            "07 Suggested application answers",
            f"Draft prose — unresolved fields require human input.\n{prose.suggested_answers}",
            _template_refs(snapshot, ANSWER_FIELDS),
        ),
    )
    return tuple(
        DraftPackSection(key=k, title=t, content=c, evidence_refs=r) for k, t, c, r in entries
    )
