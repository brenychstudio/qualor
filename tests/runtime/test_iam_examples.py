import json
import re
from pathlib import Path

EXAMPLES = Path(__file__).parents[2] / "infra" / "iam" / "examples"


def documents():
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(EXAMPLES.glob("*.json"))
    }


def actions(statement):
    value = statement["Action"]
    return {value} if isinstance(value, str) else set(value)


def test_iam_bundle_contains_only_the_four_review_templates():
    assert set(documents()) == {
        "qualor-agentcore-gateway-role-policy.example.json",
        "qualor-agentcore-gateway-role-trust.example.json",
        "qualor-dev-agentcore-gateway.example.json",
        "qualor-dev-bedrock-invoke.example.json",
    }


def test_iam_bundle_has_no_real_account_ids_or_broad_actions():
    raw = "\n".join(path.read_text(encoding="utf-8") for path in EXAMPLES.glob("*.json"))
    assert re.search(r"(?<!\d)\d{12}(?!\d)", raw) is None
    assert "arn:" not in raw
    assert '"bedrock:*"' not in raw
    assert '"bedrock-agentcore:*"' not in raw
    assert '"iam:*"' not in raw


def test_agentcore_wildcard_resources_are_limited_to_create_and_list():
    policy = documents()["qualor-dev-agentcore-gateway.example.json"]
    wildcard = [statement for statement in policy["Statement"] if statement["Resource"] == "*"]
    assert {next(iter(actions(statement))) for statement in wildcard} == {
        "bedrock-agentcore:CreateGateway",
        "bedrock-agentcore:ListGateways",
    }
    create = next(statement for statement in wildcard if "CreateGateway" in str(statement))
    assert create["Condition"]["StringEquals"] == {
        "aws:RequestTag/Project": "QUALOR",
        "aws:RequestTag/Environment": "hackathon",
        "aws:RequestTag/Owner": "BrenychStudio",
    }


def test_passrole_is_single_role_and_single_service():
    policy = documents()["qualor-dev-agentcore-gateway.example.json"]
    statement = next(s for s in policy["Statement"] if s["Action"] == "iam:PassRole")
    assert statement["Resource"] == "<QUALOR_GATEWAY_ROLE_ARN>"
    assert statement["Condition"] == {
        "StringEquals": {"iam:PassedToService": "bedrock-agentcore.amazonaws.com"}
    }


def test_service_role_can_invoke_only_gateway_and_aws_owned_web_search():
    policy = documents()["qualor-agentcore-gateway-role-policy.example.json"]
    assert {action for statement in policy["Statement"] for action in actions(statement)} == {
        "bedrock-agentcore:InvokeGateway",
        "bedrock-agentcore:InvokeWebSearch",
    }
    web = next(s for s in policy["Statement"] if s["Action"].endswith("InvokeWebSearch"))
    assert web["Resource"] == "<AWS_US_EAST_1_WEB_SEARCH_TOOL_ARN>"
