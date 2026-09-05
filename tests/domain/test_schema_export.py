import json
from pathlib import Path

EXPECTED = {
    "FounderProfile",
    "ProjectProfile",
    "OpportunityRecord",
    "EvidenceRecord",
    "RuleCandidate",
    "RuleEvaluation",
    "EligibilityGate",
    "Reward",
}


def test_schema_exports_all_public_contracts_deterministically(tmp_path):
    from qualor.schemas.export import export_schemas

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


def test_committed_schemas_are_current():
    from qualor.schemas.export import check_schemas

    assert check_schemas(Path(__file__).parents[2] / "schemas")
