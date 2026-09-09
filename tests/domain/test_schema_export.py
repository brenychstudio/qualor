import json
from pathlib import Path

EXPECTED = {
    "PortfolioView",
    "ProfileUpdateRequest",
    "ProjectUpdateRequest",
    "InboxResponse",
    "InboxItem",
    "OpportunityWorkspaceResponse",
    "DecisionCanvasView",
    "EvidenceSheetView",
    "ActivityResponse",
    "ApprovalRequest",
    "ApprovalView",
    "DraftPackView",
    "ApprovalConfirmRequest",
    "SessionView",
    "ProductError",
    "FounderProfile",
    "ProjectProfile",
    "OpportunityRecord",
    "EvidenceRecord",
    "RuleCandidate",
    "RuleEvaluation",
    "EligibilityGate",
    "Reward",
    "ProjectMatch",
    "ProjectSelection",
    "ReadinessAssessment",
    "EffortEstimate",
    "CapacityAssessment",
    "AffordabilityAssessment",
    "StrategyAssessment",
    "ActiveSubmission",
    "ConflictAssessment",
    "DecisionRecord",
    "DecisionFixture",
    "DecisionResult",
    "DecisionInput",
    "DecisionOutput",
    "StudioInput",
    "FetchedSourceRef",
    "ExtractedClaimBatch",
    "ExtractedClaimBatchTransport",
    "AgentRunResult",
}


def test_schema_exports_all_public_contracts_deterministically(tmp_path):
    from qualor.schemas.export import CONTRACTS, export_schemas

    assert {model.__name__ for model in CONTRACTS} == EXPECTED
    files = export_schemas(tmp_path)
    assert {path.name.removesuffix(".schema.json") for path in files} == EXPECTED
    before = {path.name: path.read_bytes() for path in files}
    export_schemas(tmp_path)
    assert before == {path.name: path.read_bytes() for path in files}
    for path in files:
        schema = json.loads(path.read_bytes())
        if "$ref" in schema:
            schema = schema["$defs"][schema["$ref"].rsplit("/", 1)[1]]
        assert schema["title"] in EXPECTED
        if "schema_version" in schema["properties"]:
            assert "schema_version" in schema["required"]
        assert schema["additionalProperties"] is False


def test_schema_drift_check_does_not_rewrite(tmp_path):
    from qualor.schemas.export import check_schemas, export_schemas

    assert not check_schemas(tmp_path)
    paths = export_schemas(tmp_path)
    assert check_schemas(tmp_path)
    paths[0].write_text("{}", encoding="utf-8")
    assert not check_schemas(tmp_path)
    assert paths[0].read_text() == "{}"
    export_schemas(tmp_path)
    paths[0].unlink()
    assert not check_schemas(tmp_path)
    export_schemas(tmp_path)
    (tmp_path / "Obsolete.schema.json").write_text("{}")
    assert not check_schemas(tmp_path)


def test_public_schema_properties_never_claim_probability(tmp_path):
    from qualor.schemas.export import export_schemas

    def inspect(value):
        if isinstance(value, dict):
            for name in value.get("properties", {}):
                assert not any(term in name.lower() for term in ("probability", "chance"))
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    for path in export_schemas(tmp_path):
        inspect(json.loads(path.read_bytes()))


def test_committed_schemas_are_current():
    from qualor.schemas.export import check_schemas

    assert check_schemas(Path(__file__).parents[2] / "schemas")


def test_inbox_priority_contract_is_required_and_bounded(tmp_path):
    from qualor.schemas.export import export_schemas

    export_schemas(tmp_path)
    item = json.loads((tmp_path / "InboxItem.schema.json").read_text())
    assert {"priority_rank", "discovered_at"} <= set(item["required"])
    assert item["properties"]["priority_rank"]["type"] == "integer"
    assert item["properties"]["priority_rank"]["minimum"] == 0
    assert item["properties"]["discovered_at"]["format"] == "date-time"


def test_inbox_presentation_state_is_required_typed_enum(tmp_path):
    from qualor.schemas.export import export_schemas

    export_schemas(tmp_path)
    for name in ("InboxItem", "InboxResponse"):
        schema = json.loads((tmp_path / f"{name}.schema.json").read_text())
        item = schema if name == "InboxItem" else schema["$defs"]["InboxItem"]
        assert "presentation_state" in item["required"]
        assert item["properties"]["presentation_state"]["$ref"] == (
            "#/$defs/InboxPresentationState"
        )
        assert schema["$defs"]["InboxPresentationState"]["enum"] == [
            "DISCOVERED", "VERIFYING", "EVALUATED", "NEEDS_REVIEW",
        ]
        assert schema["$defs"]["InboxPresentationState"]["type"] == "string"


def test_workspace_run_presentation_is_required_and_preserves_nullable_run_facts(tmp_path):
    from qualor.schemas.export import export_schemas

    export_schemas(tmp_path)
    schema = json.loads((tmp_path / "OpportunityWorkspaceResponse.schema.json").read_text())
    inbox = json.loads((tmp_path / "InboxItem.schema.json").read_text())
    assert schema["properties"]["presentation_state"] == inbox["properties"]["presentation_state"]
    assert {"presentation_state", "run_state", "mode"} <= set(schema["required"])
    assert schema["properties"]["presentation_state"]["$ref"] == (
        "#/$defs/InboxPresentationState"
    )
    assert schema["$defs"]["InboxPresentationState"]["enum"] == [
        "DISCOVERED", "VERIFYING", "EVALUATED", "NEEDS_REVIEW",
    ]
    for field, enum in [("run_state", "RunState"), ("mode", "RuntimeMode")]:
        assert schema["properties"][field]["anyOf"] == [
            {"$ref": f"#/$defs/{enum}"}, {"type": "null"},
        ]
