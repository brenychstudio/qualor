# Bounded Acquisition Plan V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the finite deterministic acquisition plan that removes the over-broad Cartesian coverage requirement without weakening authority, context, budget, or eligibility invariants.

**Architecture:** SectionIndex gains child-local routing metadata; a new immutable AcquisitionPlan owns finite membership, tiering, rank, and activation predicates; SectionScheduler executes the plan; CoverageLedger accounts only activated obligations; SectionAcquisition owns one plan per source revision and maps bounded plan exhaustion truthfully to existing runtime semantics.

**Tech Stack:** Python 3.12, Pydantic contracts, pytest, Strands controlled transport, SQLite workspace acceptance, existing QUALOR runtime.

**Spec:** [docs/superpowers/specs/2026-09-14-bounded-acquisition-plan-v1-design.md](../specs/2026-09-14-bounded-acquisition-plan-v1-design.md)

## Implementation authority and baseline

Owner approval applies to the specification and this planning task only. Production
and test implementation remains unauthorized until a later explicit controller task.
No task below may be executed from this document alone.

Planning baseline: branch `feature/qualor-live-production`, HEAD
`70a5cf5c1da547a5db861b5d760c5fd623d7b109`, clean. The intended worktree is
`C:\PROJECTS\qualor\.worktrees\qualor-live-production`; the spelling
`qualor.worktrees` does not authorize creation of a second checkout.

Before future execution, read `AGENTS.md`, `docs/00_CANONICAL_BRIEF_UA.md`, the
approved specification, and this plan. Verify the branch, exact implementation-start
HEAD supplied by the controller, and a clean worktree. Do not reset, rebase, stash,
or discard unrelated work to manufacture the baseline.

## Global Constraints

The following constraints are copied verbatim from the controller instruction and
apply to every task:

```text
QUALOR_5F_INFERENCE_MAX_CALLS=9
PLANNING_CALLS=2
MAX_EXTRACTION_DISPATCHES=7
QUALOR_5F_COST_CAP_USD=0.35
MAX_STEPS=24
MAX_EXTRACTED_CLAIMS_PER_CALL=2

UNKNOWN != PASS
AMBIGUOUS != PASS
UNSUPPORTED != PASS

LLM_FINAL_ELIGIBILITY_AUTHORITY=NO

No eligibility-engine change.
No decision-engine change.
No persistence-policy change.
No successful-completion-policy change.
No frontend verdict-policy change.
No provider/model change.
No database migration.
No public schema change.
No call/cost/token increase.

No Devpost-specific, AWS Agents for Humans-specific, contest-name, source-domain,
archive-hash, or known-outcome production branches.

No paid LIVE run during implementation.
```

Additional execution constraints:

- Use RED/GREEN TDD within every behavioral task. A failing import proves only a
  missing interface; each task must then prove the named semantic failures before
  implementation.
- Use `apply_patch` for repository edits and explicit-path staging. Never use blanket
  staging.
- Keep the existing `LiveBudgetGuard` as the only physical call/cost authority.
- Keep `SourceSection` routing, AcquisitionPlan membership, CoverageLedger progress,
  semantic AdapterResult authority, effective coverage guard, deterministic decision,
  and WorkspaceRunCapture persistence as separate layers.
- Do not create a second planner, eligibility engine, decision engine, fact store,
  persistence path, or frontend policy.
- Keep external I/O denied for archive acceptance. No AWS, Bedrock, AgentCore,
  source download, DNS, external HTTP, deployment, push, or paid request.
- Keep raw model requests in test memory only. Do not persist prompts, responses,
  source bodies, credentials, or private profile data.
- After each commit, run the task's GREEN and regression commands, inspect the exact
  commit paths, require `git status --short` empty, and record the new HEAD before
  starting the next task.

---

## File structure and ownership

| Path | Action | Sole responsibility in this change |
| --- | --- | --- |
| `src/qualor/runtime/sections.py` | Modify | Child-local body/heading routing metadata, rule-like detection, unchanged structural/context graph, compatibility category union |
| `src/qualor/runtime/acquisition_plan.py` | Create | Immutable finite inventory, tiering, rank, activation predicates, plan/item identity, seven-dispatch capacity |
| `src/qualor/runtime/acquisition_coverage.py` | Modify | Plan activation/progress, semantic outcomes, category accounting, context/overflow diagnostics; no relevance classification |
| `src/qualor/runtime/section_scheduler.py` | Modify | Consume active plan items in stored order, preserve context closure, enforce plan capacity and truthful no-job reasons |
| `src/qualor/runtime/section_acquisition.py` | Modify | Build one plan per source revision, orchestrate extraction/activation, retain raw/effective authority separation, map acquisition stops |
| `tests/runtime/test_sections.py` | Modify | Routing and context invariants |
| `tests/runtime/test_acquisition_plan.py` | Create | Plan contracts, identity, tiering, ordering, activation, capacity, overflow |
| `tests/runtime/test_acquisition_coverage.py` | Modify | Plan-aware progress/accounting and temporary-constructor transition |
| `tests/runtime/test_section_scheduler.py` | Modify | Plan execution, context, bounds, deduplication, stop semantics |
| `tests/runtime/test_section_acquisition.py` | Modify | One-plan orchestration, guarded authority, Task 14 symptom regression |
| `tests/runtime/test_section_extraction.py` | Modify in Task 4 only | Constructor companion required by its real scheduler-based context tests; no extraction semantics change |
| `tests/runtime/conftest.py` | Modify in Task 4 only | Populate required plan identity fields in the shared direct `ExtractionJob` fixture; no fixture authority or extraction behavior change |
| `tests/runtime/test_archived_compiler_acceptance.py` | Modify | Archive plan/accounting/call/authority gates |
| `tests/runtime/archived_compiler_support.py` | Modify only in Task 5 | Expose bounded safe plan diagnostics and allow an actual 2-planning/at-most-7-extraction sequence; never route or decide |
| `tests/runtime/test_compiler_cost_simulation.py` | Modify only if Task 6 RED proves old exact-count assertions stale | Frozen policy and conservative request-cost gates |
| `tests/workspace/test_compiler_completion_gate.py` | Prefer unchanged | Truthful Task 14 case and persistence diagnostic |

No other production, test, generated, schema, frontend, documentation, or migration
file is planned. If a direct import/constructor search during execution finds another
consumer, stop the current commit, name the exact consumer and obtain controller
scope review before editing it.

## Dependency and checkpoint strategy

Dependency order is `1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8`.

Task 3 uses transition method A: add plan-aware CoverageLedger state behind
`CoverageLedger(index, plan=None)` while active production continues to construct
`CoverageLedger(index)` and therefore remains wholly legacy. The optional argument is
a temporary migration seam, not a runtime choice and not a second production
authority. Task 4 atomically:

1. changes the constructor to `CoverageLedger(index, plan)` with no default;
2. changes `SectionScheduler(index, plan, ledger, budget)`;
3. changes SectionAcquisition to build and supply the plan;
4. updates every direct constructor test consumer, including
   `test_section_extraction.py` and the direct `ExtractionJob` fixture in
   `tests/runtime/conftest.py`; and
5. deletes the legacy Cartesian `_is_relevant`/fallback derivation.

No commit may contain a CoverageLedger or SectionScheduler signature that its active
SectionAcquisition caller cannot satisfy. Task 1 retains the compatibility
`candidate_categories` union so the old scheduler remains functional. Task 2 creates
an unused production module. Task 3 adds an opt-in test path without activating it.
Task 4 is the only activation checkpoint; after it no legacy scheduling authority
remains. Every commit must pass touched-subsystem tests and leave a clean worktree.

---

## Task 1 — Section-local routing metadata

**Goal:** Remove sibling-body category smear while preserving every current section,
offset, span, parent, reference, global-scope, and context-completeness behavior. Do
not activate AcquisitionPlan.

**Files:**

- Modify: `src/qualor/runtime/sections.py`
- Modify: `tests/runtime/test_sections.py`

**Interfaces:**

- Consumes: existing `Category`, `Contract`, `SourceDocument`,
  `EvidenceSpanRegistry`, `_logical_regions()`, `_bounded_ranges()`, `_categories()`,
  `_section_references()`, and `_structural_ancestry()`.
- Produces in `sections.py`:

```python
ROUTING_VERSION = "bounded-acquisition-routing-v1"
INDEXER_VERSION = "section-index-v2"

class SectionRoutingReason(StrEnum):
    BODY_CATEGORY_TERM = "BODY_CATEGORY_TERM"
    HEADING_CATEGORY_TERM = "HEADING_CATEGORY_TERM"
    RULE_LIKE_MARKER = "RULE_LIKE_MARKER"
    STRUCTURAL_REFERENCE = "STRUCTURAL_REFERENCE"
    GLOBAL_SCOPE = "GLOBAL_SCOPE"

class RuleLikeMarker(StrEnum):
    OBLIGATION = "OBLIGATION"
    PROHIBITION = "PROHIBITION"
    LIMITATION = "LIMITATION"
    PERMISSION_OR_SCOPE = "PERMISSION_OR_SCOPE"
    TECHNOLOGY_OR_LICENSE = "TECHNOLOGY_OR_LICENSE"
    FINANCIAL_OR_REWARD = "FINANCIAL_OR_REWARD"
    SUBMISSION_OR_TIME = "SUBMISSION_OR_TIME"
    EVALUATION_OR_SELECTION = "EVALUATION_OR_SELECTION"
    STRUCTURAL_RULE_ITEM = "STRUCTURAL_RULE_ITEM"

class RuleLikeRouting(Contract):
    rule_like: StrictBool
    category_hints: tuple[Category, ...]
    marker_codes: tuple[RuleLikeMarker, ...]

class SectionRoutingMetadata(Contract):
    routing_version: Literal["bounded-acquisition-routing-v1"]
    body_categories: tuple[Category, ...]
    heading_categories: tuple[Category, ...]
    rule_like: StrictBool
    rule_like_category_hints: tuple[Category, ...]
    reason_codes: tuple[SectionRoutingReason, ...]

def detect_rule_like_routing(
    *, heading_text: str | None, body_text: str
) -> RuleLikeRouting
```

- Adds required `routing: SectionRoutingMetadata` to `SourceSection`.
- Preserves `candidate_categories: tuple[Category, ...]` as the canonical enum-order
  union of `routing.body_categories` and `routing.heading_categories` only.
- `SourceSection.heading` remains physically present only on the first bounded child;
  the exact logical heading is passed separately into every child's routing metadata.

- [ ] **RED:** Add failing tests for child-local versus heading routing

Add these named tests to `test_sections.py` using the existing `document` fixture and
a neutral logical heading whose oversized body splits across children:

```python
def test_sibling_body_category_does_not_smear_across_bounded_children(document):
    source = document(
        "Rules\n"
        + ("General explanatory material. " * 50)
        + "\nAn MIT license is required.\n"
        + ("Operational background. " * 50)
        + "\nProjects must use Widget SDK."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"r" * 32))
    license_child = next(
        section for section in index.sections
        if "MIT license" in source.text[section.start_offset:section.end_offset]
    )
    technology_child = next(
        section for section in index.sections
        if "Widget SDK" in source.text[section.start_offset:section.end_offset]
    )
    assert Category.LICENSE in license_child.routing.body_categories
    assert Category.REQUIRED_TECHNOLOGY not in license_child.routing.body_categories
    assert Category.REQUIRED_TECHNOLOGY in technology_child.routing.body_categories
    assert Category.LICENSE not in technology_child.routing.body_categories

def test_logical_heading_routes_every_child_but_is_not_child_zero_body(document):
    source = document("License\n" + ("General details. " * 120))
    index = index_source(source, EvidenceSpanRegistry(secret=b"h" * 32))
    assert len(index.sections) > 1
    assert all(Category.LICENSE in s.routing.heading_categories for s in index.sections)
    assert Category.LICENSE not in index.sections[0].routing.body_categories
    assert all(s.candidate_categories == (Category.LICENSE,) for s in index.sections)
```

- [ ] **Command:** Run the focused RED

Run:

```powershell
uv run --locked pytest tests/runtime/test_sections.py::test_sibling_body_category_does_not_smear_across_bounded_children tests/runtime/test_sections.py::test_logical_heading_routes_every_child_but_is_not_child_zero_body -q
```

**Expected RED:** `SourceSection` has no `routing` field and current logical-region
categories place sibling body categories on both children.

- [ ] **Step 3: Add RED tests for the exact generic detector and structural predicates**

Parameterize the fixed marker families and add structural/definition/no-category
tests:

```python
@pytest.mark.parametrize(
    ("text", "marker", "category"),
    [
        ("Participants must be eligible.", "OBLIGATION", Category.ENTRANT_TYPE),
        ("Residents may not enter.", "PROHIBITION", Category.GEOGRAPHY),
        ("Only incorporated companies qualify.", "LIMITATION", Category.LEGAL_ENTITY),
        ("Projects must use an API or SDK.", "TECHNOLOGY_OR_LICENSE", Category.REQUIRED_TECHNOLOGY),
        ("Copyright license is required.", "TECHNOLOGY_OR_LICENSE", Category.LICENSE),
        ("Funding support is prohibited.", "FINANCIAL_OR_REWARD", Category.FINANCIAL_SUPPORT),
        ("Award winners are subject to verification.", "FINANCIAL_OR_REWARD", Category.REWARD_CONDITIONS),
        ("Submit before the deadline.", "SUBMISSION_OR_TIME", Category.DEADLINE),
        ("Judging criteria use points and tie rules.", "EVALUATION_OR_SELECTION", Category.REWARD_CONDITIONS),
    ],
)
def test_rule_like_detector_is_generic_and_category_bounded(text, marker, category):
    routed = detect_rule_like_routing(heading_text=None, body_text=text)
    assert routed.rule_like
    assert RuleLikeMarker(marker) in routed.marker_codes
    assert category in routed.category_hints

def test_rule_like_without_category_hint_remains_unclassified():
    routed = detect_rule_like_routing(
        heading_text=None, body_text="Unless otherwise specified, this condition applies."
    )
    assert routed.rule_like
    assert routed.category_hints == ()

def test_structural_rule_item_and_definition_entry_are_recorded(document):
    source = document("License\n- License: MIT is required.\n")
    section = index_source(source, EvidenceSpanRegistry(secret=b"s" * 32)).sections[0]
    assert RuleLikeMarker.STRUCTURAL_RULE_ITEM in detect_rule_like_routing(
        heading_text="License", body_text="- License: MIT is required."
    ).marker_codes
    assert Category.LICENSE in section.routing.body_categories
    assert SectionRoutingReason.RULE_LIKE_MARKER in section.routing.reason_codes
```

- [ ] **Step 4: Run the detector RED**

Run:

```powershell
uv run --locked pytest tests/runtime/test_sections.py -k "rule_like or structural_rule_item or definition_entry" -q
```

Expected RED: the detector contracts/functions and marker enums do not exist.

- [ ] **Implementation:** Add routing metadata without changing context construction

In `sections.py`:

1. Add the enums/contracts/constants above with bounded validators that reject
   duplicate categories, marker codes, and reason codes.
2. Normalize detector input with `" ".join(text.casefold().split())` and boundary-aware
   regexes. Use only the generic marker phrases in the approved spec.
3. Implement private `_body_without_heading(text, start, end, heading, logical_start)`;
   remove the exact heading prefix only when `start == logical_start`.
4. Implement the approved predicates `_has_governing_marker()`,
   `_is_structural_rule_item()`, and `_is_definition_entry(category)` exactly as the
   spec defines them.
5. For every bounded range compute:

```python
body_text = _body_without_heading(source.text, start, end, heading, logical_start)
body_categories = _categories(body_text)
heading_categories = _categories(heading or "")
rule_like = detect_rule_like_routing(
    heading_text=heading,
    body_text=body_text,
)
candidate_categories = tuple(
    category
    for category in Category
    if category in body_categories or category in heading_categories
)
```

6. Set routing reason codes from the computed local/heading/detector data, then add
   `STRUCTURAL_REFERENCE` and `GLOBAL_SCOPE` during the existing context pass without
   changing how reference targets, ancestry, parent IDs, global IDs, overflow, unsafe
   cuts, or `context_complete` are calculated.
7. Bump `INDEXER_VERSION` to `section-index-v2` so identities do not reuse V1 routing
   semantics.

- [ ] **Step 6: Prove context and genericity invariants**

Add `test_routing_metadata_preserves_parent_reference_global_context` using the
existing final context fixture and assert the same expected parent/ancestry/reference/
global IDs and `context_complete` values. Keep every existing context test unchanged.
Add:

```python
def test_routing_source_has_no_archive_or_contest_specific_branches():
    source = inspect.getsource(importlib.import_module("qualor.runtime.sections")).casefold()
    forbidden = (
        "devpost", "agents for humans", "official-rules.raw",
        "e3f7640c", "agentsforhumans", "aws.amazon.com",
    )
    assert not any(value in source for value in forbidden)
```

- [ ] **GREEN:** Run the focused and neighboring regression commands

Run:

```powershell
uv run --locked pytest tests/runtime/test_sections.py tests/runtime/test_sources.py tests/runtime/test_evidence_spans.py tests/runtime/test_context_extraction.py -q
uv run --locked ruff check src/qualor/runtime/sections.py tests/runtime/test_sections.py
git diff --check
```

Expected GREEN: all listed tests pass; each child has deterministic routing metadata;
all prior exact offset/context tests pass; the active production scheduler still runs
through the compatibility union.

**Regression:** The GREEN block includes `test_sources.py`,
`test_evidence_spans.py`, and `test_context_extraction.py`; all must exit 0.

- [ ] **Review gate:** Inspect routing and context invariants

Review that `_logical_regions`, `_bounded_ranges`, `_section_references`,
`_structural_ancestry`, context ID order, unsafe-cut handling, and span capabilities
have no semantic changes beyond the version bump and routing metadata. Confirm no
model/provider/evaluator import.

**Commit:** Stage the two exact Task 1 paths and create the named checkpoint.

```powershell
git add src/qualor/runtime/sections.py tests/runtime/test_sections.py
git diff --cached --name-only
git diff --cached --check
git commit -m "feat: add section-local acquisition routing metadata"
git status --short
```

The staged name list must contain exactly the two paths above; final status must be
empty.

---

## Task 2 — Immutable acquisition plan

**Goal:** Introduce the finite planning authority and prove its identities, tiers,
ranking, activation predicates, and capacity without activating it in production.

**Files:**

- Create: `src/qualor/runtime/acquisition_plan.py`
- Create: `tests/runtime/test_acquisition_plan.py`

**Interfaces:**

- Consumes: `SectionIndex`, `SourceSection`, `SectionRoutingMetadata`,
  `SectionRoutingReason`, `RuleLikeMarker`, `ROUTING_VERSION`, and `Category` from
  Task 1.
- Produces the exact spec contracts `AcquisitionTier`,
  `ConditionalActivationReason`, `AcquisitionRanking`, `AcquisitionPlanItem`,
  `AcquisitionPlan`, `PlanActivation`, and `PlanOverflow`.
- Contract fields and bounds are fixed as follows; imports are `StrEnum`, `Literal`,
  `Annotated`, `StrictBool`, `StrictInt`, `Field`, `Contract`, and existing
  `NonEmpty`/`Category`:

```python
class AcquisitionTier(StrEnum):
    MANDATORY_ANCHOR = "MANDATORY_ANCHOR"
    CONDITIONAL_DISCOVERY = "CONDITIONAL_DISCOVERY"
    RESERVE_FALLBACK = "RESERVE_FALLBACK"

class ConditionalActivationReason(StrEnum):
    NO_SUPPORTED_ANCHOR = "NO_SUPPORTED_ANCHOR"
    AMBIGUOUS_ANCHOR = "AMBIGUOUS_ANCHOR"
    INCOMPLETE_GOVERNING_CONTEXT = "INCOMPLETE_GOVERNING_CONTEXT"
    RULE_LIKE_FALLBACK = "RULE_LIKE_FALLBACK"
    EXPLICIT_REFERENCE_REQUIRED = "EXPLICIT_REFERENCE_REQUIRED"
    GLOBAL_CONTEXT_REQUIRED = "GLOBAL_CONTEXT_REQUIRED"
    ROUTING_UNCERTAIN = "ROUTING_UNCERTAIN"

class AcquisitionRanking(Contract):
    tier_rank: Annotated[StrictInt, Field(ge=0, le=2)]
    category_rank: Annotated[StrictInt, Field(ge=0, le=8)] | None
    local_signal_rank: Annotated[StrictInt, Field(ge=0, le=3)]
    context_dependency_count: Annotated[StrictInt, Field(ge=0, le=12)]
    start_offset: Annotated[StrictInt, Field(ge=0)]

class AcquisitionPlanItem(Contract):
    item_id: str
    source_revision: str
    section_id: str
    categories: tuple[Category, ...]
    tier: AcquisitionTier
    context_section_ids: tuple[str, ...]
    context_complete: StrictBool
    activation_reasons: tuple[ConditionalActivationReason, ...]
    routing_reason_codes: tuple[SectionRoutingReason, ...]
    ranking: AcquisitionRanking

class AcquisitionPlan(Contract):
    plan_id: str
    source_id: NonEmpty
    source_revision: str
    indexer_version: NonEmpty
    routing_version: Literal["bounded-acquisition-routing-v1"]
    policy_name: Literal["QUALOR_5F"]
    planning_calls_reserved: Literal[2]
    max_extraction_jobs: Literal[7]
    items: tuple[AcquisitionPlanItem, ...]

class PlanActivation(Contract):
    item_id: str
    categories: tuple[Category, ...]
    reason: ConditionalActivationReason
    caused_by_item_ids: tuple[str, ...]
    authority_revision: Annotated[StrictInt, Field(ge=0)]

class PlanOverflow(Contract):
    item_id: str
    categories: tuple[Category, ...]
    reason_code: Literal["EXTRACTION_CAPACITY_REACHED"]
    dispatches_used: Literal[7]
```

- Produces:

```python
build_acquisition_plan(index: SectionIndex) -> AcquisitionPlan

def initial_plan_activations(
    plan: AcquisitionPlan, *, authority_revision: int
) -> tuple[PlanActivation, ...]

def activate_plan_items(
    plan: AcquisitionPlan,
    *,
    existing: tuple[PlanActivation, ...],
    reason: ConditionalActivationReason,
    categories: tuple[Category, ...],
    caused_by_item_ids: tuple[str, ...],
    authority_revision: int,
) -> tuple[PlanActivation, ...]
```

`initial_plan_activations()` returns static conditional activations for
`RULE_LIKE_FALLBACK`, `ROUTING_UNCERTAIN`, no-anchor
`NO_SUPPORTED_ANCHOR`, and reference/global dependencies of initially active
mandatory items. `activate_plan_items()` returns the full deduplicated activation
snapshot after adding the requested trigger and closing finite reference/global
dependencies to a fixed point. Neither function inspects model payloads or semantic
values.

- [ ] **RED:** Write failing contract and validation tests

Create the new test file with imports for every contract. Test enum values, field
bounds, required/forbidden category shapes, ID patterns, context uniqueness, and the
fixed policy fields:

```python
def test_plan_binds_the_frozen_qualor_5f_capacity(document):
    index = index_source(
        document("License\nAn MIT license is required."),
        EvidenceSpanRegistry(secret=b"p" * 32),
    )
    plan = build_acquisition_plan(index)
    assert plan.policy_name == "QUALOR_5F"
    assert plan.planning_calls_reserved == 2
    assert plan.max_extraction_jobs == 7
```

Add `test_plan_rejects_reserve_categories`,
`test_plan_rejects_empty_mandatory_categories`,
`test_plan_rejects_more_than_two_categories`, and
`test_plan_rejects_duplicate_context_or_activation_reasons`.

- [ ] **Command:** Run the contract RED

Run:

```powershell
uv run --locked pytest tests/runtime/test_acquisition_plan.py -k "capacity or rejects" -q
```

**Expected RED:** `qualor.runtime.acquisition_plan` does not exist.

- [ ] **Step 3: Add RED tier and inventory tests**

Use generic documents and Task 1 routing metadata:

```python
def test_all_sections_are_represented_without_reserve_cartesian_product(document):
    index = index_source(
        document("Background\nOrdinary descriptive text.\n"),
        EvidenceSpanRegistry(secret=b"p" * 32),
    )
    plan = build_acquisition_plan(index)
    reserve = [item for item in plan.items if item.tier is AcquisitionTier.RESERVE_FALLBACK]
    assert {item.section_id for item in plan.items} == {
        section.section_id for section in index.sections
    }
    assert len(reserve) == len(index.sections)
    assert all(item.categories == () for item in reserve)

def test_heading_only_signal_is_conditional_not_mandatory(document):
    index = index_source(
        document("License\nGeneral descriptive background."),
        EvidenceSpanRegistry(secret=b"p" * 32),
    )
    item = next(i for i in build_acquisition_plan(index).items if Category.LICENSE in i.categories)
    assert item.tier is AcquisitionTier.CONDITIONAL_DISCOVERY

def test_local_governing_body_signal_is_mandatory(document):
    index = index_source(
        document("Rules\nProjects must use Widget SDK."),
        EvidenceSpanRegistry(secret=b"p" * 32),
    )
    item = next(
        i for i in build_acquisition_plan(index).items
        if Category.REQUIRED_TECHNOLOGY in i.categories
    )
    assert item.tier is AcquisitionTier.MANDATORY_ANCHOR
```

Also assert no pair exists from sibling-only body vocabulary and every
`(section_id, category)` occurs in one tier only.

- [ ] **Step 4: Add RED identity, ordering, packing, and activation tests**

Add these named cases:

- `test_plan_identity_is_stable_across_run_scoped_span_capabilities`
- `test_plan_identity_changes_with_source_revision_indexer_routing_or_context`
- `test_plan_signature_excludes_clock_run_profile_model_and_verdict`
- `test_category_packing_requires_equal_tier_context_activation_and_rank`
- `test_category_packing_never_exceeds_two`
- `test_plan_order_is_tier_then_breadth_then_stable_ties`
- `test_initial_rule_like_conditionals_are_activated`
- `test_no_anchor_activates_matching_conditionals`
- `test_reference_and_global_activation_reaches_finite_fixed_point`
- `test_duplicate_activation_is_idempotent`
- `test_overflow_records_are_bounded_to_finite_plan_items`

Identity stability must construct indexes using different span-registry secrets and
assert identical plan/item IDs. Signature exclusion must assert
`tuple(inspect.signature(build_acquisition_plan).parameters) == ("index",)` and that
`acquisition_plan.py` imports neither eligibility, decisions, model, provider, agent,
nor workspace modules.

- [ ] **Step 5: Run semantic RED**

Run:

```powershell
uv run --locked pytest tests/runtime/test_acquisition_plan.py -q
```

Expected RED after the module shell exists: tier membership, stable hash identity,
breadth ordering, static activation, fixed-point closure, and overflow assertions
fail until their real logic is present.

- [ ] **Implementation:** Build the immutable plan with the specified pure helpers

Implement Pydantic contracts with `model_validator` checks from the spec. Use
canonical JSON (`sort_keys=True`, compact separators) and SHA-256 for IDs. Exclude
`span_ids`, current time, run ID, authority revision, facts, and outcomes from both
item and plan identity.

Use these private pure helpers:

```python
_local_mandatory(section: SourceSection, category: Category) -> bool
_tiered_pairs(section: SourceSection) -> tuple[tuple[Category, AcquisitionTier], ...]
_activation_reasons(section: SourceSection, category: Category) -> tuple[ConditionalActivationReason, ...]
_local_signal_rank(section: SourceSection, category: Category) -> int
_coalesce_items(items: tuple[AcquisitionPlanItem, ...]) -> tuple[AcquisitionPlanItem, ...]
_canonical_item_id(payload: dict[str, object]) -> str
_canonical_plan_id(payload: dict[str, object]) -> str
```

Construct mandatory body-local governing pairs first, conditional remaining body/
heading/rule-like/context pairs second, and one category-free reserve only when a
section has no category-addressed item. Coalesce only identical section/tier/context/
activation/local-rank pairs in enum order, two categories maximum. Compute breadth
depth per category/tier and sort by the exact spec key. Validate all index section
IDs and context references before returning the plan.

Activation uses only immutable plan metadata. Follow `context_section_ids` by plan
item section identity, emit `EXPLICIT_REFERENCE_REQUIRED` or
`GLOBAL_CONTEXT_REQUIRED` from stored routing reasons, and terminate after at most
the number of `(item_id, category)` obligations. Use the spec's reason precedence.

- [ ] **GREEN:** Run plan tests and no-import regressions

Run:

```powershell
uv run --locked pytest tests/runtime/test_acquisition_plan.py tests/runtime/test_sections.py -q
uv run --locked ruff check src/qualor/runtime/acquisition_plan.py tests/runtime/test_acquisition_plan.py
git diff --check
```

Expected GREEN: all plan and section tests pass; no existing production caller imports
or constructs AcquisitionPlan yet.

**Regression:** The GREEN block includes the unchanged section suite plus Ruff and
whitespace verification; every command must exit 0.

- [ ] **Review gate:** Inspect plan determinism, finiteness, and dependency direction

Review every hash input, tuple order, validator, tier predicate, capacity literal,
activation reason, and import. Confirm no source text/body, model outcome, applicant
fact, or verdict enters identity/rank.

**Commit:** Stage exactly the new plan module and its test, then create the named
checkpoint.

```powershell
git add src/qualor/runtime/acquisition_plan.py tests/runtime/test_acquisition_plan.py
git diff --cached --name-only
git diff --cached --check
git commit -m "feat: add deterministic bounded acquisition plan"
git status --short
```

The staged list must contain exactly the two new files and status must be empty.

---

## Task 3 — Plan-aware coverage accounting

**Goal:** Implement plan-owned activation, progress, semantic retention, category
accounting, context failure, and overflow behind a temporary additive constructor,
while leaving the active production runtime on its intact legacy path until Task 4.

**Files:**

- Modify: `src/qualor/runtime/acquisition_coverage.py`
- Modify: `tests/runtime/test_acquisition_coverage.py`

**Interfaces:**

- Consumes: Task 2 `AcquisitionPlan`, `AcquisitionPlanItem`, `AcquisitionTier`,
  `ConditionalActivationReason`, `PlanActivation`, `PlanOverflow`,
  `initial_plan_activations()`, and `activate_plan_items()`; existing
  `AcquisitionOutcome`, `AcquisitionState`, `AttemptKey`, `CoverageTransition`, and
  `SectionIndex`.
- Adds:

```python
type PlanObligationKey = tuple[str, str, Category]  # plan_id, item_id, category
type ActivatedPlanItem = tuple[AcquisitionPlanItem, tuple[Category, ...]]

class CategoryAccountingState(StrEnum):
    PENDING = "PENDING"
    SUPPORTED = "SUPPORTED"
    EXHAUSTED_UNRESOLVED = "EXHAUSTED_UNRESOLVED"
    CONTEXT_UNRESOLVED = "CONTEXT_UNRESOLVED"
    OVERFLOW_UNRESOLVED = "OVERFLOW_UNRESOLVED"

class PlanItemState(StrEnum):
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    EXTRACTION_ATTEMPTED = "EXTRACTION_ATTEMPTED"
    ACCOUNTED = "ACCOUNTED"
    CONTEXT_UNRESOLVED = "CONTEXT_UNRESOLVED"
    OVERFLOW_UNDISPATCHED = "OVERFLOW_UNDISPATCHED"
```

- Task 3 temporary constructor and final Task 4 constructor:

```python
# Task 3 only
CoverageLedger(index: SectionIndex, plan: AcquisitionPlan | None = None)

# Task 4 final
CoverageLedger(index: SectionIndex, plan: AcquisitionPlan)
```

- Plan-aware API introduced in Task 3 and retained:

```python
accounting_state(self, category: Category) -> CategoryAccountingState
def active_items(
    self, tier: AcquisitionTier | None = None
) -> tuple[ActivatedPlanItem, ...]
def unresolved_obligations(
    self, category: Category | None = None
) -> tuple[PlanObligationKey, ...]
reconcile_plan(self, authority_revision: int) -> tuple[PlanActivation, ...]
def begin_item(
    self,
    item_id: str,
    categories: tuple[Category, ...],
    authority_revision: int,
) -> None
def complete_item(
    self,
    item_id: str,
    categories: tuple[Category, ...],
    outcomes: dict[Category, AcquisitionOutcome],
    authority_revision: int,
) -> None
def operational_failure_item(
    self, item_id: str, categories: tuple[Category, ...], reason_code: str
) -> None
def budget_blocked_item(
    self, item_id: str, categories: tuple[Category, ...]
) -> None
def mark_context_unresolved(
    self, item_id: str, categories: tuple[Category, ...], authority_revision: int
) -> None
def mark_plan_overflow(
    self, *, dispatches_used: Literal[7], authority_revision: int
) -> tuple[PlanOverflow, ...]
replace_index(self, index: SectionIndex, plan: AcquisitionPlan) -> None
```

Properties `activations`, `plan_item_states`, `overflows`, `attempts`, `outcomes`,
`attempt_tiers`, and `transitions` return immutable snapshots. In plan mode,
`attempt_tiers` maps existing AttemptKeys to `AcquisitionTier`; it remains diagnostic
compatibility and is not a relevance authority.

`CoverageTransition` gains `plan_id`, `item_id`, `accounting_before`, and
`accounting_after`. A transition without an extraction key still binds source
revision/category for activation, context, and overflow causes.

- [ ] **Step 1: Preserve legacy production behavior before adding plan mode**

Run the pre-change baseline:

```powershell
uv run --locked pytest tests/runtime/test_acquisition_coverage.py tests/runtime/test_section_scheduler.py tests/runtime/test_section_acquisition.py tests/runtime/test_section_extraction.py -q
```

Expected baseline: PASS. Record counts. This is the evidence that Task 3 must not
break while `plan=None` remains the active production construction.

- [ ] **RED:** Write failing tests for discoverability, activation, and obligations

Add `_planned(index)` returning `(build_acquisition_plan(index),
CoverageLedger(index, plan))` and these tests:

```python
def test_inactive_conditional_is_not_unfinished_mandatory(document):
    index = _index(document, "License\nGeneral background.")
    plan = build_acquisition_plan(index)
    ledger = CoverageLedger(index, plan)
    assert ledger.active_items(AcquisitionTier.MANDATORY_ANCHOR) == ()
    assert all(
        state is PlanItemState.INACTIVE
        for key, state in ledger.plan_item_states.items()
        if key[2] is Category.LICENSE
    )

def test_reserve_is_discoverable_without_nine_category_obligations(document):
    index = _index(document, "Ordinary background notes.")
    plan = build_acquisition_plan(index)
    ledger = CoverageLedger(index, plan)
    assert len(plan.items) == len(index.sections)
    assert ledger.unresolved_obligations() == ()
    assert all(ledger.state(category) is not AcquisitionState.SUPPORTED for category in Category)
```

Also add named tests for active mandatory and active conditional blocking support.

- [ ] **Command:** Run the activation RED

Run:

```powershell
uv run --locked pytest tests/runtime/test_acquisition_coverage.py -k "inactive_conditional or reserve_is_discoverable or active_mandatory or active_conditional" -q
```

**Expected RED:** CoverageLedger does not accept a plan and exposes none of the plan
accounting APIs.

- [ ] **Step 4: Add RED semantic/accounting tests**

Add these exact cases:

- `test_supported_requires_authority_and_all_activated_obligations_accounted`
- `test_supported_context_incomplete_is_context_unresolved`
- `test_ambiguous_outcome_is_retained_and_never_supported`
- `test_unknown_outcome_is_retained_and_never_supported`
- `test_unsupported_outcome_is_retained_and_never_supported`
- `test_exhausted_unresolved_is_acquisition_state_not_pass`
- `test_overflow_preserves_every_activated_undispatched_obligation`
- `test_transition_binds_plan_item_category_source_and_authority_revision`
- `test_revised_source_requires_matching_new_plan_and_cannot_reuse_attempts`
- `test_plan_mode_never_calls_cartesian_relevance`

For the support case, begin/complete one mandatory item with a real
`AcquisitionOutcome(normalization_status="SUPPORTED", supported_rule_ids=("rule-1",),
conditional=False, context_complete=True, reason_code="SECTION_CANDIDATES_ADMITTED")`
and assert both states are `SUPPORTED` only after every activated obligation for the
category is accounted. For ambiguous/unknown/unsupported, assert the exact stored
normalization status and non-supported accounting state.

- [ ] **Step 5: Run semantic RED**

Run:

```powershell
uv run --locked pytest tests/runtime/test_acquisition_coverage.py -k "supported_requires or context_incomplete or outcome_is_retained or exhausted_unresolved or overflow_preserves or transition_binds or revised_source or cartesian" -q
```

Expected RED: missing plan-item transitions/accounting or current Cartesian
`_is_relevant` produces category obligations for reserve sections.

- [ ] **Implementation:** Add the temporary opt-in plan-aware accounting path

Keep the current implementation unchanged in private `_LegacyCoverageLedger` logic
called only when `plan is None`. For `plan is not None`:

1. Validate plan/index source ID, source revision, and indexer version.
2. Initialize mandatory obligation keys as `ACTIVE`, conditional keys as `INACTIVE`,
   category-free reserve inventory without obligation keys, then apply
   `initial_plan_activations()`.
3. Store plan item states keyed by `(plan_id, item_id, category)`. Reserve promotion
   creates keys only from validated PlanActivation categories.
4. `reconcile_plan()` derives `AMBIGUOUS_ANCHOR`, `NO_SUPPORTED_ANCHOR`, and incomplete
   context triggers from retained outcomes, invokes Task 2 activation closure until
   no new record appears, and never calls a model.
5. `begin_item()` validates ACTIVE state, exact categories, source revision, and no
   duplicate AttemptKey before recording both item and legacy attempt diagnostics.
6. `complete_item()` retains each exact semantic outcome and moves the obligation to
   ACCOUNTED before deriving category state.
7. Derive `SUPPORTED` only with supported rule IDs, all activated obligations
   accounted, no ambiguity/contradiction reason, and complete section/outcome context.
8. Mark context and overflow obligations explicitly; map boundedly finished incomplete
   acquisition to existing `AcquisitionState.EXHAUSTED` with the separate exact
   CategoryAccountingState.
9. Return immutable copies/proxies for every diagnostic property.

Do not route a plan-mode method through legacy `_is_relevant`; test this by
monkeypatching that function to raise while plan-mode tests pass.

- [ ] **GREEN:** Run accounting tests and active-production compatibility

Run:

```powershell
uv run --locked pytest tests/runtime/test_acquisition_coverage.py -q
uv run --locked pytest tests/runtime/test_section_scheduler.py tests/runtime/test_section_acquisition.py tests/runtime/test_section_extraction.py -q
uv run --locked ruff check src/qualor/runtime/acquisition_coverage.py tests/runtime/test_acquisition_coverage.py
git diff --check
```

Expected GREEN: plan-aware accounting tests pass; legacy scheduler/acquisition tests
remain green through `plan=None`; no production call site has changed.

**Regression:** The GREEN block includes unchanged scheduler, acquisition, and
extraction suites plus Ruff; every command must exit 0.

- [ ] **Review gate:** Inspect temporary seam isolation and semantic retention

Review that the temporary legacy branch is reachable only by omitted `plan`, current
production omits it, tests cannot select plan mode through runtime input, and Task 4
is explicitly responsible for deleting it. Verify all semantic outcomes remain
retained and no state value equals eligibility PASS.

**Commit:** Stage only the coverage module and its test, then create the named
checkpoint.

```powershell
git add src/qualor/runtime/acquisition_coverage.py tests/runtime/test_acquisition_coverage.py
git diff --cached --name-only
git diff --cached --check
git commit -m "feat: add plan-aware acquisition accounting"
git status --short
```

The staged list must contain exactly these two paths; status must be empty.

---

## Task 4 — Plan-driven scheduler and production cutover

**Goal:** Atomically activate the finite plan in production, remove legacy Cartesian
coverage/scheduling, and preserve a runnable repository across the constructor
cutover.

**Files:**

- Modify: `src/qualor/runtime/acquisition_coverage.py`
- Modify: `src/qualor/runtime/section_scheduler.py`
- Modify: `src/qualor/runtime/section_acquisition.py`
- Modify: `tests/runtime/test_acquisition_coverage.py`
- Modify: `tests/runtime/test_section_scheduler.py`
- Modify: `tests/runtime/test_section_acquisition.py`
- Modify: `tests/runtime/test_section_extraction.py` only to construct plan-aware
  ledger/scheduler in `_scheduled_license()` and related scheduler fixtures
- Modify: `tests/runtime/conftest.py` only to supply required plan identity fields on
  its direct `ExtractionJob` fixture; do not change fixture authority

**Interfaces:**

- Consumes Task 2 plan contracts/functions and Task 3 plan-aware CoverageLedger API.
- Final constructors:

```python
CoverageLedger(index: SectionIndex, plan: AcquisitionPlan)

SectionScheduler(
    index: SectionIndex,
    plan: AcquisitionPlan,
    ledger: CoverageLedger,
    budget: LiveBudgetGuard,
)
```

- `ExtractionJob` adds:

```python
plan_id: str  # acquisition_plan_<32 hex>
plan_item_id: str  # plan_item_<32 hex>
tier: AcquisitionTier
```

- `NoExtractionReason` adds literal `PLAN_EXHAUSTED`.
- SectionAcquisition initializes:

```python
self.index = index_source(source, run.extractor.span_registry)
self.plan = build_acquisition_plan(self.index)
self.ledger = CoverageLedger(self.index, self.plan)
self.scheduler = SectionScheduler(self.index, self.plan, self.ledger, run.budget)
```

- [ ] **RED:** Write failing scheduler tests against the plan interfaces

Replace test helpers with:

```python
def _scheduled(index, budget=None):
    plan = build_acquisition_plan(index)
    ledger = CoverageLedger(index, plan)
    scheduler = SectionScheduler(index, plan, ledger, budget or live_budget())
    return plan, ledger, scheduler
```

Add:

```python
def test_scheduler_executes_stored_plan_order_not_cartesian_relevance(document):
    index = _priority_index(document)
    plan, ledger, scheduler = _scheduled(index)
    expected = next(
        item for item in plan.items
        if item.tier is AcquisitionTier.MANDATORY_ANCHOR
    )
    job = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)
    assert job.plan_id == plan.plan_id
    assert job.plan_item_id == expected.item_id
    assert job.categories == expected.categories

def test_category_free_reserve_is_never_directly_dispatched(document):
    index = _index(document, "Ordinary background notes.")
    plan, _ledger, scheduler = _scheduled(index)
    assert all(item.tier is AcquisitionTier.RESERVE_FALLBACK for item in plan.items)
    result = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)
    assert isinstance(result, NoExtractionJob)
    assert result.reason_code == "PLAN_EXHAUSTED"
```

Add/replace exact cases for mandatory-before-conditional, breadth-before-depth,
stored-rank tie breaking, max-two categories, duplicate pair refusal, reference/global
fixed-point activation, context closure equality, context-unresolved marking, reserve
promotion only by indexed edges, and strong source-exhaustion predicate.

- [ ] **Command:** Run the scheduler RED

Run:

```powershell
uv run --locked pytest tests/runtime/test_section_scheduler.py -q
```

**Expected RED:** SectionScheduler does not accept a plan, ExtractionJob lacks plan fields,
and current fallback schedules the category-free reserve across categories.

- [ ] **Step 3: Add physical-capacity and budget-order RED tests**

The scheduler captures `self._inference_calls_at_start` from the shared budget at
construction. Its physical extraction count is
`budget.snapshot().inference_calls - self._inference_calls_at_start`. Add:

```python
def test_seventh_physical_extraction_exhausts_plan_before_budget_check(document):
    index = _many_mandatory_items_index(document)
    budget = live_budget()
    plan, ledger, scheduler = _scheduled(index, budget)
    for revision in range(7):
        job = scheduler.next_job(
            authority_revision=revision, steps_remaining=24 - revision, terminated=False
        )
        scheduler.begin(job)
        receipt = budget.reserve(LiveCallKind.INFERENCE)
        budget.commit(receipt)
        ledger.operational_failure_item(job.plan_item_id, job.categories, "CONTROLLED_FAILURE")
    stopped = scheduler.next_job(authority_revision=7, steps_remaining=17, terminated=False)
    assert stopped.reason_code == "PLAN_EXHAUSTED"
    assert stopped.pivot_eligible is False
    assert ledger.overflows

def test_real_guard_refusal_before_seven_remains_budget_blocked(document):
    budget = _cost_exhausted_budget_with_inference_capacity()
    _plan, _ledger, scheduler = _scheduled(_priority_index(document), budget)
    stopped = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)
    assert stopped.reason_code == "BUDGET_BLOCKED"
```

Do not expose the budget as a public scheduler property in production. The test
retains its local budget reference and commits controlled reservations through that
shared object.

- [ ] **Step 4: Add SectionAcquisition RED for the Task 14 symptom**

Extend the existing controlled LIVE harness with enough generic mandatory/conditional
sections to consume seven extraction calls. Add:

```python
def test_bounded_plan_stops_without_bookkeeping_budget_exhaustion(harness):
    run, client = harness(behavior="supported", source_text=_bounded_plan_source())
    run_agent(run, model=_model(client, run.budget))
    assert run.budget.snapshot().inference_calls <= 9
    assert run.section_acquisition.plan.max_extraction_jobs == 7
    assert run.termination_reason == "NO_PROGRESS"
    assert run.section_acquisition.ledger.overflows
    assert run.termination_reason != "BUDGET_EXHAUSTED"
```

Retain existing `test_nine_call_ceiling_and_step_guard_are_shared` as a genuine
physical budget test, changing its setup so it exhausts the guard before plan
capacity rather than relying on an eighth bookkeeping selection.

- [ ] **Step 5: Run acquisition RED**

Run:

```powershell
uv run --locked pytest tests/runtime/test_section_acquisition.py::test_bounded_plan_stops_without_bookkeeping_budget_exhaustion -q
```

Expected RED: `SectionAcquisition` has no `plan`; after two planning and seven
extraction calls the old scheduler asks for another Cartesian pair and maps the guard
refusal to `BUDGET_EXHAUSTED`.

- [ ] **Implementation:** Perform the atomic coverage, scheduler, and orchestration cutover

In `acquisition_coverage.py`, remove the optional plan default, delete the legacy
branch and `_is_relevant`, and make `replace_index(index, plan)` validate a new
revision-bound plan. All states derive from plan obligations.

In `section_scheduler.py`:

1. Store `index`, `plan`, `ledger`, `budget`, and the construction-time inference
   count.
2. At `next_job()`, check run termination and steps, call
   `ledger.reconcile_plan(authority_revision)`, and consume `ledger.active_items()` in
   the plan's stored order.
3. Mark unsafe context through `mark_context_unresolved()` and continue to the next
   active item; never truncate spans.
4. Before checking general budget availability, compare physical extraction calls
   since scheduler construction to `plan.max_extraction_jobs`. At seven, call
   `mark_plan_overflow(dispatches_used=7, ...)` and return `PLAN_EXHAUSTED`.
5. Preserve the existing budget snapshot check for a permitted first-through-seventh
   job. Return `BUDGET_BLOCKED` on real physical refusal.
6. Build jobs only from active plan item/category pairs. Use plan/item/tier in job ID.
7. Return `SOURCE_EXHAUSTED` only when all indexed sections are accounted, no active
   or promotable obligation remains, context is complete, and no uninspected reserve
   exists; otherwise return `PLAN_EXHAUSTED` or `CONTEXT_UNRESOLVED`.
8. `begin(job)` validates all plan fields and calls `ledger.begin_item()`.

In `section_acquisition.py`, add `self.plan = None`, build it exactly once beside the
index, and use the final constructors. Complete/fail/unwind by plan item ID. Extend
the no-job mapping only as follows:

```python
terminal_reason = {
    "STEP_BOUND": "MAX_STEPS",
    "BUDGET_BLOCKED": "BUDGET_EXHAUSTED",
    "PLAN_EXHAUSTED": "NO_PROGRESS",
}.get(job.reason_code, "NO_PROGRESS")
```

Do not change `_effective_authority()` except to ask the plan-aware ledger state. Raw
observations stay in `_observations`; effective supported results remain guarded
unless `ledger.state(category) is AcquisitionState.SUPPORTED`.

- [ ] **Step 7: Update every constructor consumer in the same uncommitted change**

Update helpers in `test_acquisition_coverage.py`, `test_section_scheduler.py`, and
the `_scheduled_license()` helper in `test_section_extraction.py` to build one plan
and pass it to both ledger and scheduler. Update the direct `ExtractionJob`
construction in `tests/runtime/conftest.py` with an item from the same immutable plan.
The planning-baseline constructor audit proves this companion update is required; it
belongs in the atomic cutover instead of being hidden behind defaults or an
unvalidated legacy-job path.

Run before committing:

```powershell
rg -n "CoverageLedger\([^,\n]+\)|SectionScheduler\([^,\n]+,[^,\n]+,[^,\n]+\)" src tests --glob '*.py'
```

Expected: no old production/test constructor remains. Manually inspect multiline
matches because regex absence alone is not proof.

- [ ] **GREEN:** Run the coordinated activation verification

Run:

```powershell
uv run --locked pytest tests/runtime/test_acquisition_plan.py tests/runtime/test_acquisition_coverage.py tests/runtime/test_section_scheduler.py tests/runtime/test_section_acquisition.py tests/runtime/test_section_extraction.py -q
uv run --locked pytest tests/runtime/test_agent.py tests/runtime/test_live_inference_efficiency.py tests/runtime/test_model_receipts.py tests/runtime/test_section_handoff.py tests/runtime/test_canonical_adapters.py tests/runtime/test_autonomous_loop.py -q
uv run --locked pytest tests/workspace/test_live_run_persistence.py tests/e2e/test_live_workspace_persistence.py tests/test_hosted_live_runs.py -q
uv run --locked ruff check src/qualor/runtime/acquisition_coverage.py src/qualor/runtime/section_scheduler.py src/qualor/runtime/section_acquisition.py tests/runtime/conftest.py tests/runtime/test_acquisition_coverage.py tests/runtime/test_section_scheduler.py tests/runtime/test_section_acquisition.py tests/runtime/test_section_extraction.py
git diff --check
```

Expected GREEN: all commands exit 0; the Task 14 symptom regression ends
`NO_PROGRESS`, no test requires CASE_A, and existing provider/failure/persistence
semantics remain green.

**Regression:** The GREEN block includes agent, inference-efficiency, receipt,
handoff, adapter, autonomous-loop, workspace, E2E, hosted, extraction, and Ruff
suites; every command must exit 0.

- [ ] **Review gate:** Inspect the single scheduling authority and stop mappings

Require:

```text
ACTIVE_SCHEDULING_AUTHORITIES=1
CARTESIAN_RELEVANCE_CALLS=0
PLAN_BUILDS_PER_SOURCE_REVISION=1
MAX_EXTRACTION_DISPATCHES=7
EIGHTH_MODEL_RESERVATION=0
PLAN_EXHAUSTED_RUNTIME_MAPPING=NO_PROGRESS
PHYSICAL_BUDGET_BLOCK_RUNTIME_MAPPING=BUDGET_EXHAUSTED
SUCCESS_TERMINATION_SET_CHANGED=NO
SOURCE_PIVOT_ACTIVATED=NO
```

Inspect imports and diff to prove no changes to `loop.py` completion rules,
eligibility, decisions, adapters, budget, provider, workspace, or frontend.

- [ ] **Commit:** Stage and commit the indivisible activation checkpoint

```powershell
git add src/qualor/runtime/acquisition_coverage.py src/qualor/runtime/section_scheduler.py src/qualor/runtime/section_acquisition.py tests/runtime/conftest.py tests/runtime/test_acquisition_coverage.py tests/runtime/test_section_scheduler.py tests/runtime/test_section_acquisition.py tests/runtime/test_section_extraction.py
git diff --cached --name-only
git diff --cached --check
git commit -m "feat: activate bounded acquisition plan"
git status --short
```

The staged list must contain exactly these eight paths. Do not split constructor
changes across commits. Status must be empty.

---

## Task 5 — Archived compiler acceptance and hidden-clause accounting

**Goal:** Prove the real hash-bound archive travels through the plan-driven production
chain within seven extractions, retains deadline authority, explicitly accounts for
all critical categories and diagnosed hidden clauses, and does not stop for
bookkeeping-induced budget exhaustion.

**Files:**

- Modify: `tests/runtime/test_archived_compiler_acceptance.py`
- Modify: `tests/runtime/archived_compiler_support.py`

**Interfaces:**

- Consumes: unchanged `load_archived_rules()`, `deny_external_io()`, controlled
  Strands/Bedrock transport, production SectionAcquisition plan/ledger, and existing
  `compile_section_authority()`.
- Extends test-only `ArchivedCompilerReport` with safe bounded fields:

```python
plan_id: str
plan_items: tuple[MappingProxyType, ...]
plan_activations: tuple[MappingProxyType, ...]
plan_overflows: tuple[MappingProxyType, ...]
accounting_states: MappingProxyType
```

Each `plan_items` entry contains only `item_id`, `section_id`, `start_offset`,
`end_offset`, `tier`, `categories`, `rule_like`, `rule_like_category_hints`,
`child_local_unclassified`, `is_context_dependency`, `plan_item_state`, and
`accounting_states`. It contains no
source text, prompt, candidate value, private fact, model response, or verdict.

- Changes helper constants/validation to:

```python
CANONICAL_PLANNING_REQUESTS = 2
MAX_CANONICAL_EXTRACTION_REQUESTS = 7
```

`simulate_request_sequence()` must require exactly two planning requests, between one
and seven extraction requests for this accepted compiler path, one search, one fetch,
and exact event/request count agreement. It continues to use production request
dictionaries and reservation functions only.

- Adds calculated gate values with exact keys:

```text
PLANNING_CALLS
EXTRACTION_CALLS
TOTAL_MODEL_CALLS
OVER_BROAD_RELEVANCE_BUDGET_EXHAUSTED
ALL_NINE_CATEGORIES_DISCOVERABLE
ALL_NINE_CATEGORIES_ACCOUNTED_OR_EXPLICITLY_UNRESOLVED
DEADLINE_RAW_AUTHORITY_SUPPORTED
DEADLINE_RAW_AUTHORITY_EXECUTABLE
UNKNOWN_CATEGORIES_REMAIN_UNRESOLVED
HIDDEN_GOVERNING_CLAUSE_SILENTLY_SKIPPED
```

- [ ] **RED:** Run the archive test unchanged to expose stale Cartesian assertions

Run offline:

```powershell
$env:UV_OFFLINE='1'
$env:QUALOR_REQUIRE_ARCHIVE='1'
$env:QUALOR_ARCHIVE_DIR='C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source\.qualor\local\killer-demo-real-source'
uv run --locked pytest tests/runtime/test_archived_compiler_acceptance.py -q
```

**Expected RED:** the old acceptance expects `coverage_states["DEADLINE"] ==
"SECTION_AVAILABLE"` and `DEADLINE_RELEVANT_UNATTEMPTED_REMAINS > 0`; the new
plan-driven result exposes different bounded accounting and lacks the new gate fields.
If it instead fails due provider/network/archive/hash, stop and diagnose that blocker.

- [ ] **Command:** Add the bounded assertions, then rerun the same offline RED command

```powershell
$env:UV_OFFLINE='1'
$env:QUALOR_REQUIRE_ARCHIVE='1'
$env:QUALOR_ARCHIVE_DIR='C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source\.qualor\local\killer-demo-real-source'
uv run --locked pytest tests/runtime/test_archived_compiler_acceptance.py -q
```

Expected: the new gate assertions fail until the passive helper exposes actual plan,
activation, overflow, category-accounting, and hidden-clause diagnostics.

Replace obsolete Cartesian-progress assertions with:

```python
assert report.gate_values["PLANNING_CALLS"] == 2
assert report.gate_values["EXTRACTION_CALLS"] <= 7
assert report.gate_values["TOTAL_MODEL_CALLS"] <= 9
assert report.gate_values["OVER_BROAD_RELEVANCE_BUDGET_EXHAUSTED"] is False
assert report.gate_values["ALL_NINE_CATEGORIES_DISCOVERABLE"] is True
assert report.gate_values[
    "ALL_NINE_CATEGORIES_ACCOUNTED_OR_EXPLICITLY_UNRESOLVED"
] is True
assert report.gate_values["DEADLINE_RAW_AUTHORITY_SUPPORTED"] is True
assert report.gate_values["DEADLINE_RAW_AUTHORITY_EXECUTABLE"] is True
assert report.gate_values["UNKNOWN_CATEGORIES_REMAIN_UNRESOLVED"] is True
assert report.gate_values["HIDDEN_GOVERNING_CLAUSE_SILENTLY_SKIPPED"] == 0
```

Retain every existing source hash, exact quote, qualifier/exception, independent fact,
raw/effective authority, rule evidence, decision authority, receipt, and mode
assertion. Do not assert eligibility PASS or a recommendation.

- [ ] **Step 3: Add RED hidden-clause accounting assertions**

Derive the diagnosed set from generic production routing metadata, not archive names:

```python
potential_hidden = tuple(
    item for item in report.plan_items
    if item["child_local_unclassified"]
    and item["rule_like"]
    and item["rule_like_category_hints"]
    and item["tier"] in {"MANDATORY_ANCHOR", "CONDITIONAL_DISCOVERY"}
)
assert len(potential_hidden) == 7
assert all(
    item["plan_item_state"]
    in {"ACCOUNTED", "CONTEXT_UNRESOLVED", "OVERFLOW_UNDISPATCHED"}
    or item["is_context_dependency"]
    for item in potential_hidden
)
```

The helper computes `HIDDEN_GOVERNING_CLAUSE_SILENTLY_SKIPPED` over the seven
Task 15 child-local fallback records identified by the generic predicate and their
safe `(section_id, start_offset, end_offset)` inventory. A record counts as skipped
unless it is mandatory, conditional, or an indexed context dependency and has an
explicit accounted/context/overflow state at stop. The test may retain these safe
IDs/ranges; production may not import them.

- [ ] **Implementation:** Extend the helper as a passive bounded-plan observer only

After `run_agent()` returns, read:

```python
plan = run.section_acquisition.plan
ledger = run.section_acquisition.ledger
```

Project plan/item/activation/overflow/accounting data into immutable safe dictionaries
with only the allowed fields. Calculate gates from actual plan, ledger, request
sequence, receipts, raw results, and runtime result. Do not call plan construction,
activation, adapters, handoff, eligibility, decide, or persistence a second time.

Replace deadline relevance calculation based on `candidate_categories` with actual
deadline plan obligations/accounting. Keep raw deadline authority compilation from
`raw_section_results`; confirm its supported DATE_BETWEEN rule still exists. Set
`OVER_BROAD_RELEVANCE_BUDGET_EXHAUSTED` true only when the runtime terminates
`BUDGET_EXHAUSTED` after the bounded plan would otherwise have attempted more
relevance work. Under the accepted sequence it must be false.

- [ ] **GREEN:** Run archive acceptance and integrity regressions

Run:

```powershell
$env:UV_OFFLINE='1'
$env:QUALOR_REQUIRE_ARCHIVE='1'
$env:QUALOR_ARCHIVE_DIR='C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source\.qualor\local\killer-demo-real-source'
uv run --locked pytest tests/runtime/test_archived_compiler_acceptance.py tests/runtime/test_section_acquisition.py tests/runtime/test_canonical_adapters.py tests/runtime/test_section_handoff.py -q
uv run --locked ruff check tests/runtime/test_archived_compiler_acceptance.py tests/runtime/archived_compiler_support.py
git diff --check
```

Expected GREEN: two planning calls, at most seven extraction calls, no relevance-
bookkeeping budget stop, all nine categories explicitly accounted or unresolved,
deadline raw authority retained/executable, hidden skipped count zero, and all legacy
authority integrity assertions pass.

**Regression:** The GREEN block includes acquisition, adapter, and handoff neighbors
plus Ruff; every command must exit 0.

- [ ] **Review gate:** Inspect the passive-helper boundary and secret safety

Require helper imports no production-private routing constants beyond reading the
run's public internal objects, creates no rules/facts/verdicts, makes no network call,
does not serialize `model_requests`, and records no raw archive text.

**Commit:** Stage exactly the archive acceptance test and passive helper, then create
the named checkpoint.

```powershell
git add tests/runtime/test_archived_compiler_acceptance.py tests/runtime/archived_compiler_support.py
git diff --cached --name-only
git diff --cached --check
git commit -m "test: prove bounded archive acquisition accounting"
git status --short
```

The staged list must contain exactly these two test paths; status must be empty.

---

## Task 6 — Call and cost envelope regression

**Goal:** Re-prove the actual bounded request sequence and all frozen budget policies
without changing production budget code or buying correctness with more calls.

**Files:**

- Modify only if RED: `tests/runtime/test_compiler_cost_simulation.py`
- Test unchanged: `tests/runtime/test_live_budget.py`
- Consume Task 5 helper changes: `tests/runtime/archived_compiler_support.py`
- No production file

**Interfaces:**

- Consumes `ArchivedCompilerReport.model_requests`, `budget_events`,
  `simulate_request_sequence()`, `estimate_model_reservation()`,
  `model_request_metrics()`, `WEB_SEARCH_RESERVED_COST_USD`, `LiveBudgetGuard`, and
  `live_budget()`.
- Produces no runtime interface. Test constants become:

```python
PLANNING_REQUESTS = 2
MAX_EXTRACTION_REQUESTS = 7
MAX_LIVE_CALLS = 9
```

- [ ] **RED:** Run the existing cost suite against the bounded report

**Command:** Execute the exact offline cost command below.

Run:

```powershell
$env:UV_OFFLINE='1'
$env:QUALOR_REQUIRE_ARCHIVE='1'
$env:QUALOR_ARCHIVE_DIR='C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source\.qualor\local\killer-demo-real-source'
uv run --locked pytest tests/runtime/test_compiler_cost_simulation.py tests/runtime/test_live_budget.py -q
```

**Expected RED:** A RED is permitted only at assertions that hardcode exactly seven
extraction requests or nine actual calls when the truthful plan used fewer. A PASS
with no edit is also valid. Any guard admission, request shape, reservation, policy,
or cost failure is a stop condition, not test debt.

Expected: either PASS with the archive still using seven extraction calls, requiring
no test edit/commit, or RED only at assertions that hardcode exactly seven extraction
requests/nine actual calls when the truthful plan used fewer. Any guard admission,
request shape, reservation, policy, or cost failure is a stop condition, not test debt.

- [ ] **Implementation:** If and only if exact-count assertions are RED, make them bounded

Replace only actual-sequence assertions:

```python
assert kinds.count("PLANNING") == PLANNING_REQUESTS
assert 1 <= kinds.count("EXTRACTION") <= MAX_EXTRACTION_REQUESTS
assert len(report.model_requests) <= MAX_LIVE_CALLS
assert len(report.model_requests) == len(report.request_sequence)
```

Keep exact event/request order and count agreement. Build the independent tenth-call
proof by admitting captured requests and, when fewer than nine were used, repeating a
validated captured extraction request through `estimate_model_reservation()` until
the guard contains nine inference reservations. Assert the next reservation fits the
remaining USD ceiling but fails with `INFERENCE call cap reached` and no cost-cap
fields. This filler is a budget-unit input only; it is not a runtime request sequence
or archive outcome.

- [ ] **Step 3: Prove conservative cost and historical policies**

Retain/add assertions:

```python
costs = simulate_request_sequence(report)
assert costs.admitted is True
assert costs.projected_reserved_cost == costs.projected_worst_case_cost
assert costs.projected_worst_case_cost <= Decimal("0.35")
assert costs.remaining_headroom == Decimal("0.35") - costs.projected_worst_case_cost
assert live_budget().policy.inference_max_calls == 9
assert live_budget().policy.cost_cap_usd == Decimal("0.35")
```

Use existing policy-specific unit cases to assert `QUALOR_03B3` remains USD 0.20 and
diagnostic remains 6 calls/USD 0.15. Never call `reconcile()` in conservative replay.

- [ ] **GREEN:** Run cost verification and budget neighbors

Run:

```powershell
uv run --locked pytest tests/runtime/test_compiler_cost_simulation.py tests/runtime/test_live_budget.py tests/runtime/test_agent.py tests/runtime/test_live_inference_efficiency.py -q
uv run --locked ruff check tests/runtime/test_compiler_cost_simulation.py
git diff --check
```

Expected GREEN: bounded actual sequence admitted under USD 0.35, tenth call blocked by
call count, production request dictionaries/reservation functions used, historical
policies unchanged.

**Regression:** The GREEN block includes live-budget, agent, inference-efficiency,
Ruff, and whitespace checks; every command must exit 0.

- [ ] **Review gate:** Inspect caps, request provenance, and the conditional diff

If Step 1 passed without edits, record `TASK6_COMMIT=NONE` and proceed with a clean
worktree. If Step 2 was required:

**Commit:** Use `TASK6_COMMIT=NONE` when no assertion changed; otherwise stage only
the one proven stale test and create the named checkpoint.

```powershell
git add tests/runtime/test_compiler_cost_simulation.py
git diff --cached --name-only
git diff --cached --check
git commit -m "test: verify bounded acquisition cost envelope"
git status --short
```

The staged list must contain exactly that one test path. Any production budget diff,
cap increase, or helper change in this task blocks the plan.

---

## Task 7 — Task 14 completion diagnostic rerun

**Goal:** Run the existing completion/persistence diagnostic unchanged and classify
the actual bounded compiler result without targeting CASE_A, CASE_B, recommendation,
or eligibility.

**Files:**

- Test unchanged: `tests/workspace/test_compiler_completion_gate.py`
- Read-only dependency: `tests/runtime/archived_compiler_support.py`
- No planned modification

**Interfaces:**

- Consumes existing `CompletionDiagnostic`, `_classify()`,
  `run_archived_compiler(..., sink=sink)`, shared `live_budget()`,
  `WorkspaceRunCapture`, `Database`, `WorkspaceStore`, and wraps-only
  `handoff.decide` spy.
- Produces the observed `CASE_A`, `CASE_B`, or `OTHER_BLOCKER` result packet only; no
  production or test interface.

- [ ] **RED:** Run Task 14 unchanged so any real classification regression is observable

**Command:** Execute the exact offline diagnostic command below.

Run:

```powershell
$env:UV_OFFLINE='1'
$env:QUALOR_REQUIRE_ARCHIVE='1'
$env:QUALOR_ARCHIVE_DIR='C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source\.qualor\local\killer-demo-real-source'
uv run --locked pytest tests/workspace/test_compiler_completion_gate.py -q
```

**Expected RED:** Any failure must identify the exact real linkage, authority,
budget, persistence, or classifier assertion. Do not manufacture a failure or target
a preferred case.

Expected GREEN: the outcome-neutral classifier passes, shared budget identity holds,
terminal telemetry reopens, no fake Opportunity/Decision graph exists for a
non-success stop, and persistence invokes no second decision. Record actual case,
eligibility, recommendation, termination, calls, accounting, graph counts, and
decide-spy calls.

If it fails, classify the exact assertion. A result that needs a preferred case,
verdict stub, graph seed, completion mapping change, or classifier weakening stops
for controller review. Do not edit the test.

**Implementation:** Make no code or test change. Record the real classifier output;
if it fails, stop for controller review with the exact blocker.

- [ ] **GREEN:** Run the unchanged diagnostic and persistence neighbors

Run:

```powershell
uv run --locked pytest tests/workspace/test_compiler_completion_gate.py tests/workspace/test_live_run_persistence.py tests/e2e/test_live_workspace_persistence.py tests/runtime/test_archived_compiler_acceptance.py -q
```

Expected GREEN: all pass with the same selected runtime decision authority and no
fake partial-success graph.

**Regression:** The GREEN command includes workspace persistence, live E2E
persistence, and archive acceptance; every test must pass with archived tests
executed rather than skipped.

- [ ] **Review gate:** Inspect the truthful classification and persistence identities

Require:

```text
NO_FAKE_PARTIAL_SUCCESS_GRAPH=YES
SECOND_DECISION_AUTHORITY=0
FOURTH_PAID_RUN_AUTHORIZED=NO
```

If CASE_A, record fourth-run candidate YES but authorization NO. If CASE_B, candidate
NO and completion-semantics controller review is the next action only when every Case
B predicate is true. If OTHER_BLOCKER, record its exact cause. Require empty Git
status and set `TASK7_COMMIT=NONE`.

**Commit:** None. This diagnostic task must end with `TASK7_COMMIT=NONE` and a clean
worktree.

---

## Task 8 — Full regression, genericity, authority, and zero-network closeout

**Goal:** Verify the final committed implementation across Python, frontend, browser,
canonical drift, genericity, authority, persistence, and network boundaries. Make no
feature change and create no empty verification commit.

**Files:**

- No planned modifications
- Review production diff from the Task 1 baseline through final implementation HEAD
- Test all paths named below

**Interfaces:**

- Consumes the complete Task 1-7 implementation and existing verification scripts.
- Produces only the final evidence packet. No schema, runtime, frontend, database, or
  policy interface.

- [ ] **RED:** Establish the final candidate and expose any dirty-state or offline-policy violation

**Command:** Run the exact baseline and environment commands below before any suite.

Run:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
$env:UV_OFFLINE='1'
$env:npm_config_offline='true'
$env:npm_config_audit='false'
$env:npm_config_fund='false'
$env:NO_UPDATE_NOTIFIER='1'
$env:QUALOR_REQUIRE_ARCHIVE='1'
$env:QUALOR_ARCHIVE_DIR='C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source\.qualor\local\killer-demo-real-source'
```

Require empty status, correct branch, committed implementation HEAD, and exact offline
values. Do not test internet connectivity.

**Expected RED:** Any dirty status, wrong branch/HEAD, missing offline value, or later
verification failure is a real closeout blocker; Task 8 performs no repair.

**Implementation:** None. This task only executes verification, inspects the committed
diff and fresh logs, and reports exact evidence.

- [ ] **GREEN:** Run archive-required targeted Python regression

Run:

```powershell
uv run --locked pytest tests/runtime tests/workspace tests/e2e tests/test_hosted_live_runs.py tests/test_hosted_action_capability.py tests/test_hosted_approval.py -q
```

Expected GREEN: failed=0 and required archive tests skipped=0. Record passed/skipped
counts from fresh output.

**Regression:** Steps 3-5 run full Python, lint/drift, frontend, and all controlled
Playwright matrices as separate commands with recorded exit codes.

- [ ] **Step 3: Run full Python and lint/drift gates separately**

Run each and record each exit code:

```powershell
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked python -m qualor.schemas.export --check
node apps/web/scripts/generate-domain.mjs --check
```

Expected GREEN: full Python failed=0, Ruff PASS, schema drift PASS, frontend domain
drift PASS. No generated file changes are allowed.

- [ ] **Step 4: Run frontend gates separately**

Run:

```powershell
npm --prefix apps/web run test:run
npm --prefix apps/web run test:run -- src/a11y/accessibility.test.tsx
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

Expected GREEN: unit and accessibility suites pass; typecheck and build exit 0.

- [ ] **Step 5: Run controlled Playwright matrices**

Run:

```powershell
Push-Location apps/web
try {
    npm run test:e2e
    if ($LASTEXITCODE -ne 0) { throw "PLAYWRIGHT_DEFAULT_FAILED" }
    npm run test:e2e -- --config playwright.live.config.ts
    if ($LASTEXITCODE -ne 0) { throw "PLAYWRIGHT_LIVE_FAILED" }
    npm run test:e2e -- --config playwright.task4.config.ts
    if ($LASTEXITCODE -ne 0) { throw "PLAYWRIGHT_TASK4_FAILED" }
} finally {
    Pop-Location
}
```

Expected GREEN: default, controlled LIVE, and controlled Task4 configurations pass.
They may use loopback only; no gateway/profile/network call.

- [ ] **Review gate:** Inspect genericity and changed-file scope

List production changes from the implementation baseline and scan them:

```powershell
git diff --name-only 70a5cf5c1da547a5db861b5d760c5fd623d7b109..HEAD
git diff 70a5cf5c1da547a5db861b5d760c5fd623d7b109..HEAD -- src/qualor/runtime
rg -n -i "devpost|agents for humans|agentsforhumans|official-rules\.raw|e3f7640c|desired.*(pass|fail)|known.*outcome" src/qualor/runtime/sections.py src/qualor/runtime/acquisition_plan.py src/qualor/runtime/acquisition_coverage.py src/qualor/runtime/section_scheduler.py src/qualor/runtime/section_acquisition.py
```

Manually distinguish generic semantic vocabulary from prohibited implementation
branches. Require:

```text
DEVPOST_SPECIFIC_BRANCHES=0
AWS_AGENTS_FOR_HUMANS_SPECIFIC_BRANCHES=0
CONTEST_NAME_MATCHING=0
ARCHIVE_HASH_OUTCOME_BRANCHES=0
SOURCE_DOMAIN_OUTCOME_BRANCHES=0
```

- [ ] **Step 7: Review authority, context, and stop semantics**

Inspect production diff and owning tests. Require:

```text
UNKNOWN_NEVER_PASS=YES
AMBIGUOUS_NEVER_PASS=YES
UNSUPPORTED_NEVER_PASS=YES
LLM_FINAL_ELIGIBILITY_AUTHORITY=NO
RAW_EFFECTIVE_AUTHORITY_SEPARATION=YES
DECISION_USES_GUARDED_AUTHORITY=YES
CONTEXT_GRAPH_PRESERVED=YES
QUALIFIERS_DROPPED=0
EXCEPTIONS_DROPPED=0
HIDDEN_MODEL_RETRIES=0
SECOND_DECISION_AUTHORITY=0
FRONTEND_VERDICT_POLICY=0
FAKE_SOURCE_EXHAUSTION=0
FAKE_SUCCESS_GRAPH=0
```

Confirm no changes under eligibility, decisions, workspace persistence, frontend,
schemas, providers, budget policy, or successful completion mapping.

- [ ] **Step 8: Run canonical verification under the same offline environment**

Inspect `scripts/verify.ps1` first and confirm it contains no AWS, deployment, or paid
action. Then run in the same PowerShell process containing the Step 1 environment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
```

Expected GREEN: exit 0 and `VERIFY_SCRIPT=PASS`. Inspect npm logs created during this
invocation for `http fetch`, `https fetch`, audit POST, registry request, PyPI, GitHub,
and AWS endpoint evidence. Registry URLs appearing only as local cache keys/metadata
are not external requests. Require npm=0, uv=0, other external requests=0.

- [ ] **Commit:** Create no verification commit; run the final Git gate

Run:

```powershell
git status --short
git diff --check
git diff --cached --check
git rev-parse HEAD
```

Expected: empty status, both diff checks exit 0, HEAD unchanged by Task 8. Set
`TASK8_COMMIT=NONE`, `AWS_PAID_CALLS=0`, `REAL_EXTERNAL_NETWORK_CALLS=0`, and
`PUSH=NO`.

---

## Stop conditions

Stop implementation and return the exact evidence to controller review if any of
these occurs:

1. The archived path still ends `BUDGET_EXHAUSTED` because of relevance bookkeeping.
2. More than 7 extraction calls are needed.
3. The USD 0.35 conservative envelope no longer fits.
4. A hidden governing clause is silently skipped.
5. Deadline raw authority disappears.
6. Context, qualifier, or exception integrity weakens.
7. UNKNOWN, AMBIGUOUS, or UNSUPPORTED can become effective PASS.
8. Production requires contest-, source-, domain-, archive-, or known-outcome-specific routing.
9. The eligibility or decision engine must change.
10. Persistence or successful-completion policy must change.
11. A public schema, database, or frontend migration becomes necessary.
12. Task 14 requires outcome targeting or classifier weakening.
13. External network is required for local verification.

Also stop if plan construction cannot remain deterministic/finite, plan and legacy
scheduling would both be active after Task 4, a required context cannot fail closed,
or an unplanned file must change. Do not raise a limit, hide overflow, seed a graph,
stub a verdict, or create an archive-specific exception to continue.

## Intermediate repository safety checklist

Before every implementation commit and before advancing to the next task, require:

- imports resolve;
- all touched-subsystem tests pass;
- active production constructors match their call sites;
- exactly one scheduling authority is active;
- no partially activated plan module exists;
- no source/context/authority object is silently dropped;
- staged paths equal the task's exact list;
- `git diff --cached --check` exits 0;
- the commit contains its RED/GREEN evidence;
- `git status --short` is empty after commit.

Task 3's temporary optional constructor is removed in Task 4. Task 4 is one atomic
commit containing CoverageLedger constructor cutover, SectionScheduler constructor
cutover, SectionAcquisition activation, and every direct constructor consumer. It may
not be divided into separate commits.

## Spec-to-task coverage

| Specification requirement | Implementation/proof task |
| --- | --- |
| Accepted Task 14/15 root cause and no call-cap workaround | Global constraints; Tasks 4-6 |
| Child-local body routing and inherited heading separation | Task 1 |
| Generic rule-like/structural/definition detection | Task 1; archive proof Task 5 |
| Three mutually exclusive relevance tiers | Task 2 |
| Immutable deterministic finite identities | Task 2 |
| Seven-dispatch physical capacity and overflow | Tasks 2-4; cost proof Task 6 |
| Conditional reasons and finite fixed-point activation | Tasks 2-4 |
| Mandatory before conditional; breadth before depth; max two categories | Tasks 2 and 4 |
| Reserve discoverable without nine-category multiplication | Tasks 2-4 |
| Indexed discoverability versus activation/attempt/accounting | Task 3 |
| UNKNOWN/AMBIGUOUS/UNSUPPORTED and EXHAUSTED fail closed | Tasks 3, 5, and 8 |
| Context/parent/reference/global/unsafe-boundary invariants | Tasks 1, 4, 5, and 8 |
| PLAN_EXHAUSTED versus SOURCE_EXHAUSTED | Tasks 3-5 |
| PLAN_EXHAUSTED maps to existing NO_PROGRESS only | Task 4; Task 7 persistence proof |
| Physical budget refusal remains BUDGET_EXHAUSTED | Tasks 4 and 6 |
| Raw/effective authority separation and guarded decision | Tasks 4, 5, 7, and 8 |
| All nine archive categories accounted/discoverable | Task 5 |
| Deadline raw authority retained and executable | Task 5 |
| Seven diagnosed hidden clauses explicitly accounted | Tasks 1, 2, and 5 |
| QUALOR_5F/historical/diagnostic budget invariants | Task 6 |
| Task 14 truthful case and no fake graph/second decision | Task 7 |
| No public/schema/database/frontend/provider/policy change | Tasks 4 and 8 |
| Genericity and zero external network | Tasks 1, 5, and 8 |

## Plan self-review checklist

Before committing this plan document, the author must verify:

1. Every normative spec section maps to at least one task in the table above.
2. The plan contains no unfinished markers or instructions that defer a design
   decision to implementation.
3. Type names, enum values, signatures, constructor arguments, and property names are
   consistent from producer task through consumer task.
4. Dependency order is acyclic and Task 4 performs the only production activation.
5. Each committed checkpoint has an exact GREEN/regression command and compatible
   imports/call sites.
6. Every archive, authority, context, hidden-clause, stop, call, and cost acceptance
   invariant has a named test task.
7. The document states no implementation, paid-run, deployment, network, or push
   authorization.
8. Call, cost, step, token, output, and claim limits are unchanged.
9. Eligibility, decision, persistence, successful completion, provider, public schema,
   database, and frontend policies are not redesigned.
10. Archive measurements are acceptance evidence only and never production rank,
    membership, or outcome inputs.

## Execution handoff

After controller review and separate implementation authorization, choose one of the
required Superpowers workflows:

1. **Subagent-Driven (recommended):** use
   `superpowers:subagent-driven-development`, dispatch a fresh worker per task, and
   perform specification and quality review between commits.
2. **Inline Execution:** use `superpowers:executing-plans`, execute in bounded batches,
   and stop at each named review checkpoint.

No execution option is authorized by this planning commit itself.
