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
