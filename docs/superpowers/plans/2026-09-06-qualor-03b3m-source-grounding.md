# QUALOR-03B3M Deterministic Source Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace model-authored evidence excerpts at the Bedrock JSON boundary with runtime-resolved, source-scoped evidence-span capabilities.

**Architecture:** `SourceDocument.text` remains the canonical evidence representation. A per-extractor registry deterministically segments the bounded extraction window and assigns HMAC-derived opaque span IDs. Bedrock returns a span ID; the runtime resolves it to exact source text before constructing the unchanged immutable `ExtractedClaim`, so existing evidence validation remains authoritative.

**Tech Stack:** Python 3.12, Pydantic v2, boto3 Bedrock Converse JSON Schema, pytest, Ruff.

**Spec:** Owner-approved task `QUALOR-03B3M — DETERMINISTIC CLAIM-TO-SOURCE GROUNDING`.

## Global Constraints

- Offline only: zero Bedrock inference, Web Search, paid AWS calls, IAM, or AWS resource changes.
- Preserve `EXTRACTION_MAX_OUTPUT_TOKENS=1024`, two claims per extraction, exact source grounding, SSRF boundaries, prompt-injection containment, and deterministic verdict authority.
- Do not accept fuzzy text, same-domain inference, model-authored quote repair, arbitrary offsets, cross-source spans, or cross-run spans.
- Preserve canonical brief bytes and do not begin QUALOR-04A.

---

### Task 1: Evidence-span capability

**Files:**
- Create: `src/qualor/runtime/spans.py`
- Create: `tests/runtime/test_evidence_spans.py`

**Interfaces:**
- Consumes: `SourceDocument.id`, canonical `SourceDocument.text`, a bounded focus window.
- Produces: `EvidenceSpan`, `EvidenceSpanRegistry.register(source, focus)`, and `EvidenceSpanRegistry.resolve(source_id, span_id)`.

- [ ] Write G01/G03–G10/G14–G16 tests first. Assert every span is an exact source slice, no span exceeds the explicit byte cap, IDs are opaque, and invented/cross-source/cross-registry IDs fail.
- [ ] Run the focused tests and confirm RED because the span module does not exist.
- [ ] Implement deterministic bounded block segmentation and extractor-local HMAC IDs. Keep citation identity on `SourceDocument`; never place arbitrary offsets under model authority.
- [ ] Run the focused tests and confirm GREEN.

### Task 2: JSON transport and exact grounding

**Files:**
- Modify: `src/qualor/runtime/extraction.py`
- Modify: `src/qualor/runtime/claims.py`
- Modify: `src/qualor/runtime/loop.py`
- Modify: `src/qualor/runtime/run_models.py`
- Modify: `src/qualor/domain/evidence.py`
- Modify: `tests/runtime/test_extraction_wire.py`
- Modify: `tests/runtime/test_context_extraction.py`
- Modify: `tests/runtime/test_extraction_receipts.py`

**Interfaces:**
- Consumes: canonical wrapped JSON with `supporting_span_id` selected from the current extraction request.
- Produces: immutable domain `ExtractedClaim.excerpt` resolved from registered `EvidenceSpan.exact_text`; runtime EvidenceRecord retains optional source ID for backward-compatible V1 records.

- [ ] Add RED tests for the new wire schema, current-source resolution, paraphrase rejection, full native replay to EvidenceRecord, and `SOURCE_SPAN_SELECTED` trace ordering.
- [ ] Run focused tests and confirm failures are caused by the old model-authored `excerpt` contract.
- [ ] Replace only the JSON transport claim with span-ID authority; resolve before domain construction. Leave `validate_claim` substring/value semantics unchanged.
- [ ] Add the judge-safe span-selection trace event and run the focused tests to GREEN.

### Task 3: Budget, documentation, and complete verification

**Files:**
- Modify: `scripts/extraction-budget-report.py`
- Modify: `docs/status/QUALOR-03.md`

**Interfaces:**
- Consumes: actual labelled extraction request and existing five-call projection.
- Produces: request-byte overhead and projected run total under USD 0.20.

- [ ] Measure labelled request size using owned synthetic source data; assert the projected total remains at or below USD 0.20 without changing the cap or token/call limits.
- [ ] Run live-like replay and prove one exact runtime excerpt, EvidenceRecord, linked critical rule, deterministic decision, readable trace, and zero AWS calls.
- [ ] Record the proven root cause, unavailable historical excerpts, representation policy, span authority, measured overhead, and limitations in the status document.
- [ ] Run `scripts/verify.ps1`, read-only `scripts/aws-preflight.ps1`, schema/type generation, Ruff, pytest, frontend install/build, whitespace and secret scans.
- [ ] Commit `fix: ground extracted claims to source spans`, push `qualor-03-live-agent`, and report exact HEADs. Do not merge.
