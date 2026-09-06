# QUALOR-03 checkpoint: live handoff localized (03B3D BLOCKED)

## Final authorized diagnostic run: QUALOR-03B3D

Date: 2026-09-06. Starting HEAD: `7ae18612109beeb3efd3878629c8bdfcda611dd0`.
Instrumented run HEAD: `3d967dc9c2989d9a72f7bbabd074f4fe4e6835c2`.
Status: **BLOCKED_ROOT_CAUSE_IDENTIFIED**. Evidence admission is still unproven;
this is not a successful live handoff or permission to merge.

The original run's root cause remains UNKNOWN because its rejection details were
not retained. The new run precisely localizes the first failing boundary:

- Boundary **B3: SearchCandidate registry -> fetch_official_source**.
- Diagnostic event sequence **3**: `SOURCE_FETCH_RESULT`, status `REJECTED`,
  reason `URL_NOT_DISCOVERED`, component `fetch_official_source`, recoverable `YES`.
- Input shape: `object{url:string,focus:string}`. Output: structured rejection with
  reason code, component, safe summary, recoverability and missing/invalid-field lists.
- Exact behavior: the requested URL did not equal any URL registered by this run's
  search results. The guard rejected it **before HTTP fetching**. The requested URL
  value was not recorded, so a normalization bug versus a model-selected undiscovered
  URL is not distinguished. No such speculative fix is claimed.

The actual tool sequence was search -> rejected fetch -> accepted official FAQ fetch
-> rejected fetch -> search. The accepted source was the [official competition FAQ](https://agentsforhumans.devpost.com/details/faqs),
retrieved at `2026-09-06T11:21:09.181503Z`. Its URL, time, authority and body hash were
retained; its full text was not committed. The second rejection had the same B3 code.
The agent received actionable rejection results and issued a second search.

The next model request was blocked by the **cost reservation guard**, before AWS:
three model calls were used out of six, so this was the projected cost condition,
not the model-call ceiling. Event 11 records `BUDGET_EXHAUSTED` in `strands_model`.
The remaining reservation headroom was USD 0.088644; the proposed request exceeded it.
The exact proposed reservation was not retained. Actual spend need not reach the cap
for a conservative pre-call guard to stop. No model output from that request exists.

Crucially, **record_evidence was never called**. There were no SDK tool errors,
candidate claim validations, or evidence admission attempts in this run. A defect in
B6/B7/B8 is therefore not demonstrated. `EXTRACTION_NO_CRITICAL_CLAIMS` at termination
is a downstream observation, not the first causal rejection.

### Counts and authority

- One additional authorized live run, numbered **2**; no third run or post-run code fix.
- One Strands Agent, 5 tool requests, 3 paid Bedrock calls, 2 Web Search calls,
  5 Gateway MCP HTTP requests, 1 fetched official document, 1 retained source citation.
- EvidenceRecord count **0**; critical evidence links **0**;
  `LIVE_CRITICAL_RULE_WITH_EVIDENCE=NO`. No snippets promoted to evidence.
- All three projects: deterministic `REVIEW_REQUIRED / WATCH` from missing critical
  coverage. Best project unresolved; portfolio strategy/effort/readiness unknown.
- Termination: `BUDGET_EXHAUSTED`; agent tool steps: 5.
- Trace proves search, source selection/fetch and safe deterministic fallback. It does
  not prove an evidence-bearing deterministic handoff. Failure diagnosis is readable;
  the requested successful judge demonstration remains unfulfilled.

### Cost and security

Current-task limits: six model calls, three searches, five documents, USD 0.15.
Reported usage: 11,992 input tokens, 492 output tokens. Model estimate USD 0.043356;
search/Gateway estimate USD 0.014025; **task estimate USD 0.057381**. Guard accounting:
USD 0.061356 including conservative search overhead. Pricing basis is unchanged from
ADR 0003; estimates are not billing observations. Historical B3 spend is separate.

The existing Gateway and target remain the only QUALOR resources (one each), READY.
STS verified the expected non-root IAM user and temporary credentials. No IAM,
credential, Gateway/target or other infrastructure changes occurred. Run-1 and run-2
artifacts remain separate and gitignored; the run-2 exclusive marker prevents retry.

### Offline verification and next action

The pre-run clean commit passed **537 tests**, Ruff, full verification, schema/type
generation, frontend build and secret scanning. Eight new diagnostics regressions
cover strict SDK argument validation, actionable errors, source/claim events, privacy,
and run-2 limits/repeat protection. An independent read-only diagnostic review led to
retaining sanitized validation locations/types and restoring specific safe failure
codes. No decision or claim-admission policy was loosened. All six requested handoff
event types are implemented and exercised offline; unreached live stages are not faked.

Post-run gates and exact final HEAD are reported in the Result Packet. The two existing
upstream Python deprecation warnings and intentionally deferred Runtime permission
gap remain unchanged. Next: owner review of B3 URL admission and the B5 model-context
reservation boundary; any new implementation or paid run requires a separate task.
No final PR, merge or QUALOR-04A work.

## Historical QUALOR-03B3 checkpoint

## Current checkpoint: 2026-09-06

Starting HEAD: `06e3133a39a0559fbf8cb71f354e16d290e384db` on
`qualor-03-live-agent`. Canonical bytes and dependency locks are unchanged.
The implementation and offline gates pass; **the live evidence handoff does not**.
This checkpoint is not ready for protected merge or QUALOR-04A.

### Implemented and verified offline

- One Strands **1.54.0** Agent, model `global.anthropic.claude-sonnet-4-6`, temperature
  zero, output capped at 1,600 tokens. Four tools: search, approved-source fetch,
  typed evidence proposal, deterministic state evaluation. No model verdict setter.
- Actual SDK planning loop tested with an offline model choosing tools from previous
  observations. LIVE uses the existing SigV4 AgentCore SearchProvider. FIXTURE/REPLAY
  reject production AWS/network providers and reuse the same orchestration contract.
- HTTPS fetch with approved host registry, public-address DNS validation, pinned
  connection with original TLS hostname/SNI, bounded redirects/body/timeouts and
  HTML/JSON/plain extraction. No browser, PDF platform or full-page repository storage.
- Pydantic claims preserve source reference, excerpt and extraction state. Unsupported
  values, amounts/timezones and N/A are rejected. Narrow controlled clauses can feed
  existing rule operators; other legal interpretation remains unknown. Official-source
  disagreements force review. The model cannot set eligibility or recommendation.
- Three explicitly fictional project profiles and effort assumptions; no private
  financial data. Unknown opportunity requirements, costs and conflict rules remain
  unknown. Mode-correct engine inputs preserve strict legacy fixture contracts.
- Shared reservation guard: at most six model calls, five searches, ten documents,
  USD 0.20. Physical Converse requests are reserved, including any SDK repair path;
  automatic retries are disabled. Successful usage reconciles cost downward.
- New public schemas: DecisionInput, DecisionOutput, StudioInput, AgentRunResult.
  All **24 schemas** and generated `apps/web/src/generated/domain.ts` are reproducible.

RED/GREEN tests covered the new boundaries and reproduced two discovered defects:
partial technology-name admission and duplicate session/region arguments to the pinned
Strands constructor. Both are fixed without a dependency upgrade. After live observation,
additional RED/GREEN tests added specific safe failure codes and retained fetched-source
citation metadata even when no claim is admitted. Those observability fixes have been
verified **offline only**, not demonstrated in another live run.

Independent code review then identified three additional boundary defects, reproduced
with failing offline tests and fixed: quote punctuation hiding adjacent exceptions,
equivalent/additive technology claims producing false contradictions, and a body-read
deadline that did not interrupt slow responses. The reviewer confirmed the corrections
by read-only diff inspection. None of these fixes was used to justify another paid run.

### Actual bounded live observation

The first launch failed before Agent construction: Strands rejects simultaneous
`boto_session` and `region_name`. The constructor failure was reproduced offline;
no inference or search was reached. Its local marker was archived separately.

After the constructor fix and 522 passing offline tests, exactly **one actual live
dogfood run** investigated AWS Agents for Humans Professional Agents. It instantiated
one Strands Agent and made **5 tool calls**, **3 Bedrock Converse calls**, **1 real
Web Search query**, **4 Gateway MCP HTTP requests**, and **1 successful official-source
fetch**. It stopped at `TOOL_FAILURE_BOUND_REACHED` after three model turns.

**Admitted EvidenceRecord count: 0. Critical evidence citations: 0.** The original
trace did not retain the specific rejected-tool error, tool names, or the fetched URL
when no claims were accepted. Its generic rejection events do not prove whether the
failure was source coverage, URL admission or SDK argument validation. No root cause
is invented. The original local result is preserved; it has not been retroactively
rewritten using the subsequent observability fixes. No source citation is fabricated.

The deterministic engines returned **REVIEW_REQUIRED / WATCH** for all three projects
with empty-rule-set and incomplete-critical-coverage reasons. Best project remained
unresolved; portfolio strategy, effort and readiness remained unknown. This demonstrates
fail-closed authority, but does not yet demonstrate the requested non-trivial live
eligibility or project-selection judgment. It is more than search-only transport, but
it is **not** an accepted end-to-end evidence-first demonstration.

No second paid dogfood run was attempted: the task permits a second only after a
specific recoverable search-coverage fix, and the retained evidence does not establish
that condition. Another diagnostic live run requires owner authorization.

### Cost and security evidence

Reported model usage: 11,573 input tokens and 434 output tokens. Estimated model cost:
USD 0.041229. One search plus conservatively charging all four Gateway requests adds
USD 0.007020, for **USD 0.048249 estimated task cost**. The shared guard retained
USD 0.050229 including its search overhead allowance, below USD 0.20.
These are engineering estimates, not observed billing. Pricing basis is recorded
in [ADR 0003](../decisions/0003-live-evidence-authority.md) and the historical B2 section.

STS and preflight passed as the expected non-root IAM user with temporary credentials.
Gateway and target remained READY. No IAM changes, access keys, new infrastructure,
Bedrock Runtime deployment, submissions or raw third-party pages were committed.
The general preflight still reports the intentionally unavailable
`bedrock-agentcore:ListAgentRuntimes`; it performs no model/search inference itself.

### Final local gates and next action

**529 pytest tests passed**, including all 472 baseline tests. Ruff, npm ci/build,
schema/type generation and diff whitespace checks passed. The two inherited upstream
Python deprecation warnings remain. The clean-tree `scripts/verify.ps1` gate is run
after committing; its exact result and resulting HEAD are reported in the Result Packet.

Remaining blocker: `LIVE_EVIDENCE_HANDOFF_UNPROVEN`. The next useful action is owner
review and authorization for one diagnostic run using the improved bounded trace,
with an explicit remaining task budget. Do not merge on the strength of offline tests.
No QUALOR-04A work, final PR or merge is included.

## Historical checkpoint: bounded Web Search (03B2)

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
