"""Synthetic search responses; no AWS access in this suite."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from qualor.cli import app
from qualor.runtime.budget import BudgetLimitExceeded, LiveBudgetGuard, LiveBudgetPolicy
from qualor.runtime.providers import SearchCandidate, SearchRequest


def schema():
    return {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "maxResults": {"type": "integer"},
            "filters": {
                "type": "object",
                "properties": {
                    "domainFilter": {
                        "type": "object",
                        "properties": {
                            "include": {"type": "array", "items": {"type": "string"}},
                            "exclude": {"type": "array", "items": {"type": "string"}},
                        },
                    }
                },
            },
        },
    }


class RpcStub:
    """Only replace external RPC, leaving validation/parser/budget real."""

    def __init__(self, result=None):
        self.requests = []
        self.tool = {"name": "different-prefix___WebSearch", "inputSchema": schema()}
        self.result = (
            result
            if result is not None
            else {
                "structuredContent": {
                    "id": "query-owned",
                    "results": [
                        {
                            "text": "Owned synthetic excerpt",
                            "url": "https://example.org/rules",
                            "title": "Owned rules",
                            "publishedDate": "2026-09-01",
                        }
                    ],
                }
            }
        )

    def rpc(self, method, params):
        self.requests.append((method, params))
        if method == "tools/list":
            return {"tools": [self.tool]}
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def provider(mode="LIVE", rpc=None, budget=None):
    from qualor.runtime.search import AgentCoreSearchProvider

    return AgentCoreSearchProvider(
        mode=mode,
        transport=rpc or RpcStub(),
        budget=budget
        or LiveBudgetGuard(LiveBudgetPolicy(search_max_calls=2, cost_cap_usd=Decimal("0.02"))),
    )


@pytest.mark.parametrize("mode", ["FIXTURE", "REPLAY"])
def test_S01_S02_S19_offline_mode_rejects_provider_before_rpc(mode):
    rpc = RpcStub()
    with pytest.raises(RuntimeError):
        provider(mode, rpc)
    assert rpc.requests == []


def test_S03_live_requires_explicit_transport():
    from qualor.runtime.search import AgentCoreSearchProvider

    with pytest.raises(RuntimeError):
        AgentCoreSearchProvider(mode="LIVE", transport=None, budget=LiveBudgetGuard())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": "x" * 201},
        {"query": " "},
        {"query": "q", "max_results": 0},
        {"query": "q", "max_results": 26},
        {"query": "q", "max_results": True},
        {"query": "q", "max_results": 1.5},
    ],
)
def test_S04_S05_S06_invalid_query_limits_fail_locally(kwargs):
    with pytest.raises(ValueError):
        SearchRequest(**kwargs)


def test_S07_S09_S10_dynamic_name_and_filters_reach_wire():
    rpc = RpcStub()
    p = provider(rpc=rpc)
    filters = {
        "domainFilter": {"include": ["example.org"]},
        "publishedDateFilter": {"from": "2026-01-01T00:00:00Z"},
    }
    candidates = p.search(SearchRequest("owned query", filters=filters, run_id="run-owned"))
    assert rpc.requests[0] == ("tools/list", {})
    assert rpc.requests[1][1]["name"] == "different-prefix___WebSearch"
    assert rpc.requests[1][1]["arguments"] == {
        "query": "owned query",
        "maxResults": 5,
        "filters": filters,
    }
    assert candidates[0].run_id == "run-owned"


def test_S08_missing_filter_schema_prevents_search():
    rpc = RpcStub()
    del rpc.tool["inputSchema"]["properties"]["filters"]
    with pytest.raises(ValueError):
        provider(rpc=rpc).search(SearchRequest("q"))
    assert len(rpc.requests) == 1


@pytest.mark.parametrize("structured", [True, False])
def test_S11_S12_S13_S20_citations_survive_parser_and_serialization(structured):
    body = {
        "id": "provider-query",
        "results": [
            {
                "url": "https://example.org/rules",
                "title": "Owned title",
                "text": "Owned snippet",
                "publishedDate": "2026-08-25",
            }
        ],
    }
    result = (
        {"structuredContent": body}
        if structured
        else {"content": [{"type": "text", "text": json.dumps(body)}]}
    )
    c = provider(rpc=RpcStub(result)).search(SearchRequest("q"))[0]
    exported = json.loads(json.dumps(asdict(c), default=str))
    assert exported["url"] == "https://example.org/rules"
    assert exported["title"] == "Owned title"
    assert exported["published_date"] == "2026-08-25"
    assert c.source_domain == "example.org"
    assert c.query_id == "provider-query"
    assert c.retrieved_at <= datetime.now(UTC)
    assert c.citable_for_user_output is True


def test_S14_missing_citations_never_fabricated():
    rpc = RpcStub({"structuredContent": {"results": [{"text": "uncited knowledge"}]}})
    c = provider(rpc=rpc).search(SearchRequest("q"))[0]
    assert c.url is None and c.title is None and c.published_date is None
    assert not c.citable_for_user_output
    assert not c.can_prove_hard_eligibility


def test_S15_S16_candidate_remains_separate_from_hard_evidence():
    from qualor.domain import EvidenceRecord

    c = provider().search(SearchRequest("q"))[0]
    assert isinstance(c, SearchCandidate) and not isinstance(c, EvidenceRecord)
    assert c.can_prove_hard_eligibility is False


def test_S17_shared_guard_stops_third_search_before_rpc():
    rpc = RpcStub()
    p = provider(rpc=rpc)
    p.search(SearchRequest("first"))
    p.search(SearchRequest("second"))
    with pytest.raises(BudgetLimitExceeded):
        p.search(SearchRequest("third"))
    assert [m for m, _ in rpc.requests].count("tools/call") == 2


def test_S18_failed_request_consumes_reservation_without_retry():
    rpc = RpcStub(RuntimeError("network failure"))
    budget = LiveBudgetGuard(LiveBudgetPolicy(search_max_calls=1))
    p = provider(rpc=rpc, budget=budget)
    with pytest.raises(RuntimeError):
        p.search(SearchRequest("q"))
    assert budget.snapshot().search_calls == 1
    assert budget.snapshot().reserved_cost_usd > 0
    with pytest.raises(BudgetLimitExceeded):
        p.search(SearchRequest("retry"))
    assert [m for m, _ in rpc.requests].count("tools/call") == 1


@pytest.mark.parametrize(
    "result",
    [
        {"isError": True},
        {"structuredContent": {"results": "bad"}},
        {"content": [{"type": "text", "text": "not JSON"}]},
        {"structuredContent": {"results": [{"text": 123}]}},
        {"structuredContent": {"results": [{"text": "ok", "url": 123}]}},
    ],
)
def test_malformed_search_is_not_an_empty_success(result):
    with pytest.raises(ValueError):
        provider(rpc=RpcStub(result)).search(SearchRequest("q"))


def test_cli_default_cannot_activate_live_search():
    result = CliRunner().invoke(app, ["search-live", "q"])
    assert result.exit_code != 0
    assert "LIVE_REQUIRES_EXPLICIT_MODE" in result.output


def test_cli_live_path_preserves_citations_without_real_aws(monkeypatch):
    from contextlib import contextmanager

    import qualor.runtime.search_transport as module

    @contextmanager
    def fake_gateway(**kwargs):
        assert kwargs == {"mode": "LIVE", "gateway_id": "owned"}
        yield RpcStub()

    monkeypatch.setattr(module, "open_gateway_transport", fake_gateway)
    result = CliRunner().invoke(
        app,
        [
            "search-live",
            "owned query",
            "--mode",
            "LIVE",
            "--gateway-id",
            "owned",
            "--include-domain",
            "example.org",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "MODE=LIVE" in result.output
    assert "PROVIDER=AGENTCORE_WEB_SEARCH" in result.output
    assert "CITATION_COUNT=1" in result.output
    assert '"url": "https://example.org/rules"' in result.output


@pytest.mark.parametrize(
    "broken_schema", [None, {"properties": []}, {"type": "object", "properties": {"query": None}}]
)
def test_malformed_catalog_fails_closed_with_validation_error(broken_schema):
    rpc = RpcStub()
    rpc.tool["inputSchema"] = broken_schema
    with pytest.raises(ValueError):
        provider(rpc=rpc).search(SearchRequest("q"))
    assert [m for m, _ in rpc.requests] == ["tools/list"]


def test_returned_unknown_date_is_preserved_without_fabrication():
    result = {"structuredContent": {"results": [{"text": "synthetic", "publishedDate": "unknown"}]}}
    assert provider(rpc=RpcStub(result)).search(SearchRequest("q"))[0].published_date == "unknown"
