from datetime import UTC, datetime, timedelta

import pytest

from qualor.domain import (
    EvidenceRecord,
    FounderProfile,
    OpportunityRecord,
    ProjectProfile,
    RuleCandidate,
)
from qualor.domain.enums import Category

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


def meta(record_id):
    return dict(
        schema_version="1",
        id=record_id,
        version=1,
        created_at=NOW,
        updated_at=NOW,
        provenance="DOCUMENTED",
    )


@pytest.fixture
def scenario():
    def build():
        from qualor.domain.fixture import EvaluationContext

        evidence = tuple(
            EvidenceRecord(
                **meta("e_" + category.value),
                original_url="https://synthetic.example/rules",
                final_url="https://synthetic.example/rules",
                retrieved_at=NOW,
                source_type="SYNTHETIC_FIXTURE",
                content_hash="a" * 64,
                supporting_excerpt="Owned synthetic assertion for " + category.value,
                normalized_field=category,
                extraction_state="REVIEWED",
            )
            for category in Category
        )
        founder = FounderProfile(
            **meta("founder"),
            legal_form=dict(value="INCORPORATED_COMPANY", provenance="DOCUMENTED"),
            country_of_residence=dict(value="Spain", provenance="USER_ASSERTED"),
        )
        project = ProjectProfile(**meta("project"), name="Synthetic project")
        opportunity = OpportunityRecord(
            **meta("opportunity"),
            organizer="Synthetic Foundation",
            program_name="Example program",
            edition="2026",
            canonical_rules_url="https://synthetic.example/rules",
            deadlines=[NOW + timedelta(days=10)],
            status="OPEN",
        )
        context = EvaluationContext(
            founder=founder,
            project=project,
            opportunity=opportunity,
            evidence=evidence,
            evaluated_at=NOW,
            mode="FIXTURE",
        )
        rules = tuple(
            RuleCandidate(
                **meta("r_" + category.value),
                rule_type=category,
                operator="EQ",
                operands=[dict(kind="text", value="INCORPORATED_COMPANY")]
                if category == Category.LEGAL_ENTITY
                else [],
                subject_reference="founder.legal_form"
                if category == Category.LEGAL_ENTITY
                else None,
                criticality="CRITICAL",
                evidence_ids=["e_" + category.value],
                supported=True,
                source_text_summary="Owned synthetic rule",
                not_applicable_reason=None
                if category == Category.LEGAL_ENTITY
                else "Synthetic rules explicitly impose no condition in this category",
            )
            for category in Category
        )
        return context, rules

    return build


def replace(model, **changes):
    return type(model).model_validate(dict(model.model_dump(), **changes))
