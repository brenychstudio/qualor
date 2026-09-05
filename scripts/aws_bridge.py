"""QUALOR operator utilities. No product imports and no write/inference operations."""

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROFILE = "qualor-dev"
REGION = "us-east-1"
PROXY_VERSION = "1.6.5"
ENDPOINT = "https://aws-mcp.us-east-1.api.aws/mcp"
ROOT = Path(__file__).resolve().parents[1]
READ_OPERATIONS = {
    ("sts", "get-caller-identity"),
    ("bedrock", "list-foundation-models"),
    ("bedrock", "list-inference-profiles"),
    ("bedrock-agentcore-control", "list-agent-runtimes"),
    ("bedrock-agentcore-control", "list-gateways"),
}
READ_ACTIONS = {
    ("sts", "get-caller-identity"): "sts:GetCallerIdentity",
    ("bedrock", "list-foundation-models"): "bedrock:ListFoundationModels",
    ("bedrock", "list-inference-profiles"): "bedrock:ListInferenceProfiles",
    ("bedrock-agentcore-control", "list-agent-runtimes"): "bedrock-agentcore:ListAgentRuntimes",
    ("bedrock-agentcore-control", "list-gateways"): "bedrock-agentcore:ListGateways",
}


def run(args, env=None, timeout=90):
    """Capture raw identity/error data privately; callers only emit normalized facts."""
    try:
        return subprocess.run(
            args,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def supported_cli(version):
    match = re.search(r"aws-cli/(\d+)\.(\d+)\.(\d+)", version)
    return bool(match and int(match[1]) == 2 and tuple(map(int, match.groups())) >= (2, 35, 0))


def aws_executable():
    found = shutil.which("aws")
    if found:
        return found
    for base, suffix in [
        (os.environ.get("LOCALAPPDATA", ""), "Programs/Amazon/AWSCLIV2/aws.exe"),
        (os.environ.get("ProgramFiles", ""), "Amazon/AWSCLIV2/aws.exe"),
    ]:
        candidate = Path(base) / suffix
        if candidate.is_file():
            return str(candidate)
    return None


def aws_environment(directory, inherited=None):
    """Do not inherit default identities, endpoint overrides or credential providers."""
    env = {
        key: value
        for key, value in (os.environ if inherited is None else inherited).items()
        if not key.upper().startswith("AWS_")
    }
    env.update(
        {
            "AWS_PROFILE": PROFILE,
            "AWS_REGION": REGION,
            "AWS_DEFAULT_REGION": REGION,
            "AWS_CONFIG_FILE": str(directory / "config"),
            "AWS_SHARED_CREDENTIALS_FILE": str(directory / "credentials"),
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_PAGER": "",
            "AWS_CLI_AUTO_PROMPT": "off",
            # Disable the legacy ~/.boto provider as well as AWS_* providers.
            "BOTO_CONFIG": os.devnull,
        }
    )
    return env


def anonymous_environment(directory, inherited=None):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config").write_text(f"[profile {PROFILE}]\nregion = {REGION}\n")
    (directory / "credentials").write_text("")
    return aws_environment(directory, inherited)


def principal_type(identity):
    resource = str(identity.get("Arn", "")).split(":", 5)[-1]
    if resource == "root":
        return "ROOT"
    for prefix, kind in [
        ("user/", "IAM_USER"),
        ("assumed-role/", "ASSUMED_ROLE"),
        ("federated-user/", "FEDERATED"),
    ]:
        if resource.startswith(prefix):
            return kind
    return "UNKNOWN"


def authentication_allowed(kind, provider):
    return kind in {"IAM_USER", "ASSUMED_ROLE", "FEDERATED"} and provider == "login"


def profile_state(directory):
    config = configparser.RawConfigParser()
    try:
        config.read(directory / "config", encoding="utf-8")
        section = f"profile {PROFILE}"
        if not config.has_section(section):
            return "BLOCKED_MISSING", "UNKNOWN", "UNKNOWN"
        values = dict(config[section])
        region = values.get("region", "UNKNOWN")
        # Custom providers/endpoints could change the identity or where signatures go.
        permitted = {"region", "output", "login_session"}
        if set(values) - permitted or not values.get("login_session"):
            return "BLOCKED_NON_LOGIN_CONFIGURATION", region, "UNKNOWN"
        credentials = configparser.RawConfigParser()
        credentials.read(directory / "credentials", encoding="utf-8")
        if credentials.has_section(PROFILE) and dict(credentials[PROFILE]):
            return "BLOCKED_STATIC_PROFILE", region, "UNKNOWN"
        return "PASS", region, "login"
    except (OSError, configparser.Error, UnicodeError):
        return "BLOCKED_CONFIG", "UNKNOWN", "UNKNOWN"


def aws_read(executable, service, operation, env, error=None):
    if (service, operation) not in READ_OPERATIONS:
        raise ValueError("Operation is not allowed")
    result = run(
        [
            executable,
            service,
            operation,
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--output",
            "json",
            "--no-cli-pager",
            "--cli-connect-timeout",
            "10",
            "--cli-read-timeout",
            "30",
        ],
        env,
    )
    if result is None or result.returncode:
        if error is not None:
            action = READ_ACTIONS[(service, operation)]
            denied = bool(
                result
                and re.search(
                    r"An error occurred \("
                    r"(?:AccessDeniedException|AccessDenied|UnauthorizedOperation)\)",
                    result.stderr,
                )
                and re.search(rf"(?<![\w:-]){re.escape(action)}(?![\w:-])", result.stderr)
            )
            error.update(
                status="BLOCKED_PERMISSION" if denied else "BLOCKED",
                action=action if denied else "NONE",
            )
        return None
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        return None


def inspect_identity(executable, env, provider):
    identity = aws_read(executable, "sts", "get-caller-identity", env)
    kind = principal_type(identity) if isinstance(identity, dict) else "UNKNOWN"
    auth = "PASS" if isinstance(identity, dict) and identity.get("Arn") else "BLOCKED_SESSION"
    return {
        "AWS_STS": auth,
        "AWS_AUTH": auth,
        "PRINCIPAL_TYPE": kind,
        "TEMPORARY_CREDENTIALS": "YES" if auth == "PASS" and provider == "login" else "UNKNOWN",
        "ROOT_AGENT_ACCESS": "NO",
        "MCP_AUTHENTICATED_MODE": "READ_ONLY"
        if authentication_allowed(kind, provider)
        else ("BLOCKED_ROOT_IDENTITY" if kind == "ROOT" else "BLOCKED_IDENTITY"),
    }


def sonnet_discovered(models, profiles):
    identifiers = [item.get("modelId", "") for item in models]
    identifiers += [
        model.get("modelArn", "") for profile in profiles for model in profile.get("models", [])
    ]
    return any(
        re.search(r"(?<![a-z0-9])sonnet-4-6(?![a-z0-9])", value.lower())
        for value in identifiers
        if isinstance(value, str)
    )


def valid_list(response, key):
    return (
        isinstance(response, dict)
        and isinstance(response.get(key), list)
        and all(isinstance(item, dict) for item in response[key])
    )


def login_environment(source, destination):
    """Snapshot the login session so subsequent profile switches cannot change identity."""
    state, region, _ = profile_state(source)
    if state != "PASS" or region != REGION:
        return None
    config = configparser.RawConfigParser()
    config.read(source / "config", encoding="utf-8")
    session = config[f"profile {PROFILE}"]["login_session"]
    env = anonymous_environment(destination)
    snapshot = configparser.RawConfigParser()
    snapshot[f"profile {PROFILE}"] = {"region": REGION, "login_session": session}
    with (destination / "config").open("w", encoding="utf-8") as handle:
        snapshot.write(handle)
    return env


def proxy_state():
    result = run(["uvx", "--offline", f"mcp-proxy-for-aws-cli=={PROXY_VERSION}", "--help"])
    return (
        "PASS"
        if result
        and result.returncode == 0
        and (
            f"MCP Proxy for AWS v{PROXY_VERSION}" in result.stdout
            and "--read-only" in result.stdout
        )
        else "BLOCKED_PROXY"
    )


def proxy_arguments():
    return [
        "uvx",
        "--from",
        f"mcp-proxy-for-aws-cli=={PROXY_VERSION}",
        "python",
        str(ROOT / "scripts" / "aws_mcp_proxy.py"),
        ENDPOINT,
        "--profile",
        PROFILE,
        "--region",
        REGION,
        "--metadata",
        f"AWS_REGION={REGION}",
        "--read-only",
        "--disable-telemetry",
        "--connect-timeout",
        "30",
        "--timeout",
        "60",
        "--tool-timeout",
        "60",
    ]


def expected_mcp_transport():
    return {
        "type": "stdio",
        "command": "powershell.exe",
        "args": ["-NoProfile", "-NonInteractive", "-File", str(ROOT / "scripts" / "aws-mcp.ps1")],
        "env": {
            "AWS_PROFILE": PROFILE,
            "AWS_REGION": REGION,
            "QUALOR_MCP_READ_ONLY": "true",
            "QUALOR_MCP_PROXY_VERSION": PROXY_VERSION,
        },
    }


def valid_mcp_entry(entry):
    expected = expected_mcp_transport()
    transport = entry.get("transport", {})
    return (
        entry.get("name") == "aws-qualor"
        and entry.get("enabled") is True
        and all(transport.get(key) == value for key, value in expected.items())
    )


def mcp_state():
    codex = shutil.which("codex.cmd") or shutil.which("codex")
    result = run([codex, "mcp", "list", "--json"]) if codex else None
    try:
        entries = json.loads(result.stdout) if result and result.returncode == 0 else []
        entries = [entry for entry in entries if entry.get("name") == "aws-qualor"]
        return "PASS" if len(entries) == 1 and valid_mcp_entry(entries[0]) else "BLOCKED_CONFIG"
    except (ValueError, TypeError):
        return "BLOCKED_CONFIG"


def preflight():
    statuses = {
        "AWS_CLI": "BLOCKED_NOT_INSTALLED",
        "AWS_CLI_VERSION": "UNKNOWN",
        "AWS_PROFILE": "BLOCKED_MISSING",
        "AWS_PROFILE_NAME": PROFILE,
        "AWS_REGION": REGION,
        "AWS_PROFILE_REGION": "UNKNOWN",
        "AWS_AUTH": "BLOCKED_SESSION",
        "AWS_STS": "BLOCKED_SESSION",
        "PRINCIPAL_TYPE": "UNKNOWN",
        "TEMPORARY_CREDENTIALS": "UNKNOWN",
        "ROOT_AGENT_ACCESS": "NO",
        "MCP_AUTHENTICATED_MODE": "BLOCKED_IDENTITY",
        "BEDROCK_CONTROL_PLANE": "BLOCKED_AUTH",
        "SONNET_4_6_DISCOVERY": "BLOCKED_AUTH",
        "SONNET_4_6_INFERENCE": "NOT_TESTED",
        "AGENTCORE_CONTROL_PLANE": "BLOCKED_AUTH",
        "AGENTCORE_RUNTIME_DISCOVERY": "BLOCKED_AUTH",
        "AGENTCORE_GATEWAY_DISCOVERY": "BLOCKED_AUTH",
        "AGENTCORE_WEB_SEARCH_DISCOVERY": "UNVERIFIED",
        "AGENTCORE_DENIED_ACTIONS": "NONE",
        "CODEX_MCP": mcp_state(),
        "AWS_MCP_SERVER": "UNVERIFIED",
        "AWS_MCP_MODE": "READ_ONLY",
        "MCP_PROXY_VERSION": PROXY_VERSION,
        "MCP_PROXY": proxy_state(),
        "MCP_AUTHENTICATED_WRITE_MODE": "DEFERRED",
        "AWS_RESOURCES_CREATED": "0",
        "AWS_PAID_CALLS": "0",
    }
    executable = aws_executable()
    version = run([executable, "--version"]) if executable else None
    if not version or version.returncode or not supported_cli(version.stdout):
        if executable:
            statuses["AWS_CLI"] = "BLOCKED_VERSION"
        return statuses
    statuses["AWS_CLI"] = "PASS"
    statuses["AWS_CLI_VERSION"] = re.search(r"aws-cli/([\d.]+)", version.stdout)[1]
    directory = Path.home() / ".aws"
    state, region, provider = profile_state(directory)
    statuses.update(AWS_PROFILE=state, AWS_PROFILE_REGION=region)
    if state != "PASS" or region != REGION:
        return statuses
    env = aws_environment(directory)
    statuses.update(inspect_identity(executable, env, provider))
    if statuses["PRINCIPAL_TYPE"] == "ROOT":
        for key in [
            "BEDROCK_CONTROL_PLANE",
            "SONNET_4_6_DISCOVERY",
            "AGENTCORE_CONTROL_PLANE",
            "AGENTCORE_RUNTIME_DISCOVERY",
            "AGENTCORE_GATEWAY_DISCOVERY",
        ]:
            statuses[key] = "BLOCKED_ROOT_IDENTITY"
    if statuses["AWS_AUTH"] != "PASS" or not authentication_allowed(
        statuses["PRINCIPAL_TYPE"], provider
    ):
        return statuses
    model_error, profile_error = {}, {}
    models = aws_read(executable, "bedrock", "list-foundation-models", env, model_error)
    profiles = aws_read(executable, "bedrock", "list-inference-profiles", env, profile_error)
    models = models if valid_list(models, "modelSummaries") else None
    profiles = profiles if valid_list(profiles, "inferenceProfileSummaries") else None
    statuses["BEDROCK_CONTROL_PLANE"] = (
        "PASS" if models is not None else model_error.get("status", "BLOCKED")
    )
    found = sonnet_discovered(
        (models or {}).get("modelSummaries", []),
        (profiles or {}).get("inferenceProfileSummaries", []),
    )
    statuses["SONNET_4_6_DISCOVERY"] = (
        "PASS"
        if found
        else "NOT_FOUND"
        if models is not None and profiles is not None
        else "BLOCKED_PERMISSION"
        if "BLOCKED_PERMISSION" in [model_error.get("status"), profile_error.get("status")]
        else "BLOCKED"
    )
    denied_actions = []
    for operation, key, response_key in [
        ("list-agent-runtimes", "AGENTCORE_RUNTIME_DISCOVERY", "agentRuntimes"),
        ("list-gateways", "AGENTCORE_GATEWAY_DISCOVERY", "items"),
    ]:
        # Input skeleton generation is local and checks the installed service API model.
        support = run(
            [
                executable,
                "bedrock-agentcore-control",
                operation,
                "--generate-cli-skeleton",
                "input",
            ],
            env,
        )
        if not support or support.returncode:
            statuses[key] = "UNAVAILABLE"
        else:
            error = {}
            result = aws_read(executable, "bedrock-agentcore-control", operation, env, error)
            statuses[key] = (
                "PASS" if valid_list(result, response_key) else error.get("status", "BLOCKED")
            )
            if error.get("status") == "BLOCKED_PERMISSION":
                denied_actions.append(error["action"])
    statuses["AGENTCORE_DENIED_ACTIONS"] = ",".join(sorted(denied_actions)) or "NONE"
    results = [statuses["AGENTCORE_RUNTIME_DISCOVERY"], statuses["AGENTCORE_GATEWAY_DISCOVERY"]]
    statuses["AGENTCORE_CONTROL_PLANE"] = (
        "PASS"
        if all(value == "PASS" for value in results)
        else "UNAVAILABLE"
        if all(value == "UNAVAILABLE" for value in results)
        else "BLOCKED_PERMISSION"
        if all(value in {"PASS", "BLOCKED_PERMISSION"} for value in results)
        else "BLOCKED"
    )
    return statuses


def launch_proxy():
    """Recheck identity at every start; anonymous fallback has empty credential files."""
    executable = aws_executable()
    directory = Path.home() / ".aws"
    args = proxy_arguments()
    with tempfile.TemporaryDirectory(prefix="qualor-mcp-session-") as temporary:
        isolated = Path(temporary)
        env = login_environment(directory, isolated)
        if executable and env:
            identity = inspect_identity(executable, env, "login")
            if identity["AWS_AUTH"] == "PASS" and authentication_allowed(
                identity["PRINCIPAL_TYPE"], "login"
            ):
                return subprocess.call(args, env=env)
        print("QUALOR_MCP=ANONYMOUS_KNOWLEDGE_ONLY; AUTHENTICATED_MODE=BLOCKED", file=sys.stderr)
        env = anonymous_environment(isolated)
        return subprocess.call([*args, "--skip-auth"], env=env)


def preflight_passed(report):
    required = [
        "AWS_CLI",
        "AWS_PROFILE",
        "AWS_AUTH",
        "AWS_STS",
        "CODEX_MCP",
        "MCP_PROXY",
        "BEDROCK_CONTROL_PLANE",
    ]
    # QUALOR-00B1 explicitly permits these documented read-only IAM gaps.
    agentcore = report["AGENTCORE_CONTROL_PLANE"] == "PASS"
    if report["AGENTCORE_CONTROL_PLANE"] == "BLOCKED_PERMISSION":
        expected_denials = {
            READ_ACTIONS[("bedrock-agentcore-control", operation)]
            for operation, key in [
                ("list-agent-runtimes", "AGENTCORE_RUNTIME_DISCOVERY"),
                ("list-gateways", "AGENTCORE_GATEWAY_DISCOVERY"),
            ]
            if report.get(key) == "BLOCKED_PERMISSION"
        }
        agentcore = bool(expected_denials) and (
            set(report.get("AGENTCORE_DENIED_ACTIONS", "").split(",")) == expected_denials
            and all(
                report.get(key) in {"PASS", "BLOCKED_PERMISSION"}
                for key in ["AGENTCORE_RUNTIME_DISCOVERY", "AGENTCORE_GATEWAY_DISCOVERY"]
            )
        )
    return (
        all(report[key] == "PASS" for key in required)
        and agentcore
        and authentication_allowed(report.get("PRINCIPAL_TYPE"), "login")
        and report.get("TEMPORARY_CREDENTIALS") == "YES"
        and report["MCP_AUTHENTICATED_MODE"] == "READ_ONLY"
        and report["AWS_PROFILE_REGION"] == REGION
        and report["SONNET_4_6_DISCOVERY"] in {"PASS", "NOT_FOUND"}
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["proxy"]:
        raise SystemExit(launch_proxy())
    if sys.argv[1:]:
        raise SystemExit("Supported commands: no arguments (preflight), proxy")
    report = preflight()
    print("QUALOR AWS PREFLIGHT\n")
    for key, value in report.items():
        print(f"{key}={value}")
    raise SystemExit(0 if preflight_passed(report) else 1)
