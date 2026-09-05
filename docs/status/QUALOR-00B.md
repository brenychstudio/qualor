# QUALOR-00B status

Date: 2026-09-05. Status: PARTIAL. Infrastructure enablement only.

## Repository checkpoint

- Base: `main`, `021f9b85b9cee26020b6e2217218f4655d2a0f75`.
- Task branch: `qualor-00b-aws-development-bridge`.
- Repository: `brenychstudio/qualor`, PRIVATE.
- Canonical SHA-256: `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`.
- Canonical size: 62438 bytes; unchanged.
- Baseline verification passed on the exact clean main tree before branch creation.
- Delivery uses an unmerged PR. Exact delivery HEAD and final clean-tree verification
  are reported in the PR and Result Packet to avoid a self-referential commit hash.

## Installed bridge and authentication

```text
AWS_CLI_VERSION=2.36.40
AWS_LOGIN_COMMAND=PASS
AWS_AGENT_TOOLKIT_COMMAND=PASS
CODEX_INSTALLED_VERSION=0.151.0
CODEX_FRESH_SMOKE_VERSION=0.153.4
UV_VERSION=0.12.5
UVX_VERSION=0.12.5
MCP_PROXY_VERSION=1.6.5
AWS_PROFILE=qualor-dev
AWS_REGION=us-east-1
AWS_AUTH=PASS
AWS_STS=PASS
PRINCIPAL_TYPE=ROOT
TEMPORARY_CREDENTIALS=YES
ROOT_AGENT_ACCESS=NO
MCP_AUTHENTICATED_MODE=BLOCKED_ROOT_IDENTITY
MCP_AUTHENTICATED_WRITE_MODE=DEFERRED
```

The official per-user AWS installer had a valid Amazon signature. Automatic
execution review blocked the combined installer command; the owner completed
installation manually. Browser `aws login` completed successfully. Only nonsecret
region metadata was subsequently set in the named profile. No keys were created
or exported. AWS config and login cache remain outside the repository.

STS identified root, so no authenticated Bedrock/AgentCore discovery or MCP
execution followed. A separately created non-root identity is required. This task
does not create IAM identities or policies.

## Capability evidence

```text
BEDROCK_CONTROL_PLANE=BLOCKED_ROOT_IDENTITY
SONNET_4_6_DISCOVERY=BLOCKED_ROOT_IDENTITY
SONNET_4_6_INFERENCE=NOT_TESTED
AGENTCORE_CONTROL_PLANE=BLOCKED_ROOT_IDENTITY
AGENTCORE_RUNTIME_DISCOVERY=BLOCKED_ROOT_IDENTITY
AGENTCORE_GATEWAY_DISCOVERY=BLOCKED_ROOT_IDENTITY
AGENTCORE_WEB_SEARCH_DISCOVERY=DOCUMENTED_US_EAST_1_EXECUTION_UNVERIFIED
CLI_LIST_AGENT_RUNTIMES=PASS
CLI_LIST_GATEWAYS=PASS
AWS_RESOURCES_CREATED=0
AWS_PAID_CALLS=0
AWS_ESTIMATED_TASK_COST=USD_0
```

CLI AgentCore entries were inspected with local input-skeleton generation, not
authenticated API calls. Official regional/model documentation supports the
canonical direction with the inference-profile clarification in
[ADR 0002](../decisions/0002-aws-development-bridge.md). Documentation and model
listing do not establish runtime permission.

## MCP evidence

One enabled `aws-qualor` entry exists. No AWS MCP entry, legacy API/Knowledge
server, AWS profile or Agent Toolkit setup existed in the inspected local
configuration before this task. Unrelated Codex entries were preserved.

The guarded launcher enforces the pinned proxy and read-only mode. With root
blocked, it provides isolated, unauthenticated knowledge access. A direct MCP SDK
client successfully initialized the exact configured launcher, listed six tools,
and called `aws___get_regional_availability`. The service returned
`Amazon Bedrock: isAvailableIn` for `us-east-1`.

All six tools had `readOnlyHint=true`: `aws___get_tasks`,
`aws___get_regional_availability`, `aws___list_regions`,
`aws___read_documentation`, `aws___retrieve_skill`, and
`aws___search_documentation`. Installed proxy source inspection confirmed filtering
on both tool discovery and invocation. No write tool was invoked.

```text
CODEX_MCP_ENTRY=PASS
MCP_PROXY=PASS
MCP_MODE=READ_ONLY
DIRECT_MCP_CONNECTION=PASS
DIRECT_MCP_TOOL_DISCOVERY=PASS
DIRECT_MCP_KNOWLEDGE_TOOL=PASS
MCP_WRITE_CAPABILITY=HIDDEN_OR_BLOCKED
FRESH_CODEX_MCP_CONNECTION=BLOCKED_HANDSHAKE
```

The installed Codex CLI could not use the configured model and required a newer
CLI. A pinned temporary `npx @openai/codex@0.153.4` process used the existing MCP
configuration, without a global Codex upgrade. Fresh-process attempts encountered
tool-call errors and an explicit MCP initialization error `-32603`. Direct SDK
success is not represented as a successful Codex end-to-end smoke. Raw diagnostics
remain under ignored `.qualor/local/`.

## Repository validation

- TDD RED: new bridge test module initially failed because the implementation was
  absent. Additional negative tests reproduced discovery/reporting defects before fixes.
- GREEN: 24 offline bridge tests; 38 total pytest tests passed.
- Ruff passed; frontend locked install, TypeScript check and Vite build passed.
- Independent review covered credential isolation, immutable login-session
  snapshots, root fallback, read-only filtering and truthful failure exits.
- `scripts/aws-preflight.ps1` reports the root blocker and exits 1 as intended.
  It does not claim successful authenticated discovery or MCP connection.
- The existing full `scripts/verify.ps1` remains the final clean-tree delivery gate.
- No proprietary code was imported; no product behavior was added or changed.

## Unresolved and deferred

Required blockers: non-root temporary AWS identity and successful fresh Codex MCP
knowledge smoke. BDB registration remains blocked from QUALOR-00 and is outside
this task. No domain implementation, live agent/search, model invocation,
AgentCore deployment, write-enabled MCP, IAM automation role, resources or
QUALOR-01 work was performed.
