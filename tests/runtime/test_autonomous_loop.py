from datetime import UTC, datetime
from decimal import Decimal

import pytest

from qualor.runtime.budget import LiveBudgetGuard, LiveBudgetPolicy
from qualor.runtime.providers import SearchCandidate


def inputs():
    from qualor.decisions.fixture import ProjectDecisionInput
    from qualor.domain.base import Fact
    from qualor.domain.profiles import FounderProfile, ProjectProfile
    from qualor.effort import EffortAssumptions
    from qualor.runtime.run_models import StudioInput

    now = datetime.now(UTC)
    base = dict(
        schema_version="1",
        id="owned",
        version=1,
        created_at=now,
        updated_at=now,
        provenance="USER_ASSERTED",
    )
    founder = FounderProfile(**base)
    project = ProjectProfile(
        **base,
        name="Owned",
        technology_stack=Fact(value=("Other SDK",), provenance="USER_ASSERTED"),
    )
    return StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Find an owned synthetic opportunity",
        allowed_hosts=("example.org",),
        founder=founder,
        projects=(ProjectDecisionInput(project=project, effort=EffortAssumptions(items=())),),
    )


def make_run(mode="FIXTURE", **options):
    from qualor.runtime.loop import OpportunityRun
    from qualor.runtime.sources import SourceDocument

    class Search:
        def search(self, request):
            return (SearchCandidate("https://example.org/rules", "Owned rules", "discovery only"),)

    class Fetch:
        def fetch(self, request):
            return SourceDocument(
                id="s",
                original_url=request.url,
                final_url=request.url,
                retrieved_at=datetime.now(UTC),
                authority="OFFICIAL_RULES",
                content_hash="a" * 64,
                text="Projects must use Widget SDK.",
            )

    class Extract:
        def extract(self, source, focus):
            del focus
            return (
                {
                    "source_id": source.id,
                    "source_url": source.final_url,
                    "field": "required_technology",
                    "value": ["Widget SDK"],
                    "excerpt": "Projects must use Widget SDK.",
                    "state": "CANDIDATE",
                    "confidence": "HIGH",
                },
            )

    return OpportunityRun(
        inputs(),
        mode=mode,
        search=Search(),
        fetcher=Fetch(),
        extractor=options.pop("extractor", Extract()),
        budget=LiveBudgetGuard(LiveBudgetPolicy(cost_cap_usd=Decimal(".20"))),
        **options,
    )


def record(run, value="Widget SDK"):
    source = next(iter(run.sources.values()), None)
    return run.record_evidence(
        {
            "source_id": source.id if source else "s",
            "source_url": source.final_url if source else "https://example.org/rules",
            "field": "required_technology",
            "value": [value],
            "excerpt": f"Projects must use {value}.",
            "state": "CANDIDATE",
            "confidence": "HIGH",
        }
    )


def discover_and_fetch(run, query="q"):
    result = run.search_web(query)
    return run.fetch_official_source(result["results"][0]["candidate_id"])


@pytest.mark.parametrize("mode", ["FIXTURE", "REPLAY"])
def test_A01_A02_A22_A23_offline_contract_can_search_fetch_and_evaluate(mode):
    r = make_run(mode)
    discover_and_fetch(r, "owned query")
    record(r)
    result = r.evaluate_current_state()
    assert result["candidates"][0]["eligibility"] == "FAIL"
    assert result["recommendation"] == "SKIP"
    assert r.decision.mode == mode
    assert r.budget.snapshot().search_calls == 0
    assert r.budget.snapshot().inference_calls == 0


def test_A05_search_snippet_cannot_be_recorded_as_source():
    r = make_run()
    r.search_web("query")
    result = record(r)
    assert result["status"] == "REJECTED"
    assert not r.claims


def test_additive_technology_requirements_are_not_contradictions():
    from qualor.runtime.sources import SourceDocument

    r = make_run()
    discover_and_fetch(r)
    record(r)
    r.sources["other"] = SourceDocument(
        id="other",
        original_url="https://example.org/faq",
        final_url="https://example.org/faq",
        retrieved_at=datetime.now(UTC),
        content_hash="b" * 64,
        authority="OFFICIAL_FAQ",
        text="Projects must use Other SDK.",
    )
    r.record_evidence(
        {
            "source_id": "other",
            "source_url": "https://example.org/faq",
            "field": "required_technology",
            "value": ["Other SDK"],
            "excerpt": "Projects must use Other SDK.",
            "state": "CANDIDATE",
            "confidence": "HIGH",
        }
    )
    result = r.evaluate_current_state()
    assert result["candidates"][0]["eligibility"] == "FAIL"
    assert result["recommendation"] == "SKIP"
    assert not r.contradictions


def test_A09_disagreeing_official_deadlines_force_review():
    from qualor.runtime.sources import SourceDocument

    r = make_run()
    for index, value in enumerate(("September 1", "September 2")):
        url = f"https://example.org/rules{index}"
        excerpt = f"The deadline is {value}."
        r.sources[str(index)] = SourceDocument(
            id=str(index),
            original_url=url,
            final_url=url,
            retrieved_at=datetime.now(UTC),
            content_hash="b" * 64,
            authority="OFFICIAL_RULES",
            text=excerpt,
        )
        r.record_evidence(
            dict(
                source_id=str(index),
                source_url=url,
                field="deadline",
                value=value,
                excerpt=excerpt,
                state="CANDIDATE",
                confidence="HIGH",
            )
        )
    result = r.evaluate_current_state()
    assert result["candidates"][0]["eligibility"] == "REVIEW_REQUIRED"
    assert result["recommendation"] == "WATCH"
    assert r.contradictions == ("deadline",)


def test_A20_step_limit_prevents_tool_action():
    r = make_run(max_steps=1)
    result = r.search_web("q")
    assert r.fetch_official_source(result["results"][0]["candidate_id"])["status"] == "STOPPED"
    assert r.termination_reason == "MAX_STEPS"
    assert not r.sources


def test_A21_repeated_no_progress_stops():
    r = make_run()
    r.search_web("q")
    for _ in range(3):
        r.search_web("q")
    assert r.termination_reason == "NO_PROGRESS"


def test_A24_A25_trace_is_bounded_action_only_and_final_engine_owns_result():
    r = make_run()
    discover_and_fetch(r)
    record(r)
    result = r.finish()
    assert result.decision.recommendation == "SKIP"
    assert result.termination_reason
    assert "reasoning" not in result.model_dump_json().lower()
    assert len(result.trace) <= 100
    assert all(
        set(e.model_dump())
        == {
            "event",
            "reason_code",
            "source_ids",
            "span_ids",
            "count",
            "normalized_field",
            "normalization_status",
            "normalizer_version",
        }
        for e in result.trace
    )
    normalization = next(
        event for event in result.trace if event.event == "CLAIM_NORMALIZATION_RESULT"
    )
    assert normalization.normalized_field == "required_technology"
    assert normalization.normalization_status == "SUPPORTED"
    assert normalization.normalizer_version == "1"
    assert result.trace.index(normalization) < next(
        index for index, event in enumerate(result.trace) if event.event == "EVIDENCE_RECORDED"
    )


def test_rejected_request_records_safe_specific_code_without_private_error_text():
    r = make_run()
    result = r.fetch_official_source("candidate_not_discovered")
    assert result["reason_code"] == "CANDIDATE_NOT_FOUND"
    assert r.trace[-1].reason_code == "CANDIDATE_NOT_FOUND"
    result = r.failure(RuntimeError("potentially sensitive arbitrary service response"))
    assert result["reason_code"] == "TOOL_OR_CLAIM_REJECTED"


def test_rejected_claim_exposes_bounded_normalization_result_without_value_or_excerpt():
    r = make_run()
    discover_and_fetch(r)
    source = next(iter(r.sources.values()))
    result = r.record_evidence(
        {
            "source_id": source.id,
            "source_url": source.final_url,
            "field": "required_technology",
            "value": ["Different SDK"],
            "excerpt": "Projects must use Widget SDK.",
            "state": "CANDIDATE",
            "confidence": "HIGH",
        }
    )

    assert result["reason_code"] == "MODEL_VALUE_CONFLICTS_WITH_SOURCE_NORMALIZATION"
    event = next(e for e in r.trace if e.event == "CLAIM_NORMALIZATION_RESULT")
    assert event.normalized_field == "required_technology"
    assert event.normalization_status == "SUPPORTED"
    assert event.normalizer_version == "1"
    assert "Different SDK" not in event.model_dump_json()
    assert "Projects must use" not in event.model_dump_json()
    assert r.failures == 0
    assert r.termination_reason is None


def test_fetched_source_citation_survives_even_without_admitted_claims():
    r = make_run()
    discover_and_fetch(r)
    result = r.finish()
    assert result.citation_urls == ("https://example.org/rules",)
    assert result.sources[0].final_url == "https://example.org/rules"
    assert "text" not in result.sources[0].model_dump()


def test_equivalent_scalar_and_list_technology_claims_do_not_change_verdict():
    r = make_run()
    discover_and_fetch(r)
    record(r)
    earlier = r.evaluate_current_state()["recommendation"]
    # Use a fresh run because the first run correctly terminates on hard failure.
    r = make_run()
    discover_and_fetch(r)
    record(r)
    payload = next(iter(r.claims.values())).claim.model_dump()
    payload["value"] = "Widget SDK"
    r.record_evidence(payload)
    assert r.evaluate_current_state()["recommendation"] == earlier
    assert r.contradictions == ()


class _RealRunSemanticOutcomeExtractor:
    """Offline reproduction of the three extraction batches from paid run 2."""

    def extract(self, source, focus):
        common = {
            "source_id": source.id,
            "source_url": source.final_url,
            "state": "CANDIDATE",
            "confidence": "HIGH",
        }
        if focus == "batch-1":
            return (
                {
                    **common,
                    "field": "entrant_type",
                    "value": "INDIVIDUAL",
                    "excerpt": "Applicants may enter.",
                },
                {
                    **common,
                    "field": "geography",
                    "value": "United States",
                    "excerpt": "The challenge is open worldwide.",
                },
            )
        if focus == "batch-2":
            return (
                {
                    **common,
                    "field": "required_technology",
                    "value": ["Widget SDK"],
                    "excerpt": "Projects can use Widget SDK.",
                },
                {
                    **common,
                    "field": "required_technology",
                    "value": ["Widget SDK"],
                    "excerpt": "Projects must use Widget SDK or another tool.",
                },
            )
        return (
            {
                **common,
                "field": "deadline",
                "value": "2030-10-01T17:00:00Z",
                "excerpt": "Submissions close October 1, 2030.",
            },
        )


def _semantic_outcome_run():
    from qualor.runtime.sources import SourceDocument

    run = make_run(extractor=_RealRunSemanticOutcomeExtractor())
    run.sources["source_real_shape"] = SourceDocument(
        id="source_real_shape",
        original_url="https://example.org/rules",
        final_url="https://example.org/rules",
        retrieved_at=datetime.now(UTC),
        content_hash="c" * 64,
        authority="OFFICIAL_RULES",
        text=(
            "Applicants may enter. The challenge is open worldwide. "
            "Projects can use Widget SDK. "
            "Projects must use Widget SDK or another tool. "
            "Submissions close October 1, 2030."
        ),
    )
    return run


def test_three_semantic_rejection_batches_do_not_reach_tool_failure_bound():
    run = _semantic_outcome_run()

    results = [
        run.extract_official_claims("source_real_shape", focus)
        for focus in ("batch-1", "batch-2", "batch-3")
    ]

    assert all(result["status"] == "EXTRACTED" for result in results)
    assert run.failures == 0
    assert run.termination_reason is None
    assert sorted(claim.normalization_status for claim in run.claims.values()) == [
        "AMBIGUOUS",
        "AMBIGUOUS",
    ]
    rejected = [
        event
        for event in run.boundary_events
        if event.event == "EVIDENCE_ADMISSION_RESULT" and event.status == "REJECTED"
    ]
    assert [event.reason_code for event in rejected] == [
        "CLAIM_VALUE_UNSUPPORTED",
        "CLAIM_VALUE_UNSUPPORTED",
        "CLAIM_VALUE_UNSUPPORTED",
    ]


def test_three_ambiguous_claims_remain_unknown_without_operational_failures():
    run = _semantic_outcome_run()

    for confidence in ("HIGH", "MEDIUM", "LOW"):
        result = run.record_evidence(
            {
                "source_id": "source_real_shape",
                "source_url": "https://example.org/rules",
                "field": "entrant_type",
                "value": "INDIVIDUAL",
                "excerpt": "Applicants may enter.",
                "state": "CANDIDATE",
                "confidence": confidence,
            }
        )
        assert result["status"] == "UNKNOWN"

    assert run.failures == 0
    assert run.termination_reason is None
    assert all(claim.normalized_value is None for claim in run.claims.values())
    assert all(claim.support_state == "UNKNOWN" for claim in run.claims.values())


@pytest.mark.parametrize("failure_shape", ["provider", "schema", "source_reference"])
def test_three_operational_failures_still_reach_tool_failure_bound(failure_shape):
    class BrokenExtractor:
        def extract(self, source, focus):
            del source, focus
            if failure_shape == "provider":
                raise RuntimeError("provider unavailable")
            return ({"not": "an ExtractedClaim"},)

    run = make_run(extractor=BrokenExtractor())
    if failure_shape == "source_reference":
        for index in range(3):
            result = run.extract_official_claims(f"source_missing_{index}", "technology")
    else:
        discover_and_fetch(run)
        source_id = next(iter(run.sources))
        for index in range(3):
            result = run.extract_official_claims(source_id, f"technology-{index}")

    assert result["status"] == "REJECTED"
    assert run.failures == 3
    assert run.termination_reason == "TOOL_FAILURE_BOUND_REACHED"
