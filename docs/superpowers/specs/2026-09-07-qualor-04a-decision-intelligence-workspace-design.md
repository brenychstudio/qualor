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

QUALOR V1 is desktop-first because the primary work and judge-demo environments require dense comparison, evidence reading, and visible agent activity. At wide desktop sizes, the workspace uses three zones:

| Zone | Role | Visual weight | Indicative width |
| --- | --- | --- | --- |
| Left: Opportunity Inbox | Quiet priority queue and selection | Supporting | 260–320 px |
| Center: Decision Canvas | Recommendation, core facts, action | Dominant | Flexible, at least 560 px |
| Right: Live Intelligence / Evidence Rail | Contextual activity and source status | Supporting | 280–340 px |

The top navigation is minimal: **Inbox**, **Portfolio**, and **Activity**. Product identity, current workspace context, and one restrained account/control area may share this bar. A conventional oversized SaaS sidebar is prohibited.

Between approximately 1024 and 1279 px, the Decision Canvas remains dominant while the intelligence rail may collapse into a user-invoked contextual panel. Below desktop width, the same content becomes a readable single-column sequence: inbox selection, decision, why/proof, activity, and action. Mobile receives no separate workflow, navigation model, or feature set in QUALOR-04A.

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

Pipeline states are:

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

### Sorting, filtering, and search

Default sorting is **Priority**, derived from the existing deterministic decision layer. It must not be presented as opaque AI ranking. Other V1 sort modes are **Deadline**, **Newest**, and **Decision**.

V1 filters are **All**, **Apply**, **Prepare**, **Watch**, and **Skip**. A simple text search matches opportunity title and organizer. Advanced query builders, complex geography filtering, saved-filter systems, and configurable dashboard layouts are outside scope.

A restrained summary such as `2 apply · 3 prepare · 4 watch · 3 skip` may appear above the list. It uses text hierarchy rather than a row of colored chips.

Empty, loading, and unavailable states must explain the next meaningful action. An empty inbox may invite the user to run discovery; it must not fabricate opportunities or claim that live discovery occurred.

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

It is a prioritization score, never a win probability. Circular gauges, speedometers, radar charts, and dominant progress bars are prohibited. A user interaction may reveal the existing factors: Product fit, Readiness, Time feasibility, Strategic value, and Economic affordability.

### Four core facts

The first level contains exactly four primary facts:

| Fact | Meaning |
| --- | --- |
| Best project | The deterministic top project, or an unresolved state |
| Eligibility | `PASS`, `FAIL`, `REVIEW_REQUIRED`, or unresolved truth from the engine |
| Effort | Bounded effort range or `UNKNOWN` |
| Deadline | Verified deadline/time remaining or `UNKNOWN` |

The canvas must not expand into a KPI wall. Missing facts use explicit `UNKNOWN` language and a path into the evidence layer.

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

The rail must make LIVE, FIXTURE, and REPLAY modes visually explicit whenever applicable. Synthetic or replayed activity can never appear live.

## 11. Human approval boundary

Human approval is a primary product principle, not a confirmation dialog added at the end.

QUALOR may autonomously discover, search, fetch, verify, evaluate, match projects, estimate effort, assess conflicts, and recommend. Preparation begins only after the user deliberately selects **Approve preparation** or **Approve application** for an eligible recommendation.

V1 approval states are deliberately narrow:

- `NOT_REVIEWED`
- `APPROVED_FOR_PREPARATION`
- `DRAFT_READY`

`WATCH` routes to **Resolve unknowns**. `SKIP` routes to **Review rejection** and cannot generate an application pack. Approval never submits externally and never implies that eligibility is guaranteed.

The approval transition must identify what will be generated and which unresolved items remain. If required evidence is `UNKNOWN`, `CONFLICT`, or `STALE`, the action remains fail-closed according to existing deterministic policy.

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

The pack must preserve evidence references and distinguish verified facts, deterministic interpretations, user-provided project facts, and draft narrative. Suggested answers remain editable drafts. Unknown or conflicting facts remain visible and cannot be silently completed.

QUALOR-04A provides in-product viewing and section navigation for the generated draft. Editing and export capabilities require separate owner approval and are not required by this specification. External submission, form automation, email, and Devpost write integration are prohibited.

## 13. Core interaction flows

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
3. User confirms approval.
4. Approval state becomes `APPROVED_FOR_PREPARATION`.
5. QUALOR generates the draft pack without external submission.
6. State becomes `DRAFT_READY`, and the product enters light document mode.

## 14. Judge demo choreography

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

## 15. First-five-seconds gate

Without narration, a judge looking at the main workspace for approximately three to five seconds must understand:

- multiple opportunities exist;
- QUALOR evaluated the selected opportunity;
- a recommendation exists;
- a best-project state exists or remains explicitly unresolved;
- evidence exists and can be opened;
- effort and deadline matter;
- the next consequential action belongs to the human.

If these facts compete for attention, the recommendation wins, then the four core facts, then the action. Agent telemetry, detailed factors, filters, and provenance remain secondary. Failure of this hierarchy is a design defect, even if every required datum is technically present.

## 16. Accessibility and interaction quality

QUALOR-04A establishes a usable baseline rather than deferring basic quality to polish:

- All core flows are keyboard reachable with visible, restrained focus states.
- Recommendation and evidence state never rely on color alone.
- Text and controls meet WCAG AA contrast in both dark and light materials.
- Evidence excerpts preserve readable line length and selectable text.
- Motion respects reduced-motion preferences.
- Time remaining is paired with an accessible absolute deadline when known.
- UNKNOWN, CONFLICT, and STALE use explicit text labels.
- Sheet and contextual-panel behavior preserves focus order and a reliable return point.
- Loading and live activity use announced state changes without continuously interrupting screen-reader users.

These are foundation requirements for QUALOR-04A. QUALOR-04B refines the experience but does not own baseline accessibility.

## 17. QUALOR-04A delivery boundary

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

## 18. QUALOR-04B refinement boundary

QUALOR-04B builds directly on the 04A structure with:

- final art-direction refinement;
- premium typography, spacing, material, and tonal polish;
- motion choreography and micro-interactions;
- responsive refinement;
- demo-specific cinematic transitions;
- final judge-facing composition and finish.

QUALOR-04B may tune presentation and interaction quality. It may not require rewriting the three-zone architecture, `Decision → Why → Proof`, recommendation hierarchy, evidence model, approval boundary, application-pack structure, or responsive content order.

## 19. Explicitly deferred scope

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

## 20. Design acceptance contract

The implemented experience conforms to this spec only when all of the following remain true:

- Product archetype is Decision Intelligence Workspace.
- Desktop is the primary composition and mobile remains a responsive expression of the same flow.
- Dark workspace and light proof/document materiality retain their functional meaning.
- Opportunity Inbox is a priority list rather than a card grid.
- Decision Canvas is dominant and recommendation is more prominent than strategy score.
- Only Best Project, Eligibility, Effort, and Deadline appear as first-level core facts.
- Recommendation-specific primary actions preserve the human approval boundary.
- Evidence Sheet clearly separates QUALOR interpretation from exact source proof.
- UNKNOWN, CONFLICT, and STALE remain visible and honest.
- Intelligence Rail presents bounded telemetry rather than chat or chain-of-thought.
- Application Pack appears only after valid human approval and never submits externally.
- A judge can understand the selected opportunity, recommendation, evidence availability, effort/deadline, and human action in the first five seconds.
- QUALOR-04B can polish the experience without replacing its information architecture.

## 21. Self-review record

```text
PLACEHOLDERS=0
TBD=0
TODO=0
CONTRADICTIONS=0
DARK_FIRST_HYBRID_DIRECTION=PRESERVED
PROGRESSIVE_INTELLIGENCE=PRESERVED
HUMAN_APPROVAL_BOUNDARY=PRESERVED
EVIDENCE_FIRST_PRODUCT_STORY=PRESERVED
04A_04B_BOUNDARY=CLEAR
SCOPE_CREEP=NO
```

This document is a design specification. It contains no implementation sequence, task breakdown, persistence schema, component code, or implementation authorization.
