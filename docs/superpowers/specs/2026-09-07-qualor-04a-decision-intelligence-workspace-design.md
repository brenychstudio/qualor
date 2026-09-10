# QUALOR-04A Decision Intelligence Workspace Design

**Status:** Owner-approved canonical product design for QUALOR-04A and the visual foundation for QUALOR-04B

**Date:** 2026-09-07

**Product:** QUALOR — Autonomous Opportunity Intelligence

**Tagline:** Find what qualifies. Pursue what matters.

This specification translates the approved product direction into an implementation-ready experience contract. It refines the canonical brief without changing its evidence, authority, safety, or human-approval invariants. QUALOR-04A must implement this information architecture as a durable product foundation. QUALOR-04B may refine its visual expression and motion, but must not replace its structure.

The known `QUALOR-05-HARDEN-CLAIM-NORMALIZER-COVERAGE` limitation remains explicit and outside this work. The interface must represent unresolved normalization truthfully; this design does not expand normalizer coverage.

## 1. Product archetype

QUALOR is a **decision intelligence workspace** for founders and small studios deciding which opportunities deserve scarce time. It is not a generic AI chatbot, a grant-search list, a SaaS administration dashboard, a developer console, or a widget-heavy analytics dashboard.

The experience must feel premium, restrained, editorial, professional, intelligent, calm, expensive, trustworthy, and intuitive. Its governing principle is:

> Simple on the surface. Powerful underneath.

The interface exposes information in three intentional levels:

1. **Decision** — what QUALOR recommends and what the user can do next.
2. **Why** — the few factors that materially produced the recommendation.
3. **Proof** — exact evidence, citations, uncertainty, conflicts, and optional technical provenance.

Each deeper level is user-invoked or contextually required. The main workspace must not expose system complexity merely because the system has it.

## 2. Product truth and authority

The product surface must preserve the existing authority model:

- Strands may discover, search, fetch, inspect, and request evidence.
- Model output may propose structured facts.
- Source-grounded `EvidenceRecord` objects provide provenance.
- Deterministic engines own eligibility, matching, strategy, effort, conflict, capacity, readiness, and the final `APPLY`, `PREPARE`, `WATCH`, or `SKIP` recommendation.
- `UNKNOWN` is a valid outcome and never appears as `PASS`.
- Search snippets are discovery material and never appear as verified hard evidence.
- Consequential preparation requires human approval.
- V1 never submits externally.

UI language must identify whether a statement is a recommendation, a deterministic evaluation, verified source evidence, an unresolved fact, or agent activity. It must never visually blur those categories.

## 3. Desktop-first composition

QUALOR V1 is desktop-first because the primary work and judge-demo environments require dense comparison, evidence reading, and visible agent activity. Owner-approved change record `QUALOR-04A-A1_2-CANONICAL-RULING-01B` (`docs/decisions/0004-a1-2-four-zone-workspace-body.md`) supersedes the earlier three-zone wording: at 1280 px and above the workspace body is four persistent zones, in this order.

| Zone | Role | Visual weight | Material |
| --- | --- | --- | --- |
| 1. Opportunity Inbox | Selection and priority queue | Supporting | Dark workspace |
| 2. Decision Canvas | Dominant deterministic judgment: recommendation, core facts, action | Dominant | Dark workspace |
| 3. Why & Proof / Evidence Plane | Causal explanation and source-grounded proof: citations, uncertainty, conflicts | Supporting | Warm light proof |
| 4. Intelligence Rail | Persisted operational telemetry, run activity, and runtime state (Activity) | Supporting | Dark workspace |

Zones 3 and 4 are separate because they hold separate product authority and separate material roles. The Evidence Plane owns source-grounded proof; the Intelligence Rail owns run telemetry. Neither owns deterministic decision policy. This is a decision workspace composition, not a generic four-column dashboard: the Decision Canvas remains visually dominant, the other three zones remain supporting, and the Evidence Plane presents proof subordinately until `Why this decision →` invokes the full Evidence Sheet.

Header and top navigation are not body zones.

The top navigation is minimal: **Inbox**, **Portfolio**, and **Activity**. Product identity, current workspace context, and one restrained account/control area may share this bar. A conventional oversized SaaS sidebar is prohibited.

Below 1280 px, the Decision Canvas remains dominant while supporting proof and activity surfaces collapse or become contextual. Between 768 and 1279 px the Opportunity Inbox remains a persistent column beside the Decision Canvas, the Why & Proof plane moves below the canvas in the same column, and the Intelligence Rail becomes a user-invoked contextual panel rather than a persistent zone. Below 768 px the same content becomes a readable single-column sequence: inbox selection, decision, why/proof, activity, and action. Mobile receives no separate workflow, navigation model, or feature set in QUALOR-04A.

Responsive changes may alter placement, but they must preserve state, evidence links, action meaning, and the `Decision → Why → Proof` order.

## 4. Hybrid dark-first material system

The canonical direction is **hybrid dark-first**, with an approximate visual dominance of 85% dark intelligence workspace and 15% light evidence/document surfaces. This is a functional material distinction, not a theme toggle.

> Dark is where QUALOR thinks. Light is where QUALOR proves.

Dark material represents navigation, evaluation, judgment, agent activity, and the selected recommendation. It uses deep warm graphite and charcoal rather than pure black, restrained tonal separation rather than card borders everywhere, high-quality typography, and minimal decorative color.

Light material represents proof, source reading, and generated application documents. It uses warm paper-like neutrals, strong long-form legibility, and an editorial document character. It must not resemble a generic white modal or a white dashboard card placed over a dark application.

QUALOR-04A must establish stable semantic roles for workspace background, elevated workspace surface, quiet divider, primary text, secondary text, muted text, proof paper, proof ink, citation link, focus, and the four recommendation tones. QUALOR-04B may refine exact color, typography, texture, elevation, and motion values without changing these roles.

The visual system must avoid cyberpunk motifs, neon AI gradients, glowing agent effects, badge soup, heavy glassmorphism, generic Tailwind dashboard composition, and decorative color without semantic value.

## 5. Color and recommendation semantics

Typography and hierarchy carry the primary meaning. Color is a secondary reinforcement.

- **APPLY** is the clearest and highest-confidence state. It receives the strongest legibility and most resolved composition, without becoming a bright green success badge.
- **PREPARE** receives restrained warm emphasis that communicates useful momentum and remaining work.
- **WATCH** is quieter and cooler, communicating unresolved evidence or timing without warning-yellow treatment.
- **SKIP** uses reduced intensity and contrast. It is a deliberate decision, not an error, and must not use aggressive red.

Pipeline states and decision states use separate visual treatments. Pipeline state appears as quiet metadata; recommendation is the primary semantic object.

## 6. Motion as product state

Motion communicates that QUALOR is progressing through a bounded process:

**Discovering → Verifying → Evaluating → Decision updated**

Transitions should generally complete within 400–700 ms when motion adds comprehension. A newly reached recommendation may resolve through controlled typography, opacity, and spatial emphasis so it feels earned rather than pre-rendered. Evidence-sheet entry should establish the transition from dark intelligence to light proof. Application-pack entry should establish the transition from approved decision to document work.

Constant movement, pulsing AI effects, gaming loaders, ambient glow, and decorative parallax are prohibited. Reduced-motion preferences must replace spatial or cinematic transitions with immediate state changes and short opacity changes while preserving comprehension.

No visual or interaction decision may be added merely because it looks impressive. Every feature or motion element must improve clarity, trust, decision comprehension, evidence comprehension, demo impact, or product usability. Otherwise it is deferred.

## 7. Opportunity Inbox

The Opportunity Inbox is a quiet, scan-efficient priority queue. It is a vertically composed list, not a card grid.

Each row contains only:

- opportunity or program name;
- organizer or track when it disambiguates the opportunity;
- recommendation;
- deadline or time remaining;
- best-project name or a clear unresolved state;
- minimal verification/pipeline state.

Conceptual hierarchy:

```text
AWS Agents for Humans
Professional Agents

PREPARE                         6d 14h
QUALOR · best fit              Evaluated
```

The row supports selection without opening a separate route unless routing improves browser history or deep-linking. Selection updates the Decision Canvas and contextual rail as one coherent workspace.

Opportunity-processing labels shown quietly in the Inbox are:

- `DISCOVERED`
- `VERIFYING`
- `EVALUATED`
- `NEEDS_REVIEW`

Decision states are:

- `APPLY`
- `PREPARE`
- `WATCH`
- `SKIP`

An opportunity may be `EVALUATED` and still be `WATCH`; these states must never be conflated.

Canonical persisted run states are separate from both sets of presentation labels:

- `CREATED`
- `RUNNING`
- `COMPLETED`
- `PARTIAL`
- `FAILED`
- `CANCELLED`
- `BUDGET_STOPPED`

The UI derives processing labels and live phase copy from `RunRecord` and `RunEvent`; it does not replace them. A `PARTIAL` run may contain individually verified evidence while still exposing incomplete coverage. Run state describes execution completeness. Decision state describes the deterministic recommendation. Neither may visually stand in for the other.

### Sorting, filtering, and search

Default sorting is **Priority**, derived from the existing deterministic decision layer. It must not be presented as opaque AI ranking. Other V1 sort modes are **Deadline**, **Newest**, and **Decision**.

### Inbox Priority Contract V1

Owner-approved change record: `QUALOR-04A-TASK8-PREREQ-01` establishes `QUALOR_INBOX_PRIORITY_CONTRACT_V1`. Priority ranks what deserves the user's attention now. `WorkspaceService` owns this deterministic total order; neither React, the repository, nor an LLM owns ranking policy.

Apply these keys in order:

1. **Current attention tier:** `EVALUATED + APPLY` (0), `EVALUATED + PREPARE` (1), `NEEDS_REVIEW` (2), `EVALUATED + WATCH` (3), `VERIFYING` (4), `DISCOVERED` (5), `EVALUATED + SKIP` (6). Current presentation consumes persisted run state and existing deterministic safety results. A retained older recommendation does not override `NEEDS_REVIEW`; a completed evaluation without a safe selected recommendation requires review. Ranking never fabricates, erases, or rewrites the underlying recommendation.
2. **Deadline within the tier:** reliable UTC future deadlines first, earliest first; unknown, missing, calendar-only or otherwise unreliable deadlines second; past deadlines last. The earliest reliable deadline determines the bucket. At the exact deadline instant it is past, consistent with the existing `deadline <= now` boundary. Unknown and past buckets have no further timestamp ordering. Deadline never crosses attention tiers. Capture one UTC `now` per ordering operation for all current-state and deadline evaluation.
3. **Strategy:** known `strategy_score` descending, null/unknown after known scores. Strategy is prioritization, not win probability.
4. **Newest:** first-discovered time descending. `InboxItem.discovered_at` is the earliest persisted `created_at` across all versions of the stable opportunity identity. A later version, including A → B → A, must not make the identity new again.
5. **Final tie-break:** `opportunity_id` ascending, producing a total stable order.

`UNKNOWN != PASS`: unknown strategy cannot outrank a known score at equal preceding keys; an unreliable deadline follows reliable future deadlines in the same tier; unresolved best project stays null. Do not introduce `STALE = NEEDS_REVIEW` as a blanket rule. Consume the existing safety assessment of consequential use, preserve previous recommendations and freshness/partial information, and retain distinct LIVE/FIXTURE/REPLAY modes. Deadline-only action denial is represented by the deadline ordering dimension; it does not itself rewrite attention tier. Ordinary WATCH/SKIP non-actionability is not an evidence/graph safety failure.

The existing persisted-state projection is: no run → `DISCOVERED`; created/running run → `VERIFYING`; incomplete terminal run → `NEEDS_REVIEW`; completed run → its evaluated recommendation tier unless selection or existing evidence/graph/policy safety requires review. This ordering projection grants no new approval or drafting authority.

The public contract adds required `InboxItem.priority_rank` (integer ≥ 0, lower means higher priority, never displayed as a score) and `InboxItem.discovered_at` (UTC datetime using the existing serialization convention). Both are derived read values, without a persisted priority column or migration. Construct current read inputs for all stable opportunity identities, compute the total order, assign absolute zero-based ranks, then apply `limit`/`offset` and return the bounded existing `InboxResponse` from `GET /api/v1/inbox`. Never paginate by repository ID before ranking. The browser consumes these typed values without reconstructing the policy.

Owner-approved change record `QUALOR-04A-TASK8-PREREQ-02` exposes that same assessment as required, non-null `InboxItem.presentation_state: InboxPresentationState`, with exactly `DISCOVERED`, `VERIFYING`, `EVALUATED`, and `NEEDS_REVIEW`. The existing server attention assessment produces this derived state once per item; both the public row and the unchanged V1 priority tier consume it. This is not a persisted column, recommendation, run state, or approval state, and introduces no new safety policy. `recommendation=APPLY` with `presentation_state=NEEDS_REVIEW` is valid and preserves the decision. React consumes the typed state without reconstructing safety policy or inferring it from rank. The API route, priority contract, and stale/partial semantics above remain unchanged.

V1 filters are **All**, **Apply**, **Prepare**, **Watch**, and **Skip**. A simple text search matches opportunity title and organizer. Advanced query builders, complex geography filtering, saved-filter systems, and configurable dashboard layouts are outside scope.

A restrained summary such as `2 apply · 3 prepare · 4 watch · 3 skip` may appear above the list. It uses text hierarchy rather than a row of colored chips.

Empty, loading, and unavailable states must explain the next meaningful action. An empty inbox may invite the user to run discovery; it must not fabricate opportunities or claim that live discovery occurred.

### Required product-state behavior

These states are part of the product contract rather than exceptional developer screens. In every state, the Decision Canvas preserves the same spatial hierarchy so the healthy default view does not accumulate permanent warning controls.

| Product state | Decision Canvas | Primary action | Intelligence Rail | Evidence Sheet | Approval and drafting |
| --- | --- | --- | --- | --- | --- |
| `EMPTY_PROFILE` | Replaces the recommendation with a concise profile-required state; no score or project match appears | **Complete profile** | Idle; explains that no run has started | Unavailable because no opportunity was evaluated | Prohibited |
| `NO_RESULTS` | Shows that discovery or the current simple filter returned no opportunities; no recommendation appears | **Run discovery** when the inbox is empty, or **Clear search** when local filtering caused the state | Shows the completed discovery run or quiet filter context, never invented progress | Unavailable | Prohibited |
| `PARTIAL_SOURCE_FAILURE` | Shows the latest deterministic result only if current admitted evidence supports it; otherwise shows `WATCH` and `Not enough evidence`, with incomplete coverage visible | **Review available evidence** | Shows `PARTIAL`, successful sources, failed source count, and bounded failure reason | Available for successfully admitted evidence and labels missing coverage | Prohibited while required critical coverage is incomplete |
| `STALE_EVIDENCE` | Retains the last decision as a stale historical snapshot and removes any implication that it was freshly renewed | **Refresh evidence** | Shows failed refresh, prior freshness time, and `STALE` | Available with stale labels on affected claims and sources | New approval and drafting prohibited until freshness requirements pass |
| `UNKNOWN_ELIGIBILITY` | Shows eligibility as `UNKNOWN` or `REVIEW_REQUIRED` and recommendation as deterministic `WATCH`; no invented score appears | **Resolve unknowns** | Names bounded unresolved fields and the last completed run | Available when any admitted evidence exists; unresolved claims are first-class | Prohibited |
| `BUDGET_STOPPED` | Shows the latest valid deterministic state or `Not enough evidence`; it never converts incomplete work into a recommendation | **Review current evidence** | Shows actual `BUDGET_STOPPED`, consumed limits, estimated cost, and termination time | Available for evidence admitted before the stop | New approval and drafting prohibited when the stopped run left critical coverage incomplete |
| `DISCONNECTED_LIVE_PROVIDER` | Shows the last persisted snapshot with a clear disconnected/freshness treatment; no live activity is implied | **Reconnect provider** | Shows disconnected provider and last successful event | Persisted evidence remains readable with its original freshness | New live approval and drafting prohibited until required provider-dependent checks are current |
| `PENDING_APPROVAL` | Keeps the deterministic recommendation visible and presents the exact action, versions, expiry, and remaining blockers awaiting review | **Confirm approval** | Shows the completed run and pending human boundary, not a running cloud session | Available | Drafting has not started; user may confirm or cancel |
| `REVOKED_APPROVAL` | Shows that a previously approved decision no longer matches current critical versions | **Review changes** | Shows a bounded revocation reason and the change that invalidated approval | Available for both retained historical proof and current evidence | Prohibited until a new valid approval is created |
| `FINISHED_PACK` | Shows the decision/version that produced the pack and a concise completion state | **Open application pack** | Shows the separate drafting job as completed | Available and linked to the pack's evidence references | Pack remains accessible; the consumed approval cannot be reused |

When two states apply, the safer actionability rule wins. For example, disconnected stale evidence remains readable, but cannot support a new approval. No state fabricates a recommendation, freshness claim, source count, or progress event.

## 8. Decision Canvas

The Decision Canvas is the visual hero and dominant workspace surface. It is composed as a continuous editorial decision area, not a collection of independent cards.

Its reading order is fixed:

1. Quiet opportunity context: organizer, program, track, and verified freshness.
2. Recommendation: `APPLY`, `PREPARE`, `WATCH`, or `SKIP`.
3. One concise human-readable reason line.
4. Strategy score.
5. Four core facts.
6. Readiness summary.
7. One dominant action.
8. `Why this decision →` as the primary secondary interaction.

The reason line summarizes deterministic output in plain language. It must not become a long model-generated paragraph. Examples include `Strong strategic fit. Two readiness gaps remain.` and `Two critical rules remain unresolved.`

### Strategy score

Strategy appears as a restrained large number with a plain label:

```text
82
Strategy
```

Canonical UI copy must make the boundary explicit: **Strategy is prioritization, not probability of winning.** Circular gauges, speedometers, radar charts, and dominant progress bars are prohibited. A user interaction may reveal the existing factors: Product fit, Readiness, Time feasibility, Strategic value, and Economic affordability.

If deterministic inputs are insufficient to calculate strategy, the score area shows **Not enough evidence**. It must not show `0`, `50`, an estimated probability, or a placeholder number.

### Four core facts

The first level contains exactly four primary facts:

| Fact | Meaning |
| --- | --- |
| Best project | The deterministic top project, or an unresolved state |
| Eligibility | `PASS`, `FAIL`, `REVIEW_REQUIRED`, or unresolved truth from the engine |
| Effort | Bounded effort range or `UNKNOWN` |
| Deadline | Verified deadline/time remaining or `UNKNOWN` |

The canvas must not expand into a KPI wall. Missing facts use explicit `UNKNOWN` language and a path into the evidence layer.

### Canonical decision metadata

The full decision architecture retains program and edition, best project, recommendation, eligibility scope, reward type, deadline with timezone, effort range, most important blocker, and freshness. Progressive disclosure determines placement:

- Level 1 keeps the organizer/program/track/edition and freshness as quiet context, the recommendation as hero, the four core facts, and the most important blocker in the readiness line.
- Level 2 `Why` exposes eligibility scope, reward type, the absolute deadline with timezone, detailed effort range, blocker context, strategy factors, and freshness status.
- Level 3 `Proof` links those claims to evidence and technical provenance.

Time remaining never replaces the absolute deadline. If a verified timezone is unavailable, the UI displays that uncertainty and does not invent one. Reward type remains distinct from monetary amount or total-pool interpretation.

### Readiness summary

One adaptive line below the facts explains the immediate context:

- APPLY: `Ready to submit`
- PREPARE: `2 readiness gaps · Demo proof · Public repository`
- WATCH: `2 critical unknowns · Legal form · Project reuse rule`
- SKIP: `Hard eligibility conflict · Incorporated entity required`

This line summarizes existing structured results. It does not invent a narrative.

### Primary action

Exactly one action is visually dominant:

| Recommendation | Primary action |
| --- | --- |
| APPLY | Approve application |
| PREPARE | Approve preparation |
| WATCH | Resolve unknowns |
| SKIP | Review rejection |

Generic labels such as `Continue`, `Next`, and `Proceed` are prohibited. Secondary interactions remain visually quiet and cannot compete with the recommendation-specific action.

## 9. Why and Proof: the Evidence Sheet

`Why this decision →` opens the signature QUALOR proof experience. The dark workspace remains visible but de-emphasized while a warm, light, document-like layer enters above it. The sheet may occupy most of the center and right workspace while preserving enough context to show that proof belongs to the selected decision.

It must feel like an editorial evidence document, not a generic dialog, modal, accordion stack, or white dashboard card.

The top establishes:

```text
WHY THIS DECISION

Eligibility
PASS

7 verified claims · 3 official sources
Updated 4m ago
```

Counts must reflect actual evidence state. `Verified` applies only to evidence meeting the corresponding verification contract.

### Evidence sections

Evidence is organized into four continuous editorial sections:

1. Eligibility
2. Project Fit
3. Constraints & Conflicts
4. Reward & Deadline

Sections use typography, spacing, and subtle rules. They must not default to four giant accordion cards. Long sections may support a quiet section index or targeted disclosure without hiding critical failures or conflicts.

### Claim blocks

Each claim block distinguishes system interpretation from source proof:

```text
ENTRANT TYPE

PASS

“Exact source-grounded evidence text”

Official Rules
official-domain.example

Source grounded · Verified 4m ago
View original ↗
```

The exact excerpt receives document-like quotation treatment. QUALOR's state and explanation appear outside that quotation. The citation remains actionable and visually associated with the excerpt.

### Evidence states

The Evidence Sheet supports five first-class states:

- **PASS** — a deterministic rule is positively supported by admissible evidence.
- **FAIL** — a deterministic rule is contradicted by admissible evidence.
- **UNKNOWN** — no admissible evidence resolves the fact.
- **CONFLICT** — authoritative sources disagree or deterministic precedence cannot safely resolve them.
- **STALE** — evidence exists but freshness policy requires renewed verification.

UNKNOWN copy states the missing fact and offers a bounded resolution action. For example: `No verified official source currently resolves whether the current legal form qualifies.`

CONFLICT presents the opposing source evidence, source authority, and need for human review. It never asks the model to choose a preferred answer. STALE retains the previous evidence for audit while clearly preventing it from appearing current.

### Technical provenance

HMAC identifiers, offsets, normalizer versions, and policy metadata are hidden from the primary proof surface. `Technical provenance →` opens Level 3 audit detail containing the source ID, span ID, retrieval time, policy version, normalizer version, and extraction state when present.

Technical provenance is selectable/copyable for audit, but does not expose credentials, signed requests, hidden model reasoning, raw full pages, or private AWS identifiers.

## 10. Live Intelligence Rail

The right rail is structured operational telemetry, never a chat. It has no assistant avatar, chat bubbles, first-person model narration, or raw chain-of-thought.

The user-facing navigation label **Activity** is the presentation of canonical `RunRecord` and `RunEvent` history. `ACTIVITY_DOMAIN_SOURCE=RUN_RECORD_AND_RUN_EVENT`. QUALOR-04A must not introduce a parallel Activity domain entity or copy run history into a second source of truth.

At rest, its header may show:

```text
LIVE
3 official sources
7 verified claims
Fresh · 4m
```

Its activity timeline uses concise, factual events:

```text
12:41  Opportunity discovered
12:41  Official rules located
12:42  2 sources verified
12:42  Eligibility evaluated
12:42  Project fit updated
12:43  Decision changed → PREPARE
```

During a run, the rail displays a bounded operational state such as:

```text
SEARCHING
Official sources

2 / 5 search calls
1 source fetched
$0.021 estimated
```

The canonical user-facing phases are **Discovering**, **Verifying**, **Evaluating**, and **Decision updated**. Events expose action codes and observations that improve trust. They do not expose prompts, internal reasoning, credentials, terminal-like logs, or developer-only protocol traffic.

The rail renders actual persisted `RunEvent` observations. It must not create fake animated progress, inferred timestamps, fictional source counts, or decorative events between real states. Motion may transition between received states but cannot imply work that did not occur.

LIVE, FIXTURE, and REPLAY modes are visually explicit whenever applicable. A disconnected provider displays `DISCONNECTED` with its last successful event. A budget stop displays canonical `BUDGET_STOPPED` with bounded usage. A partial, failed, or cancelled run retains its canonical run state. Synthetic or replayed activity can never appear live.

## 11. Human approval boundary

Human approval is a primary product principle, not a confirmation dialog added at the end.

QUALOR may autonomously discover, search, fetch, verify, evaluate, match projects, estimate effort, assess conflicts, and recommend. Preparation begins only after the user deliberately selects **Approve preparation** or **Approve application** for an eligible recommendation.

V1 approval presentation states are deliberately narrow:

- `NOT_REVIEWED`
- `PENDING_APPROVAL`
- `APPROVED_FOR_PREPARATION`
- `REVOKED_APPROVAL`
- `DRAFT_READY`

`WATCH` routes to **Resolve unknowns**. `SKIP` routes to **Review rejection** and cannot generate an application pack. Approval never submits externally and never implies that eligibility is guaranteed.

The approval transition must identify what will be generated and which unresolved items remain. If required evidence is `UNKNOWN`, `CONFLICT`, or `STALE`, the action remains fail-closed according to existing deterministic policy.

### Approval record semantics

Every consequential approval is a persisted `ApprovalRecord` bound to:

- actor identity;
- opportunity content hash and version;
- founder profile version;
- selected project version;
- deterministic policy version;
- approved action;
- creation time and expiry.

The only approved consequential V1 action is `GENERATE_DRAFT_PACK`. Approval expires 24 hours after creation or at the verified opportunity deadline, whichever occurs first. If no verified deadline exists, the 24-hour limit applies and the missing deadline remains visible.

Approval is one-time, version-bound, and idempotent. Repeating the same approved request with the same idempotency identity returns the existing drafting job or pack rather than creating a duplicate. Consuming an approval for a drafting job prevents reuse for another pack.

A critical change to rules/opportunity hash, founder profile, selected project, license state, or policy version invalidates the approval before use and presents `REVOKED_APPROVAL`. Expiry also makes it non-actionable. Historical approval remains auditable, but only a newly reviewed `ApprovalRecord` bound to current versions may start drafting.

### Run-to-drafting boundary

The live research/evaluation run completes before human review:

```text
Run completes
→ readiness brief and approval request persist
→ user approves
→ new bounded drafting job starts
```

QUALOR never keeps the original live cloud session open while waiting for the user. The new drafting job receives only the approved action and version-bound persisted inputs. It cannot search again, submit externally, or expand authority merely because approval exists.

## 12. Application Pack

After valid human approval, QUALOR creates a draft application pack with seven canonical sections:

01. Submission summary
02. Project fit narrative
03. Eligibility checklist
04. Required deliverables
05. Evidence references
06. Readiness gaps
07. Suggested application answers

The pack naturally shifts into the light document materiality. This creates the product rhythm:

**Dark decision/intelligence → human approval → light application/documentation**

The pack must preserve evidence references and distinguish verified facts, deterministic interpretations, user-provided project facts, and draft narrative. Suggested answers are clearly labeled draft material. Unknown or conflicting facts remain visible and cannot be silently completed.

Every `DraftPack` is versioned and attributable. It retains its approval reference, opportunity hash/version, founder profile version, project version, policy version, source/evidence references, missing fields, creation timestamp, and pack version. A later rerun or profile change does not rewrite a finished historical pack.

QUALOR-04A provides in-product viewing and section navigation for the generated draft. Editing and export capabilities require separate owner approval and are not required by this specification. External submission, form automation, email, and Devpost write integration are prohibited.

## 13. Persistence, restart, and rerun semantics

QUALOR-04A uses canonical local SQLite transactions for durable product state. One committed transaction must either preserve the complete state transition or preserve none of it; the UI cannot show a decision, approval, or pack whose required linked records were only partially written.

The minimum persisted model set is:

- `FounderProfile`;
- `ProjectProfile`;
- versioned `OpportunityRecord`;
- `EvidenceRecord`;
- `DecisionRecord`;
- `RunRecord`;
- append-only `RunEvent`;
- `ApprovalRecord`;
- versioned `DraftPack`.

This is a product-state contract, not a database schema. Implementation planning must map existing domain models before introducing storage representations.

### Restart behavior

After a process or machine restart:

- Inbox items and their selected/current opportunity versions remain available;
- decisions remain linked to the exact opportunity, profile, project, evidence, and policy versions that produced them;
- evidence excerpts, citations, provenance, and freshness survive;
- run history and ordered run events survive;
- an approval survives only if it remains unconsumed, unexpired, and bound to current critical versions;
- revoked or expired approval cannot start a drafting job;
- a generated Draft Pack remains accessible with its original attribution.

Recovery must never infer completion from a partially committed write. Interrupted runs reopen as their last transactionally recorded state and are rendered truthfully as running-recovery, partial, failed, cancelled, or budget-stopped according to canonical state transition policy.

### Deduplication and meaningful reruns

Opportunity identity and content version are distinct. Rediscovering an unchanged opportunity updates bounded discovery/freshness metadata without creating a duplicate Inbox item. Equality must derive from the canonical opportunity identity and meaningful content hash, not title similarity.

A meaningful critical change creates a new `OpportunityRecord` version and a new linked decision after reevaluation. Previous opportunity, evidence, decision, run, approval, and pack history remains append-only and inspectable. The Inbox points to the current version while history explains what changed and why the recommendation may differ.

When evidence refresh fails, the last successful snapshot remains available. It is marked `STALE`; its freshness is not silently renewed, and actionability is not restored merely because old evidence exists. The rail records the failed refresh, while the Evidence Sheet distinguishes retained proof from missing current verification.

## 14. Core interaction flows

### Triage and decision

1. User lands in the Inbox with Priority sorting.
2. User selects an opportunity row.
3. Decision Canvas updates to the deterministic result.
4. Intelligence Rail shows current source/evaluation freshness.
5. User either acts on the recommendation or opens `Why this decision`.

### Evidence review

1. User opens `Why this decision`.
2. Light Evidence Sheet enters while preserving selected-opportunity context.
3. User scans section states and exact source excerpts.
4. User may open the original source or optional technical provenance.
5. User closes/returns to the same Decision Canvas state.

### Unknown or conflict resolution

1. User selects `Resolve unknowns` or a claim-level `Resolve →` action.
2. QUALOR identifies the exact unresolved field and current evidence state.
3. Any subsequent live research remains bounded and mode-labeled.
4. New admissible evidence triggers deterministic reevaluation.
5. The activity rail records whether the recommendation changed.

### Approval and pack generation

1. User selects the recommendation-specific approval action.
2. QUALOR presents the preparation scope and unresolved blockers.
3. A version-bound request enters `PENDING_APPROVAL`; user confirms or cancels it.
4. A valid `ApprovalRecord` becomes `APPROVED_FOR_PREPARATION` and the completed research run stays closed.
5. A new bounded drafting job consumes the approval idempotently and generates the draft without external submission.
6. State becomes `DRAFT_READY`, and the product enters light document mode.

## 15. Judge demo choreography

The product architecture must support this exact story without narration carrying the interface:

1. Opportunity Inbox is visible with several evaluated opportunities.
2. The judge opens AWS Agents for Humans.
3. Decision Canvas immediately shows the actual recommendation and four core facts.
4. The judge opens `Why this decision`.
5. The light Evidence Sheet shows exact official evidence and honest unresolved states.
6. The judge returns to the dark Decision Canvas.
7. The Intelligence Rail shows bounded agent activity from discovery through decision.
8. The user chooses **Approve preparation** or **Approve application** when the recommendation permits it.
9. QUALOR transitions into the light Application Pack.
10. The draft package is visible with evidence and readiness gaps.

The resulting story is: **discover → verify → decide → prove → human approves → prepare**.

The demo must use real state labels. LIVE, FIXTURE, and REPLAY remain visibly distinct, and no synthetic opportunity is presented as current live discovery.

## 16. First-five-seconds gate

Without narration, a judge looking at the main workspace for approximately three to five seconds must understand:

- multiple opportunities exist;
- QUALOR evaluated the selected opportunity;
- a recommendation exists;
- a best-project state exists or remains explicitly unresolved;
- evidence exists and can be opened;
- effort and deadline matter;
- the next consequential action belongs to the human.

If these facts compete for attention, the recommendation wins, then the four core facts, then the action. Agent telemetry, detailed factors, filters, and provenance remain secondary. Failure of this hierarchy is a design defect, even if every required datum is technically present.

## 17. Accessibility, responsive behavior, and language

QUALOR-04A establishes a usable baseline rather than deferring basic quality to polish:

- All core flows are keyboard reachable with visible, restrained focus states. Tab order follows the visual hierarchy; arrow-key behavior may support composite Inbox controls; Enter and Space activate controls according to platform semantics.
- Recommendation and evidence state never rely on color alone.
- Text and controls meet WCAG AA contrast in both dark and light materials.
- Evidence excerpts preserve readable line length and selectable text.
- Motion respects reduced-motion preferences.
- Time remaining is paired with an accessible absolute deadline when known.
- UNKNOWN, CONFLICT, and STALE use explicit text labels.
- The Evidence Sheet has a semantic heading, traps focus only while modal behavior is active, closes with Escape, and returns focus to `Why this decision`.
- Pages and document sections use semantic headings and landmarks rather than visual-only hierarchy.
- Loading and live activity use announced state changes without continuously interrupting screen-reader users.

The same content and actions remain readable from 320 through 1440 px and beyond. At 320 px, zones stack without horizontal page scrolling, evidence text remains readable, and no action disappears. Desktop remains the primary experience; this responsive baseline does not create a separate mobile workflow.

Competition-facing product UI is English. Ukrainian may remain the canonical language for owner documentation. Full internationalization is not part of V1.

These are foundation requirements for QUALOR-04A. QUALOR-04B refines the experience but does not own baseline accessibility, responsive correctness, or language truthfulness.

## 18. QUALOR-04A delivery boundary

QUALOR-04A builds the complete functional product foundation:

- final information architecture;
- durable hybrid product shell;
- persistence required by the approved V1 experience;
- Opportunity Inbox, sorting, filters, and search;
- Decision Canvas and recommendation-specific actions;
- Strategy detail disclosure and four core facts;
- Evidence Sheet, citations, evidence states, and optional technical provenance;
- Live Intelligence Rail and mode-safe bounded activity;
- human approval states and transitions;
- draft Application Pack with its seven sections;
- a clear responsive and accessible baseline.

QUALOR-04A must not be intentionally ugly, disposable, or structured as a temporary dashboard. Its components and navigation must support the final experience without replacement.

## 19. QUALOR-04B refinement boundary

QUALOR-04B builds directly on the 04A structure with:

- final art-direction refinement;
- premium typography, spacing, material, and tonal polish;
- motion choreography and micro-interactions;
- responsive refinement;
- demo-specific cinematic transitions;
- final judge-facing composition and finish.

QUALOR-04B may tune presentation and interaction quality. It may not require rewriting the four-zone wide-body architecture, `Decision → Why → Proof`, recommendation hierarchy, evidence model, approval boundary, application-pack structure, or responsive content order.

## 20. Explicitly deferred scope

The following are outside QUALOR-04A and QUALOR-04B unless a later owner-approved change record adds them:

- multi-user accounts and permissions;
- billing;
- Gmail, calendar, CRM, and external communication integrations;
- comments and collaboration;
- complex notifications;
- automatic Devpost or other external submission;
- browser extension;
- native mobile workflow;
- advanced saved filters and custom dashboards;
- vector database;
- multi-agent swarm;
- QUALOR-05 claim-normalizer hardening.

## 21. Design acceptance contract

The implemented experience conforms to this spec only when all of the following remain true:

- Product archetype is Decision Intelligence Workspace.
- Desktop is the primary composition and mobile remains a responsive expression of the same flow.
- Dark workspace and light proof/document materiality retain their functional meaning.
- At 1280 px and above the workspace body carries four zones in order: Opportunity Inbox, Decision Canvas, Why & Proof / Evidence Plane, and Intelligence Rail, with evidence and telemetry authority kept distinct.
- Opportunity Inbox is a priority list rather than a card grid.
- Decision Canvas is dominant and recommendation is more prominent than strategy score.
- Only Best Project, Eligibility, Effort, and Deadline appear as first-level core facts.
- Recommendation-specific primary actions preserve the human approval boundary.
- Evidence Sheet clearly separates QUALOR interpretation from exact source proof.
- UNKNOWN, CONFLICT, and STALE remain visible and honest.
- Run state and decision state remain separate, and Activity renders canonical `RunRecord`/`RunEvent` history.
- Intelligence Rail presents actual bounded telemetry rather than chat, fake progress, or chain-of-thought.
- Approval is actor-, version-, action-, and expiry-bound; critical changes revoke it.
- Drafting starts as a new bounded job after the research run closes.
- Application Pack appears only after valid human approval, retains complete attribution, and never submits externally.
- SQLite transactions preserve Inbox, evidence, versioned decisions, runs, approvals, and packs across restart.
- Opportunity deduplication and failed-refresh `STALE` behavior preserve history without renewing actionability.
- Strategy displays `Not enough evidence` instead of an invented score when inputs are insufficient.
- English product UI remains readable and operable from 320 through 1440 px with keyboard, focus, contrast, Escape, and reduced-motion support.
- A judge can understand the selected opportunity, recommendation, evidence availability, effort/deadline, and human action in the first five seconds.
- QUALOR-04B can polish the experience without replacing its information architecture.

## 22. Self-review record

```text
PLACEHOLDERS=0
TBD=0
TODO=0
CONTRADICTIONS=0
APPROVED_VISUAL_DIRECTION_CHANGED=NO
APPROVED_IA_CHANGED=NO
DARK_FIRST_HYBRID_DIRECTION=PRESERVED
PROGRESSIVE_INTELLIGENCE=PRESERVED
HUMAN_APPROVAL_BOUNDARY=PRESERVED
EVIDENCE_FIRST_PRODUCT_STORY=PRESERVED
04A_04B_BOUNDARY=CLEAR
REQUIRED_PRODUCT_STATES=COMPLETE
RUN_DECISION_SEPARATION=PASS
ACTIVITY_RUN_MAPPING=PASS
DECISION_METADATA_COMPLETENESS=PASS
STRATEGY_SCORE_SEMANTICS=PASS
APPROVAL_VERSIONING=PASS
APPROVAL_EXPIRY=PASS
APPROVAL_REVOCATION=PASS
DRAFT_JOB_BOUNDARY=PASS
PERSISTENCE_MODEL_SET=COMPLETE
RESTART_SEMANTICS=PASS
DEDUP_RERUN_SEMANTICS=PASS
STALE_EVIDENCE_SEMANTICS=PASS
ACCESSIBILITY_BASELINE=PASS
RESPONSIVE_BASELINE=PASS
UI_LANGUAGE_POLICY=PASS
LIVE_TRUTHFULNESS=PASS
SCOPE_CREEP=NO
```

This document is a design specification. It contains no implementation sequence, task breakdown, persistence schema, component code, or implementation authorization.
