import json
from pathlib import Path

import pytest
from test_autonomous_loop import discover_and_fetch, make_run, record


def test_handoff_events_cover_success_and_reference_fetched_source():
    r = make_run()
    discover_and_fetch(r)
    record(r)
    result = r.finish()
    names = {e.event for e in result.boundary_events}
    assert {
        "SOURCE_FETCH_RESULT",
        "EXTRACTION_RESULT",
        "CLAIM_VALIDATION_RESULT",
        "EVIDENCE_ADMISSION_ATTEMPT",
        "EVIDENCE_ADMISSION_RESULT",
    } <= names
    assert any(e.source_ids for e in result.boundary_events)


def test_rejected_claim_is_actionable_and_traced():
    r = make_run()
    r.search_web("q")
    result = record(r)
    assert result["status"] == "REJECTED"
    assert result["reason_code"] == "CLAIM_SOURCE_REFERENCE_MISSING"
    assert result["component"] == "claim_validation"
    assert result["recoverable"] == "YES"
    assert result["safe_summary"]
    assert r.boundary_events[-1].status == "REJECTED"


def test_missing_claim_fields_are_reported_without_input_values():
    r = make_run()
    result = r.record_evidence({"source_id": "private-value-must-not-leak"})
    assert result["status"] == "REJECTED"
    assert "source_url" in result["missing_fields"]
    assert "private-value-must-not-leak" not in json.dumps(result)
    assert "private-value-must-not-leak" not in r.finish().model_dump_json()


def test_safe_rejection_unwraps_sdk_pydantic_cause():
    from qualor.runtime.claims import ExtractedClaim
    from qualor.runtime.diagnostics import reject

    try:
        try:
            ExtractedClaim.model_validate({"password": "must-not-leak"})
        except ValueError as inner:
            raise ValueError("SDK message containing must-not-leak") from inner
    except ValueError as outer:
        result = reject(outer, component="record_evidence")
    assert result.reason_code == "TOOL_ARGUMENT_VALIDATION_FAILED"
    assert "source_url" in result.missing_fields
    assert "must-not-leak" not in result.model_dump_json()


def test_type_shapes_do_not_record_values_or_unrecognized_keys():
    from qualor.runtime.diagnostics import shape

    rendered = shape({"source_url": "private-value", "secret-key-name": "private-value"})
    assert "source_url:string" in rendered
    assert "private" not in rendered and "secret-key-name" not in rendered


def test_diagnostic_run_policy_is_tighter_and_repeat_marker_fails_before_aws(tmp_path, monkeypatch):
    import qualor.runtime.live_cli as cli

    policy = cli.diagnostic_policy()
    assert (policy.inference_max_calls, policy.search_max_calls, policy.fetch_max_documents) == (
        6,
        3,
        5,
    )
    assert str(policy.cost_cap_usd) == "0.15"
    profile = Path("examples/profiles/synthetic-studio.json").resolve()
    monkeypatch.chdir(tmp_path)
    marker = Path(".qualor/local/qualor-03b3d-live-run-2.json")
    marker.parent.mkdir(parents=True)
    marker.write_text('{"status":"STARTED"}')
    monkeypatch.setattr(cli, "execute_live", lambda *a, **k: pytest.fail("AWS forbidden on repeat"))
    with pytest.raises(FileExistsError):
        cli.run_command(profile, "gateway", diagnostic=True)


def test_strands_has_no_direct_model_authored_evidence_admission_capability():
    from strands.models.model import Model

    from qualor.runtime.agent import run_agent

    class InspectingModel(Model):
        inspected = False

        def update_config(self, **kwargs):
            pass

        def get_config(self):
            return {}

        async def structured_output(self, *a, **k):
            raise AssertionError("No additional model")
            yield

        async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
            del messages, system_prompt, kwargs
            names = {item["name"] for item in tool_specs}
            assert names == {
                "search_web",
                "fetch_official_source",
                "extract_official_claims",
                "evaluate_current_state",
            }
            assert "record_evidence" not in names
            self.inspected = True
            yield {"messageStart": {"role": "assistant"}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            yield {
                "metadata": {
                    "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                    "metrics": {"latencyMs": 1},
                }
            }

    model = InspectingModel()
    result, metrics = run_agent(make_run(), model=model)
    assert model.inspected, metrics
    assert not result.claims
