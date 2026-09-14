"""Offline controlled acceptance for the archived canonical compiler path."""

import socket
from pathlib import Path

import pytest
from archived_compiler_support import (
    ARCHIVE_SHA256,
    ArchiveInputError,
    deny_external_io,
    load_archived_rules,
    over_broad_relevance_budget_exhausted,
    run_archived_compiler,
)

from qualor.domain.enums import Category, Operator, Provenance, SubjectReference
from qualor.runtime.budget import QUALOR_5F_COST_CAP_USD
from qualor.runtime.canonical_compilation import compile_section_authority

ARCHIVE_ROOT = Path(
    r"C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source"
    r"\.qualor\local\killer-demo-real-source"
)
TASK15_HIDDEN_SECTION_IDS = frozenset(
    {
        "section_e04f6bf27157fdaf642f2ec12e606139",
        "section_6fc24aae0861dadfbae600081cf16647",
        "section_a0a70c55f05bc2a7604d3dc498bce1d9",
        "section_4a38bebe61ee1795a9a025317db33682",
        "section_632db9fb94e5b6df6e566fcd0add38d6",
        "section_a5a633769e93ecb0843bba87467120b6",
        "section_ed774619086470501fefa37544880176",
    }
)


def _deny_external_io_with_loopback_runtime(monkeypatch):
    """Keep the archive guard while allowing asyncio's local Windows self-pipe."""

    loopback_sockets = socket.socketpair()
    deny_external_io(monkeypatch)
    supplied = False

    def asyncio_socketpair(*args, **kwargs):
        nonlocal supplied
        if supplied or args or kwargs:
            raise ArchiveInputError("ARCHIVE_EXTERNAL_IO_DENIED")
        supplied = True
        return loopback_sockets

    monkeypatch.setattr(socket, "socketpair", asyncio_socketpair)
    return loopback_sockets


def test_over_broad_budget_exhaustion_diagnostic_is_true_and_false_sensitive():
    """A full bounded plan may stop on budget only when work remains unresolved."""

    assert over_broad_relevance_budget_exhausted(
        termination_reason="BUDGET_EXHAUSTED",
        extraction_calls=7,
        max_extraction_jobs=7,
        unresolved_obligations=("planned-item",),
    )
    assert not over_broad_relevance_budget_exhausted(
        termination_reason="BUDGET_EXHAUSTED",
        extraction_calls=7,
        max_extraction_jobs=7,
        unresolved_obligations=(),
    )
    assert not over_broad_relevance_budget_exhausted(
        termination_reason="NO_PROGRESS",
        extraction_calls=7,
        max_extraction_jobs=7,
        unresolved_obligations=("planned-item",),
    )
    assert not over_broad_relevance_budget_exhausted(
        termination_reason="BUDGET_EXHAUSTED",
        extraction_calls=6,
        max_extraction_jobs=7,
        unresolved_obligations=("planned-item",),
    )


@pytest.mark.archived_source
def test_archived_canonical_compiler_preserves_authority_and_unknowns(monkeypatch):
    """A compiler that skips source grounding, coverage, or budget gates must fail here."""

    monkeypatch.setenv("QUALOR_REQUIRE_ARCHIVE", "1")
    monkeypatch.setenv("QUALOR_ARCHIVE_DIR", str(ARCHIVE_ROOT))
    loopback_sockets = _deny_external_io_with_loopback_runtime(monkeypatch)
    try:
        report = run_archived_compiler(ARCHIVE_ROOT)
    finally:
        for loopback_socket in loopback_sockets:
            loopback_socket.close()
    source = load_archived_rules(ARCHIVE_ROOT)
    # The compiler's own observations and the coverage-guarded authority that reaches
    # the decision are different layers, and this acceptance proves both.
    raw_authority = compile_section_authority(report.raw_section_results)
    effective_authority = compile_section_authority(report.effective_section_results)
    attempts = tuple(report.attempted_pairs)
    all_rules = tuple(rule for result in report.section_results for rule in result.rules)
    raw_rules = tuple(rule for result in report.raw_section_results for rule in result.rules)
    all_evidence = tuple(record for result in report.section_results for record in result.evidence)
    potential_hidden = tuple(
        item
        for item in report.plan_items
        if item["child_local_unclassified"]
        and item["rule_like"]
        and item["rule_like_category_hints"]
        and item["tier"] in {"MANDATORY_ANCHOR", "CONDITIONAL_DISCOVERY"}
    )
    hidden_section_ids = {item["section_id"] for item in potential_hidden}
    task15_hidden = tuple(
        item for item in potential_hidden if item["section_id"] in TASK15_HIDDEN_SECTION_IDS
    )

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
    assert report.gate_values["PLANNING_CALLS"] == 2
    assert report.gate_values["EXTRACTION_CALLS"] <= 7
    assert report.gate_values["TOTAL_MODEL_CALLS"] <= 9
    assert report.gate_values["OVER_BROAD_RELEVANCE_BUDGET_EXHAUSTED"] is False
    assert report.gate_values["ALL_NINE_CATEGORIES_DISCOVERABLE"] is True
    assert report.gate_values["ALL_NINE_CATEGORIES_ACCOUNTED_OR_EXPLICITLY_UNRESOLVED"] is True
    assert report.gate_values["DEADLINE_RAW_AUTHORITY_SUPPORTED"] is True
    assert report.gate_values["DEADLINE_RAW_AUTHORITY_EXECUTABLE"] is True
    assert report.gate_values["UNKNOWN_CATEGORIES_REMAIN_UNRESOLVED"] is True
    assert report.gate_values["HIDDEN_RULELIKE_SECTIONS"] >= 7
    assert report.gate_values["HIDDEN_GOVERNING_CLAUSE_SILENTLY_SKIPPED"] == 0
    assert TASK15_HIDDEN_SECTION_IDS <= hidden_section_ids
    assert len({item["section_id"] for item in task15_hidden}) == 7
    assert any(item["is_context_dependency"] for item in potential_hidden)
    assert all(
        item["plan_item_state"]
        in {"ACCOUNTED", "CONTEXT_UNRESOLVED", "OVERFLOW_UNDISPATCHED"}
        or item["is_context_dependency"]
        for item in potential_hidden
    )
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
    planning_calls = sum(item["request_kind"] == "PLANNING" for item in report.request_sequence)
    extraction_calls = sum(
        item["request_kind"] == "EXTRACTION" for item in report.request_sequence
    )
    assert planning_calls == 2
    assert 1 <= extraction_calls <= 7
    assert len(report.request_sequence) == planning_calls + extraction_calls <= 9
    assert len(report.receipts) == len(report.request_sequence)
    assert report.gate_values["dispatched_model_requests"] == len(report.request_sequence)
    assert report.gate_values["model_cost_cap_usd"] == str(QUALOR_5F_COST_CAP_USD)
    assert report.gate_values["max_steps"] == 24
