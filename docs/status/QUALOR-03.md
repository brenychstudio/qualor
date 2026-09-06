# QUALOR-03 final live cutoff (03F)

## QUALOR-03F: source-grounded mechanics passed; supported normalization not proven

Date: 2026-09-07. Baseline: `d39cbb772b81a0d68b6e370380e14de2295107b2`.
Exactly one owner-authorized live acceptance run was performed. No IAM, Gateway or
GatewayTarget changes were made, and no retry or post-run backend fix was attempted.

The live run proved one Strands agent, AgentCore Web Search, opaque current-run
candidate selection, two official fetches, 28 exact dual-bounded EvidenceSpans,
runtime HMAC span selection, native structured extraction and deterministic claim
normalization. It admitted one exact-source `OFFICIAL_FAQ` EvidenceRecord for a
critical `required_technology` candidate. The field normalizer conservatively marked
that qualified clause `AMBIGUOUS`, so the EvidenceRecord remained `UNVERIFIED` and
the rule remained unsupported. A second grounded `project_policy` proposal was
rejected as `CLAIM_VALUE_UNSUPPORTED`. No normalization result was `SUPPORTED`.

The accepted live cutoff retains the normalizer coverage limitation explicitly:

```text
NORMALIZATION_SUPPORTED_COUNT=0
NORMALIZATION_AMBIGUOUS_COUNT=1
NORMALIZATION_UNSUPPORTED_COUNT=1
```

The run therefore did not meet the final authoritative-evidence acceptance gate.
The deterministic engines failed closed with unresolved portfolio eligibility and
`WATCH`; they did not promote the ambiguous claim. The earliest acceptance failure
is B7 claim validation, classified as a normalizer coverage gap. A later extraction
attempt also returned a strict schema rejection and was not retried. Normalization
events retained field, status, reason and version, but the trace contract lacks the
separately requested `value_kind`, so the final diagnostic gate is partial.

The bounded run used six Bedrock inference calls, three Web Search calls and six
Gateway MCP calls for an estimated **USD 0.106593**, below the USD 0.20 cap. Maximum
ordinary Strands request size was 15,268 bytes; raw fetched bodies did not return to
agent context. Search snippets remained discovery-only and the evidence validator
was not relaxed.

### QUALOR-05 hardening backlog

- `QUALOR-05-HARDEN-CLAIM-NORMALIZER-COVERAGE`: build a sanitized official-clause
  regression corpus for qualified required-technology and project-policy wording;
  extend deterministic normalization only where exact source language proves a safe
  mapping; add `value_kind` to bounded normalization receipts; retain strict span,
  evidence and model-authority boundaries. The later strict extraction-schema
  rejection should be reproduced from sanitized envelope diagnostics before any
  change.

QUALOR-03 live debugging is frozen at this cutoff. Product-layer work may proceed
separately; this task does not begin QUALOR-04A.

# Historical checkpoint: deterministic claim-value grounding (03B3Q)

## QUALOR-03B3Q: offline field-aware source normalization

Date: 2026-09-06. Baseline: `f09e01077848cf9967144e7625a933422115784b`.
This checkpoint made zero Bedrock inference, Web Search or paid AWS calls and made
no IAM or infrastructure changes.

The B3P live diagnostics retained two string claim shapes and the common
`CLAIM_VALUE_UNSUPPORTED` rejection, but intentionally did not retain their fields,
values or exact source spans. Those historical values cannot be reconstructed and
are not invented here. Code review proved the applicable contract defect: every
canonical model value was previously required to occur literally in the grounded
span, even when a canonical enum legitimately differs from the source wording.

The admission boundary now treats the runtime-grounded exact span as source
authority, a versioned deterministic field normalizer as normalization authority,
and the model value as a proposal. Version 1 implements only the bounded V1
families already exercised by the architecture: entrant-type explicit phrases,
required-technology controlled clauses and new-project controlled clauses. Open
text retains normalized exact-substring support. Unsupported proposals fail;
model/source conflicts receive a distinct rejection; ambiguous or unknown wording
keeps `normalized_value=None` and can never become a definitive hard fact.

EvidenceRecords continue to store the exact runtime source excerpt and citation.
No fuzzy matching, embeddings, model adjudication, search-snippet evidence or
evidence-validation relaxation was added. The trace now emits a bounded
`CLAIM_NORMALIZATION_RESULT` with field, status, reason code and normalizer version
before evidence admission. Prompt-injection text cannot change the deterministic
normalized value or final authority.

The full live-like replay still reaches one source-grounded EvidenceRecord, links a
critical rule and deterministically returns **SKIP**. The five-call projection is
unchanged at **USD 0.154590** against the USD 0.20 cap. A further live run requires
separate owner authorization.

# Historical checkpoint: dual-bounded evidence spans (03B3O)

## QUALOR-03B3O: offline producer/consumer contract alignment

Date: 2026-09-06. Baseline: `e037bb331c2b85856bce0079d10027510d298e21`.
This checkpoint made zero Bedrock inference, Web Search or paid AWS calls and made
no IAM or infrastructure changes.

The source-grounded live path had already resolved a model-selected, current-run
HMAC span capability to exact canonical source text. Admission then failed because
the producer allowed 800 UTF-8 bytes while `ExtractedClaim.excerpt` allowed 700
characters. A 750-character ASCII source reproduced the exact mismatch offline:
it passed the producer and failed Pydantic with `string_too_long` downstream.

`MAX_EVIDENCE_EXCERPT_CHARS=700` is now the single domain character policy used by
`EvidenceRecord`, `ExtractedClaim`, and `EvidenceSpan`. Span generation guarantees
both at most 700 characters and at most 800 UTF-8 bytes. It continues to prefer
paragraph/list-row, sentence and whitespace boundaries before a deterministic hard
boundary. Each emitted span remains an exact canonical-source slice with unchanged
character offsets; its HMAC identity remains bound to run registry, source, offsets
and content hash. Normal blocks below both bounds remain intact. No fuzzy matching,
model-authored quote authority, evidence relaxation or domain-limit increase was
introduced.

The successful live-like replay now exposes `EVIDENCE_SPANS_CREATED`,
`STRUCTURED_EXTRACTION`, `SOURCE_SPAN_SELECTED` and evidence-admission events before
deterministic eligibility and decision. It admits one exact source-grounded
EvidenceRecord, links the critical technology rule, and deterministically returns
**SKIP**, with zero AWS calls. The prior recovered B2 tool-result warning has no
reproducible current blocker and was not redesigned.

The post-fix five-call live-like projection is **USD 0.154590** against the unchanged
USD 0.20 cap. Planner/extraction token limits and the two-claim extraction maximum
are unchanged. A further live run requires separate owner authorization.

# Historical checkpoint: deterministic claim grounding (03B3M)

## QUALOR-03B3M: offline source-span authority

Date: 2026-09-06. Baseline: `30f189c8e941be673626817307bbfc2828853afa`.
This checkpoint made zero Bedrock inference, Web Search or paid AWS calls and made
no IAM or infrastructure changes.

### Root cause and source representations

The latest live run retained the two rejection codes but intentionally did not
retain model-authored excerpts or raw pages, so the historical excerpt values and
their direct raw/normalized comparisons are unavailable. Code tracing nevertheless
establishes the failing class. The HTTP fetcher decodes UTF-8 with replacement;
HTML uses entity conversion, removes script/style/noscript/SVG text, collapses
whitespace within text nodes and joins visible nodes with line breaks. JSON is
parsed and serialized deterministically; plain text remains decoded text. That
result is the single canonical `SourceDocument.text` stored in run memory.

The extraction request used a bounded substring of that same `SourceDocument.text`.
The evidence validator checked the full same value, with case folding and whitespace
collapse only for membership. Any exact extraction-input quote therefore had to be
present in the validation source. Both `CLAIM_EXCERPT_MISSING` results establish that
the model-authored quote was not grounded even under this normalized comparison.
The primary root-cause class is **MODEL_PARAPHRASED_EXCERPT**; no representation
mismatch or fuzzy matching fix was justified.

### Capability-safe grounding

The extraction JSON transport now accepts `supporting_span_id` instead of a
model-authored excerpt. Before extraction, QUALOR deterministically segments the
bounded canonical source window into semantically bounded blocks of at most 800
UTF-8 bytes. Each `EvidenceSpan` records exact text and source character offsets.
Its ID is an HMAC capability created with a random per-extractor secret, binding
source ID, offsets and text hash. Unknown, cross-source and prior-run IDs fail
closed. No same-domain inference, fuzzy match, semantic similarity or quote repair
can establish evidence authority.

The model receives labelled exact spans and may select a span ID. The runtime
resolves that ID, constructs the immutable domain claim with the registered exact
text, and then calls the unchanged evidence validator. New EvidenceRecords retain
the run source ID, exact excerpt, citation URL, retrieval time and normalized field.
The public Strands tool set no longer exposes direct `record_evidence`; evidence
admission is an internal deterministic step after structured extraction. The trace
adds `SOURCE_SPAN_SELECTED` with separate source and span references, without raw
page content or model reasoning.

### Cost, replay and verification

The top-level `{"claims":[...]}` JSON contract, native array, two-claim limit,
1024-token extraction limit, prompt-injection boundary and exact evidence checks
remain. Span labels produce a conditional five-call projection of **USD 0.154353**:
input $0.090273, output $0.046080, search $0.014 and Gateway allowance $0.004.
This remains below the unchanged $0.20 hard cap. The output-size bounds for one and
two grounded transport claims are 297 and 573 UTF-8 bytes respectively.

The offline live-like replay traverses search, candidate capability, fetch, bounded
source reference, structured span selection, exact evidence admission, linked
critical rule and deterministic **SKIP**. It emits a judge-readable source-grounding
event and performs zero AWS calls. The evidence-admission strictness is unchanged;
search snippets remain ineligible for hard evidence. Full regression results and
the final commit are recorded in the B3M Result Packet. A further live run requires
separate owner authorization.

# Historical checkpoint: extraction envelope and token policy (03B3K)

## QUALOR-03B3K: offline response semantics and output sizing

Date: 2026-09-06. Baseline: `b8be6658ed11d278ab377e47a5d021160ecb624b`.
Zero inference, Web Search or paid AWS calls; no IAM/infrastructure changes.

### Historical evidence and adapter diagnosis

The ignored bounded J report retained extraction usage of 3293 input / 512 output
tokens and `EXTRACTION_SCHEMA_REJECTED`, but no raw response, `stopReason`, response
text length, JSON error or schema issue details. Historical stopReason is
**UNAVAILABLE**. Output tokens equalling 512 does **not** prove truncation.

Before this change, Converse returned a transient envelope to the extractor;
`BudgetedBedrockClient` retained input/output usage for cost reconciliation. The
extractor discarded termination, total tokens, content-block metadata and latency,
and collapsed missing single-text content and JSON decode failures into schema
rejection. `additionalModelResponseFields` was not requested or retained.

The adapter now classifies `max_tokens` as `EXTRACTION_OUTPUT_TRUNCATED` before
JSON/Pydantic. `malformed_model_output`/`malformed_tool_use`, `content_filtered`,
`guardrail_intervened`, and `model_context_window_exceeded` have distinct bounded
failure codes. Missing/unknown termination or provider exceptions fail closed.
An `end_turn` response must contain the expected text envelope, valid JSON, then
the canonical schema; JSON errors and schema errors remain separate. Stop names
were checked against installed botocore and the official
[Converse response contract](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html).

Frozen receipts retain safe stop reason, input/output/total tokens, block count and
known block types, text byte length, JSON/schema states, model ID, output limit,
latency and response SHA-256. At most six enter run metrics. No raw text, source
page, response prefix/suffix, exception prose, credentials or reasoning is retained.
The existing tool rejection/trace path receives the precise failure code.

### Measured output policy and conditional projection

Reproduce locally: `uv run python scripts/extraction-budget-report.py`.
Owned distinct synthetic claims extend the replay technology clause solely for
sizing; they are not live opportunity rules. Default JSON serialization produces:

| Claims | UTF-8 bytes / conservative output token bound |
| --- | ---: |
| 1 | 382 |
| 2 | 801 |
| 3 | 1121 |
| 5 | 1813 |

These are one-token-per-UTF-8-byte conservative estimates, not provider token
counts. The retained maximum is **two focused claims**. Planning stays at 512;
extraction uses **1024**: the measured two-claim bound exceeds both 512 and 768,
and fits 1024 with 223 tokens of headroom. Arbitrarily verbose valid domain claims
are not guaranteed to fit; truncation and batches exceeding two fail closed.
The extraction prompt asks for concise focused claims, without a format-repair loop.
No token estimator, $0.20 task cap, reservation/reconciliation or call count rule
was relaxed. The guard checks the extraction-specific allowance independently.

Five-call projection: four historical planner input counts (2402, 3575, 4401,
4888), worst configured planner outputs (4 x 512), and one isolated extraction
(1024 output; input bound is the larger of the reconstructed request and the
historical 11972 bytes, plus the existing 2048 overhead). Cost components:
input **$0.087858**, output **$0.046080**, two searches **$0.014**, Gateway allowance
**$0.004**, total **$0.151938**. Rates reuse the existing model/search policy.
Gateway amount is a conservative allowance, not measured billing.

This projection is conditional on the observed planner input prefix and one
successful focused extraction followed by deterministic finalization. It is not
a worst-case forecast for arbitrary future agent actions. Each actual request
still reserves before execution and reconciles actual usage; it can be stopped
by the unchanged hard cap. No live run occurred to validate this new projection.

### Replay and regression

Initial adapter/policy RED suite: 12 expected failures. GREEN replay traverses one
Strands planner, search candidate, source capability, bounded reference, recorded
native canonical JSON, one admitted EvidenceRecord, a linked critical rule and
deterministic **SKIP**. Receipt stop/usage/validation metadata survives into run
metrics. Replay inference/search AWS calls are zero. The JSON wrapper/native array,
immutable post-validation domain tuple, evidence admission and deterministic
authority are unchanged. Full Python regression: **599 tests**, with the two
existing upstream dependency deprecation warnings. Schema/type regeneration,
frontend install/build and read-only AWS preflight passed. The local Node 22/npm 10
engine warning remains; the project declares Node 24/npm 11. No dependency/runtime
upgrades or warning suppression were included in this bounded task.

Historical truncation remains unproven. A further paid proof requires explicit
owner authorization; this checkpoint does not claim live evidence acceptance.

## QUALOR-03B3I: structured extraction transport closure

Date: 2026-09-06. Starting HEAD: `41c8bd3a8f5951296b2ff2153fe995825c63e8c2`.
This checkpoint is offline: zero Bedrock inference, Web Search, paid AWS calls, IAM
changes, or resource mutations. Another live acceptance run requires explicit owner
authorization.

### Exact failure and root cause

The 03B3H live trace retained safe validation evidence rather than raw model payloads.
The first extraction output omitted the required `claims` wrapper
(`claims:missing`). The second supplied a non-array value at `claims`
(`claims:tuple_type`). Exact raw outputs were intentionally not persisted.

Baseline reproduction disproved a Python-tuple/JSON-array impedance defect: the prior
Pydantic domain batch accepted canonical `{"claims": [valid claim]}` and converted both
the outer claims array and an array claim value to tuples. A missing wrapper fails with
`missing`, a bare top-level array fails with `model_type`, and a single object in
`claims` reproduces the live `tuple_type` error class. The emitted schema already described
an object with a required array. The actual defect was relying on forced Bedrock tool use:
it forced the output tool name but did not guarantee that the generated tool arguments
conformed to the schema, consuming additional extraction attempts on formatting errors.

### Canonical JSON wire boundary

Extraction now has one explicit `ExtractedClaimBatchTransport` wire contract:

```json
{"claims": [{"source_id": "...", "field": "...", "state": "..."}]}
```

The transport collection is a JSON-native `list[ExtractedClaim]`. It requires the wrapper,
forbids extra fields through the existing extra-forbid contract policy, rejects bare arrays,
Python tuples, and other non-array collections, permits an explicit empty findings list, and
preserves UNKNOWN.
Only after validation is it converted once to immutable domain
`tuple[ExtractedClaim, ...]`.

The direct isolated extraction request now uses the installed Bedrock Converse native
`outputConfig.textFormat` JSON Schema facility. A Bedrock-specific projection removes local
validation keywords that the documented Bedrock subset does not support; the complete
Pydantic constraints are still enforced locally. It requests a single structured JSON text
result and passes that result through the one transport validator. There is no format-repair
LLM loop, permissive dictionary fallback, or heuristic JSON repair. The complete bounded
claims-plus-observations tool result is checked before evidence state can mutate. The source capability,
9,000-byte extraction window, 512-token output ceiling, prompt-injection delimiter, exact
source ID/URL checks, evidence admission, and deterministic authority remain unchanged.

### Replay and budget evidence

An offline native-JSON replay traverses source capability resolution, bounded extraction,
transport validation, immutable domain conversion, existing `record_evidence`, one linked
critical EvidenceRecord, deterministic eligibility, and deterministic `SKIP`. It uses zero
Bedrock and Web Search calls. Missing wrappers, bare arrays, malformed/extra claims,
non-array claims, forged shapes, UNKNOWN, citation/excerpt preservation, and immutable
conversion are covered directly.

For a 60,000-byte trusted source with the unchanged 9,000-byte extraction window, the
native-schema extraction request is 11,445 bytes and reserves USD 0.048159. Combining the
run-3 ledger (USD 0.077949), the isolated planning reservation (USD 0.043560), and this
extraction reservation yields a fully conservative USD 0.169668 projection beneath the
unchanged USD 0.20 acceptance cap. The successful replay uses four planner turns, including
the post-extraction deterministic evaluation turn, plus one isolated extraction call. Removing
the two observed formatting retries therefore reduces the projected successful path from six
Bedrock calls to five.

The completed local suite contains **584 tests**. Exact commit, push, and clean-tree evidence
is recorded in the Result Packet.

# Previous checkpoint: source-context isolation (03B3G)

## QUALOR-03B3G: agent context and extraction budget boundary

Date: 2026-09-06. Starting HEAD: `7a991240091af9cfda874bd0e7c44cebe6e9c78c`.
This checkpoint is offline: zero Bedrock inference, Web Search, paid AWS calls, IAM
changes, or resource mutations. A fourth live run is not authorized here.

### Run-3 forensic reconstruction

The ignored run-3 artifact records four successful model calls with provider usage of
2,272/125, 3,449/102, 5,893/100, and 6,219/103 input/output tokens. Their actual model
cost totals USD 0.059949; two fixed search commitments bring the guard ledger to
USD 0.077949. The rejected fifth request reserved USD 0.109659 against USD 0.072051
remaining, projecting USD 0.187608.

The unchanged reservation formula proves the rejected request was exactly 31,945 UTF-8
serialized bytes:

```text
input  = (31,945 + 2,048) * USD 0.000003 = USD 0.101979
output = 512 * USD 0.000015               = USD 0.007680
total                                          USD 0.109659
```

The fifth turn contained nine messages: the initial input plus four assistant tool-use /
user tool-result pairs. Historical per-message and fetched-body byte counts were not
persisted, so they are reported as unavailable rather than reconstructed from guesses.
Code inspection establishes the actual defect: each successful fetch returned up to 9,000
source characters in its ordinary Strands tool result. After two fetches, those untrusted
bodies were retained and retransmitted with the complete conversation. Evidence admission
was never called, so its implementation remains unchanged.

The primary root-cause class is `AGENT_CONTEXT_BLOAT`. The byte-based estimator remains a
deliberately conservative fail-closed upper bound; no separate accounting or estimator bug
was proven. Exact historical reservation-to-actual ratios are unavailable because request
reservations/bytes for successful calls 1-4 were not retained. Provider token usage itself
is retained as listed above.

### Repaired capability boundary

Full `SourceDocument.text` now remains only in run-scoped trusted state. The fetch tool
returns a `FetchedSourceRef` with an opaque random current-run `source_id`, candidate ID,
citation URL/title, authority, content type/length, retrieval time, and a UTF-8-safe excerpt
capped at 512 bytes. All ordinary tool results are capped at 4,096 serialized bytes. A
forged or prior-run source ID cannot resolve. The existing HTTPS, host allowlist, DNS/IP,
redirect, TLS, time, content-type, and document-size rules are unchanged.

Strands now chooses a source and extraction focus through
`extract_official_claims(source_id, focus)`. The runtime resolves the capability and makes
one direct, budgeted structured extraction call over only its system contract, that focus,
one exact registered source, and the constrained claim schema. The full source stays in
trusted run state; sources above the explicit fetch-to-extraction budget boundary supply a
deterministic focus window capped at 9,000 bytes. The extraction call receives no Strands
conversation and exposes no search, fetch, verdict, shell, filesystem, IAM, or arbitrary
tool capability. Source text is explicitly delimited as untrusted data. At most two typed
claims are accepted per call and passed immediately through the existing deterministic
`record_evidence` validation inside the same tool invocation. This avoids requiring a
seventh Strands model turn after the six-call live ceiling; the evidence admission rules
themselves remain unchanged.

There is still exactly one autonomous Strands agent. It owns search, source selection,
fetch, and extraction-focus planning. It cannot set eligibility or recommendation.

### Offline projection and replay proof

A live-like nine-message projection with two 60,000-byte fetched documents produces a
9,912-byte planning request after isolation: 2,502 tool-result bytes, zero raw fetched-body
bytes in those results, and 7,410 other request bytes. Individual message sizes are
1,443, 115, 324, 161, 1,015, 115, 328, 161, and 1,023 bytes. Its fail-closed reservation
is USD 0.043560, producing USD 0.121509 when tested against run 3's pre-call ledger.

The separate extraction request keeps the full 60,000-byte source in trusted state but
sends only its 9,000-byte focus window. The 11,718-byte request reserves USD 0.048978.
Using the largest provider-reported actual cost among prior planning turns (USD 0.020202)
as the conservative empirical next-planning projection yields a sequential total of
USD 0.147129. This is below the unchanged USD 0.15 cap; the guard still stops any actual
request whose pre-call reservation does not fit. Reserving both future calls at once would
produce USD 0.170487, but the guard never does that: it reserves and reconciles each call
sequentially from provider usage before the next call.

The owned REPLAY performs search -> candidate capability -> fetch -> bounded source
reference -> extraction focus -> typed claim -> unchanged evidence admission ->
deterministic eligibility and decision. It admits one critical EvidenceRecord, links that
record into the decision, and returns `FAIL / SKIP` for the synthetic technology mismatch.
It performs zero Bedrock and Web Search calls. Prompt-injection strings in source data
cannot add tools or verdict fields and cannot override deterministic output. The trace is
bounded and reads source reference -> structured extraction -> evidence recorded ->
deterministic eligibility -> deterministic decision, without raw bodies or model reasoning.

The completed local suite contains **570 tests**. Exact final commit and push evidence is
reported in the Result Packet. A separately authorized final live proof remains required.

# Previous checkpoint: offline handoff closure (03B3E)

## QUALOR-03B3E: URL admission and budget root cause

Date: 2026-09-06. Starting HEAD: `8ad689c28e10adc6dd301fc58c78317f794ef872`.
This checkpoint performs no live run, Bedrock inference, Web Search, IAM change, or AWS
resource mutation. It repairs and proves the upstream handoff offline; a separately
authorized live proof is still required.

### B3 data flow and exact defect

The run-2 implementation used this path:

1. AWS structured result `url` -> `SearchCandidate.url`: literal provider value; no
   normalization.
2. Search candidate -> run registry: literal URL used as both key and value.
3. Registry -> tool result: literal URL, including its path/query/fragment form.
4. Tool result -> Strands fetch argument: model-generated `url` string.
5. Fetch admission: byte-for-byte membership in the registry.
6. Redirect handling: only after admission, with HTTPS/host/DNS/IP validation at each hop.

Thus a model had to reproduce a raw network address exactly. Run 2 proves the supplied
string differed from the registry and was rejected. The trace did not retain the two URL
values, so whether its mismatch was a fragment, case, slash, query, canonical/redirect URL,
or an invented path remains unknowable. The proven contract defect is independent of that
missing historical value: raw model text was being used as a network capability reference.

The repaired boundary assigns a random, run-scoped `candidate_id` to every citable search
observation. `search_web` returns that ID alongside the original title and URL;
`fetch_official_source` accepts only the ID and resolves it to the registered address.
Unknown, fabricated, raw-URL, alternate-path and prior-run references fail closed. A
rejection returns at most five current IDs/titles/sanitized public URLs so the agent can
recover without another search. Trace diagnostics retain the sanitized requested public URL
when the rejected reference is URL-shaped, candidate count/domains and bounded candidate
URLs; query and fragment data are removed. The original provider URL remains visible in the
search citation.

Registry identity permits only these explicit equivalences:

- scheme and IDNA host case;
- default HTTP/HTTPS port removal;
- fragment removal;
- empty path and `/`.

It does not merge distinct paths, non-empty trailing-slash variants, subdomains, query
strings, non-default ports, or HTTP with HTTPS. `SEARCH_CANDIDATE_EXACT` and
`SEARCH_CANDIDATE_CANONICAL_EQUIVALENT` are the only admitted provenance classes. An
official-document link or redirect target is not a model-selectable registry capability;
the existing fetcher may follow a bounded redirect only as transport continuation after an
admitted candidate, reapplying the complete SSRF policy. There is no same-domain shortcut.

The existing source fetch defenses remain unchanged: HTTPS-only LIVE sources, operator host
allowlist, public resolved addresses, DNS-pinned socket, TLS/certificate/hostname/SNI
verification, bounded redirects, time, size and content types. Evidence admission itself is
unchanged because run 2 never invoked `record_evidence` and supplied no evidence of a B6-B8
defect.

### Budget root cause and correction

Run 2's completed usage was reconciled correctly: model cost USD 0.043356 plus two
conservative search commitments of USD 0.009 each produced the guard value USD 0.061356.
The remaining cap was USD 0.088644. There was no duplicate model charge, completed model
reservation leak, or retained fetch cost. Search uses a fixed conservative amount; it is now
explicitly marked committed on success so open-reservation state is accurate, without
reducing the charged amount.

The rejected model request used this fail-closed reservation formula:

```text
((UTF8_SERIALIZED_REQUEST_BYTES + 2048) * USD 0.000003)
+ (MAX_OUTPUT_TOKENS * USD 0.000015)
```

With the former 1,600-token maximum, the output component alone was USD 0.024. The exact
historical request bytes and proposed total were not persisted and are not invented; the
known fact is that the projection exceeded USD 0.15. The guard now carries current,
attempted, remaining and projected costs in a bounded exception for future diagnostics.
The 03B3 diagnostic policy lowers maximum output to 512 tokens (USD 0.00768 maximum output
reservation), consistent with observed tool turns of 113-201 tokens. Call count and USD 0.15
ceilings are unchanged. The conservative input-byte bound, reserve-before-call behavior,
failed-call retention and actual-usage reconciliation remain fail closed.

### Offline proof

RED/GREEN tests cover exact/current-run capability resolution, unknown/fabricated/prior-run
rejection, canonical equivalence, citation retention, SSRF non-bypass, safe diagnostics and
recovery without a second search. Budget tests cover one-time reconciliation/commit,
non-mutating over-cap rejection, exact projected-cost diagnostics and the explicit integer
reservation formula.

An independent offline review found three additional issues before commit: budget amounts
were not propagated into run diagnostics, registry identity had been used as the fetch URL,
an abnormal offline registry could exceed the diagnostic count schema, and successful
zero-cost fetch reservations remained marked open. Focused RED/GREEN
tests now prove that budget projections reach the bounded trace, the original provider URL
enters the fetch request while canonicalization remains registry-only, and reported counts
remain within schema bounds. Successful fetches now close their receipts while failed fetches
retain theirs. Fragment removal occurs inside the HTTPS fetch transport while the original
discovered URL remains provenance.

A REPLAY-mode Strands test now executes:

```text
AGENT_SEARCH -> SEARCH_CANDIDATES -> rejected fabricated reference
-> valid current candidate selected -> SOURCE_FETCHED -> CLAIM_EXTRACTED
-> EVIDENCE_RECORDED -> DETERMINISTIC_ELIGIBILITY -> DETERMINISTIC_DECISION
```

It performs one recorded search, zero AWS/Bedrock calls, recovers without another search,
admits one fetched-source EvidenceRecord, links that record to a critical technology rule,
and returns deterministic `FAIL / SKIP` for the synthetic mismatch. The result is not tuned
to APPLY. Search snippets remain unable to prove hard eligibility, citations survive, and
the trace contains action events rather than model reasoning.

The final offline suite contains **556 passing tests** (19 above the B3E baseline), with the
two existing upstream dependency deprecation warnings unchanged.

Final gate counts, exact commit and push state are recorded in the Result Packet. The next
step is owner authorization for one live proof run of this repaired boundary; no live claim
is made by this offline checkpoint.

# Previous checkpoint: live handoff localized (03B3D BLOCKED)

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
