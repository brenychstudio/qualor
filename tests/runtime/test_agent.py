import json
from decimal import Decimal

import pytest

from qualor.runtime.budget import BudgetLimitExceeded, LiveBudgetGuard, LiveBudgetPolicy


def test_pinned_strands_production_factory_accepts_explicit_session_without_network(monkeypatch):
    from botocore.credentials import Credentials

    from qualor.runtime import agent

    monkeypatch.setattr(
        agent, "_temporary_credentials", lambda: Credentials("synthetic", "synthetic", "synthetic")
    )
    model = agent.live_model(LiveBudgetGuard())
    assert isinstance(model.client, agent.BudgetedBedrockClient)
    assert model.client.client.meta.region_name == "us-east-1"
    assert model.client.client.meta.config.retries["total_max_attempts"] == 1


def test_A18_every_physical_model_attempt_reserved_and_usage_reconciled():
    from qualor.runtime.agent import BudgetedBedrockClient

    calls = []

    class Client:
        def converse(self, **request):
            calls.append(request)
            return {"usage": {"inputTokens": 20, "outputTokens": 10}}

    budget = LiveBudgetGuard(LiveBudgetPolicy(inference_max_calls=1))
    wrapped = BudgetedBedrockClient(Client(), budget)
    wrapped.converse(
        modelId="global.anthropic.claude-sonnet-4-6",
        messages=[],
        inferenceConfig={"maxTokens": 100},
    )
    assert budget.snapshot().reserved_cost_usd == Decimal("0.000210")
    with pytest.raises(BudgetLimitExceeded):
        wrapped.converse(
            modelId="global.anthropic.claude-sonnet-4-6",
            messages=[],
            inferenceConfig={"maxTokens": 100},
        )
    assert len(calls) == 1


def test_failed_model_call_is_not_refunded_or_retried():
    from qualor.runtime.agent import BudgetedBedrockClient

    class Client:
        def converse(self, **request):
            raise RuntimeError("synthetic")

    budget = LiveBudgetGuard()
    with pytest.raises(RuntimeError):
        BudgetedBedrockClient(Client(), budget).converse(
            modelId="global.anthropic.claude-sonnet-4-6",
            messages=[],
            inferenceConfig={"maxTokens": 100},
        )
    assert budget.snapshot().inference_calls == 1
    assert budget.snapshot().reserved_cost_usd > 0


def test_actual_strands_loop_chooses_tools_from_observations_and_cannot_set_verdict():
    from strands.models.model import Model
    from test_autonomous_loop import make_run

    from qualor.runtime.agent import run_agent

    class PlanningModel(Model):
        def update_config(self, **kwargs):
            pass

        def get_config(self):
            return {}

        async def structured_output(self, *args, **kwargs):
            raise AssertionError("No separate extraction model")
            yield

        async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
            rendered = json.dumps(messages, default=str)
            tools = tool_specs
            assert {t["name"] for t in tools} == {
                "search_web",
                "fetch_official_source",
                "record_evidence",
                "evaluate_current_state",
            }
            fetch_schema = next(t for t in tools if t["name"] == "fetch_official_source")[
                "inputSchema"
            ]["json"]
            assert "candidate_id" in fetch_schema["properties"]
            assert "url" not in fetch_schema["properties"]
            assert "candidate_id" in fetch_schema["required"]
            if "discovery only" not in rendered:
                name, args = "search_web", {"query": "owned query"}
            elif "Projects must use Widget SDK." not in rendered:
                candidate_id = rendered.split('candidate_id\\\": \\\"', 1)[1].split('\\\"', 1)[0]
                name, args = "fetch_official_source", {"candidate_id": candidate_id}
            elif "CONTROLLED_CLAUSE_VERIFIED" not in rendered:
                name, args = (
                    "record_evidence",
                    {
                        "claims": [
                            {
                                "source_id": "s",
                                "source_url": "https://example.org/rules",
                                "field": "required_technology",
                                "value": ["Widget SDK"],
                                "excerpt": "Projects must use Widget SDK.",
                                "state": "CANDIDATE",
                                "confidence": "HIGH",
                            }
                        ]
                    },
                )
            else:
                name, args = "evaluate_current_state", {}
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockStart": {
                    "contentBlockIndex": 0,
                    "start": {"toolUse": {"toolUseId": str(len(messages)), "name": name}},
                }
            }
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"toolUse": {"input": json.dumps(args)}},
                }
            }
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            yield {
                "metadata": {
                    "usage": {"inputTokens": 10, "outputTokens": 10, "totalTokens": 20},
                    "metrics": {"latencyMs": 1},
                }
            }

    r = make_run()
    result, metrics = run_agent(r, model=PlanningModel())
    assert metrics["strands_tool_calls"] >= 3, metrics
    assert result.decision.recommendation == "SKIP", (metrics, result.trace)
    assert result.mode == "FIXTURE"
    assert result.termination_reason == "HARD_FAIL_CONFIRMED"


def test_U16_U19_replay_recovers_reference_and_reaches_deterministic_evidence_handoff():
    from strands.models.model import Model
    from test_autonomous_loop import make_run

    from qualor.runtime.agent import run_agent

    class ReplayPlanningModel(Model):
        turns = 0

        def update_config(self, **kwargs):
            pass

        def get_config(self):
            return {}

        async def structured_output(self, *args, **kwargs):
            raise AssertionError("No separate extraction model")
            yield

        async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
            self.turns += 1
            rendered = json.dumps(messages, default=str)
            if self.turns == 1:
                name, args = "search_web", {"query": "owned query"}
            elif self.turns == 2:
                name, args = "fetch_official_source", {"candidate_id": "candidate_fabricated"}
            elif self.turns == 3:
                assert "CANDIDATE_NOT_FOUND" in rendered
                assert "available_candidates" in rendered
                candidate_id = rendered.rsplit('candidate_id\\\": \\\"', 1)[1].split('\\\"', 1)[0]
                name, args = "fetch_official_source", {"candidate_id": candidate_id}
            elif self.turns == 4:
                assert "Projects must use Widget SDK." in rendered
                name, args = (
                    "record_evidence",
                    {
                        "claims": [
                            {
                                "source_id": "s",
                                "source_url": "https://example.org/rules",
                                "field": "required_technology",
                                "value": ["Widget SDK"],
                                "excerpt": "Projects must use Widget SDK.",
                                "state": "CANDIDATE",
                                "confidence": "HIGH",
                            }
                        ]
                    },
                )
            else:
                name, args = "evaluate_current_state", {}
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockStart": {
                    "contentBlockIndex": 0,
                    "start": {"toolUse": {"toolUseId": str(self.turns), "name": name}},
                }
            }
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"toolUse": {"input": json.dumps(args)}},
                }
            }
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            yield {
                "metadata": {
                    "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                    "metrics": {"latencyMs": 1},
                }
            }

    run = make_run(mode="REPLAY")
    result, metrics = run_agent(run, model=ReplayPlanningModel())

    assert run.search_calls == 1
    assert len(result.claims) == 1
    evidence_id = result.claims[0].evidence.id
    assert evidence_id in result.decision.model_dump_json()
    assert result.decision.recommendation == "SKIP"
    assert result.claims[0].evidence.source_type == "OFFICIAL_RULES"
    assert all(
        not registered.observation.can_prove_hard_eligibility
        for registered in run.candidates.values()
    )
    assert metrics["strands_tool_calls"] >= 5
    events = [event.event for event in result.trace]
    assert events.index("SEARCH_REQUESTED") < events.index("CANDIDATE_SELECTED")
    assert events.index("SOURCE_FETCHED") < events.index("EVIDENCE_RECORDED")
    assert events.index("EVIDENCE_RECORDED") < events.index("ELIGIBILITY_EVALUATED")
