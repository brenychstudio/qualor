"""Offline controlled acceptance for the archived canonical compiler path."""

from pathlib import Path

import pytest
from archived_compiler_support import (
    ARCHIVE_SHA256,
    load_archived_rules,
    run_archived_compiler,
)

from qualor.domain.enums import Category, Operator, Provenance, SubjectReference
from qualor.runtime.budget import QUALOR_5F_COST_CAP_USD
from qualor.runtime.canonical_compilation import compile_section_authority

ARCHIVE_ROOT = Path(
    r"C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source"
    r"\.qualor\local\killer-demo-real-source"
)


@pytest.mark.archived_source
def test_archived_canonical_compiler_preserves_authority_and_unknowns(monkeypatch):
    """A compiler that skips source grounding, coverage, or budget gates must fail here."""

    monkeypatch.setenv("QUALOR_REQUIRE_ARCHIVE", "1")
    monkeypatch.setenv("QUALOR_ARCHIVE_DIR", str(ARCHIVE_ROOT))

    report = run_archived_compiler(ARCHIVE_ROOT)
    source = load_archived_rules(ARCHIVE_ROOT)
    # The compiler's own observations and the coverage-guarded authority that reaches
    # the decision are different layers, and this acceptance proves both.
    raw_authority = compile_section_authority(report.raw_section_results)
    effective_authority = compile_section_authority(report.effective_section_results)
    attempts = tuple(report.attempted_pairs)
    categories = {result.category for result in report.section_results}
    all_rules = tuple(rule for result in report.section_results for rule in result.rules)
    raw_rules = tuple(rule for result in report.raw_section_results for rule in result.rules)
    all_evidence = tuple(record for result in report.section_results for record in result.evidence)
    required = {
        Category.PROJECT_POLICY,
        Category.LICENSE,
        Category.REQUIRED_TECHNOLOGY,
        Category.FINANCIAL_SUPPORT,
        Category.REWARD_CONDITIONS,
    }
    independently_surfaced = {
        Category.DEADLINE,
        Category.ENTRANT_TYPE,
        Category.GEOGRAPHY,
        Category.LEGAL_ENTITY,
        Category.PROJECT_POLICY,
        Category.LICENSE,
        Category.REQUIRED_TECHNOLOGY,
        Category.FINANCIAL_SUPPORT,
        Category.REWARD_CONDITIONS,
    }

    assert report.source_hash == ARCHIVE_SHA256
    assert report.indexed_sections > 0
    assert report.gate_values["DEFAULT_9KB_WINDOW_ONLY"] is False
    assert report.gate_values["REPEATED_IDENTICAL_WINDOW"] is False
    assert len(attempts) == len(set(attempts))
    assert report.gate_values["duplicate_section_category_attempts"] == 0
    assert report.gate_values["extraction_after_exhaustion"] == 0
    assert report.gate_values["planner_rediscovery_calls"] == 0
    assert report.section_results == report.effective_section_results
    assert raw_authority.supported_claim_count > 0
    assert report.gate_values["RAW_EXECUTABLE_RULES"] > 0
    assert any(rule.supported for rule in raw_rules)
    assert all(rule.evidence_ids for rule in raw_rules if rule.supported)
    assert all(rule.evidence_ids for rule in all_rules if rule.supported)
    assert report.gate_values["sourceless_rules"] == 0
    assert report.gate_values["decision_derived_from_canonical_authority"] is True
    assert required <= set(report.reached_categories)
    assert independently_surfaced <= categories
    assert report.gate_values["unresolved_remains_unresolved"] is True
    assert all(record.clause_context is not None for record in all_evidence)
    assert all(record.supporting_excerpt in source.text for record in all_evidence)
    assert report.gate_values["quote_fabrication"] == 0
    assert report.gate_values["qualifier_or_exception_drops"] == 0
    assert report.gate_values["owner_facts_inferred_from_rules"] == 0
    assert report.gate_values["project_facts_inferred_from_rules"] == 0
    for profile in (
        report.result.bundle.decision_input.founder,
        *(item.project for item in report.result.bundle.decision_input.projects),
    ):
        assert all(
            fact.provenance is Provenance.UNKNOWN
            for field, fact in profile
            if field
            not in {
                "schema_version",
                "id",
                "version",
                "created_at",
                "updated_at",
                "provenance",
                "name",
            }
            and hasattr(fact, "provenance")
        )
    # The compiler genuinely read one executable interval out of the archived source.
    raw_deadline = next(
        result
        for result in report.raw_section_results
        if result.category is Category.DEADLINE and result.normalization_status == "SUPPORTED"
    )
    raw_rule = raw_deadline.rules[0]
    assert raw_rule.supported
    assert raw_rule.operator is Operator.DATE_BETWEEN
    assert raw_rule.subject_reference is SubjectReference.EVALUATED_AT
    assert [operand.kind for operand in raw_rule.operands] == ["instant", "instant"]
    assert raw_rule.operands[0].value < raw_rule.operands[1].value
    assert all(record.supporting_excerpt in source.text for record in raw_deadline.evidence)
    assert all(record.clause_context.context_complete for record in raw_deadline.evidence)

    # Coverage is genuinely incomplete, so that reading may not become a predicate yet.
    assert report.coverage_states["DEADLINE"] == "SECTION_AVAILABLE"
    assert report.gate_values["DEADLINE_RELEVANT_UNATTEMPTED_REMAINS"] > 0
    assert report.gate_values["COVERAGE_GUARDED_SUPPORTED_CLAIMS"] > 0
    assert report.gate_values["EFFECTIVE_AUTHORITATIVE_CANONICAL_FACTS"] == (
        effective_authority.supported_claim_count
    )
    guarded = next(
        result
        for result in report.effective_section_results
        if result.category is Category.DEADLINE
        and "CATEGORY_COVERAGE_INCOMPLETE" in result.reason_codes
    )
    guard = guarded.rules[0]
    assert guarded.normalization_status == "UNKNOWN"
    assert not guard.supported
    assert guard.source_text_summary == "CATEGORY_COVERAGE_INCOMPLETE"
    assert any(
        child.supported
        and child.operator is Operator.DATE_BETWEEN
        and child.subject_reference is SubjectReference.EVALUATED_AT
        for child in guard.children
    )

    # The decision consumes the guarded authority, never the raw observation.
    decision_rules = report.result.bundle.decision_input.eligibility_rules
    deadline_rules = [rule for rule in decision_rules if rule.rule_type is Category.DEADLINE]
    assert deadline_rules
    assert not any(rule.supported for rule in deadline_rules)
    assert guard.id in {rule.id for rule in decision_rules}
    assert raw_rule.id not in {rule.id for rule in decision_rules}

    assert report.result.mode == "LIVE"
    assert report.result.search_calls == 1
    assert report.result.fetched_documents == 1
    assert len(report.request_sequence) == 9
    assert len(report.receipts) == 9
    assert sum(item["request_kind"] == "PLANNING" for item in report.request_sequence) == 2
    assert sum(item["request_kind"] == "EXTRACTION" for item in report.request_sequence) == 7
    assert report.gate_values["dispatched_model_requests"] == 9
    assert report.gate_values["model_cost_cap_usd"] == str(QUALOR_5F_COST_CAP_USD)
    assert report.gate_values["max_steps"] == 24
