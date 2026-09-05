"""Offline safety tests; fabricated responses are never live capability evidence."""

import importlib.util
import os
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "aws_bridge", Path(__file__).parents[1] / "scripts" / "aws_bridge.py"
)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("aws-cli/2.35.0 Python/3", True),
        ("aws-cli/2.36.1", True),
        ("aws-cli/2.34.99", False),
        ("aws-cli/1.99.0", False),
        ("unknown", False),
    ],
)
def test_supported_cli(version, expected):
    assert bridge.supported_cli(version) is expected


@pytest.mark.parametrize(
    ("resource", "expected"),
    [
        ("root", "ROOT"),
        ("user/test", "IAM_USER"),
        ("assumed-role/test/session", "ASSUMED_ROLE"),
        ("federated-user/test", "FEDERATED"),
        ("unknown", "UNKNOWN"),
    ],
)
def test_identity_normalization(resource, expected):
    identity = {"Arn": ":".join(["arn", "aws", "iam", "", "1" * 12, resource])}
    assert bridge.principal_type(identity) == expected


def test_root_and_unknown_or_static_identity_cannot_launch_authenticated_proxy():
    for kind, provider in [
        ("ROOT", "login"),
        ("UNKNOWN", "login"),
        ("IAM_USER", "shared-credentials-file"),
        ("ASSUMED_ROLE", "env"),
    ]:
        assert not bridge.authentication_allowed(kind, provider)
    assert bridge.authentication_allowed("IAM_USER", "login")
    assert bridge.authentication_allowed("ASSUMED_ROLE", "login")


def test_environment_cannot_override_the_named_profile(tmp_path):
    inherited = {
        "PATH": "path",
        "AWS_ACCESS_KEY_ID": "fixture",
        "AWS_MCP_PROXY_PROFILES": "other",
        "AWS_ENDPOINT_URL": "bad",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI": "bad",
    }
    env = bridge.aws_environment(tmp_path, inherited)
    assert env["PATH"] == "path"
    assert env["AWS_PROFILE"] == "qualor-dev"
    assert env["AWS_REGION"] == "us-east-1"
    assert env["AWS_EC2_METADATA_DISABLED"] == "true"
    assert not set(inherited).intersection(env) - {"PATH"}
    assert env["AWS_CONFIG_FILE"] == str(tmp_path / "config")


def test_discovery_ignores_user_controlled_profile_names():
    assert not bridge.sonnet_discovered([], [{"inferenceProfileName": "sonnet-4-6"}])
    assert bridge.sonnet_discovered([{"modelId": "anthropic.claude-sonnet-4-6"}], [])
    assert bridge.sonnet_discovered([], [{"models": [{"modelArn": "model/sonnet-4-6"}]}])
    assert not bridge.sonnet_discovered([{"modelId": "anthropic.claude-sonnet-4-60"}], [])


def test_invalid_success_json_is_not_capability_evidence():
    assert not bridge.valid_list({}, "modelSummaries")
    assert not bridge.valid_list([], "modelSummaries")
    assert not bridge.valid_list({"modelSummaries": "bad"}, "modelSummaries")
    assert bridge.valid_list({"modelSummaries": []}, "modelSummaries")


def test_control_plane_blocker_fails_preflight():
    report = dict.fromkeys(
        [
            "AWS_CLI",
            "AWS_PROFILE",
            "AWS_AUTH",
            "CODEX_MCP",
            "MCP_PROXY",
            "BEDROCK_CONTROL_PLANE",
            "AGENTCORE_CONTROL_PLANE",
        ],
        "PASS",
    )
    report.update(
        MCP_AUTHENTICATED_MODE="READ_ONLY",
        AWS_PROFILE_REGION="us-east-1",
        SONNET_4_6_DISCOVERY="PASS",
    )
    assert bridge.preflight_passed(report)
    report["BEDROCK_CONTROL_PLANE"] = "BLOCKED"
    assert not bridge.preflight_passed(report)
    report["BEDROCK_CONTROL_PLANE"] = "PASS"
    report["SONNET_4_6_DISCOVERY"] = "BLOCKED"
    assert not bridge.preflight_passed(report)


def test_profile_requires_login_and_rejects_custom_or_static_providers(tmp_path):
    config = tmp_path / "config"
    config.write_text("[profile qualor-dev]\nregion=us-east-1\nlogin_session=fixture\n")
    assert bridge.profile_state(tmp_path) == ("PASS", "us-east-1", "login")
    (tmp_path / "credentials").write_text("[qualor-dev]\naws_access_key_id=fixture\n")
    assert bridge.profile_state(tmp_path)[0] == "BLOCKED_STATIC_PROFILE"
    (tmp_path / "credentials").write_text("")
    config.write_text(config.read_text() + "credential_process=unexpected\n")
    assert bridge.profile_state(tmp_path)[0] == "BLOCKED_NON_LOGIN_CONFIGURATION"


def test_cli_adapter_rejects_any_operation_outside_read_allowlist_before_execution():
    with pytest.raises(ValueError, match="Operation is not allowed"):
        bridge.aws_read("aws", "bedrock-runtime", "invoke-model", {})


def test_auth_failure_prevents_control_plane_calls(monkeypatch, tmp_path):
    calls = []

    def fake_read(executable, service, operation, env):
        calls.append((service, operation))
        return None

    monkeypatch.setattr(bridge, "aws_read", fake_read)
    result = bridge.inspect_identity("aws", {}, "login")
    assert result["AWS_AUTH"] == "BLOCKED_SESSION"
    assert calls == [("sts", "get-caller-identity")]


def test_proxy_contract_is_pinned_read_only_and_single_profile():
    args = bridge.proxy_arguments()
    assert args[:2] == ["uvx", "mcp-proxy-for-aws-cli==1.6.5"]
    assert args.count("--read-only") == 1
    assert args[args.index("--profile") + 1] == "qualor-dev"
    assert args[args.index("--region") + 1] == "us-east-1"
    assert "AWS_REGION=us-east-1" in args
    assert "--skip-auth" not in args


def test_anonymous_proxy_isolated_from_user_credentials(tmp_path):
    env = bridge.anonymous_environment(tmp_path, {"AWS_ACCESS_KEY_ID": "fixture"})
    assert "AWS_ACCESS_KEY_ID" not in env
    config = Path(env["AWS_CONFIG_FILE"]).read_text()
    assert "login_session" not in config
    assert "[profile qualor-dev]" in config
    assert Path(env["AWS_SHARED_CREDENTIALS_FILE"]).read_text() == ""
    assert env["BOTO_CONFIG"] == os.devnull


def test_legacy_credential_provider_cannot_escape_anonymous_isolation(tmp_path, monkeypatch):
    from botocore.credentials import BotoProvider

    legacy = tmp_path / "legacy"
    legacy.write_text("[Credentials]\naws_access_key_id=fixture\naws_secret_access_key=fixture\n")
    env = bridge.anonymous_environment(tmp_path / "isolated", {"BOTO_CONFIG": str(legacy)})
    monkeypatch.setenv("BOTO_CONFIG", env["BOTO_CONFIG"])
    assert BotoProvider().load() is None


def test_proxy_session_snapshot_cannot_follow_later_profile_switch(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    config = source / "config"
    config.write_text("[profile qualor-dev]\nregion=us-east-1\nlogin_session=first\n")
    env = bridge.login_environment(source, tmp_path / "isolated")
    config.write_text("[profile qualor-dev]\nregion=us-east-1\nlogin_session=second\n")
    snapshot = Path(env["AWS_CONFIG_FILE"]).read_text()
    assert "first" in snapshot
    assert "second" not in snapshot
    assert Path(env["AWS_SHARED_CREDENTIALS_FILE"]).read_text() == ""
    assert env["BOTO_CONFIG"] == os.devnull


def test_root_session_never_reaches_proxy(monkeypatch, tmp_path):
    source = tmp_path / ".aws"
    source.mkdir()
    (source / "config").write_text(
        "[profile qualor-dev]\nregion=us-east-1\nlogin_session=root-fixture\n"
    )
    monkeypatch.setattr(bridge.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(bridge, "aws_executable", lambda: "aws")
    monkeypatch.setattr(
        bridge, "inspect_identity", lambda *args: {"AWS_AUTH": "PASS", "PRINCIPAL_TYPE": "ROOT"}
    )

    def check_launch(args, env):
        assert "--skip-auth" in args
        assert "login_session" not in Path(env["AWS_CONFIG_FILE"]).read_text()
        assert Path(env["AWS_SHARED_CREDENTIALS_FILE"]).read_text() == ""
        assert env["BOTO_CONFIG"] == os.devnull
        return 0

    monkeypatch.setattr(bridge.subprocess, "call", check_launch)
    assert bridge.launch_proxy() == 0


def test_mcp_configuration_fails_closed():
    good = bridge.expected_mcp_transport()
    entry = {"name": "aws-qualor", "enabled": True, "transport": good}
    assert bridge.valid_mcp_entry(entry)
    for key, value in [("command", "different"), ("args", []), ("env", {"AWS_PROFILE": "other"})]:
        assert not bridge.valid_mcp_entry({**entry, "transport": {**good, key: value}})
    assert not bridge.valid_mcp_entry({**entry, "enabled": False})
