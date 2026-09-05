# Read-only capability discovery. No inference, search execution or resource creation.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$preflightExit = 0
Push-Location $repositoryRoot
try {
    git check-ignore --quiet .qualor/local/preflight-details.json
    if ($LASTEXITCODE -ne 0) { throw 'Local reports must be ignored before preflight' }
    New-Item -ItemType Directory -Path '.qualor/local' -Force | Out-Null
    foreach ($tool in @('git', 'gh', 'python', 'uv', 'node', 'npm', 'aws')) {
        $key = $tool.ToUpperInvariant()
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            Write-Output "${key}_TOOL=BLOCKED_NOT_INSTALLED"
            $preflightExit = 1
            continue
        }
        $toolOutput = @(& $tool --version 2>&1)
        $toolExit = $LASTEXITCODE
        $toolOutput | Set-Content -LiteralPath ".qualor/local/tool-$tool.txt"
        $versionMatch = [regex]::Match(($toolOutput -join ' '), '\d+\.\d+[^\s,)]*')
        if ($toolExit -eq 0 -and $versionMatch.Success) {
            Write-Output "${key}_VERSION=$($versionMatch.Value)"
        } else {
            Write-Output "${key}_TOOL=BLOCKED_VERSION_CHECK"
            $preflightExit = 1
        }
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'UV_NOT_INSTALLED'
    }
    # Raw SDK output never reaches the terminal. Python writes only normalized statuses
    # to stdout; unexpected stderr and response metadata remain in ignored local files.
    $capabilityOutput = @(@'
import json
import os
import pathlib
import re
import sys

os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
statuses = {
    "PYTHON_3_12": "PASS" if sys.version_info[:2] == (3, 12) else "BLOCKED",
    "AWS_STS": "BLOCKED",
    "BEDROCK_CONTROL_PLANE": "BLOCKED",
    "SONNET_4_6_DISCOVERY": "BLOCKED",
    "SONNET_4_6_INFERENCE": "NOT_TESTED",
    "AGENTCORE_CONTROL_PLANE": "BLOCKED",
    "AGENTCORE_WEB_SEARCH": "UNVERIFIED",
    "AWS_PAID_SMOKE": "NOT_RUN_BY_POLICY",
    "AWS_RESOURCES_CREATED": "0",
}
details = {"region": "us-east-1", "operations": {}, "errors": {}}

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import UnknownServiceError

    session = boto3.Session(region_name="us-east-1")
    config = Config(connect_timeout=5, read_timeout=10, retries={"total_max_attempts": 1})

    def read(service, operation, **kwargs):
        # Explicit allowlist is the complete set of authorized service actions.
        allowed = {
            ("sts", "get_caller_identity"): "GetCallerIdentity",
            ("bedrock", "list_foundation_models"): "ListFoundationModels",
            ("bedrock", "list_inference_profiles"): "ListInferenceProfiles",
            ("bedrock-agentcore-control", "list_agent_runtimes"): "ListAgentRuntimes",
        }
        api_name = allowed[(service, operation)]
        model = session._session.get_service_model(service)
        if api_name not in model.operation_names:
            raise NotImplementedError(api_name)
        client = session.client(service, config=config)
        result = getattr(client, operation)(**kwargs)
        if result.get("ResponseMetadata", {}).get("HTTPStatusCode") != 200:
            raise ValueError("Unexpected control-plane response")
        details["operations"].setdefault(api_name, []).append(result)
        return result

    def failed(name, error):
        # Error class is enough to identify local access blockers without credentials.
        details["errors"][name] = type(error).__name__

    try:
        identity = read("sts", "get_caller_identity")
        if not all(identity.get(key) for key in ("Account", "Arn", "UserId")):
            raise ValueError("Incomplete identity response")
        statuses["AWS_STS"] = "PASS"
    except Exception as error:
        failed("AWS_STS", error)

    models, profiles = [], []
    models_complete = profiles_complete = False
    try:
        models = read("bedrock", "list_foundation_models")["modelSummaries"]
        if not isinstance(models, list):
            raise ValueError("Invalid model list")
        models_complete = True
        statuses["BEDROCK_CONTROL_PLANE"] = "PASS"
    except Exception as error:
        failed("BEDROCK_CONTROL_PLANE", error)

    try:
        token = None
        for _ in range(100):
            page = read("bedrock", "list_inference_profiles", **({"nextToken": token} if token else {}))
            summaries = page["inferenceProfileSummaries"]
            if not isinstance(summaries, list):
                raise ValueError("Invalid profile list")
            profiles.extend(summaries)
            token = page.get("nextToken")
            if not token:
                profiles_complete = True
                break
        if not profiles_complete:
            raise ValueError("Profile pagination limit reached")
    except Exception as error:
        failed("INFERENCE_PROFILE_DISCOVERY", error)

    discovered = any(
        re.search(r"(?:^|/)anthropic\.claude-sonnet-4-6(?:$|[-:])", identifier)
        for identifier in (
            [model.get("modelId", "") for model in models]
            + [model.get("modelArn", "") for profile in profiles for model in profile.get("models", [])]
        )
    )
    if discovered:
        statuses["SONNET_4_6_DISCOVERY"] = "PASS"
    elif models_complete and profiles_complete:
        statuses["SONNET_4_6_DISCOVERY"] = "NOT_FOUND"

    try:
        runtimes = read("bedrock-agentcore-control", "list_agent_runtimes", maxResults=1)
        if not isinstance(runtimes["agentRuntimes"], list):
            raise ValueError("Invalid runtime list")
        statuses["AGENTCORE_CONTROL_PLANE"] = "PASS"
    except (UnknownServiceError, NotImplementedError) as error:
        statuses["AGENTCORE_CONTROL_PLANE"] = "UNAVAILABLE"
        failed("AGENTCORE_CONTROL_PLANE", error)
    except Exception as error:
        failed("AGENTCORE_CONTROL_PLANE", error)
except Exception as error:
    details["errors"]["PREFLIGHT"] = type(error).__name__
finally:
    details["statuses"] = statuses
    pathlib.Path(".qualor/local/preflight-details.json").write_text(
        json.dumps(details, indent=2, default=str), encoding="utf-8"
    )
    for key, value in statuses.items():
        print(f"{key}={value}")
sys.exit(1 if any(value in {"BLOCKED", "UNAVAILABLE"} for value in statuses.values()) else 0)
'@ | uv run --locked --no-sync python - 2> .qualor/local/preflight-stderr.txt)
    $sdkExit = $LASTEXITCODE
    $safeLines = @($capabilityOutput | Where-Object {
        $_ -match '^[A-Z0-9_]+=(PASS|BLOCKED|NOT_FOUND|NOT_TESTED|UNAVAILABLE|UNVERIFIED|NOT_RUN_BY_POLICY|0)$'
    })
    $safeLines | Set-Content -LiteralPath '.qualor/local/preflight-status.txt'
    Write-Output $safeLines
    if ($sdkExit -ne 0 -or $safeLines.Count -ne 9) { $preflightExit = 1 }
    if ($safeLines.Count -ne 9) { throw 'SDK_PREFLIGHT_OUTPUT_INCOMPLETE' }
} catch {
    # Do not echo exceptions that could include credential or account metadata.
    Write-Output 'PREFLIGHT=BLOCKED_LOCAL_CHECK'
    Write-Output 'AWS_STS=BLOCKED'
    Write-Output 'BEDROCK_CONTROL_PLANE=BLOCKED'
    Write-Output 'SONNET_4_6_DISCOVERY=BLOCKED'
    Write-Output 'SONNET_4_6_INFERENCE=NOT_TESTED'
    Write-Output 'AGENTCORE_CONTROL_PLANE=BLOCKED'
    Write-Output 'AGENTCORE_WEB_SEARCH=UNVERIFIED'
    Write-Output 'AWS_PAID_SMOKE=NOT_RUN_BY_POLICY'
    Write-Output 'AWS_RESOURCES_CREATED=0'
    $preflightExit = 1
} finally {
    Pop-Location
}
exit $preflightExit
