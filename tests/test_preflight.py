"""Offline metadata regressions; these fixtures prove no AWS capability."""

import ast
import re
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("models", "profiles", "expected"),
    [
        ([], [{"inferenceProfileName": "Sonnet 4.6 evaluation", "models": []}], False),
        (
            [],
            [
                {
                    "inferenceProfileName": "Sonnet 4.6 evaluation",
                    "models": [
                        {
                            "modelArn": ":".join(
                                (
                                    "arn",
                                    "aws",
                                    "bedrock",
                                    "us-east-1",
                                    "",
                                    "foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
                                )
                            )
                        }
                    ],
                }
            ],
            False,
        ),
        ([{"modelId": "anthropic.claude-sonnet-4-6"}], [], True),
        (
            [],
            [
                {
                    "models": [
                        {
                            "modelArn": ":".join(
                                (
                                    "arn",
                                    "aws",
                                    "bedrock",
                                    "us-east-1",
                                    "",
                                    "foundation-model/anthropic.claude-sonnet-4-6",
                                )
                            )
                        }
                    ]
                }
            ],
            True,
        ),
        ([{"modelId": "anthropic.claude-sonnet-4-60"}], [], False),
    ],
)
def test_sonnet_discovery_uses_model_identifiers_not_profile_labels(models, profiles, expected):
    # Execute only the real discovery expression from the embedded SDK script.
    # No script startup, boto3 session, network, or local reports are involved.
    script = Path(__file__).resolve().parents[1] / "scripts" / "preflight.ps1"
    payload = script.read_text(encoding="utf-8").split("@'", 1)[1].split("'@", 1)[0]
    expression = next(
        node.value
        for node in ast.walk(ast.parse(payload))
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "discovered" for target in node.targets
        )
    )
    result = eval(
        compile(ast.Expression(expression), str(script), "eval"),
        {"models": models, "profiles": profiles, "re": re},
    )
    assert result is expected
