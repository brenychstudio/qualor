# QUALOR-00B status, updated by QUALOR-00B1

Date: 2026-09-05. Blocker-resolution checkpoint: PASS with explicit AgentCore
read-permission gaps permitted by QUALOR-00B1 Phase H. No QUALOR-01 work.

## Repository checkpoint

- Repository: `brenychstudio/qualor`, PRIVATE; existing PR #2 remains unmerged.
- Branch: `qualor-00b-aws-development-bridge`.
- QUALOR-00B1 starting HEAD: `94c583c2f4bc4e9090e7c6ba24d3fa4c1e261eb3`.
- Main baseline: `021f9b85b9cee26020b6e2217218f4655d2a0f75`.
- Canonical SHA-256: `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`.
- Canonical size: 62438 bytes, unchanged. Exact delivery HEAD and final clean-tree
  verification are reported in PR #2 and the Result Packet.

## Root identity resolved

The owner provisioned `qualor-dev-user` in `qualor-dev-readonly`, with
`SignInLocalDevelopmentAccess` and `AmazonBedrockReadOnly`. Codex did not modify
IAM, broaden permissions, or create access keys.

Phase A logged out the named profile and completed browser `aws login`, replacing
its previous root login-session reference with the owner's IAM login. STS verified
the expected user and temporary credentials. Phase A was not repeated during the
Phase B continuation. Later read-only preflight again verified non-root identity.

```text
AWS_CLI_VERSION=2.36.40
CODEX_VERSION=0.153.4
UV_VERSION=0.12.5
UVX_VERSION=0.12.5
MCP_PROXY_VERSION=1.6.5_PINNED
AWS_PROFILE=qualor-dev
AWS_REGION=us-east-1
AWS_AUTH=PASS
AWS_STS=PASS
PRINCIPAL_TYPE=IAM_USER
ROOT_IDENTITY=NO
TEMPORARY_CREDENTIALS=YES
ROOT_AGENT_ACCESS=NO
AWS_ACCESS_KEYS_CREATED=0
IAM_CHANGED_BY_CODEX=NO
```

AWS config/cache stay under the user profile, outside the repository. The
immutable session snapshot, alternate-provider isolation and root guard remain.

## Read-only capability evidence

Both the repository preflight and independent CLI reads succeeded for Bedrock
foundation-model and inference-profile lists. Authoritative model identifiers
confirmed Sonnet 4.6 in both responses. No inference permission was tested.

```text
BEDROCK_CONTROL_PLANE=PASS
SONNET_4_6_DISCOVERY=PASS
SONNET_4_6_INFERENCE=NOT_TESTED
AGENTCORE_CONTROL_PLANE=BLOCKED_PERMISSION
AGENTCORE_RUNTIME_DISCOVERY=BLOCKED_PERMISSION
AGENTCORE_GATEWAY_DISCOVERY=BLOCKED_PERMISSION
AGENTCORE_WEB_SEARCH_DISCOVERY=UNVERIFIED
AGENTCORE_DENIED_ACTIONS=bedrock-agentcore:ListAgentRuntimes,bedrock-agentcore:ListGateways
```

Both denied calls returned `AccessDeniedException`. No permissions were added.
AgentCore API models exist in the installed CLI; documentation confirms regional
Web Search availability as recorded in ADR 0002, but no connector, search or
deployment was executed.

## MCP diagnosis and the single fix

Before changing code/configuration, Phase C captured installed Codex 0.153.4,
the enabled `aws-qualor` stdio entry, and proxy 1.6.5 help. The configured command
was and remains `powershell.exe -NoProfile -NonInteractive -File
C:\PROJECTS\qualor\scripts\aws-mcp.ps1`. Profile and region were explicit;
read-only mode was enabled. Startup/tool timeout configuration was unset.
Existing unrelated MCP entries were preserved.

The exact launcher outside Codex returned a valid JSON-RPC error `-32603` with
an empty message after 4.844 seconds, then exited 0 when stdin was closed. A fresh
installed Codex process also produced an empty knowledge-tool error. The primary
pre-fix class was `UNKNOWN`; the supplied taxonomy has no network/TLS category.
It was not established as a Codex-only failure, argument error or startup timeout.

One additional debug run showed successful profile/region propagation and SigV4
signing, followed by `httpx.ConnectError` during `start_tls`. Direct TLS probes
found some IPv6 addresses resetting connections (Windows error 10054), while all
probed IPv4 addresses negotiated TLS 1.3. IPv4-bound HTTPX reached the same managed
endpoint with certificate verification enabled.

Hypothesis: intermittent IPv6 TLS resets produce the empty downstream connection
error surfaced by MCP. The single handshake fix supplies a direct IPv4 HTTPX
transport inside the pinned proxy process, through its existing client factory.
No Codex timeout/configuration, IAM policy, endpoint, TLS verification, proxy pin
or read-only filter was weakened. See [ADR 0002](../decisions/0002-aws-development-bridge.md)
for the narrow adapter and HTTP-proxy compatibility limitation.

After the fix, the same launcher initialized successfully in 6.750 seconds and
exited 0 after stdin closure. A server waiting for protocol input was not treated
as a hang.

## Fresh Codex evidence

Two genuinely fresh installed Codex 0.153.4 processes used the existing
configuration. Each requested one knowledge call and no retry:

1. `aws___list_regions`: succeeded, returned 37 regions.
2. `aws___get_regional_availability`: returned `Amazon Bedrock: isAvailableIn`
   for `us-east-1`, with no failed regions or next page.

Independent direct-client discovery found exactly six tools, all with
`readOnlyHint=true`: `aws___get_tasks`, `aws___get_regional_availability`,
`aws___list_regions`, `aws___read_documentation`, `aws___retrieve_skill`, and
`aws___search_documentation`. Upstream filtering still applies to discovery and
invocation. No write tool was invoked.

```text
FRESH_CODEX_MCP_CONNECTION=PASS
FRESH_CODEX_TOOL_DISCOVERY=PASS
AWS_KNOWLEDGE_TOOLS=PASS
REGIONAL_DISCOVERY=PASS
MCP_MODE=READ_ONLY
MCP_WRITE_CAPABILITY=HIDDEN_OR_BLOCKED
MCP_AUTH_METHOD=SIGV4_NAMED_TEMPORARY_PROFILE
MCP_AUTHENTICATED_WRITE_MODE=DEFERRED
```

Knowledge success does not establish authenticated AWS API execution through MCP.
Independent CLI results above are a separate capability class. Raw diagnostics
remain under ignored `.qualor/local/`; no browser/credential material is committed.

## Verification and remaining boundaries

- RED/GREEN tests cover the IPv4 adapter and explicit permission-gap reporting.
  The suite has 42 passing tests, including all original bootstrap behaviors.
- Ruff passes. The existing full clean-tree verification, locked frontend
  install/build, Git whitespace and tracked-secret audit remain delivery gates.
- `scripts/aws-preflight.ps1` returns 0 for this explicitly permitted diagnostic
  state and continues to show each denied AgentCore action. It still fails on
  missing/root authentication, unknown errors, Bedrock failures, or unsupported
  MCP configuration. Its `AWS_MCP_SERVER=UNVERIFIED` means live MCP knowledge is
  verified by the separate fresh-process smokes, not inferred by the CLI script.
- Independent review verified TLS verification, SigV4 hooks, root/credential
  guards and read-only filtering remain intact.
- AWS resources created: 0. Paid AWS calls: 0. Estimated task cost: USD 0.
- No long-term keys, proprietary imports, IAM changes, product features,
  inference, AgentCore Web Search execution, deployment or external submissions.

Remaining permission gaps: `bedrock-agentcore:ListAgentRuntimes` and
`bedrock-agentcore:ListGateways`. Inference and Web Search execution remain
untested. BDB registration remains unchanged/out of scope. PR #2 is not merged;
the next checkpoint is QUALOR-00BM, not QUALOR-01.
