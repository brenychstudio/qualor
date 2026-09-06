# QUALOR-03B3K: extraction envelope and measured output budget

Canonical source: `docs/00_CANONICAL_BRIEF_UA.md`, unchanged. Baseline:
`b8be6658ed11d278ab377e47a5d021160ecb624b`, `qualor-03-live-agent`.
Scope is offline envelope observability and focused extraction output policy.
No live proof, IAM, infrastructure, evidence admission redesign or QUALOR-04A.

1. Verify clean baseline, Ruff, 584 tests and verification script. Inspect the
   ignored bounded J report and committed Converse/extraction path before edits.
   Distinguish absent historical stop metadata from evidence of truncation.
2. RED: feed recorded Converse envelopes through `BedrockClaimExtractor.extract`.
   Require stop semantics before JSON/schema validation, safe receipt counters,
   isolated output policy, and unchanged evidence handoff. Initial 12 cases must
   fail against the baseline adapter; then implement the smallest adapter change.
3. Add frozen `StructuredExtractionReceipt`, returned by `response_metadata` with
   transient text blocks. Retain only known stop/type names, numeric usage/latency,
   byte counts, validation states and a digest. Keep six receipts in run metrics.
   Distinguish truncation, provider termination, JSON failure and schema failure;
   route bounded reason codes through the existing rejection trace.
4. Measure owned distinct canonical batches with 1/2/3/5 claims using the existing
   conservative UTF-8 byte token bound. Keep two claims per extraction. Separate
   `STRANDS_MAX_OUTPUT_TOKENS` from `EXTRACTION_MAX_OUTPUT_TOKENS`; select extraction
   allowance from the measurements and retain the shared fail-closed reservation
   guard. Report a conditional five-call projection, never a promised final bill.
5. GREEN and replay: native wrapped JSON through the actual adapter, current-run
   source capability, existing claim admission, linked critical evidence, and
   deterministic decision. Assert receipt survives `run_agent` metrics. Cover
   malformed output, invalid JSON, invalid schema, filtered/guardrail/context
   stops, sensitive payload exclusion, oversized batches and true budget excess.
6. Run full Ruff/Pytest, read-only AWS preflight, schema/type regeneration, frontend
   install/build and whitespace/secret checks. Commit scoped code/tests/docs, run
   the clean-tree verification script, then push the exact branch. No live run.

Acceptance mapping: R01-R09 envelope/receipt tests; R10-R15 measured batches,
independent limits and guard tests; R16-R18 native adapter and full Strands replay.
Existing prompt-injection, capability and evidence tests remain regression gates.
Future live validation needs separate owner authorization; historical missing
stopReason cannot be recovered by another inference in this task.
