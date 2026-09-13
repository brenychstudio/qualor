"""Offline reproduction of the first real LIVE run's inference-call shape."""

import json
from datetime import UTC, datetime
from decimal import Decimal

from strands.models.model import Model

from qualor.decisions.fixture import ProjectDecisionInput
from qualor.domain.base import Fact
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.effort import EffortAssumptions
from qualor.runtime.agent import run_agent
from qualor.runtime.budget import (
    QUALOR_5F_COST_CAP_USD,
    LiveBudgetGuard,
    LiveBudgetPolicy,
    LiveCallKind,
)
from qualor.runtime.live_cli import live_budget
from qualor.runtime.loop import OpportunityRun
from qualor.runtime.providers import SearchCandidate
from qualor.runtime.run_models import StudioInput
from qualor.runtime.sources import SourceDocument

SOURCE_TEXT = (
    "Participants enter from eligible locations. "
    "Organizer: Example Foundation."
)


def _profile() -> StudioInput:
    now = datetime.now(UTC)
    common = dict(
        schema_version="1",
        id="owned",
        version=1,
        created_at=now,
        updated_at=now,
        provenance="USER_ASSERTED",
    )
    project = ProjectProfile(
        **common,
        name="Owned",
        technology_stack=Fact(value=("Other SDK",), provenance="USER_ASSERTED"),
    )
    return StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Reproduce the bounded real-run call shape offline",
        allowed_hosts=("example.org",),
        founder=FounderProfile(**common),
        projects=(
            ProjectDecisionInput(project=project, effort=EffortAssumptions(items=())),
        ),
    )


class _Search:
    def search(self, request):
        del request
        return (
            SearchCandidate(
                "https://example.org/rules", "Owned rules", "Discovery only"
            ),
        )


class _Fetch:
    def fetch(self, request):
        return SourceDocument(
            id="source",
            original_url=request.url,
            final_url=request.url,
            retrieved_at=datetime.now(UTC),
            authority="OFFICIAL_RULES",
            content_hash="a" * 64,
            text=SOURCE_TEXT,
        )


def _reserve_inference(budget: LiveBudgetGuard) -> None:
    receipt = budget.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=Decimal(".01"))
    budget.reconcile(receipt, actual_cost_usd=Decimal(".01"))


class _TraceShapeExtractor:
    """One useful batch, one schema failure, then one useful recovery batch."""

    def __init__(self, budget: LiveBudgetGuard):
        self.budget = budget
        self.attempts = 0
        self.focuses = []
        self.receipts = []
        self.last_created_span_ids = ()
        self.last_selected_span_ids = ()

    def extract(self, source, focus):
        self.attempts += 1
        self.focuses.append(focus)
        _reserve_inference(self.budget)
        if self.attempts == 1:
            return (
                {
                    "source_id": source.id,
                    "source_url": source.final_url,
                    "field": "entrant_type",
                    "value": "INDIVIDUAL",
                    "excerpt": "Participants enter from eligible locations.",
                    "state": "CANDIDATE",
                    "confidence": "MEDIUM",
                },
                {
                    "source_id": source.id,
                    "source_url": source.final_url,
                    "field": "geography",
                    "value": "Spain",
                    "excerpt": "Participants enter from eligible locations.",
                    "state": "CANDIDATE",
                    "confidence": "MEDIUM",
                },
            )
        if self.attempts == 2:
            raise ValueError("EXTRACTION_SCHEMA_REJECTED")
        return (
            {
                "source_id": source.id,
                "source_url": source.final_url,
                "field": "organizer",
                "value": "Example Foundation",
                "excerpt": "Organizer: Example Foundation.",
                "state": "CANDIDATE",
                "confidence": "HIGH",
            },
        )


class _TraceShapePlanner(Model):
    """Four planning turns; turn four requests two distinct evidence focuses."""

    def __init__(self, budget: LiveBudgetGuard):
        self.budget = budget
        self.turns = 0

    def update_config(self, **kwargs):
        del kwargs

    def get_config(self):
        return {}

    async def structured_output(self, *args, **kwargs):
        del args, kwargs
        raise AssertionError("Extraction remains a separate bounded tool call")
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        del tool_specs, system_prompt, kwargs
        self.turns += 1
        _reserve_inference(self.budget)
        observations = [
            json.loads(content["text"])
            for message in messages
            for block in message.get("content", [])
            if "toolResult" in block
            for content in block["toolResult"].get("content", [])
            if isinstance(content.get("text"), str)
        ]
        if self.turns == 1:
            calls = [("search_web", {"query": "owned query"})]
        elif self.turns == 2:
            calls = [
                (
                    "fetch_official_source",
                    {"candidate_id": observations[-1]["results"][0]["candidate_id"]},
                )
            ]
        elif self.turns == 3:
            calls = [
                (
                    "extract_official_claims",
                    {
                        "source_id": observations[-1]["source_id"],
                        "focus": "entrant type and geography",
                    },
                )
            ]
        elif self.turns == 4:
            source_id = next(
                observation["source_id"]
                for observation in reversed(observations)
                if isinstance(observation, dict) and "source_id" in observation
            )
            calls = [
                (
                    "extract_official_claims",
                    {"source_id": source_id, "focus": "deadline"},
                ),
                (
                    "extract_official_claims",
                    {"source_id": source_id, "focus": "organizer"},
                ),
            ]
        elif self.turns == 5:
            calls = [("evaluate_current_state", {})]
        else:
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockStart": {
                    "contentBlockIndex": 0,
                    "start": {},
                }
            }
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"text": "No further source-grounded progress."},
                }
            }
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            yield {
                "metadata": {
                    "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                    "metrics": {"latencyMs": 1},
                }
            }
            return

        yield {"messageStart": {"role": "assistant"}}
        for index, (name, arguments) in enumerate(calls):
            yield {
                "contentBlockStart": {
                    "contentBlockIndex": index,
                    "start": {
                        "toolUse": {"toolUseId": f"{self.turns}-{index}", "name": name}
                    },
                }
            }
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": index,
                    "delta": {"toolUse": {"input": json.dumps(arguments)}},
                }
            }
            yield {"contentBlockStop": {"contentBlockIndex": index}}
        yield {"messageStop": {"stopReason": "tool_use"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 1},
            }
        }


def _run_with(budget: LiveBudgetGuard):
    extractor = _TraceShapeExtractor(budget)
    run = OpportunityRun(
        _profile(),
        mode="REPLAY",
        search=_Search(),
        fetcher=_Fetch(),
        extractor=extractor,
        budget=budget,
    )
    result, metrics = run_agent(run, model=_TraceShapePlanner(budget))
    return result, metrics, extractor


def test_explicit_six_call_guard_reproduces_first_real_run_exhaustion_shape():
    budget = LiveBudgetGuard(
        LiveBudgetPolicy(
            inference_max_calls=6,
            cost_cap_usd=Decimal(".20"),
            authorization="QUALOR_03B3",
        )
    )

    result, metrics, extractor = _run_with(budget)

    assert result.termination_reason == "BUDGET_EXHAUSTED"
    assert budget.snapshot().inference_calls == 6
    assert metrics["tool_names"] == [
        "search_web",
        "fetch_official_source",
        "extract_official_claims",
        "extract_official_claims",
        "extract_official_claims",
    ]
    assert extractor.attempts == 3
    assert extractor.focuses == [
        "entrant type and geography",
        "deadline",
        "organizer",
    ]
    assert len(result.claims) == 1


def test_live_policy_allows_trace_proven_work_and_outcome_neutral_completion():
    budget = live_budget()

    result, metrics, extractor = _run_with(budget)

    assert result.termination_reason == "NO_PROGRESS"
    assert budget.snapshot().inference_calls == 9
    assert budget.snapshot().reserved_cost_usd == Decimal(".09")
    # Track the current production authorization rather than a parallel literal.
    assert budget.policy.cost_cap_usd == QUALOR_5F_COST_CAP_USD
    assert metrics["tool_names"] == [
        "search_web",
        "fetch_official_source",
        "extract_official_claims",
        "extract_official_claims",
        "extract_official_claims",
        "evaluate_current_state",
    ]
    assert extractor.attempts == 3
    assert extractor.focuses == [
        "entrant type and geography",
        "deadline",
        "organizer",
    ]
    assert len(result.claims) == 2
    claims = {claim.claim.field: claim for claim in result.claims}
    assert claims["entrant_type"].normalization_status == "AMBIGUOUS"
    assert claims["entrant_type"].support_state == "UNKNOWN"
    assert claims["organizer"].normalization_status == "SUPPORTED"
    assert claims["organizer"].support_state == "QUOTE_ONLY"
    assert result.decision.recommendation == "WATCH"
    assert result.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"
