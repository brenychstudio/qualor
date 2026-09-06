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


@pytest.mark.parametrize("case", ["missing", "unsupported_field"])
def test_actual_strands_schema_rejection_reaches_model_as_safe_actionable_result(case):
    from strands.models.model import Model

    from qualor.runtime.agent import run_agent

    class InvalidClaimModel(Model):
        turns = 0
        received = None

        def update_config(self, **kwargs):
            pass

        def get_config(self):
            return {}

        async def structured_output(self, *a, **k):
            raise AssertionError("No additional model")
            yield

        async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
            self.turns += 1
            record_schema = next(t for t in tool_specs if t["name"] == "record_evidence")
            schema = record_schema["inputSchema"]["json"]
            claim_schema = schema["$defs"]["ExtractedClaim"]
            assert claim_schema["additionalProperties"] is False
            assert "source_id" in claim_schema["required"]
            assert "source_url" in claim_schema["required"]
            assert "retrieved_at" not in claim_schema["properties"]
            assert "evidence_id" not in claim_schema["properties"]
            if self.turns == 1:
                candidate = {"source_id": "private-input-value"}
                if case == "unsupported_field":
                    candidate.update(
                        source_url="https://example.org/rules",
                        field="invented-field",
                        value="quoted",
                        excerpt="quoted",
                        state="CANDIDATE",
                        confidence="HIGH",
                    )
                yield {"messageStart": {"role": "assistant"}}
                yield {
                    "contentBlockStart": {
                        "contentBlockIndex": 0,
                        "start": {
                            "toolUse": {"toolUseId": "invalid-claim", "name": "record_evidence"}
                        },
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "contentBlockIndex": 0,
                        "delta": {"toolUse": {"input": json.dumps({"claims": [candidate]})}},
                    }
                }
                yield {"contentBlockStop": {"contentBlockIndex": 0}}
                yield {"messageStop": {"stopReason": "tool_use"}}
            else:
                self.received = next(
                    b["toolResult"]
                    for m in reversed(messages)
                    for b in m["content"]
                    if "toolResult" in b
                )
                payload = json.loads(self.received["content"][0]["text"])
                assert payload["status"] == "REJECTED"
                assert payload["reason_code"] == (
                    "TOOL_ARGUMENT_VALIDATION_FAILED"
                    if case == "missing"
                    else "CLAIM_FIELD_UNSUPPORTED"
                )
                assert payload["recoverable"] == "YES"
                if case == "missing":
                    assert any(f.endswith("source_url") for f in payload["missing_fields"])
                else:
                    assert "claims.0.field:literal_error" in payload["validation_issues"]
                assert "private-input-value" not in json.dumps(self.received)
                yield {"messageStart": {"role": "assistant"}}
                yield {"messageStop": {"stopReason": "end_turn"}}
            yield {
                "metadata": {
                    "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                    "metrics": {"latencyMs": 1},
                }
            }

    model = InvalidClaimModel()
    result, metrics = run_agent(make_run(), model=model)
    assert model.received is not None, metrics
    assert not result.claims
    assert "private-input-value" not in result.model_dump_json()
    assert any(e.status == "REJECTED" and e.validation_issues for e in result.boundary_events)
