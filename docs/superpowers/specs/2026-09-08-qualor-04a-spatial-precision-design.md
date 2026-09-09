# QUALOR-04A — Spatial Precision Design Specification

**Date:** 2026-09-08 <br>
**Status:** DESIGN APPROVED — OWNER REVIEW OF WRITTEN SPEC REQUIRED <br>
**Scope:** QUALOR-04A visual architecture correction after Task 07 / 07R visual rejection <br>
**Canonical direction:** **A1 — Spatial Precision** <br>
**Implementation status:** NOT STARTED <br>
**Task 8:** BLOCKED until owner accepts implementation screenshots <br>
**Baseline branch:** `feature/qualor-04a-workspace` <br>
**Baseline HEAD:** `8e0903d7b7ae56e477d0a700e6ec57559135ebc9`

---

## 1. Purpose

QUALOR is an autonomous opportunity-intelligence product. Its interface must communicate that it:

1. gathers opportunity signals;
2. verifies official evidence;
3. evaluates qualification and fit;
4. forms a recommendation;
5. exposes the reasoning and proof;
6. preserves a human approval boundary before consequential output.

The current Task 07 / 07R implementation is technically valid but visually rejected. The correction is not a recolor or polish pass. It is a visual-architecture correction intended to establish a distinctive, competition-grade product language.

The target is an expensive, calm, precise professional intelligence instrument. It must not read as:

- a marketing landing page;
- a generic dark SaaS dashboard;
- a three-column admin interface;
- a sci-fi / cyberpunk HUD;
- a card-grid analytics product.

The design principle remains:

> **Simple on the surface. Powerful underneath.**

And the material rule remains:

> **Dark is where QUALOR thinks. Light is where QUALOR proves.**

---

## 2. Canonical Visual Direction

### A1 — Spatial Precision

QUALOR uses a restrained carbon visual system with high structural precision.

Its canonical signature is built from four systems:

1. **Decision Field** — the spatial surface where a recommendation is formed.
2. **Decision Trace** — the persistent audit trajectory from discovery to human approval.
3. **Evidence Plane** — a materially distinct light proof layer.
4. **Dossier Grammar** — the view-first Portfolio representation of founder/project context.

The application must remain recognizable even if the QUALOR wordmark is removed.

Recognition should come from spatial behavior and information geometry, not decorative branding.

---

## 3. Main Workspace Architecture

The desktop workspace is not a conventional:

`sidebar | content | sidebar`

layout.

It is one continuous operational field with three responsibility zones:

`Opportunity Field → Decision Field → Intelligence Plane`

These zones may have tonal and alignment distinctions, but must not present as three generic boxed columns.

### 3.1 Header

Target height: approximately **56–60 px**.

Left:
- `QUALOR`
- quiet secondary identity: `OPPORTUNITY INTELLIGENCE`

Center:
- `Inbox`
- `Portfolio`
- `Activity`

Right:
- truthful runtime state only:
  - `LOCAL`
  - `FIXTURE`
  - `REPLAY`
  - `LIVE`
- connection/controller state if required

Do not add:
- oversized primary CTA;
- avatar;
- notifications;
- decorative settings controls;
- marketing straplines.

The header must feel like part of an instrument, not a website navbar.

---

## 4. Opportunity Field

Target desktop width: approximately **250–270 px**.

This field is dedicated to opportunity decisions. Navigation is not mixed into it.

Canonical item structure:

```text
AWS AGENTS FOR HUMANS
Professional Agents

PREPARE                    06D 14H
QUALOR
```

A populated state should normally expose **3–5 opportunities** with varied decision states.

### Rules

- no rounded cards;
- no large filled selected row;
- no colorful status badges;
- selected state is expressed through alignment, contrast, a precise active rail/marker, and typography;
- recommendation and deadline have independent visual axes;
- project fit / blocker / unknown count may appear as a quieter lower layer.

The field must feel like a **decision queue**, not an email inbox.

---

## 5. Decision Field

The Decision Field is the primary visual signature of QUALOR.

It is not:
- a hero;
- a report page;
- a card;
- a vertically stacked KPI layout.

It behaves as a precise coordinate field.

### 5.1 Canonical spatial hierarchy

Upper left:

```text
AWS / AGENTS FOR HUMANS
PROFESSIONAL AGENTS
```

Upper right:

```text
DEADLINE
06D 14H
```

Primary recommendation:

```text
PREPARE
```

Supporting reason:

```text
Strong fit · 2 readiness gaps
```

Strategy:

```text
82
STRATEGY
```

Recommendation and strategy must occupy different spatial coordinates. They must not be stacked as a conventional hero + KPI.

### 5.2 Four core facts

Core facts are anchors distributed across the field, not a 2×2 metric grid:

```text
BEST PROJECT                         ELIGIBILITY
QUALOR                               PASS


EFFORT                               READINESS
9–13 H                               02 GAPS
```

These anchors use negative space and alignment rather than containers.

### 5.3 Decision dominance

Recommendation is the most important result, but it must not become a landing-page headline.

The user should perceive:

`decision → facts → trace → proof`

rather than:

`headline → paragraph → cards → CTA`.

---

## 6. Decision Trace

Decision Trace is signature system #1.

Canonical trajectory:

```text
DISCOVER        VERIFY        QUALIFY        DECIDE        APPROVE
   ●──────────────●──────────────●──────────────●──────────────○
```

It represents the audit path of the actual system.

For a `PREPARE` state, for example:
- Discover — completed;
- Verify — completed;
- Qualify — completed;
- Decide — completed/active;
- Approve — waiting human.

### Rules

Decision Trace must not become:
- a generic progress bar;
- a stepper component;
- five badge pills;
- a decorative glowing timeline.

It is a thin structural trajectory integrated with the Decision Field.

In static screens it must already communicate process.

In live operation, restrained state changes may show progression.

---

## 7. Intelligence Plane

Target desktop width: approximately **290–310 px**.

The right-side system area is named **INTELLIGENCE**.

It is not a generic `Context` sidebar.

It can include:

```text
EVIDENCE
7 VERIFIED
3 OFFICIAL SOURCES
```

and:

```text
ACTIVITY

12:41  discovered
12:42  source verified
12:42  eligibility evaluated
12:43  decision → PREPARE
```

Also allowed:
- freshness/retrieval state;
- authority role;
- current source state;
- current agent phase;
- current run mode.

### Rules

- no decorative quote;
- no motivational text;
- no unrelated telemetry;
- no icon-in-circle timeline pattern unless semantically required;
- activity should use quiet typography and a precise event axis.

---

## 8. Evidence Plane

Evidence Plane is signature system #2.

It is a **materially different proof surface**, not a white card.

### 8.1 Peek state

A light proof plane may visibly enter the dark workspace as a partial overlapping layer.

Example:

```text
                  ┌────────────────────────
                  │ OFFICIAL RULES
                  │ Entrant type
                  │
                  │ “Individuals...”
                  │
                  │ verified · 4m
                  └────────────────────────
```

It should create visual tension between:
- dark analytical judgment;
- light documentary proof.

### 8.2 Expanded state

Opening `WHY THIS DECISION` transitions into an expanded light proof plane.

The Decision Field remains spatially understandable behind or adjacent to it; it is not replaced by a generic modal.

Expanded proof should expose a legible relationship:

`CLAIM → SOURCE → AUTHORITY ROLE → FRESHNESS`

Example:

```text
ELIGIBILITY PROOF

Applicant type
PASS

OFFICIAL RULES
Individuals and teams are eligible…

ROLE
Eligibility authority

VERIFIED
12:42 · official source
```

### Evidence-role integrity

The visual design must preserve backend authority boundaries.

Examples:
- eligibility proof must be visibly distinguishable from project-context proof;
- a general source must not visually imply deterministic eligibility authority;
- authoring-fact proof must not be misrepresented as decision authority.

---

## 9. Portfolio = Intelligence Dossier

Portfolio must not appear as a permanent settings form.

The default state is **view-first dossier**.

### 9.1 Founder dossier

Example:

```text
PORTFOLIO / FOUNDER

ROSTYSLAV BRENYCH
Founder · Brenych Studio

LOCATION
Barcelona, Spain

ENTITY
Individual

CAPACITY
12–16 h / week

FOCUS
AI agents
Creative technology
Spatial computing
Interactive systems
```

Context integrity may appear in an adjacent field:

```text
CONTEXT STATUS

IDENTITY        VERIFIED
LEGAL FORM      KNOWN
LOCATION        KNOWN
CAPACITY        KNOWN
FUNDING LIMIT   UNKNOWN
```

### 9.2 Project dossier

Example:

```text
PROJECT / QUALOR

AUTONOMOUS OPPORTUNITY INTELLIGENCE

STAGE
Active development

STACK
Python · Strands · Bedrock · React

TARGET
Founders / small technical teams

READINESS
Demo active
Public repository pending

CONSTRAINTS
Competition deadline
Limited implementation capacity
```

### 9.3 Editing

Editing is explicit and local.

Flow:

`view state → edit action → local edit state`

Do not render every value as a permanent HTML input.

The dossier geometry must survive edit mode.

### 9.4 Provenance / context linkage

Quiet annotations may expose states such as:
- `DOCUMENTED`
- `USER CONFIRMED`
- `UNKNOWN`

Optional thin context links can show why a fact matters:
- `ENTITY → eligibility`
- `CAPACITY → effort feasibility`
- `PROJECT STAGE → readiness`

These are not a graph visualization. They are explanatory structural cues.

---

## 10. Visual Grammar

QUALOR is constructed from three visual primitives.

### 10.1 Field

A large continuous working surface.

Examples:
- Opportunity Field
- Decision Field
- Intelligence Field

A Field has no rounded container and usually no full border.

Its boundary is established by:
- alignment;
- negative space;
- tonal shift;
- shared geometry.

### 10.2 Anchor

A compact fact positioned inside a Field.

Example:

```text
ELIGIBILITY
PASS
```

An Anchor can include:
- short label;
- stronger value;
- precise marker / hairline;
- optional provenance state.

It does not need a card.

### 10.3 Plane

A materially distinct layer that can overlap a Field.

Primary example:
- Evidence Plane

Not every content group may become a Plane. Overuse would recreate cards.

### Canonical rule

> **No container unless the information truly changes material or interaction mode.**

---

## 11. Information Density

Spatial Precision should be denser than Task 07R while remaining hierarchical.

Three simultaneous information levels are allowed.

### Primary
- recommendation;
- strategy;
- best project;
- eligibility.

### Secondary
- deadline;
- effort;
- readiness;
- blocker;
- freshness.

### Tertiary
- source count;
- retrieved time;
- run mode;
- provenance;
- activity timestamps.

The intended perception is:

> **simple at first glance, dense when inspected.**

At 1440×900 the canonical populated screen should contain approximately:
- 3–5 opportunities;
- one dominant recommendation state;
- 4 core facts;
- 2–4 secondary signals;
- Decision Trace;
- 3–5 intelligence/activity events;
- one visible proof-plane edge.

---

## 12. Recommendation-State Grammar

States:
- `APPLY`
- `PREPARE`
- `WATCH`
- `SKIP`

They must not be rendered as conventional filled badges.

State is expressed primarily through:
- position;
- typography;
- weight;
- contrast;
- restrained signal treatment.

Color is supporting, not primary.

Guidance:
- APPLY — highest clarity/contrast;
- PREPARE — strong but restrained;
- WATCH — muted cool state;
- SKIP — lower contrast, not a large red warning.

---

## 13. Materiality

The base environment is neutral carbon.

Directional palette:
- deep field: `#0B0C0E`
- primary surface: `#111316`
- secondary plane: `#171A1E`
- primary text: approximately `#F1F3F5`
- muted text: cool neutral gray
- active/focus signal: restrained ice/silver
- proof plane: warm off-white approximately `#F1F0EB`

Exact values may receive small optical tuning during implementation.

### Forbidden color drift

Do not introduce:
- olive;
- green-yellow cast;
- navy-heavy AI aesthetic;
- purple AI gradients;
- cyan-neon cyberpunk look;
- saturated state chips.

The signal accent is reserved for:
- focus;
- active trace;
- selected intelligence state;
- very small operational markers.

It is not a CTA fill system.

---

## 14. Typography

The workspace uses one strong contemporary technical grotesk system.

Manrope is not canonical and must not be treated as a final brand decision.

Typography must avoid:
- generic startup landing-page personality;
- large italic serif hero;
- futuristic display fonts;
- excessive letter spacing;
- ultra-thin display copy.

Desired hierarchy:
- recommendation — precise, wide, controlled;
- numerical values — strong dedicated numerical treatment;
- labels — compact uppercase;
- metadata — quiet;
- proof excerpts — may optionally use restrained document contrast inside the light Evidence Plane only.

If a candidate font makes the interface visibly generic, implementation must stop at the visual checkpoint rather than silently selecting arbitrary alternatives.

---

## 15. Micro-Geometry

Repeated structural rules may include:
- short 90° hairline anchors;
- tiny square/line trace markers;
- consistent baseline grid for numerical values;
- strong vertical axes for deadlines and timestamps;
- intentional asymmetric offset;
- alignment relationships between Opportunity Field and Decision Field.

Do not apply decorative HUD corners everywhere.

Geometry must have a semantic or compositional purpose.

---

## 16. Interaction and Motion

Motion reveals system state. It never compensates for weak composition.

### 16.1 State formation

Suggested sequence:

```text
VERIFY
↓
QUALIFY
↓
facts settle into coordinates
↓
strategy resolves
↓
recommendation resolves last
```

The recommendation should feel like the result of the field, not a hero appearing first.

### 16.2 Opportunity switching

Opportunity Field remains spatially stable.

Decision transition:
1. context changes;
2. anchors briefly return to neutral;
3. new values occupy the same coordinates;
4. recommendation resolves last;
5. Intelligence Plane updates independently.

Avoid full-page transition behavior.

### 16.3 Evidence transition

`WHY THIS DECISION` opens the Evidence Plane.

This is not a generic modal fade.

Expected behavior:
- Decision Field remains present;
- dark analytical field reduces emphasis;
- light proof material enters spatially above/alongside it;
- closing restores the exact previous focus/state.

### 16.4 Approval transition

No celebration animation.

Human approval completes the final Decision Trace boundary.

Conceptual transition:

`dark analytical field → human confirmation → light authored document`

### 16.5 Motion ranges

Indicative timing:
- hover/focus: **120–180 ms**
- local state/value transition: **220–320 ms**
- plane transition: **420–600 ms**

### 16.6 Reduced motion

With `prefers-reduced-motion`:
- remove spatial translation where possible;
- preserve state clarity via opacity or immediate transitions;
- never make information dependent on animation.

### Forbidden motion

- button bounce;
- floating cards;
- breathing glow;
- decorative pulsing dots;
- parallax;
- ambient looping motion;
- cursor-follow visuals.

---

## 17. Responsive Spatial Behavior

### 17.1 Desktop ≥1280 px

Full spatial instrument:

`Opportunity Field → Decision Field → Intelligence Plane`

Decision Field dominates.

Opportunity and Intelligence fields are secondary edges of the system.

### 17.2 Tablet 768–1279 px

Compressed instrument.

Guidance:
- Opportunity Field approximately 220–230 px;
- Decision Field remains primary;
- Intelligence Plane becomes contextual overlay/edge plane.

Do not force all three fields into equal narrow columns.

### 17.3 Mobile <768 px

Mobile uses a sequential projection of the same instrument:

`OPPORTUNITY → DECISION → INTELLIGENCE`

This is a responsive projection, not a new product IA.

The user must always retain access to:
- recommendation;
- eligibility;
- best project;
- deadline;
- effort/readiness;
- Decision Trace.

Tertiary telemetry may move into the Intelligence state.

### 17.4 Evidence on mobile

Evidence Plane can become a full-screen material transition.

This should emphasize:
- dark = analysis;
- light = proof.

### 17.5 Portfolio on mobile

View-first dossier remains canonical.

Do not degrade into a long permanent stack of form inputs.

### 17.6 Minimum width

Support down to **320 px** without horizontal page overflow.

### Responsive automatic failure

If mobile becomes a stack of generic SaaS cards, the design fails.

---

## 18. Empty Workspace

Empty state is a dormant instrument, not onboarding marketing.

Conceptual structure:

```text
PORTFOLIO CONTEXT

PROFILE
NOT READY

PROJECTS
0

QUALIFICATION
LOCKED


                    NO ACTIVE DECISION


TRACE
DISCOVER ○  VERIFY ○  QUALIFY ○  DECIDE ○  APPROVE ○
```

One clear action may be present:

`COMPLETE PORTFOLIO →`

No:
- hero paragraph;
- fake opportunity counts;
- fake readiness;
- fake search;
- invented live state.

---

## 19. Copy Language

QUALOR speaks operationally.

Good:
- `2 readiness gaps`
- `Eligibility requires review`
- `Official source verified`
- `Portfolio context incomplete`

Bad:
- `Unlock your potential`
- `Make smarter decisions`
- `Your opportunity awaits`
- `Powerful intelligence for you`

This applies to empty states as well.

---

## 20. Canonical Visual Proof State

The primary review frame is a populated Decision Workspace, not an empty shell.

Canonical information content should include:

```text
AWS AGENTS FOR HUMANS                              06D 14H
Professional Agents

                         82
                         STRATEGY

            PREPARE
            ───────
            Strong fit · 2 readiness gaps


BEST PROJECT                           ELIGIBILITY
QUALOR                                 PASS


EFFORT                                 READINESS
9–13 H                                 02 GAPS


DISCOVER ───── VERIFY ───── QUALIFY ───── DECIDE ───── APPROVE
   ●              ●              ●              ●              ○


                                      WHY THIS DECISION ↗
                                      7 VERIFIED · 3 SOURCES
```

This defines information hierarchy, not literal final pixel placement.

Synthetic visual proof is permitted only when permanently and visibly identified as:

`DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY`

It must never imply LIVE product truth.

---

## 21. Visual Acceptance Package

Before any final implementation commit, owner review must receive real browser screenshots of:

1. 1440×900 populated Decision Workspace;
2. 1440×900 empty Decision Workspace;
3. 1440×900 Portfolio dossier — view mode;
4. 1440×900 Portfolio dossier — edit mode;
5. 1440×900 Evidence Plane — expanded;
6. 1024 compressed instrument;
7. 390 mobile Decision state;
8. 390 mobile Evidence state;
9. keyboard-focus state;
10. reduced-motion sanity proof.

Required checkpoint status:

```text
STATUS=SPATIAL_PRECISION_VISUAL_PROOF_READY
OWNER_VISUAL_ACCEPTANCE=PENDING
COMMIT=NO
TASK8_STARTED=NO
```

The developer must stop here.

Tests passing do not authorize visual acceptance.

---

## 22. Automatic Visual Failure Conditions

The design automatically fails owner review if any of the following are true:

- the workspace reads as `sidebar + content + sidebar`;
- the main screen reads as hero + metrics;
- major content relies on boxed/card containers;
- Portfolio view mode looks like a settings form;
- Evidence looks like a white card or generic modal;
- mobile becomes stacked SaaS cards;
- `PREPARE` reads as a marketing headline;
- Decision Trace looks like a progress bar/stepper;
- the accent creates cyberpunk/AI-generic aesthetics;
- removing text reveals a generic SaaS grid;
- animation is needed to make static composition visually interesting;
- Task 07R composition has merely been recolored or reskinned;
- the design uses planets, orbit motifs, radar forms, glowing rings, fake metric dials, decorative graphs, or sci-fi wallpaper.

---

## 23. Positive Acceptance Test

QUALOR passes the visual gate when an observer can understand, without explanation, that the product:

> gathers signals, forms a decision, exposes the structure behind that decision, and allows the user to move from judgment to proof.

Removing the QUALOR logo should still leave these recognizable:
- Decision Field;
- Decision Trace;
- Evidence Plane;
- Dossier grammar.

The result should feel:
- technological;
- expensive;
- calm;
- precise;
- operational;
- distinctive;
- non-pop;
- non-generic.

---

## 24. Scope Boundaries

This visual correction must preserve current functional and architectural work wherever possible.

Do not change as part of this visual phase unless separately authorized:
- backend business logic;
- API/security contracts;
- approval policy;
- Draft Pack behavior;
- migrations;
- deterministic authority rules;
- LIVE/FIXTURE/REPLAY truthfulness;
- Task 8–10 business behavior.

The correction may modify presentation architecture, CSS/token systems, layout components, visual states, responsive projection, local interaction presentation, and view/edit presentation needed to realize this design.

No paid AWS call is required for visual implementation or review.

---

## 25. Canonical Design Decision

**APPROVED DIRECTION:** `A1 — Spatial Precision`

Core systems approved by owner:
- Decision Field;
- Decision Trace;
- material Evidence Plane;
- Portfolio Intelligence Dossier;
- Field / Anchor / Plane grammar;
- state-driven motion;
- full/compressed/sequential responsive behavior;
- hard owner visual checkpoint before commit.

Implementation planning must use this document as the visual authority for QUALOR-04A Task 07R2.
