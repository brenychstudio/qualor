# QUALOR-03B3I structured extraction JSON contract plan

**Goal:** Close the proven structured-extraction output boundary offline with one strict,
JSON-native wire contract while preserving immutable domain values, evidence admission,
deterministic authority, and the existing live budget limits.

**Authority:** `docs/00_CANONICAL_BRIEF_UA.md`, owner task QUALOR-03B3I, and the sanitized
03B3H trace. No live run, IAM mutation, or AWS resource mutation is authorized.

## Contract forensic and RED

Inspect the Pydantic contracts, emitted JSON Schema, Bedrock Converse service model, direct
provider response parser, and immutable claim types. Reproduce the missing-wrapper error,
the live `claims:tuple_type` error class, canonical wrapped-array behavior, malformed/extra
fields, empty findings, and UNKNOWN. Record the exact difference between Python-domain
tuples and JSON arrays. Add focused tests before implementation and retain their RED output.

## Minimal wire correction

Add one `ExtractedClaimBatchTransport` with required top-level object wrapper and native
JSON `claims` array. Convert it once to immutable `ExtractedClaimBatch.claims` tuple after
strict validation. Reject bare arrays, missing wrappers, non-array collections, malformed
claims, and extra fields. Do not add coercive repair, `Any`, heuristic parsing, or a format
repair model call.

Use the installed Bedrock Converse native `outputConfig.textFormat` JSON Schema boundary
for the isolated extraction request. Project the richer local Pydantic schema onto Bedrock's
documented JSON Schema subset while retaining all local validation constraints. Parse the
single structured text result with the one canonical transport validator. Continue enforcing
exact current-run source ID/URL and bound the complete claims-plus-observations result before
evidence admission. The extraction request still receives one bounded source window and no
Strands conversation or agent tools.

## Evidence and authority replay

Run a recorded native-JSON extraction through the existing `record_evidence` implementation,
then deterministic eligibility and decision. Prove one EvidenceRecord, one critical rule
reference, `FAIL / SKIP` for the owned mismatch, prompt-injection containment, zero offline
AWS calls, and unchanged final authority.

## Cost and verification

Recompute the isolated native-schema request reservation under 512 output tokens and the
USD 0.20 acceptance ceiling. Export schemas/types, run Ruff, the complete pytest suite,
`scripts/verify.ps1`, read-only `scripts/aws-preflight.ps1`, npm clean install/build,
whitespace/status checks, and the tracked secret scan. Commit and push only this contract
fix, tests, generated contracts, plan, and checkpoint documentation.
