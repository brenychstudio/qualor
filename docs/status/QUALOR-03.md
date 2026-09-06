# QUALOR-03 checkpoint: bounded Web Search (03B2)

Date: 2026-09-06. Repository: `brenychstudio/qualor`, branch `qualor-03-live-agent`.
Starting HEAD: `5da6d0badbbb3961143df0ca602e8026c9b51b7e`.
Canonical SHA-256: `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`.
The canonical document and locked dependencies are unchanged.

## Resource and authentication evidence

- Named profile `qualor-dev`, region `us-east-1`: STS passed as the expected non-root
  IAM user with temporary login credentials. No IAM changes or access keys created.
- Existing Gateway `qualor-opportunity-gateway-lcxtsb27ms` remained READY with MCP
  and AWS_IAM authorization and exact canonical Project/Environment/Owner tags.
- Target inventory was empty before creation. The installed botocore
  CreateGatewayTarget model was inspected before the single create request.
- Created exactly one target: `qualor-web-search`, ID `H8MHDUH81H`, READY.
  Readback confirms `web-search` connector version **1.2.0**, `GATEWAY_IAM_ROLE`,
  `WebSearch` configuration with empty parameter values. No permanent domain filter.
- Final unpaginated inventory: one Gateway and one GatewayTarget.
  `lastSynchronizedAt` was not returned by GetGatewayTarget; no timestamp is inferred.

## Actual MCP and search evidence

GetGateway omitted `protocolConfiguration.mcp.supportedVersions`. No update was
made to the Gateway. A legacy initialize negotiation offered `2025-11-25`; the
Gateway selected **2025-03-26**. The client adopted that version and completed the
initialized notification. This live smoke was **not stateless**. Support for
`2026-07-28` metadata/no-initialize behavior is covered with synthetic tests only
and activates only when that version is explicitly advertised.

One authenticated `tools/list` dynamically returned `qualor-web-search___WebSearch`.
Its schema exposed `query`, integer `maxResults`, `filters.domainFilter.include`
and `.exclude`, and `filters.publishedDateFilter.from`/`.to`. The implementation
discovers the name from the input schema; it contains no assumed target prefix.

Exactly one `tools/call` executed this query, with `maxResults=5`:

> AWS Agents for Humans Professional Agents hackathon official rules deadline prizes

Request-level include domains were `agentsforhumans.devpost.com` and `aws.amazon.com`.
At `2026-09-06T09:30:16.256386Z`, the provider parsed five results with five citable
URLs, all within those domains. One citation was the [Agents for Humans rules
page](https://agentsforhumans.devpost.com/rules). The other four were AWS hackathon
event page language variants; five URLs do not mean five independent sources.
All returned publication dates were the literal `unknown`, preserved as supplied.
No fallback search was needed or executed.

The live result is discovery evidence only. No source page was fetched, and no
snippet was supplied to eligibility or decision engines. Titles, URLs, snippets,
publication values, retrieval timestamps, provider and run/query IDs survive
structured parsing. Missing URLs remain missing and cannot be surfaced as cited
results or used as hard eligibility evidence. There is no fabricated LIVE output.

## Implementation and local operation

`runtime/providers.py` extends the existing SearchProvider contracts.
`runtime/search.py` adds the budgeted provider and structured-result parser.
`runtime/search_transport.py` supplies SigV4 using the installed SDK signing name
`bedrock-agentcore`, HTTPS certificate/hostname verification, JSON/SSE response
handling, ID correlation, a response size/deadline bound, and no automatic retries
or redirects. The AWS CLI exports named-profile temporary credentials **in memory**
for signing; no credential values are persisted or put into configuration.
The existing pinned botocore lacks the optional CRT login provider, so the CLI's
supported temporary-credential export is used without upgrading dependencies.

The production factory verifies the expected non-root identity and exact Gateway
ownership before opening transport. FIXTURE/REPLAY reject AWS provider construction.
The CLI validates its query before AWS access and requires explicit activation:

```powershell
uv run qualor search-live "<bounded query>" --mode LIVE --gateway-id "<local Gateway ID>" --include-domain "docs.aws.amazon.com"
```

Omitting `--mode LIVE` fails closed. This command is a paid-call entry point and
must only be used under an active task's explicit authorization. Output labels
MODE, PROVIDER, QUERY, RESULT_COUNT and CITATION_COUNT; it never prints auth material.

## Budget and boundaries

- Task allowance: at most two search attempts and USD 0.02. The shared existing
  guard reserves USD 0.009 per attempt before the request, including failures.
- Observed search attempts: **1**. Reserved amount: **USD 0.009**. Bedrock calls: **0**.
- Observed Gateway HTTP requests: **4** (initialize, initialized notification,
  tools/list, tools/call). New resources: **1 GatewayTarget**; no other creation.
- Published pricing is USD 7/1,000 searches and USD 0.005/1,000 Gateway API
  invocations. Conservatively charging all four HTTP requests gives an estimated
  **USD 0.007020**, below the reservation and task cap. This is an engineering
  estimate, not a billing observation. [AWS pricing](https://aws.amazon.com/bedrock/agentcore/pricing/).

Raw bounded smoke evidence stays in ignored `.qualor/local/`. No private Gateway
endpoint, account identifier, private ARN, credential, signed header, full page,
or bulk search content is committed. No local search index was built.

## Verification and remaining limits

RED/GREEN evidence: 23 initial provider/CLI failures, 16 initial transport failures,
then targeted failing tests for open SSE streams and malformed catalog objects.
After implementation: **472 pytest tests passed**, including 48 focused new search
tests. Ruff, frontend install/build, export of 20 existing canonical schemas and
TypeScript generation passed. Schema/type generation introduced no domain drift.
The full clean-worktree verification script is the mandatory commit/push gate;
its final result and exact resulting HEAD are reported in the task Result Packet.

The read-only AWS preflight exited successfully: STS, Bedrock discovery and Gateway
discovery passed. Its general Runtime probe still lacks
`bedrock-agentcore:ListAgentRuntimes`; this is intentionally deferred. Its generic
Web Search/MCP fields remain UNVERIFIED because that script does not perform this
paid smoke; the separate evidence above proves this specific target/tool call.
The two inherited Python dependency deprecation warnings remain upstream-only.

Deferred: Strands autonomous loop, official-source fetching/extraction, any use of
search snippets as hard evidence, AgentCore Runtime, persistence, other resources,
IAM changes, final QUALOR-03 PR/merge and QUALOR-03B3 execution.

Protocol and connector references: [AWS tools/list](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-list.html),
[AWS tools/call](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-call.html),
[AWS Web Search connector](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html).
