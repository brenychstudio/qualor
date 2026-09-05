# ADR 0002: AWS development bridge

Date: 2026-09-05. Task: QUALOR-00B.

## Decision

Use AWS CLI v2 browser login with the dedicated `qualor-dev` profile and region
`us-east-1`. Short-lived credentials remain in AWS's user-level login cache.
The intended authenticated path is:

```text
AWS CLI v2 -> aws login -> qualor-dev -> short-lived credentials
-> SigV4 MCP Proxy -> managed AWS MCP Server -> Codex
```

This avoids long-lived keys, provides an independent terminal verification path,
and supports terminal/IDE agents without changing the canonical single-account
strategy. MCP starts read-only; future capability promotion requires a separate
task and least-privilege IAM design. No legacy AWS API/Knowledge MCP servers are
installed or duplicated.

The managed endpoint was resolved from [official AWS Agent Toolkit documentation](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/getting-started-aws-mcp-server.html):
`https://aws-mcp.us-east-1.api.aws/mcp`.

Pin the official `mcp-proxy-for-aws-cli==1.6.5` distribution. Live
[AWS release metadata](https://github.com/aws/mcp-proxy-for-aws/releases/tag/v1.6.5)
and [PyPI metadata](https://pypi.org/project/mcp-proxy-for-aws-cli/1.6.5/) supersede
the task's 1.6.4 baseline and older documentation examples. The 1.6.4-to-1.6.5
release diff preserves read-only filtering and SigV4 behavior; it adds the CLI
distribution with exactly pinned transitive dependencies and region fallback
handling. QUALOR supplies the region explicitly. The wrapper resolves the base
`mcp-proxy-for-aws==1.6.5` package.

## Enforced boundaries

`scripts/aws-mcp.ps1` launches `scripts/aws_bridge.py proxy`. The proxy arguments
always contain `--read-only`, one profile, the signing region and regional request
metadata. The installed proxy filters tool discovery and calls using
`readOnlyHint=true`; prompt instructions are supplementary.

The launcher rejects static/custom credential providers. It snapshots only the
named login session and region into temporary local configuration, with empty
shared credentials and disabled legacy Boto, environment, container and instance
metadata providers. STS checks that snapshot before the proxy receives it. Later
edits to the user's AWS profile cannot switch the running proxy's identity.
Login-session refresh uses AWS's original user-level cache; credentials are never
exported into the repository.

Root, unknown or unavailable identity blocks authenticated proxy access. The
fallback uses isolated empty credential configuration and `--skip-auth` for
public knowledge only. This isolation matters: `--skip-auth` alone still signs
when a credential provider finds credentials. Root authentication is never
treated as permission for routine agent automation.

QUALOR-00B1 adds a process-local direct IPv4 HTTPS transport in
`scripts/aws_mcp_proxy.py`. The guarded launcher uses
`uvx --from mcp-proxy-for-aws-cli==1.6.5 python scripts/aws_mcp_proxy.py` with the
same endpoint, profile, region and read-only arguments. The adapter supplies
HTTPX's [documented transport option](https://www.python-httpx.org/advanced/transports/)
`local_address="0.0.0.0"` through the pinned proxy's existing SigV4 client factory.
It keeps certificate/hostname verification enabled, the upstream signing hooks,
connection limits and read-only middleware. No installed package is edited.

Evidence: proxy stderr traced empty JSON-RPC `-32603` failures to
`httpx.ConnectError` during TLS. Per-address probes found resets on some IPv6
addresses while every probed IPv4 address negotiated TLS 1.3. A direct IPv4 HTTPS
request reached the same endpoint. This one transport change then made the exact
launcher and both fresh Codex knowledge smokes pass. Codex configuration and
timeouts were not changed, and no Agent Toolkit plugin was installed.

The adapter depends on the inspected 1.6.5 factory symbol and fails closed on
another proxy version. An upgrade must recheck this integration. Explicit HTTPX
transport uses direct connections and does not inherit HTTP proxy environment
settings; none were configured in the diagnosed environment. This is not a
system-wide IPv6, DNS, firewall or TLS-policy change.

`scripts/aws-preflight.ps1` emits sanitized statuses and returns nonzero when
required gates are blocked. QUALOR-00B1 explicitly permits a recorded AgentCore
read-permission gap: exit 0 requires non-root temporary authentication, STS,
Bedrock and local MCP configuration gates, with exact denied AgentCore actions.
The individual capabilities remain `BLOCKED_PERMISSION`. Unknown/network failures
still return nonzero. Live MCP knowledge success is verified separately in fresh
Codex processes; the CLI preflight does not claim it from configuration alone.
Its CLI allowlist contains only STS identity, Bedrock
model/profile listing and AgentCore runtime/gateway listing. Local CLI skeleton
generation checks supported AgentCore operations without contacting AWS.
Discovery does not prove deployment, invocation permission or account entitlement.

## Operator workflow

Install current AWS CLI v2 using the [official Windows user installer](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
Then use [AWS browser login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html):

```powershell
aws login --profile qualor-dev --region us-east-1
aws configure set region us-east-1 --profile qualor-dev
.\scripts\aws-preflight.ps1
```

The configure command sets only nonsecret region metadata. Do not enter keys.
Renew an expired session with the same login command and restart the MCP process.
If root is selected, use a separately provisioned non-root identity; this task
does not create or attach IAM policies. Do not weaken the launcher.

The local Codex entry `aws-qualor` uses `powershell.exe -NoProfile -NonInteractive
-File C:\PROJECTS\qualor\scripts\aws-mcp.ps1`, with nonsecret profile, region,
read-only and proxy-version environment markers. The launcher enforces these
values. Existing unrelated MCP entries are preserved. A new Codex process is
required to test a changed entry; configuration alone is not connection evidence.

## Current regional evidence and canonical compatibility

AWS lists AgentCore Runtime, Gateway and Web Search in N. Virginia in the
[AgentCore regional table](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html).
The [AgentCore Web Search connector](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html)
also lists Ireland and Tokyo. QUALOR's `us-east-1` direction remains compatible;
no connector was created and no search was executed.

The [Claude Sonnet 4.6 model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-6.html)
lists geo/global inference from `us-east-1`, rather than in-Region inference.
Later tasks must select an appropriate supported inference profile and explicitly
authorize cost. Model listing is not proof of invocation access. The canonical
document remains byte-for-byte unchanged; these are implementation clarifications,
not a silent model or architecture replacement.

## Deferred

Write-enabled MCP, a dedicated QUALOR IAM automation role, AgentCore Runtime and
Gateway deployment, Web Search execution, Bedrock invocation, any resource
creation, and CloudFormation/CDK deployment. Authenticated MCP API execution is
not a QUALOR-00B smoke requirement. Live task evidence and blockers are recorded
in [QUALOR-00B status](../status/QUALOR-00B.md).
