from datetime import UTC, datetime

from test_autonomous_loop import make_run

from qualor.runtime.providers import SearchCandidate
from qualor.runtime.urls import canonical_url_identity


def _candidate_id(run) -> str:
    response = run.search_web("owned query")
    return response["results"][0]["candidate_id"]


def test_U01_exact_registered_candidate_reference_is_accepted():
    run = make_run()
    candidate_id = _candidate_id(run)

    result = run.fetch_official_source(candidate_id)

    assert result["source_url"] == "https://example.org/rules"


def test_U02_U03_unknown_or_fabricated_candidate_reference_is_rejected():
    run = make_run()
    _candidate_id(run)

    result = run.fetch_official_source("candidate_fabricated")

    assert result["status"] == "REJECTED"
    assert result["reason_code"] == "CANDIDATE_NOT_FOUND"
    assert result["recoverable"] == "YES"
    assert result["available_candidates"][0]["candidate_id"].startswith("candidate_")
    assert result["available_candidates"][0]["title"] == "Owned rules"


def test_U04_U05_reference_is_scoped_to_the_current_run():
    first = make_run()
    prior_reference = _candidate_id(first)
    second = make_run()
    current_reference = _candidate_id(second)

    assert current_reference != prior_reference
    assert second.fetch_official_source(prior_reference)["reason_code"] == "CANDIDATE_NOT_FOUND"
    assert second.fetch_official_source(current_reference)["source_id"] == "s"


def test_U06_search_candidate_url_and_fetched_citation_are_preserved():
    run = make_run()
    response = run.search_web("q")

    assert response["results"][0]["url"] == "https://example.org/rules"
    run.fetch_official_source(response["results"][0]["candidate_id"])
    result = run.finish()

    assert result.citation_urls == ("https://example.org/rules",)


def test_U08_raw_url_or_alternate_path_cannot_bypass_reference_registry():
    run = make_run()
    _candidate_id(run)

    raw = run.fetch_official_source("https://example.org/rules")
    alternate = run.fetch_official_source("https://example.org/other")

    assert raw["reason_code"] == "CANDIDATE_NOT_FOUND"
    assert alternate["reason_code"] == "CANDIDATE_NOT_FOUND"
    event = next(e for e in run.boundary_events if e.reason_code == "CANDIDATE_NOT_FOUND")
    assert event.requested_url_sanitized == "https://example.org/rules"
    assert event.candidate_url_count == 1
    assert event.candidate_domains == ("example.org",)
    assert event.closest_candidate_urls_sanitized == ("https://example.org/rules",)


def test_U09_U10_rejection_exposes_bounded_recovery_without_another_search():
    run = make_run()
    candidate_id = _candidate_id(run)
    rejected = run.fetch_official_source("candidate_missing")

    recovered = run.fetch_official_source(rejected["available_candidates"][0]["candidate_id"])

    assert recovered["source_id"] == "s"
    assert run.search_calls == 1
    assert candidate_id == rejected["available_candidates"][0]["candidate_id"]


def test_canonical_url_identity_uses_only_explicit_safe_equivalences():
    assert canonical_url_identity("HTTPS://EXAMPLE.ORG:443#part") == "https://example.org/"
    assert canonical_url_identity("https://example.org") == "https://example.org/"
    assert canonical_url_identity("https://example.org/rules") != canonical_url_identity(
        "https://example.org/rules/"
    )
    assert canonical_url_identity("https://example.org/rules?a=1") != canonical_url_identity(
        "https://example.org/rules?a=2"
    )
    assert canonical_url_identity("http://example.org/rules") != canonical_url_identity(
        "https://example.org/rules"
    )
    assert canonical_url_identity("https://sub.example.org/rules") != canonical_url_identity(
        "https://example.org/rules"
    )


def test_canonical_equivalent_search_results_share_one_reference_but_keep_first_citation():
    from qualor.runtime.budget import LiveBudgetGuard
    from qualor.runtime.loop import OpportunityRun
    from qualor.runtime.sources import SourceDocument

    class Search:
        def search(self, request):
            now = datetime.now(UTC)
            return (
                SearchCandidate("HTTPS://EXAMPLE.ORG:443#one", "One", "one", retrieved_at=now),
                SearchCandidate("https://example.org/#two", "Two", "two", retrieved_at=now),
            )

    class Fetch:
        def fetch(self, request):
            return SourceDocument(
                id="source",
                original_url=request.url,
                final_url=request.url,
                retrieved_at=datetime.now(UTC),
                authority="OTHER_OFFICIAL",
                content_hash="a" * 64,
                text="Official text",
            )

    run = OpportunityRun(
        make_run().inputs,
        mode="REPLAY",
        search=Search(),
        fetcher=Fetch(),
        budget=LiveBudgetGuard(),
    )
    results = run.search_web("q")["results"]

    assert len(results) == 2
    assert results[0]["url"] == "HTTPS://EXAMPLE.ORG:443#one"
    assert results[1]["url"] == "https://example.org/#two"
    assert results[0]["candidate_id"] == results[1]["candidate_id"]
    registered = run.candidates[results[0]["candidate_id"]]
    assert registered.provenance == "SEARCH_CANDIDATE_CANONICAL_EQUIVALENT"
    fetched = run.fetch_official_source(results[0]["candidate_id"])
    assert fetched["source_url"] == "HTTPS://EXAMPLE.ORG:443#one"


def test_U07_registered_malicious_url_still_fails_the_ssrf_destination_policy():
    from qualor.runtime.sources import validate_destination

    try:
        validate_destination("https://127.0.0.1/rules", ("127.0.0.1",), lambda _host: ["127.0.0.1"])
    except ValueError as exc:
        assert str(exc) == "SOURCE_ADDRESS_NOT_PUBLIC"
    else:
        raise AssertionError("private destination was accepted")


def test_safe_url_diagnostic_removes_query_and_fragment():
    from qualor.runtime.urls import sanitized_public_url

    assert (
        sanitized_public_url("https://example.org/rules?token=secret#fragment")
        == "https://example.org/rules"
    )


def test_candidate_diagnostic_count_is_bounded_even_for_malformed_offline_registry():
    from qualor.runtime.urls import RegisteredCandidate

    run = make_run()
    candidate = SearchCandidate("https://example.org/rules", "Owned", "snippet")
    for index in range(30):
        candidate_id = f"candidate_{index}"
        run.candidates[candidate_id] = RegisteredCandidate(
            candidate_id=candidate_id,
            observation=candidate,
            fetch_url=candidate.url,
            provenance="SEARCH_CANDIDATE_EXACT",
        )

    run.fetch_official_source("candidate_missing")
    result = run.finish()

    event = next(e for e in result.boundary_events if e.reason_code == "CANDIDATE_NOT_FOUND")
    assert event.candidate_url_count == 25
