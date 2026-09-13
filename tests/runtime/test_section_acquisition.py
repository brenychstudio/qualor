"""Offline compiler activation through concrete LIVE wrappers and fake transports."""

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
from uuid import UUID

import boto3
import pytest
from strands.models import BedrockModel

from qualor.domain.base import Fact
from qualor.runtime.adapters import adapt_candidate
from qualor.runtime.agent import BudgetedBedrockClient, run_agent
from qualor.runtime.budget import LiveCallKind
from qualor.runtime.extraction import MODEL_ID, BedrockClaimExtractor
from qualor.runtime.live_cli import live_budget
from qualor.runtime.loop import OpportunityRun
from qualor.runtime.search import AgentCoreSearchProvider
from qualor.runtime.sources import OfficialSourceFetcher


class SearchTransport:
    def __init__(self):
        self.calls = []

    def rpc(self, method, params):
        self.calls.append((method, params))
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "search",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "maxResults": {"type": "integer"},
                                "filters": {
                                    "type": "object",
                                    "properties": {
                                        "domainFilter": {
                                            "type": "object",
                                            "properties": {"include": {"type": "array"}},
                                        }
                                    },
                                },
                            },
                        },
                    }
                ]
            }
        assert method == "tools/call"
        return {
            "structuredContent": {
                "results": [
                    {
                        "url": "https://example.org/rules",
                        "title": "Synthetic rules",
                        "text": "Hint",
                    },
                    {"url": "https://example.org/faq", "title": "Synthetic FAQ", "text": "Hint"},
                ]
            }
        }


class CandidateClient:
    """Provides wire candidates only, never rules, facts, or verdicts."""

    def __init__(self, behavior="supported"):
        self.behavior = behavior
        self.requests = []
        self.run = None

    def converse(self, **request):
        self.requests.append(request)
        if "outputConfig" not in request:
            observations = [
                json.loads(item["text"])
                for message in request["messages"]
                for block in message.get("content", [])
                if "toolResult" in block
                for item in block["toolResult"]["content"]
                if "text" in item
            ]
            if not observations:
                name, args = "search_web", {"query": "synthetic rules"}
            else:
                assert "results" in observations[-1], "Unexpected extra planning turn"
                name, args = (
                    "fetch_official_source",
                    {"candidate_id": observations[-1]["results"][0]["candidate_id"]},
                )
            return {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": f"call_{len(self.requests)}",
                                    "name": name,
                                    "input": args,
                                }
                            }
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": {"inputTokens": 10, "outputTokens": 10},
                "metrics": {"latencyMs": 1},
            }
        payload = json.loads(request["messages"][0]["content"][0]["text"])
        if self.run is not None and hasattr(self.run, "section_acquisition"):
            ledger = self.run.section_acquisition.ledger
            assert all(
                (
                    self.run.section_acquisition.index.source_revision,
                    payload["section_id"],
                    category,
                )
                in ledger.attempts
                for category in payload["allowed_categories"]
            )
        if self.behavior == "provider":
            raise OSError("synthetic provider failure")
        selected = [
            s["span_id"]
            for s in payload["EVIDENCE_SPANS"]
            if s["section_id"] == payload["section_id"]
        ]
        category = payload["allowed_categories"][0]
        value = {"LICENSE": "MIT", "REQUIRED_TECHNOLOGY": "Widget SDK"}.get(category)
        if category == "LICENSE" and any(
            "Apache-2.0" in s["exact_text"]
            for s in payload["EVIDENCE_SPANS"]
            if s["section_id"] == payload["section_id"]
        ):
            value = "Apache-2.0"
        if self.behavior == "unknown":
            value = None
        elif self.behavior == "unsupported":
            value = "Unsupported interpretation"
        item = dict(
            category=category,
            proposed_value=value,
            source_id=payload["source_id"],
            section_id=payload["section_id"],
            span_ids=selected,
            qualifier_span_ids=[],
            exception_span_ids=[],
            confidence_class="HIGH",
            state="UNKNOWN" if value is None else "CANDIDATE",
        )
        if self.behavior == "capability":
            item["span_ids"] = ["span_" + "f" * 32]
        claims = [item, item] if self.behavior == "duplicate" else [item]
        if self.behavior.startswith("mixed_"):
            unknown = "unknown" in self.behavior
            other = {
                **item,
                "proposed_value": None if unknown else "Unsupported interpretation",
                "state": "UNKNOWN" if unknown else "CANDIDATE",
            }
            claims = [item, other]
            if self.behavior.endswith("_reversed"):
                claims.reverse()
        body = {"claims": claims}
        if self.behavior == "empty":
            body = {"claims": []}
        if self.behavior == "schema":
            body = {"claims": [item, item, item]}
        return {
            "output": {"message": {"role": "assistant", "content": [{"text": json.dumps(body)}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 10},
            "metrics": {"latencyMs": 1},
        }


@pytest.fixture
def harness(studio_inputs):
    def make(text="License\nProjects must intend to use MIT licenses.", behavior="supported"):
        budget = live_budget()
        transport = SearchTransport()
        requests = []

        def fetch(url, address):
            requests.append((url, address))
            return 200, {"content-type": "text/plain"}, text.encode()

        raw = CandidateClient(behavior)
        client = BudgetedBedrockClient(raw, budget)
        run = OpportunityRun(
            studio_inputs,
            mode="LIVE",
            budget=budget,
            search=AgentCoreSearchProvider(mode="LIVE", transport=transport, budget=budget),
            fetcher=OfficialSourceFetcher(
                mode="LIVE",
                allowed_hosts=("example.org",),
                budget=budget,
                resolver=lambda host: ("93.184.216.34",),
                request=fetch,
            ),
            extractor=BedrockClaimExtractor(
                client, max_output_tokens=budget.policy.extraction_max_output_tokens
            ),
        )
        raw.run = run
        return run, raw, transport, requests

    return make


def fetch_source(run):
    candidates = run.search_web("synthetic rules")
    return run.fetch_official_source(candidates["results"][0]["candidate_id"])["source_id"]


def controller(run):
    assert hasattr(run, "acquire_official_sections"), "Task 8 acquisition is absent"
    assert importlib.util.find_spec("qualor.runtime.section_acquisition") is not None
    from qualor.runtime.section_acquisition import SectionAcquisition

    return SectionAcquisition(run)


def model_for(run):
    session = boto3.Session(
        aws_access_key_id="synthetic",
        aws_secret_access_key="synthetic",
        aws_session_token="synthetic",
        region_name="us-east-1",
    )
    model = BedrockModel(
        boto_session=session,
        model_id=MODEL_ID,
        streaming=False,
        max_tokens=run.budget.policy.model_max_output_tokens,
    )
    model.client = run.extractor.client
    return model


@pytest.fixture
def decision_spy(monkeypatch):
    from qualor.runtime import handoff

    spy = Mock(wraps=handoff.decide)
    monkeypatch.setattr(handoff, "decide", spy)
    return spy


def result_for(grounded_candidate, *, state="CANDIDATE", quote=None, confidence="HIGH"):
    candidate = grounded_candidate(
        "REQUIRED_TECHNOLOGY",
        None if state == "UNKNOWN" else "Widget SDK",
        quote or "Build an agent using Widget SDK.",
        state=state,
        confidence=confidence,
    )
    return adapt_candidate(candidate, evaluated_at=candidate.source.retrieved_at)


def test_SUCCESSFUL_FIRST_SOURCE_ACTIVATES_SECTION_DRAIN(harness):
    run, client, _, _ = harness()
    result, _ = run_agent(run, model=model_for(run))
    assert getattr(run, "section_results", ()), "Successful LIVE fetch must activate compiler"
    assert result.bundle.decision_input.evidence
    assert result.bundle.decision_input.eligibility_rules[0].supported
    assert result.claims == ()  # No duplicate legacy admission path.
    assert any("outputConfig" in request for request in client.requests)


def test_NO_PLANNER_MISSING_FIELD_CALL(harness):
    run, client, _, _ = harness()
    _, metrics = run_agent(run, model=model_for(run))
    assert ["EXTRACTION" if "outputConfig" in r else "PLANNING" for r in client.requests] == [
        "PLANNING",
        "PLANNING",
        "EXTRACTION",
    ]
    assert metrics["tool_names"] == ["search_web", "fetch_official_source"]


def test_SECTION_CATEGORY_PAIR_ONCE(harness):
    run, client, _, _ = harness(behavior="duplicate")
    source_id = fetch_source(run)
    controller(run)
    run.acquire_official_sections(source_id)
    original = len(client.requests)
    for focus in ("license", "new wording", "another focus"):
        run.extract_official_claims(source_id, focus)
    assert len(client.requests) == original == 1
    assert len(run.section_acquisition.ledger.attempts) == 1
    assert len(run.section_results) == 1


@pytest.mark.parametrize("behavior", ["unknown", "unsupported"])
def test_SEMANTIC_REJECTION_NOT_OPERATIONAL_FAILURE(harness, behavior):
    run, _, _, _ = harness(behavior=behavior)
    source_id = fetch_source(run)
    controller(run)
    run.acquire_official_sections(source_id)
    assert run.failures == 0
    assert run.section_results[0].normalization_status in {"UNKNOWN", "UNSUPPORTED"}
    assert run.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"
    assert any(e.status == "REJECTED" for e in run.boundary_events)


@pytest.mark.parametrize("reverse", [False, True])
def test_transport_redundant_unknown_preserves_supported_completeness(
    harness, monkeypatch, reverse
):
    from qualor.runtime.section_acquisition import authority_fingerprint
    from qualor.runtime.spans import EvidenceSpanRegistry

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 13, 12, tzinfo=UTC)

    monkeypatch.setattr("qualor.runtime.loop.uuid4", lambda: UUID(int=1))
    monkeypatch.setattr("qualor.runtime.sources.datetime", Clock)
    runs = []
    for behavior in ("supported", "mixed_unknown_reversed" if reverse else "mixed_unknown"):
        run, raw, _, _ = harness(behavior=behavior)
        # Explicit reproducible test capabilities; each registry still owns its own state.
        run.extractor.span_registry = EvidenceSpanRegistry(secret=b"mixed-batch-test" * 3)
        run.acquire_official_sections(fetch_source(run))
        assert len(raw.requests) == run.budget.snapshot().inference_calls == 1
        assert run.failures == 0
        assert run.section_acquisition.ledger.state("LICENSE") == "SUPPORTED"
        assert run._authority_revision == 1
        runs.append(run)
    assert authority_fingerprint(runs[0].section_results) == authority_fingerprint(
        runs[1].section_results
    )
    assert runs[0].bundle.evidence == runs[1].bundle.evidence
    assert (
        runs[0].bundle.decision_input.eligibility_rules
        == runs[1].bundle.decision_input.eligibility_rules
    )
    assert (
        runs[0].section_acquisition.ledger.outcomes == runs[1].section_acquisition.ledger.outcomes
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_transport_overlapping_semantic_rejections_never_become_operational(harness, reverse):
    from qualor.runtime.canonical_compilation import compile_section_authority

    text = "\n".join(f"{i} License\nProjects must intend to use MIT licenses." for i in range(1, 4))
    behavior = "mixed_unsupported_reversed" if reverse else "mixed_unsupported"
    run, raw, _, _ = harness(text, behavior)
    run.acquire_official_sections(fetch_source(run))
    assert len(raw.requests) == run.budget.snapshot().inference_calls == 3
    assert run.failures == 0
    assert run.termination_reason == "NO_PROGRESS"
    assert {item.normalization_status for item in run.section_results} == {
        "SUPPORTED",
        "UNSUPPORTED",
    }
    assert len(run.section_results) == 6
    authority = compile_section_authority(run.section_results)
    assert len(authority.evidence) == 3
    assert authority.supported_claim_count == 3
    assert run.bundle.evidence == authority.evidence == run.bundle.decision_input.evidence
    for record in authority.evidence:
        associated = [r for r in run.section_results if record in r.evidence]
        assert len(associated) == 2
        assert record.extraction_state == "REVIEWED"
        assert record.supporting_excerpt in next(iter(run.sources.values())).text
        assert any(rule.supported for result in associated for rule in result.rules)
        assert any(not rule.supported for result in associated for rule in result.rules)
    assert run.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"
    assert any(e.status == "REJECTED" for e in run.boundary_events)


@pytest.mark.parametrize("behavior", ["provider", "schema", "capability"])
def test_THREE_REAL_OPERATIONAL_FAILURES_STILL_STOP(harness, behavior):
    text = "\n".join(f"{i} License\nProjects must intend to use MIT licenses." for i in range(1, 5))
    run, client, _, _ = harness(text, behavior)
    source_id = fetch_source(run)
    controller(run)
    run.acquire_official_sections(source_id)
    assert run.failures == 3
    assert run.termination_reason == "TOOL_FAILURE_BOUND_REACHED"
    assert len(client.requests) == 3
    assert len(run.section_acquisition.ledger.attempts) == 3
    assert not run.section_acquisition.ledger.outcomes
    run.finish()
    assert run.termination_reason == "TOOL_FAILURE_BOUND_REACHED"


def test_NO_AUTOMATIC_SOURCE_PIVOT(harness):
    run, _, transport, fetches = harness(behavior="unknown")
    source_id = fetch_source(run)
    controller(run)
    outcome = run.acquire_official_sections(source_id)
    assert outcome["pivot_eligible"] is True
    assert run.termination_reason == "NO_PROGRESS"
    assert len(fetches) == run.search_calls == 1
    assert len([method for method, _ in transport.calls if method == "tools/call"]) == 1


def test_AUTHORITY_CHANGE_REEVALUATES_ONCE(harness, grounded_candidate, decision_spy):
    run, _, _, _ = harness()
    acquisition = controller(run)
    first = result_for(grounded_candidate)
    second = adapt_candidate(
        grounded_candidate("LICENSE", "MIT", "Projects must intend to use MIT licenses."),
        evaluated_at=first.evidence[0].created_at,
    )
    acquisition._admit((first,))
    acquisition._admit((second,))
    assert run._authority_revision == decision_spy.call_count == 2
    assert len(run.bundle.decision_input.evidence) == 2
    run.evaluate_current_state()
    assert decision_spy.call_count == 2


def test_IDENTICAL_SUPPORTED_RESULT_NO_RECOMPUTE(harness, grounded_candidate, decision_spy):
    run, _, _, _ = harness()
    acquisition = controller(run)
    item = result_for(grounded_candidate)
    acquisition._admit((item,))
    bundle = run.bundle
    acquisition._admit((item, item))
    assert run.bundle is bundle
    assert run._authority_revision == decision_spy.call_count == 1


def test_CONFIDENCE_ONLY_CHANGE_NO_RECOMPUTE(harness, grounded_candidate, decision_spy):
    run, _, _, _ = harness()
    acquisition = controller(run)
    acquisition._admit((result_for(grounded_candidate, confidence="LOW"),))
    bundle = run.bundle
    acquisition._admit((result_for(grounded_candidate, confidence="HIGH"),))
    assert run.bundle is bundle
    assert run._authority_revision == decision_spy.call_count == 1


def test_REDUNDANT_UNKNOWN_NO_RECOMPUTE(harness, grounded_candidate, decision_spy):
    run, _, _, _ = harness()
    acquisition = controller(run)
    item = result_for(grounded_candidate, state="UNKNOWN")
    acquisition._admit((item,))
    acquisition._admit((item, item))
    assert len(run.section_results) == 1
    assert run._authority_revision == decision_spy.call_count == 1
    assert run.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"


def test_NEW_UNRESOLVED_EVIDENCE_CHANGING_DECISION_INPUT_REEVALUATES(
    harness, grounded_candidate, decision_spy
):
    run, _, _, _ = harness()
    acquisition = controller(run)
    acquisition._admit((result_for(grounded_candidate, state="UNKNOWN"),))
    acquisition._admit(
        (
            result_for(
                grounded_candidate,
                state="UNKNOWN",
                quote="The integration requirements remain to be clarified.",
            ),
        )
    )
    assert run._authority_revision == decision_spy.call_count == 2
    assert len(run.bundle.decision_input.evidence) == 2
    assert run.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"


def test_DECISION_BUNDLE_EVIDENCE_CANNOT_DIVERGE_FROM_REVISION(
    harness, grounded_candidate, decision_spy
):
    run, _, _, _ = harness()
    acquisition = controller(run)
    item = result_for(grounded_candidate)
    acquisition._admit((item,))
    later = item.model_copy(
        update={
            "evidence": tuple(
                e.model_copy(update={"updated_at": e.updated_at + timedelta(seconds=1)})
                for e in item.evidence
            )
        }
    )
    acquisition._admit((later,))
    assert decision_spy.call_count == 1
    assert run.section_results[0].evidence == run.bundle.evidence
    assert run.bundle.evidence == run.bundle.decision_input.evidence


def test_NO_EXTRA_TERMINAL_MODEL_TURN(harness):
    run, client, _, _ = harness()
    result, metrics = run_agent(run, model=model_for(run))
    assert result.termination_reason == "NO_PROGRESS"
    assert metrics["model_turns"] == 2
    assert len(client.requests) == run.budget.snapshot().inference_calls == 3
    assert run.failures == 0


def test_LEGACY_NON_SECTION_PATH_PRESERVED():
    from test_autonomous_loop import make_run

    run = make_run()
    controller(run)
    source_id = fetch_source(run)
    result = run.extract_official_claims(source_id, "technology")
    assert result["status"] == "EXTRACTED"
    assert len(run.claims) == 1
    assert run.section_results == ()
    assert run.finish().termination_reason == "HARD_FAIL_CONFIRMED"


def test_authority_fingerprint_excludes_redundant_observation(grounded_candidate):
    assert importlib.util.find_spec("qualor.runtime.section_acquisition") is not None, (
        "Task 8 authority fingerprint is absent"
    )
    from qualor.runtime.section_acquisition import authority_fingerprint

    item = result_for(grounded_candidate)
    assert authority_fingerprint((item,)) != authority_fingerprint(())
    assert authority_fingerprint((item, item)) == authority_fingerprint((item,))


def test_conflicting_supported_authority_is_semantic_and_reevaluates_once(
    harness, grounded_candidate, decision_spy
):
    run, _, _, _ = harness()
    acquisition = controller(run)

    def license_result(value):
        candidate = grounded_candidate(
            "LICENSE", value, f"Projects must intend to use {value} licenses."
        )
        return adapt_candidate(candidate, evaluated_at=candidate.source.retrieved_at)

    first, second = license_result("MIT"), license_result("Apache-2.0")
    acquisition._admit((first,))
    acquisition._admit((second,))
    assert run._authority_revision == decision_spy.call_count == 2
    assert run.failures == 0
    assert run.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"
    assert all(rule.contradiction for rule in run.bundle.decision_input.eligibility_rules)
    assert len(run.bundle.evidence) == 2
    assert any(event.status == "REJECTED" for event in run.boundary_events)
    assert any(event.reason_code == "CANONICAL_SOURCE_CONFLICT" for event in run.trace)
    acquisition._admit((first, second))
    assert run._authority_revision == decision_spy.call_count == 2


def test_conflict_projection_is_order_independent_and_preserves_expressions(
    harness, grounded_candidate
):
    from qualor.runtime.canonical_compilation import compile_section_authority
    from qualor.runtime.section_acquisition import authority_fingerprint

    candidates = tuple(
        grounded_candidate("LICENSE", value, f"Projects must intend to use {value} licenses.")
        for value in ("MIT", "Apache-2.0")
    )
    original = tuple(adapt_candidate(c, evaluated_at=c.source.retrieved_at) for c in candidates)
    runs = [harness()[0], harness()[0]]
    controller(runs[0])._admit(original)
    controller(runs[1])._admit(tuple(reversed(original)))
    assert authority_fingerprint(runs[0].section_results) == authority_fingerprint(
        runs[1].section_results
    )
    assert runs[0].bundle.evidence == runs[1].bundle.evidence
    assert compile_section_authority(runs[0].section_results).supported_claim_count == 0
    for item in runs[0].section_results:
        before = next(r for r in original if r.evidence == item.evidence)
        assert item.rules == tuple(
            rule.model_copy(update={"contradiction": True}) for rule in before.rules
        )
    assert runs[0].decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"


def test_nine_call_ceiling_and_step_guard_are_shared(harness):
    text = "\n".join(
        f"{i} License\nProjects must intend to use MIT licenses." for i in range(1, 13)
    )
    run, client, _, _ = harness(text)
    source_id = fetch_source(run)
    run.acquire_official_sections(source_id)
    assert len(client.requests) == run.budget.snapshot().inference_calls == 9
    assert run.termination_reason == "BUDGET_EXHAUSTED"
    assert len(run.section_acquisition.ledger.attempts) == 9
    assert run.budget.snapshot().reserved_cost_usd <= Decimal(".20")
    other, raw, _, _ = harness(text)
    other.max_steps = 3
    other.acquire_official_sections(fetch_source(other))
    assert len(raw.requests) == 1
    assert other.steps == 3
    assert other.termination_reason == "MAX_STEPS"


def test_cost_blocked_job_is_not_dispatched_or_inspected(harness):
    run, client, _, _ = harness()
    source_id = fetch_source(run)
    run.budget.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=Decimal(".18"))
    run.acquire_official_sections(source_id)
    assert run.termination_reason == "BUDGET_EXHAUSTED"
    assert run.failures == 0
    assert not client.requests
    assert not run.section_acquisition.ledger.attempts
    assert not run.section_acquisition.ledger.outcomes
    assert run.section_acquisition.ledger.transitions[-1].cause == "BUDGET_BLOCKED_UNDISPATCHED"


def test_empty_batches_consume_existing_no_progress_bound(harness):
    text = "\n".join(f"{i} License\nProjects must intend to use MIT licenses." for i in range(1, 6))
    run, client, _, _ = harness(text, "empty")
    run.acquire_official_sections(fetch_source(run))
    assert len(client.requests) == run.no_progress == 3
    assert run.failures == 0
    assert run.termination_reason == "NO_PROGRESS"


def test_invalid_source_is_operational_and_terminal_reason_is_sticky(harness):
    run, client, _, _ = harness()
    outcome = run.acquire_official_sections("not-admitted")
    assert outcome["status"] == "REJECTED"
    assert run.failures == 1
    run.stop("MAX_STEPS")
    run.acquire_official_sections("not-admitted")
    run.finish()
    assert run.termination_reason == "MAX_STEPS"
    assert run.failures == 1
    assert not client.requests


def test_post_adaptation_failure_terminalizes_and_persists_receipt(
    harness, monkeypatch, tmp_path
):
    from qualor.persistence import Database
    from qualor.runtime.acquisition_coverage import CoverageLedger
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.run_capture import WorkspaceRunCapture

    run, _, _, _ = harness()
    database = Database(tmp_path / "post-adaptation-failure.db")
    capture = WorkspaceRunCapture(database, run_id="post-adaptation-failure", mode="LIVE")
    run.sink = capture
    source_id = fetch_source(run)

    def fail_coverage_completion(self, section_id, outcomes, authority_revision):
        del self, section_id, outcomes, authority_revision
        raise RuntimeError("PRIVATE_POST_ADAPTATION_SENTINEL")

    monkeypatch.setattr(CoverageLedger, "complete", fail_coverage_completion)

    run.acquire_official_sections(source_id)
    receipt = run.receipt_ledger.snapshot()[0]
    assert receipt.execution_state == "FAILED"
    assert receipt.cost_reserved is not None
    assert receipt.cost_reconciled is not None
    assert all(item.execution_state != "DISPATCHED" for item in run.receipt_ledger.snapshot())

    result = run.finish()
    capture.require_persisted()
    assert result.model_receipts[0] == receipt

    reopened = Database(tmp_path / "post-adaptation-failure.db")
    with reopened.transaction() as connection:
        events = WorkspaceStore(connection).runs.list_run_events("post-adaptation-failure")
    persisted = [event for event in events if event.event_type == "MODEL_CALL_RECEIPT"]
    assert len(persisted) == 1
    assert persisted[0].payload.receipt == receipt
    encoded = persisted[0].payload.model_dump_json()
    assert '"execution_state":"FAILED"' in encoded
    assert '"execution_state":"DISPATCHED"' not in encoded
    assert "PRIVATE_POST_ADAPTATION_SENTINEL" not in encoded


def test_partial_category_cannot_terminate_before_later_contradictory_section(
    harness, decision_spy
):
    run, client, _, _ = harness(
        "1 License\nProjects must intend to use MIT licenses.\n"
        "2 License\nProjects must intend to use Apache-2.0 licenses."
    )
    project_input = run.inputs.projects[0]
    run.inputs = run.inputs.model_copy(
        update={
            "projects": (
                project_input.model_copy(
                    update={
                        "project": project_input.project.model_copy(
                            update={
                                "license_intent": Fact(
                                    value="Apache-2.0", provenance="USER_ASSERTED"
                                )
                            }
                        )
                    }
                ),
            )
        }
    )
    run.acquire_official_sections(fetch_source(run))
    assert len(client.requests) == 2, "Incomplete first clause must not cause HARD_FAIL"
    assert decision_spy.call_count == run._authority_revision == 2
    first_input = decision_spy.call_args_list[0].args[0]
    assert first_input.eligibility_rules[0].source_text_summary == "CATEGORY_COVERAGE_INCOMPLETE"
    assert first_input.eligibility_rules[0].children[0].supported
    assert first_input.eligibility_rules[0].children[0].operands[0].value == "MIT"
    assert run.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"
    assert run.termination_reason == "NO_PROGRESS"
    assert len(run.bundle.evidence) == 2


@pytest.mark.parametrize("unknown_first", [False, True])
def test_same_clause_unknown_cannot_conflict_with_supported_authority(
    harness, grounded_candidate, decision_spy, unknown_first
):
    run, _, _, _ = harness()
    acquisition = controller(run)
    supported = result_for(grounded_candidate)
    unknown = result_for(grounded_candidate, state="UNKNOWN")
    first, second = (unknown, supported) if unknown_first else (supported, unknown)
    acquisition._admit((first,))
    acquisition._admit((second,))
    assert run.section_results == (supported,)
    assert run._authority_revision == decision_spy.call_count == (2 if unknown_first else 1)
    assert run.bundle.evidence == supported.evidence
    assert run.failures == 0
