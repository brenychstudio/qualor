# Coverage-Driven Canonical Evidence Acquisition / Compiler

## Authority and document status

Task: `QUALOR-LIVE-PRODUCTION-TASK-5F-SPEC`.
Implementation scope described here: Task 5F; implementation is not authorized by
this documentation commit. Written-spec owner review precedes an implementation plan.

Baseline: `feature/qualor-live-production` at
`e915385900e65de389a05b61e5f206c031ef2372`.

Owner-approved change record: the Task 5F-SPEC instruction explicitly approves
the three design sections: acquisition architecture; canonical rule/fact authority;
and offline acceptance with the fourth-paid-run gate. This document records those
decisions. It does not alter the foundation brief, completion policy, deployment
architecture, or authorization to spend.

The foundation remains [00_CANONICAL_BRIEF_UA.md](../../00_CANONICAL_BRIEF_UA.md).
Its preserved SHA-256 is
`440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`.
The [Task 1 graph design](2026-09-12-qualor-live-production-task-1-design.md)
continues to govern opportunity identity/versioning, selected-decision authority,
workspace capture, and persistence failure handling.

Normative requirements use MUST and MUST NOT. Conceptual contract names below
describe responsibilities, not permission to duplicate existing domain models.
Recorded historical observations and future acceptance requirements are distinct.

## 2026-09-14 owner-authorized cost envelope amendment

This amendment has precedence over every cost-cap statement below for current
Task 5F work, from Task 12B onward. It changes the authorized maximum potential
LIVE spend only.

Every `USD 0.20` cost-cap statement in the remainder of this document describes
the original `QUALOR_03B3` authorization. That authorization remains intact and
is not retroactively restated; it was correct before the Task 12 measurement.

Task 12 measured the conservative worst case of the exact Task 11 request
sequence using the production estimator and production reservation authorities,
with no reconciliation assumed:

| Component | Measured reservation (USD) |
| --- | --- |
| 9 model requests (2 planning, 7 extraction) | 0.297591 |
| 1 web search (`WEB_SEARCH_RESERVED_COST_USD`) | 0.009000 |
| 1 official-source fetch (production default) | 0.000000 |
| **Canonical worst case** | **0.306591** |

That exceeds `QUALOR_03B3`'s USD 0.20 ceiling by USD 0.106591, and the guard
refused the sixth model request. The measurement is accepted evidence.

On 2026-09-14 the owner authorized a new, explicitly named current policy:

- `QUALOR_5F` inference ceiling: 9 model calls (unchanged).
- `QUALOR_5F` cost ceiling: USD 0.35.
- Measured canonical worst case: USD 0.306591.
- Conservative headroom: USD 0.043409.

No semantic, extraction, coverage, scheduler, evaluator, or completion limit
changes. `MAX_EXTRACTED_CLAIMS_PER_CALL`, `MAX_STEPS`, model and extraction
output-token bounds, and search/fetch limits all remain frozen. Requests MUST
NOT be altered to lower cost.

A fourth paid LIVE run still requires separate explicit owner authorization.
This amendment authorizes the ceiling, not spending it.

## 1. Context and problem

Tasks 5 through 5D established real identity/access, AgentCore network search,
official-source fetching, Bedrock structured extraction, LIVE run/event persistence,
and physical budget/failure guards. They did not establish a successful real
authoritative opportunity graph.

| Paid run | Bedrock calls | Retained UNKNOWN observations | Authoritative canonical claims | Termination | Runtime-reconciled USD |
|---|---:|---:|---:|---|---:|
| 1 | 6 | 1 | 0 | BUDGET_EXHAUSTED | 0.080499 |
| 2 | 7 | 2 | 0 | TOOL_FAILURE_BOUND_REACHED | 0.098664 |
| 3 | 9 | 3 | 0 | BUDGET_EXHAUSTED | 0.134835 |

These costs are retained runtime estimates, not independent billing confirmation.
Task 5C correctly separated semantic evidence rejection from operational failure.
The observations called validated claims in earlier summaries are not supported
canonical facts; UNKNOWN observations MUST NOT be counted as authoritative yield.

Task 5E found the following remaining architectural barriers:

1. All four Run 3 extraction batches registered the identical ordered 15-span pool.
2. Extraction uses an approximately 9 KB window; relevant archived clauses occur
   beyond its initial region. Literal broad-focus lookup can repeatedly select it.
3. Exact controlled grammars reject ordinary official-source formulations.
4. Several critical semantic families lack executable LIVE rule adapters.
5. Planner inference repeats unresolved-field knowledge already owned by runtime.
6. Source/section exhaustion is not represented explicitly.
7. Another official source is technically reachable, but deterministic exhaustion
   does not currently trigger a research pivot.
8. Increasing inference limits alone is not justified.

Historical limitations MUST remain explicit: Run 3 did not retain exact per-call
receipts, proposed values, or source-span text sufficient for a complete transcript.
The dated archived source demonstrates compiler/window limitations; it is not
asserted byte-identical to Run 3. No historical value or call attribution is invented.

## 2. Goals, non-goals, and invariants

Task 5F MUST make relevant sections reachable, schedule their inspection without
mechanical model planning, and compile safely supported source clauses into typed
canonical rules that the existing deterministic engines can evaluate. It MUST
prove that chain offline before another paid-run authorization is considered.

Task 5F MUST preserve:

- UNKNOWN != PASS; AMBIGUOUS != PASS; UNSUPPORTED != PASS.
- Strategy is prioritization, not probability of winning.
- Server/runtime canonical evidence and deterministic decision authority.
- No frontend eligibility, evidence, recommendation, or approval policy.
- One runtime-owned decision bundle per authority revision; persistence MUST NOT
  recompute a second decision or select a different approval authority.
- Truthful LIVE, REPLAY, and FIXTURE boundaries; no fake successful partial graph.
- Version-bound, expiring, single-use human approval at the consequential boundary.
- Immutable Application Packs for review; no external submission in V1.
- Source security, freshness, contradiction handling, and physical budget guards.
- No Devpost-specific parser, AWS Agents for Humans parser, contest-name matching,
  organizer-name branching, or wording-hash-based runtime behavior.

Explicit non-goals: automatic second-source research; extraction batches larger
than two; inference ceiling above nine; cost cap above USD 0.20; completion-policy
changes; new UI; hosted-security redesign; deployment; infrastructure changes;
paid execution; universal legal interpretation; a new parallel decision stack.

## 3. Architecture and data flow

Official Source -> Deterministic Section Index -> Coverage State -> Deterministic
Section Scheduler -> Bounded LLM Candidate Extraction -> Local Clause Validation
-> Typed Canonical Adapters -> OpportunityRuleSet.

OpportunityRuleSet + independently supplied ApplicantFacts / ProjectFacts
-> existing Deterministic Eligibility Engine -> existing Decision authority.

The model interprets natural-language passages and proposes candidates. It MUST NOT
author eligibility verdicts, manufacture applicant facts, drop conditions, rewrite
quotes to satisfy a normalizer, or promote its own confidence into authority.
One Strands research agent remains responsible for meaningful research reasoning;
the deterministic scheduler removes only decisions derivable from known state.

Task 5F operates on the already-fetched official source. Initial discovery/fetch
continues through existing bounded providers and host admission. No source is
admitted because the browser supplied its URL or a heading matched a category.

## 4. Section Index contract

Each logical section MUST expose:

| Field | Meaning |
|---|---|
| section_id | Deterministic identity within an immutable source revision |
| source_id | Existing source authority reference |
| heading | Exact source heading, or absent when no heading exists |
| start_offset / end_offset | Half-open offsets in canonical fetched text |
| span_ids[] | Runtime-issued exact-text capabilities, not model-created IDs |
| section_hash | Digest of the exact section text |
| candidate_categories[] | Deterministic routing hints, never factual support |

Section identity MUST bind source revision/content hash, offsets, section text hash,
and indexer version. Identical input and indexer version MUST give identical index
results. Span capabilities remain run-scoped even when section identities are stable.
The underlying source retains original/final URL, retrieved_at, content hash, and
source authority. Offsets MUST resolve to exact text without quote rewriting.

The index MUST cover the entire retained canonical source, not only its first
extraction window. It MUST use generic headings, paragraphs, lists, and boundaries.
For example, submission-period headings route toward deadline; eligibility headings
toward entrant/geography/legal-entity; submission requirements toward project policy,
license, and technology. These examples are not a document-template allowlist.
Unclassified sections MUST remain discoverable through bounded deterministic
fallback coverage rather than being silently discarded.

An oversized section MUST be represented by bounded child sections with stable
identities and parent context. Child boundaries MUST NOT hide governing definitions,
qualifiers, exceptions, negation, or cross-references. If the required context cannot
fit safely, the affected claim MUST remain unresolved with a diagnostic reason.
Reusing necessary context is allowed; repeating an identical extraction window for
the same section/category attempt is not. Renaming a section MUST NOT evade deduplication.

## 5. Coverage State and transitions

Coverage MUST distinguish acquisition progress from semantic support and eligibility.
It MUST track each critical category and its source-revision/section attempt history.
Critical categories remain deadline, entrant_type, geography, legal_entity,
project_policy, license, required_technology, financial_support, and reward_conditions.

Required acquisition states and transitions:

| State | Entry condition | Permitted next state / condition |
|---|---|---|
| UNSEEN | No relevant section inspected or scheduled | SECTION_AVAILABLE when a candidate section is indexed; EXHAUSTED only after index/fallback coverage proves no remaining section |
| SECTION_AVAILABLE | At least one relevant unattempted section exists | EXTRACTION_ATTEMPTED when a job starts |
| EXTRACTION_ATTEMPTED | Attempt recorded before invoking extraction | SUPPORTED, AMBIGUOUS, or UNSUPPORTED after validation; bounded operational failure retains the attempt and failure reason |
| SUPPORTED | Required source clauses for the category have safely compiled authority, without unresolved source interpretation/conflict | Reassess on additional conflicting evidence or source revision; this is not an eligibility verdict |
| AMBIGUOUS | Interpretation, applicability, or conflicting source language cannot be resolved safely | SECTION_AVAILABLE if another relevant section remains; otherwise EXHAUSTED |
| UNSUPPORTED | Candidate was rejected or returned UNKNOWN/no support | SECTION_AVAILABLE if another relevant section remains; otherwise EXHAUSTED |
| EXHAUSTED | No eligible unattempted relevant section remains for this source revision and category | Reopened only by a newly admitted source revision, not another model focus string |

For multi-section categories, individual supported clauses MUST be retained while
the category remains unresolved until all relevant governing context is accounted
for. A conditional rule can be semantically supported while its required applicant
fact is unknown. Such support MUST NOT imply applicant compliance.

After each job, the scheduler MUST derive the category's next acquisition state
from its retained per-section outcomes: SECTION_AVAILABLE when relevant unattempted
sections remain; SUPPORTED when source interpretation is complete and supported;
otherwise EXHAUSTED with the unresolved outcomes preserved. AMBIGUOUS and UNSUPPORTED
outcome transitions MUST be recorded before this scheduling transition. An operational
failure consumes that dispatched pair's attempt without marking it inspected
successfully; it then follows the same next-section/exhaustion calculation unless
an existing run guard has terminated execution.

EXHAUSTED is an acquisition state, not an evidence verdict. The last semantic
outcomes, partial supported rules, unresolved dependencies, and reasons MUST remain
attached. A model UNKNOWN outcome MUST retain UNKNOWN explicitly even when routed
through the UNSUPPORTED acquisition state. No state transition creates NOT_APPLICABLE
from silence. Every transition MUST record its deterministic cause and revision.

## 6. Deterministic Section Scheduler

Inputs: CoverageState, SectionIndex, attempt history, budget state, authority revision.
Output: one bounded ExtractionJob, or a bounded explanation that no job is eligible.

ExtractionJob MUST identify source_id, section_id, categories[], and the exact span
capability/context admitted for that job. Jobs MUST use the production extraction
request builder, not an alternative unconstrained model channel.

The scheduler MUST:

1. Select unresolved categories and relevant unattempted sections deterministically,
   using canonical category order and source offsets/section identity for stable ties.
2. Record a section/category/source-revision attempt before dispatch. A second
   attempt on that pair without source revision MUST be refused, including after
   schema failure; no hidden repair/retry loop is added.
3. Inspect relevant sections of the fetched source before considering a research
   pivot; distinguish not-inspected from inspected-without-authority.
4. Avoid model calls whose only purpose is identifying already-known missing fields.
5. Reevaluate after authoritative changes through the existing revision-cached
   decision path; reuse the result when authority has not changed.
6. Respect inference, reservation, step, no-progress, and operational-failure limits.
   Exhaustion MUST NOT reset their counters or mint new budget.
7. Expose pivot eligibility only when coverage is exhausted or genuinely insufficient.
   Task 5F MUST NOT automatically execute a second-source search/fetch. Its scheduled
   acquisition path returns a bounded unresolved result through existing termination
   handling. Implementing automatic pivot execution is deferred.

Attempt history and deterministic section exhaustion supplement, not remove or raise,
existing no-progress protection. A change in model focus, confidence, or requested
wording is not a source revision. A budget-blocked undispatched job MUST be identified
as blocked, not falsely recorded as a completed inspection.

## 7. Candidate extraction and local clause validation

Extractor input MUST contain source_id, section_id, allowed_categories[], and bounded
section spans/text. Arbitrary broad focus MUST NOT be the sole window selector.
MAX_EXTRACTED_CLAIMS_PER_CALL remains 2, enforced by schema and runtime.

Each CandidateClaim MUST retain category, proposed_value, source_id, section_id,
span_id/span_ids, exact quote, qualifiers[], exceptions[], and confidence_class.
Confidence is model commentary, not support or an eligibility probability.
Candidates outside allowed categories or with invalid capabilities MUST be rejected.

Local validation MUST check exact quote membership, offsets, source/section/span
binding, complete applicable clause context, and the proposed interpretation.
Model-supplied empty qualifiers/exceptions arrays are not proof that none exist.
Validation MUST compare governing context, including inherited and referenced
conditions. An unrelated qualifier elsewhere in the document MUST NOT invalidate an
independent clause solely by keyword presence; an applicable remote exception MUST
NOT be ignored. Unresolvable applicability remains UNKNOWN/AMBIGUOUS.

No adapter may rewrite the source quotation into a preferred grammar. Normalized
values and source quotes are separate. Multiple spans MUST retain their identities
and order; artificial concatenation MUST NOT be represented as a verbatim excerpt.

## 8. Typed canonical adapters and authority separation

Adapters map source-grounded candidates to existing typed canonical rule semantics,
not to PASS/FAIL. OpportunityRuleSet denotes that compiled collection, with evidence
links and unresolved conditions; it is not a second decision engine.

| Adapter | Canonical responsibility and safety boundary |
|---|---|
| DeadlineAdapter | Absolute deadline/interval with deterministically resolved timezone; preserve original date language and retrieval time. Naive, ambiguous, conflicting, or unresolvable timezone values remain UNKNOWN; never rebase a deadline. |
| EntrantTypeAdapter | Permitted entrant alternatives and attached conditions, including age or representation; a permitted type alone does not establish a user's eligibility. |
| GeographyRuleAdapter | Explicit allowed/excluded scopes and open-ended legal restrictions; retain external-check requirements and territorial granularity. |
| LegalEntityAdapter | Individual/team/entity alternatives and incorporation/representation predicates; no inferred incorporation. |
| ProjectPolicyAdapter | New/existing work, relevant time interval, reuse/disclosure conditions; project provenance remains a separate fact. |
| LicenseAdapter | Allowed license alternatives and required license/publication conditions; no inference that the project complies. |
| TechnologyRequirementAdapter | Mandatory technology predicates, alternatives, and applicability; distinguish optional deployment or scoring benefits from requirements. |
| FinancialSupportAdapter | Funding/preferential-support restrictions, timing, and exceptions; no inferred funding history or legal clearance. |
| RewardConditionAdapter | Award, verification, payment, tax, and benefit conditions; no guaranteed award, no prize-pool-as-individual-reward, no credits-as-cash. |

All adapters MUST preserve qualifiers, exceptions, source_id, section_id, span_ids,
and provenance. Supported conjunctions/alternatives MUST use existing deterministic
semantics without changing AND to OR or flattening conditions. An interpretation
not safely representable by supported operators remains unresolved; a model verdict
is not a fallback. New executable mappings MUST feed existing evaluator contracts.

ApplicantFacts and ProjectFacts denote separately versioned inputs compatible with
the existing FounderProfile, ProjectProfile, and StudioInput authorities, not new
parallel profile stores. Conceptual provenance classes OWNER_PROVIDED, PROJECT_STATE,
and VERIFIED_ACCOUNT_STATE MUST map explicitly to the existing provenance model.
Verification scope/time MUST accompany verified facts; an AWS login alone proves
neither funding eligibility nor legal compliance.

Competition rules MUST NOT become the source of residence, applicant form,
incorporation, project newness, actual technology use, license compliance, or support
history. Unknown facts remain unknown. Official rules describe predicates; the
deterministic engine compares them with independently sourced facts.

Geography canonical representation MUST retain explicitly_allowed[],
explicitly_excluded[], open_ended_legal_restriction,
requires_external_compliance_check, qualifiers[], exceptions[], and provenance.
When an open-ended restriction exists, absence from an exclusion list MUST NOT
produce PASS. A missing compliance fact leaves REVIEW_REQUIRED where required by
existing eligibility semantics; Task 5F performs no automatic compliance lookup.

Task 1 remains authoritative for source-grounded OpportunityRecord metadata,
identity, versions and evidence. Scheduling hints MUST NOT populate organizer,
program, edition, or any other opportunity field. Missing metadata remains UNKNOWN.

## 9. Failure semantics and diagnostic receipts

Task 5C's distinction MUST remain intact:

- Semantic UNSUPPORTED, AMBIGUOUS, UNKNOWN, or unresolved applicability MUST retain
  bounded reasons and non-authority. They MUST NOT increment operational failures
  solely for lack of semantic support.
- Provider/network failure, malformed schema, invalid invocation, missing or forged
  source/section/span references, and genuine tool exceptions remain operational
  failures. Three operational failures retain TOOL_FAILURE_BOUND_REACHED.
- Budget exhaustion remains budget exhaustion. Inference ceiling 9, cost cap USD
  0.20, existing max-step and no-progress bounds MUST NOT increase or be bypassed.
- No automatic provider, schema-repair, or paid-run retry is introduced.

Bounded safe receipts MUST survive terminal run persistence, including failed runs.
They MUST use existing run/event capture rather than depend only on returned
in-memory metrics. They are diagnostics, not successful graph authority.

Each receipt MUST retain call_index/call_slot, role, source_id, section_id,
requested_categories[], proposal_count, supported_count, conditional_count,
ambiguous_count, unsupported_count, rejection_codes[], authority_revision_before,
and authority_revision_after. Non-extraction calls have absent source/section fields
where inapplicable, rather than invented values. UNKNOWN count, duplicate suppression,
and execution status MUST also be explicit so proposal accounting is reconcilable.
Conditional_count is a documented subset of supported_count, not extra proposals.

Call slots MUST distinguish planned, physically dispatched, and budget-blocked
requests. Blocked slots MUST NOT inflate paid call counts. LIVE receipts additionally
retain cost_reserved and cost_reconciled where available, with unknown reconciliation
explicit rather than fabricated. Raw provider exception strings are prohibited.

Receipt count MUST be bounded by existing physical-call and attempt/step limits;
field/category arrays by declared schemas; rejection codes by a fixed safe vocabulary.
Diagnostic payloads MUST NOT contain credentials, proxy/action secrets, private owner
facts, raw prompts, full model responses, full source bodies, or chain-of-thought.
Exact evidence quotes remain in the existing protected evidence authority, not logs.

## 10. Completion and persistence are unchanged

Compiler correctness and permission to persist a successful graph are separate gates.
At this baseline, runtime completion uses existing all-candidate eligibility PASS
or all-candidate FAIL conditions; WorkspaceRunCapture validates the selected bundle
and its linkage. Task 5F MUST NOT alter those conditions or their mappings.

Eligibility outcomes PASS, FAIL, and REVIEW_REQUIRED are distinct from decision
recommendations such as WATCH. Acceptance MUST report both without treating WATCH
as a new eligibility state. No fixed positive verdict is required.

Case A: compiler proof reaches a truthful graph that existing completion semantics
can persist. Fourth-run eligibility may be considered only after all other gates.

Case B: compiler proof is correct, but legitimate REVIEW_REQUIRED cannot persist
as a successful authoritative graph under current policy. The fourth paid run stays
blocked. A separate Task 5G Completion Semantics Design is required before changing
that policy. Task 5F MUST NOT relabel the result, lower coverage, manufacture a hard
failure, or write a fake successful graph to escape Case B.

Successful persistence MUST consume the same revision-bound runtime bundle. Existing
selected-decision links, observer isolation, command-boundary capture verification,
restart behavior, approvals, and immutable packs remain unchanged.

## 11. Archived-source offline acceptance authority

The canonical offline input is the already archived official capture referenced by
the [real-source design](2026-09-12-qualor-killer-demo-real-source-design.md).
Resolve it from the existing ignored `killer-demo-real-source/source-manifest.json`
artifact directory, not from a fresh network response. Missing artifacts or hash
mismatch MUST block acceptance; no silent download, seed, or substitution is allowed.

| Manifest source | Existing raw artifact | Retrieved UTC | Required raw SHA-256 |
|---|---|---|---|
| SRC-OFFICIAL-RULES | official-rules.raw | 2026-09-12T11:25:52Z | e3f7640c0bd1e78e3858d7d5a2dfb78bb560cac9b7982c29c5e57796116794a5 |
| SRC-OFFICIAL-OVERVIEW | official-overview.raw | 2026-09-12T11:25:54Z | d7b4cd7f1c36e43631028da8a0a6a2c39fb47090d4cec1f1fe0e1fefdbd52dce |

The rules capture is the required section/compiler acceptance input. The overview
is a separately identified archive for comparison, not authorization for automatic
multi-source acquisition or stronger runtime source classification. Manifest hashes
bind test inputs only; adapters MUST NOT branch on those hashes or source names.
Full archived pages and private run/profile artifacts MUST NOT be committed.

The harness MUST parse verified archived raw bytes through the production canonical
text path and retain their original retrieval/provenance identity. A declared fixed
test clock may make offline freshness checks reproducible; it MUST NOT move source
deadlines or be represented as a current LIVE observation.

A controlled extractor may emit candidate claims with exact section/span/quote and
qualifiers/exceptions. It MUST NOT inject final RuleCandidates, RuleSets, eligibility,
or decisions. Separate fixed ApplicantFacts/ProjectFacts MUST have explicit independent
provenance. This is offline production-compiler acceptance, not real LIVE execution
or a REPLAY seed. Existing mode labels MUST remain truthful and unchanged.

## 12. Offline acceptance contract

The required end-to-end path is archived source -> production section index ->
coverage -> scheduler -> controlled candidate extraction -> production validation
-> typed adapters -> OpportunityRuleSet -> independent facts -> deterministic
eligibility/decision engines. Starting a test at a manually authored RuleSet fails.

### Section coverage and scheduling

Acceptance MUST reach deadline/submission period, entrant eligibility, geography,
legal entity/individual/team eligibility, new-project policy, license, required
technology, financial/preferential support, and reward/verification sections.

Required results:

- DEFAULT_9KB_WINDOW_ONLY=NO; REPEATED_IDENTICAL_WINDOW=NO.
- NEW_PROJECT_SECTION_REACHED=YES; LICENSE_SECTION_REACHED=YES.
- TECHNOLOGY_SECTION_REACHED=YES; FINANCIAL_SUPPORT_SECTION_REACHED=YES.
- REWARD_CONDITIONS_SECTION_REACHED=YES.
- DUPLICATE_SECTION_CATEGORY_ATTEMPTS=0.
- EXTRACTION_AFTER_SECTION_EXHAUSTED=0.
- MODEL_CALL_USED_ONLY_TO_DISCOVER_KNOWN_MISSING_FIELDS=0.

An attempted duplicate without source revision MUST be refused and fails the
acceptance sequence. Document coverage MUST NOT be reduced to fit the call target.
Dedicated negative tests MUST separately prove refusal; their intentionally invalid
inputs are not counted as a valid scheduler-produced acceptance sequence.

### Canonical authority and clause integrity

AUTHORITATIVE_CANONICAL_FACTS > 0 and EXECUTABLE_RULES > 0 are mandatory minima.
Retained UNKNOWN observations and routing hints MUST NOT enter those counts.
Where the archive safely supports deadline, entrant type, legal entity, project
policy, license, and required technology, acceptance MUST demonstrate their typed
authority; inability to do so requires an explicit source/adapter limitation, not
an unexplained minimum-count PASS. Geography, financial-support and reward conditions
may remain conditional/ambiguous/unknown when the source dictates it.

For every canonical rule: qualifiers, exceptions, provenance, source_id, section_id,
and span_ids MUST survive. Require EXCEPTIONS_DROPPED=0, QUALIFIERS_DROPPED=0,
SOURCELESS_RULES=0, OWNER_FACTS_INFERRED_FROM_RULES=0, and
PROJECT_FACTS_INFERRED_FROM_RULES=0.

Require DECISION_DERIVED_FROM_CANONICAL_AUTHORITY=YES. Tests MUST NOT prescribe APPLY,
PREPARE, or eligibility PASS as success. Negative/uncertain cases MUST prove that
UNKNOWN, AMBIGUOUS and UNSUPPORTED cannot become PASS. The existing persistence
gate, not a test shortcut, determines whether the computed result becomes a graph.

### Call and cost simulation

Offline production scheduling MUST account for every expected physical model call:
initial research/planning, extraction, and any remaining model work. Require
EXPECTED_LIVE_CALLS <= 9 with MAX_EXTRACTED_CLAIMS_PER_CALL=2 unchanged.
Search/fetch and tools remain subject to existing separate guards. No mocked
zero-cost planner or omitted request may be used to satisfy the accounting.

The harness MUST construct the proposed production requests and use existing
production reservation logic without network calls. It MUST retain model/config
identity, request-size and output bounds, sequence order, and all guard-relevant
non-inference reservations. All reachable bounded branches claimed by the acceptance
sequence MUST be covered; an unmeasured branch cannot receive a cost PASS.

Report PROJECTED_RESERVED_COST as the aggregate reservations for the measured
sequence; PROJECTED_WORST_CASE_COST as the highest bounded total across measured
accepted branches without assuming favorable token reconciliation; and
REMAINING_HEADROOM as USD 0.20 minus that worst-case bound. Simulate each reservation
transition, not only a final average. Require PROJECTED_SEQUENCE_FITS_USD_0_20_GUARD=YES.
If the existing guard cannot admit the sequence, acceptance fails without increasing
limits, assuming linear historic token costs, or hardcoding a desired estimate.

### Genericity, diagnostics, and regressions

Require DEVPOST_SPECIFIC_BRANCHES=0,
AWS_AGENTS_FOR_HUMANS_SPECIFIC_BRANCHES=0, and CONTEST_NAME_MATCHING=0.
Additional independently authored generic examples MUST exercise the same adapter
families, including qualifiers, negation, alternatives, remote exceptions and
unresolved facts. Archive-specific test inputs are not runtime policy.

Future implementation MUST use RED/GREEN tests and preserve FIXTURE, REPLAY, LIVE
security, Task 1 persistence, hosted run/UI/capability flows, budgets, three-failure
termination, approval expiry/versioning/idempotency, and Application Pack behavior.
Malformed schema, provider failures and invalid capabilities MUST remain bounded
operational failures. Semantic rejection MUST remain recorded without becoming one.
Receipts MUST survive failed-run reopen and reconcile counts without secret leakage.

The implementation review MUST find CRITICAL_FINDINGS=0 and IMPORTANT_FINDINGS=0,
with explicit checks for lost provenance, inferred owner facts, verdict authority
duplication, hidden retries, threshold changes and scope expansion.

## 13. Fourth paid-run gate

A fourth paid run is NOT authorized by this spec or by Task 5F completion.
It becomes an owner-authorization candidate only when all are proven:

- SECTION_COVERAGE=PASS.
- AUTHORITATIVE_CANONICAL_FACTS > 0; EXECUTABLE_RULES > 0.
- OWNER_PROJECT_FACT_SEPARATION=PASS; UNKNOWN_SEMANTICS=PASS.
- NO_REPEATED_WINDOWS=PASS; GENERICITY_REVIEW=PASS.
- EXPECTED_LIVE_CALLS <= 9.
- PROJECTED_SEQUENCE_FITS_USD_0_20_GUARD=YES.
- CRITICAL_FINDINGS=0; IMPORTANT_FINDINGS=0.
- EXISTING_COMPLETION_POLICY_CAN_PERSIST_TRUTHFUL_GRAPH=YES, demonstrated through
  existing capture/readback rather than a manually seeded successful graph.

If the last condition is false despite compiler correctness, Case B applies:
FOURTH_PAID_RUN_AUTHORIZED=NO; Task 5G Completion Semantics Design comes first.
Even Case A requires a new explicit owner authorization and real access preflight.
No test result, recommendation, or unused credit balance authorizes paid execution.

## 14. Risks and explicit deferred work

| Risk | Required response |
|---|---|
| Long sections or cross-referenced exceptions exceed bounded context | Preserve unresolved status; do not truncate governing conditions into authority |
| Two-claim extraction cannot cover the required clauses in nine total calls | Fail the offline efficiency gate; do not reduce coverage or raise the ceiling |
| Reservation worst case exceeds USD 0.20 despite historically lower reconciled cost | Fail the cost gate; do not assume cheaper model output |
| Typed rules are correct but independent applicant facts are missing | Preserve UNKNOWN/REVIEW_REQUIRED; never infer facts from rules |
| Valid compiler output cannot pass existing successful-graph completion policy | Block fourth run and require separate Task 5G design |
| Archived content is absent, changed, or not portable into another checkout | Block archive acceptance; use the approved existing artifact without fresh substitution |
| Generic headings or wording miss a clause | Exercise fallback section coverage and generic cases; no contest-specific exception |
| New receipt fields expose private material or grow without bound | Fixed safe schemas and existing run limits; no raw payload logging |
| Competition time is insufficient for verified compiler changes | Report the unresolved gate; no deadline-driven false PASS or paid retry |

Deferred: automatic official multi-source discovery after exhaustion; larger
extraction batches; higher inference/cost limits; completion-semantics changes;
external legal/compliance verification; deployment; any further paid dogfood run.
No implementation, test-code change, provider call, or deployment is part of
Task 5F-SPEC. Its deliverable is this document alone, followed by owner review.
