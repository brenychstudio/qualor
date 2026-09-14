# Bounded Acquisition Plan V1

## Authority and document status

Task: `QUALOR-LIVE-PRODUCTION-TASK-5F-TASK-16A`.

Status: owner/controller design approval was recorded in chat on 2026-09-14.
This document is the canonical design authority for a bounded amendment to source
acquisition relevance and accounting. It authorizes no implementation, paid LIVE
run, deployment, network access, or push. A separate owner-approved implementation
plan and task are required before production or test code changes.

Baseline: `feature/qualor-live-production` at
`275f0a987da6ed6f38ca1f3e388d4fccbbc1ac5d`.

This design amends, rather than replaces, the
[Coverage-Driven Canonical Evidence Acquisition / Compiler](2026-09-13-coverage-driven-canonical-evidence-compiler-design.md).
Its implementation must be planned against the existing
[compiler implementation plan](../plans/2026-09-13-coverage-driven-canonical-evidence-compiler-implementation.md)
and the current runtime contracts in `sections.py`, `acquisition_coverage.py`,
`section_scheduler.py`, and `section_acquisition.py`.

The foundation remains [00_CANONICAL_BRIEF_UA.md](../../00_CANONICAL_BRIEF_UA.md).
This amendment does not alter its bytes or authority. The existing eligibility
engine, decision engine, runtime successful-termination policy, persistence boundary,
frontend verdict policy, provider policy, and budget policy remain authoritative and
unchanged.

Normative requirements use MUST and MUST NOT. Type names and fields in this document
are settled implementation contracts. Internal implementation may use equivalent
Pydantic/frozen-dataclass mechanics, but it must preserve the names, values,
validation, identity inputs, and ownership boundaries stated here.

## 1. Accepted diagnostic evidence

Task 14 ran the real hash-bound archived compiler through the existing runtime and
WorkspaceRunCapture boundary. The compiler produced real source-backed authority,
including an executable deadline rule, but stopped with `BUDGET_EXHAUSTED`:

| Measurement | Result |
| --- | ---: |
| Planning calls | 2 |
| Extraction calls | 7 |
| Total inference calls | 9 |
| Raw authoritative canonical facts | 1 |
| Raw executable rules | 1 |
| Deadline raw authority | present |
| Runtime eligibility | `REVIEW_REQUIRED` |
| Runtime recommendation | `WATCH` |
| Termination | `BUDGET_EXHAUSTED` |

Task 15 then measured the acquisition relevance set without changing production:

| Diagnostic mode | Explicit section/category pairs | Fallback pairs | Extraction calls | Total model calls | Truthful acquisition stop reached |
| --- | ---: | ---: | ---: | ---: | --- |
| Current logical-region routing | 248 | 54 | 7 | 9 | no |
| Child-local routing | 132 | 117 | 7 | 9 | no |
| Current routing plus tier-aware accounting | 248 | 54 | 7 | 9 | no |
| Child-local routing plus tier-aware accounting | 132 | 117 | 7 | 9 | no |

Additional accepted measurements are:

- 46 bounded children carry categories introduced only by sibling body text in the
  current logical region.
- Current routing has 6 unclassified sections; child-local routing has 13.
- Of the 13 child-local fallback sections, 7 contain plausible governing language
  for critical categories.
- All four diagnostic modes preserve the raw deadline authority, context graph,
  unsafe-boundary fail-close behavior, qualifiers, and exceptions.
- None of the four modes reaches a truthful acquisition stop within the available
  7 extraction calls.

The root cause is not an inference ceiling that is intrinsically too low. It is an
unbounded definition of mandatory work: sibling-body category smear expands the
explicit set, while each unclassified section is multiplied across all nine critical
categories and treated as required before coverage can complete. Raising the call
cap is rejected because the work definition has no bounded semantic end. Child-local
routing alone, optional fallback alone, and the Task 15 tier-aware variants alone are
also rejected. Optional fallback can miss governing clauses; exhaustive fallback is
operationally infeasible.

## 2. Decision

The approved repair is **BOUNDED ACQUISITION PLAN V1**.

The pipeline becomes:

```text
SourceDocument
  -> SectionIndex
  -> deterministic AcquisitionPlan
  -> SectionScheduler
  -> bounded extraction
  -> CoverageLedger
  -> canonical authority
  -> deterministic eligibility and decision
```

The `AcquisitionPlan` MUST be built once from the complete `SectionIndex` before the
first model extraction. It is deterministic, immutable, finite, revision-bound, and
aware that the `QUALOR_5F` profile has physical capacity for 7 extraction dispatches
after its 2 planning calls. Model output MUST NOT add an item, category, reason,
priority, or ranking input to the plan.

The repair separates five concepts that the current implementation conflates:

1. **Index discoverability:** the section exists in the complete source index.
2. **Plan membership:** deterministic routing places the section in a finite tier.
3. **Plan activation:** a predeclared item has become required work for a category.
4. **Attempt and semantic outcome:** a dispatched pair is retained with its actual
   supported, ambiguous, unknown, unsupported, or operational outcome.
5. **Category source accounting:** the category is supported, boundedly unresolved,
   blocked by governing context, or unresolved because activated work overflowed
   physical capacity.

Discoverability is not mandatory work. Attempt is not support. Exhaustion is not
PASS. Raw semantic authority is not effective guarded authority until the acquisition
accounting requirements in this document are satisfied.

## 3. Section-local routing amendment

### 3.1 Routing inputs

`sections.py` MUST compute routing metadata independently for every bounded child.
The exact inputs are:

- `heading_text`: the exact logical-region heading, inherited as routing context by
  every bounded child in that logical region;
- `body_text`: only the exact bounded child's text, excluding the heading line when
  that heading is physically included in the first child;
- existing structural ancestry;
- existing explicit section references;
- existing expressly global-scope markers.

Category terms found only in another body child of the logical region MUST NOT enter
the current child's body categories, heading categories, rule-like category hints,
or rank. The exact heading may legitimately govern all children and therefore remains
available separately to each child.

The following internal contract is added to `sections.py`:

```python
class SectionRoutingMetadata(Contract):
    routing_version: Literal["bounded-acquisition-routing-v1"]
    body_categories: tuple[Category, ...]
    heading_categories: tuple[Category, ...]
    rule_like: StrictBool
    rule_like_category_hints: tuple[Category, ...]
    reason_codes: tuple[SectionRoutingReason, ...]
```

`SectionRoutingReason` is the bounded vocabulary:

```text
BODY_CATEGORY_TERM
HEADING_CATEGORY_TERM
RULE_LIKE_MARKER
STRUCTURAL_REFERENCE
GLOBAL_SCOPE
```

`SourceSection` gains one required internal field, `routing`, of this type.
`candidate_categories` remains during migration as a compatibility diagnostic and
MUST equal the canonical-category-order union of `body_categories` and
`heading_categories`. Neither the scheduler nor the coverage ledger may use
`candidate_categories` as plan membership after this amendment is implemented.
The contract is internal runtime state; it is not added to public domain schemas,
workspace tables, or frontend schemas.

### 3.2 Generic rule-like detector

`sections.py` MUST expose a pure deterministic function:

```python
def detect_rule_like_routing(
    *, heading_text: str | None, body_text: str
) -> RuleLikeRouting
```

with this exact result contract:

```python
class RuleLikeRouting(Contract):
    rule_like: StrictBool
    category_hints: tuple[Category, ...]
    marker_codes: tuple[RuleLikeMarker, ...]
```

The detector is routing only. It MUST NOT create EvidenceRecords, RuleCandidates,
RuleEvaluations, eligibility states, opportunity facts, owner facts, project facts,
or decision recommendations.

The detector normalizes Unicode whitespace and case, applies token/phrase boundaries,
and records marker codes rather than matched source text. `RuleLikeMarker` is the
bounded generic vocabulary below:

| Marker code | Illustrative lexical/structural indicators |
| --- | --- |
| `OBLIGATION` | must, required, shall, condition, subject to |
| `PROHIBITION` | must not, may not, prohibited, ineligible |
| `LIMITATION` | only, unless, except |
| `PERMISSION_OR_SCOPE` | eligible, resident, participant, team, project |
| `TECHNOLOGY_OR_LICENSE` | license, copyright, technology, API, SDK |
| `FINANCIAL_OR_REWARD` | funding, support, prize, award, winner |
| `SUBMISSION_OR_TIME` | submit, submission, deadline |
| `EVALUATION_OR_SELECTION` | judge, judging, criteria, score, points, tie |
| `STRUCTURAL_RULE_ITEM` | numbered/list item beneath a governing heading |

Category hints use the generic critical-category vocabulary already owned by the
indexer, augmented only with generic synonyms required to map these marker families.
For example, submission/time terms hint `DEADLINE`; entrant/resident/team terms hint
entrant/geography/legal-entity as their exact vocabulary permits; project terms hint
`PROJECT_POLICY`; API/SDK hints `REQUIRED_TECHNOLOGY`; license/copyright hints
`LICENSE`; funding/support hints `FINANCIAL_SUPPORT`; and prize/award/judging/selection
terms hint `REWARD_CONDITIONS`. A generic marker with no category-bearing noun sets
`rule_like=True` but leaves `category_hints` empty.

The detector MUST remain generic. It MUST contain no source hostname, contest name,
organizer name, archive hash, expected verdict, or archived wording branch. Archive
acceptance MUST demonstrate that each of the seven Task 15 rule-like fallback examples
is routed to a mandatory or conditional item by these generic rules. Their identities
are test evidence, not production conditions.

### 3.3 Exact structural predicates

The V1 predicates are fixed as follows:

- `has_governing_marker` is true when marker codes contain `OBLIGATION`,
  `PROHIBITION`, or `LIMITATION`.
- `is_structural_rule_item` is true when the first non-whitespace body characters
  match an unordered-list prefix (`-`, `*`, or `•` followed by whitespace) or an
  ordered-list prefix (decimal/letter followed by `.`, `)`, or `:`), and either the
  inherited heading has a critical category or the body has a governing marker.
- `is_definition_entry(category)` is true when one non-empty body line contains a
  category-bearing label before `:`, `-`, or `—`, has non-whitespace content after
  that separator, and the label or inherited heading routes to `category`.
- `local_mandatory(category)` is true exactly when `category` occurs in
  `body_categories` and at least one of `has_governing_marker`,
  `is_structural_rule_item`, or `is_definition_entry(category)` is true.

Sentence punctuation, model confidence, semantic adapter support, and the number of
times a term occurs are not tier predicates. Unsafe section cuts and incomplete
context do not make a pair disappear; they attach an unresolved context obligation.

## 4. Three relevance tiers

Every indexed section is represented in the plan inventory. A section may produce
multiple category-addressed plan items, but no item may address more than two
categories. A category-free reserve item is created only when the section has no
category-addressed item. The three tiers are mutually exclusive per
section/category pair.

### 4.1 `MANDATORY_ANCHOR`

A section/category pair is `MANDATORY_ANCHOR` only when deterministic local evidence
makes it a high-confidence candidate for a governing clause. The pair is mandatory
when all of these are true:

1. the category occurs in `routing.body_categories` for that exact child;
2. the child is rule-like, is a structural rule item, or contains a complete
   definition/list entry under its own category-bearing heading; and
3. the pair is not derived solely from heading text, a sibling body, model output,
   source identity, or desired outcome.

An incomplete context graph does not demote the pair. It remains a mandatory
unresolved obligation with `INCOMPLETE_GOVERNING_CONTEXT`; it is not dispatched as if
safe context were complete.

Mandatory anchors are active when the plan is created. A category cannot be marked
`SUPPORTED` for source accounting while an activated mandatory anchor for that
category is unattempted, context-unresolved, or capacity-overflowed.

### 4.2 `CONDITIONAL_DISCOVERY`

A section/category pair is `CONDITIONAL_DISCOVERY` when deterministic evidence makes
it plausibly relevant but not a high-confidence primary anchor. This includes:

- a category present only in the exact logical heading for that child;
- a rule-like body whose category hint is present but whose category vocabulary does
  not establish a mandatory anchor;
- a referenced or global section required by an anchor's context graph;
- a category-bearing child whose routing or governing context is incomplete; or
- a rule-like fallback carrying a generic category hint.

Conditional items exist in the immutable plan before extraction. They begin inactive
unless their static routing establishes `RULE_LIKE_FALLBACK` or
`ROUTING_UNCERTAIN`, or an initially active mandatory anchor establishes
`EXPLICIT_REFERENCE_REQUIRED` or `GLOBAL_CONTEXT_REQUIRED`. A reference/global item
reachable only from an inactive conditional item waits for that parent item to
activate. Other conditional items activate only through the bounded reasons in
section 7. Inactive conditional items remain discoverable and are not counted as
unfinished mandatory coverage.

### 4.3 `RESERVE_FALLBACK`

Every remaining indexed section is represented by one section-level
`RESERVE_FALLBACK` item. A reserve item has no category pair and therefore is not
multiplied across the nine critical categories. It retains section identity, exact
offsets, context dependencies, rule-like metadata, and deterministic source-order
rank.

A reserve item may be promoted to conditional discovery only when an indexed explicit
reference or expressly global-scope relationship from an active category-addressed
item supplies its deterministic category and one of the activation reasons in
section 7. A rule-like section with a local category hint is already conditional and
therefore is not reserve. Model text, model confidence, proposed category, or a
missing desired result MUST NOT promote reserve. A reserve item with no qualifying
context edge stays discoverable but is not extracted in V1. Its non-extraction is
never proof that a rule is absent or that a category passes.

## 5. Immutable data model and identity

The focused new module is `src/qualor/runtime/acquisition_plan.py`. It owns immutable
planning, tier assignment, deterministic rank, activation predicates, and plan
identity. It owns no semantic verdicts.

### 5.1 Enums

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
```

No other activation reason is valid in V1. `ROUTING_UNCERTAIN` means static router
metadata contains a generic rule marker and a deterministic category hint but lacks
the local evidence required for a mandatory anchor. It is not model uncertainty.

### 5.2 Ranking inputs

```python
class AcquisitionRanking(Contract):
    tier_rank: Annotated[StrictInt, Field(ge=0, le=2)]
    category_rank: Annotated[StrictInt, Field(ge=0, le=8)] | None
    local_signal_rank: Annotated[StrictInt, Field(ge=0, le=3)]
    context_dependency_count: Annotated[StrictInt, Field(ge=0, le=12)]
    start_offset: Annotated[StrictInt, Field(ge=0)]
```

`tier_rank` is 0, 1, or 2 for mandatory, conditional, or reserve. Lower values sort
first. `category_rank` is the existing `Category` declaration order and is absent
only for category-free reserve items. `local_signal_rank` is fixed as:

1. 0: body category plus an obligation/prohibition/limitation marker;
2. 1: body category plus structural rule-item or definition/list form;
3. 2: category-bearing heading plus rule-like child body;
4. 3: rule-like category hint, context dependency, or category-free reserve.

These are routing strengths, not evidence weights. Fewer required context sections
sort first only after tier and breadth depth; it may not remove a dependency.

### 5.3 Plan item

```python
class AcquisitionPlanItem(Contract):
    item_id: str  # plan_item_<32 lowercase hex>
    source_revision: str  # 64 lowercase hex
    section_id: str
    categories: tuple[Category, ...]  # zero to two
    tier: AcquisitionTier
    context_section_ids: tuple[str, ...]  # ordered, unique, max 12
    context_complete: StrictBool
    activation_reasons: tuple[ConditionalActivationReason, ...]
    routing_reason_codes: tuple[SectionRoutingReason, ...]
    ranking: AcquisitionRanking
```

Validation requires one or two categories for mandatory and conditional items and
zero categories for reserve items. Categories use canonical enum order. Context IDs
must equal the index-owned dependency order and may not be shortened for rank or
capacity. Mandatory items have no activation reasons because they begin active.
Conditional items have at least one reason. Reserve items have none; a deterministic
reference/global-context promotion is represented by `PlanActivation` and does not
mutate the item or plan.

`item_id` is SHA-256 truncated to 32 lowercase hexadecimal characters over a
canonical serialization of:

```text
source_revision
routing_version
section_id
ordered categories
tier
ordered context_section_ids
context_complete
ordered activation_reasons
ordered routing_reason_codes
ranking fields
```

### 5.4 Plan

```python
class AcquisitionPlan(Contract):
    plan_id: str  # acquisition_plan_<32 lowercase hex>
    source_id: NonEmpty
    source_revision: str
    indexer_version: NonEmpty
    routing_version: Literal["bounded-acquisition-routing-v1"]
    policy_name: Literal["QUALOR_5F"]
    planning_calls_reserved: Literal[2]
    max_extraction_jobs: Literal[7]
    items: tuple[AcquisitionPlanItem, ...]
```

The plan contains all mandatory, conditional, and reserve inventory, not only the
seven jobs that can be dispatched. `plan_id` hashes the canonical serialization of
all fields and ordered item IDs. Identical source bytes/final URL, indexer version,
routing version, and `QUALOR_5F` capacity MUST produce identical plan and item IDs.
Span capability IDs, model output, wall clock, run ID, authority revision, profile
facts, and decision results MUST NOT affect plan identity.

`build_acquisition_plan(index: SectionIndex) -> AcquisitionPlan` is pure. It verifies
that the index is complete, all referenced context IDs exist, all sections occur in
the inventory, the policy capacity is 7, and ordering is stable. An invalid or
partial index fails closed before model extraction.

### 5.5 Activation and overflow records

Activation is run-owned state, not a mutation of `AcquisitionPlan`:

```python
class PlanActivation(Contract):
    item_id: str
    categories: tuple[Category, ...]  # one or two
    reason: ConditionalActivationReason
    caused_by_item_ids: tuple[str, ...]
    authority_revision: Annotated[StrictInt, Field(ge=0)]

class PlanOverflow(Contract):
    item_id: str
    categories: tuple[Category, ...]
    reason_code: Literal["EXTRACTION_CAPACITY_REACHED"]
    dispatches_used: Literal[7]
```

For an already category-addressed conditional item, activation categories MUST equal
the item's categories. A reserve promotion may bind only categories required by its
indexed reference/global-context edge from the causing active item.
`caused_by_item_ids` is empty for static activation and otherwise names the anchors
whose accounted outcomes triggered it. Activations deduplicate by
`(item_id, categories)`.

`PlanOverflow` records each activated, safe-to-dispatch item left undispatched when
the seventh extraction dispatch has been consumed. It is bounded by the finite plan
inventory and contains no source text or model payload.

## 6. Deterministic plan construction

Plan construction processes sections in `(start_offset, section_id)` order and
categories in existing enum order.

For each section:

1. Create a mandatory pair for every category satisfying section 4.1.
2. Create a conditional pair for every remaining body, heading, rule-like, explicit
   reference, or global-context category satisfying section 4.2.
3. Coalesce categories into the same item only when section, tier, context,
   activation-reason set, and local-signal rank are identical. Coalescing follows
   canonical category order and never exceeds two categories.
4. If no category-addressed item exists, create exactly one category-free reserve
   item for that section.
5. Sort by tier, breadth depth, category order, local signal rank, context dependency
   count, source offset, section ID, then item ID.

Breadth depth is the zero-based ordinal of an item among items for the same category
and tier. The global dispatch order sorts breadth depth before a second item for any
category, ensuring each critical category's strongest available item is considered
before unnecessary depth. Mandatory items always precede conditional items even when
a conditional item has a smaller source offset.

The static plan may contain more than seven category-addressed items. Plan size does
not authorize more calls. Dispatch capacity and unresolved overflow are first-class
facts, not reasons to omit inventory.

## 7. Conditional activation

Activation is deterministic and monotonic. An item moves from inactive to active at
most once per source revision and category set. Activation cannot deactivate a
mandatory obligation or erase an outcome.

The reasons have these exact triggers:

| Reason | Trigger |
| --- | --- |
| `NO_SUPPORTED_ANCHOR` | All safe mandatory anchors for the category have accounted outcomes and none contains supported canonical authority. |
| `AMBIGUOUS_ANCHOR` | Any attempted mandatory anchor for the category returns an `AMBIGUOUS` semantic outcome. |
| `INCOMPLETE_GOVERNING_CONTEXT` | A mandatory/conditional item has `context_complete=False`, or its admitted context cannot fit existing exact-span bounds. Only statically linked context items activate; an unresolvable edge remains context-unresolved without a speculative call. |
| `RULE_LIKE_FALLBACK` | A non-mandatory exact child is rule-like and has one or more deterministic category hints. This activation occurs at plan initialization and runs after mandatory anchors. |
| `EXPLICIT_REFERENCE_REQUIRED` | The index contains a resolved explicit reference from an active item to the section. The referenced section activates for the referring categories allowed by static routing. |
| `GLOBAL_CONTEXT_REQUIRED` | The index marks the section as expressly global governing context for an active item. It activates for the item's categories allowed by static routing. |
| `ROUTING_UNCERTAIN` | Static rule-like metadata supplies a category hint but local evidence does not meet mandatory-anchor criteria. This activation occurs at plan initialization after rule-like routing validation. |

`NO_SUPPORTED_ANCHOR` and `AMBIGUOUS_ANCHOR` inspect retained normalization outcomes,
not model confidence or desired verdict. `UNKNOWN` and `UNSUPPORTED` do not become
support; after all anchors are accounted they may trigger `NO_SUPPORTED_ANCHOR`. If
a category has no mandatory anchor, `NO_SUPPORTED_ANCHOR` triggers for its matching
conditional items during initialization. A trigger activates every predeclared
conditional item that carries that reason and category; ranking and physical capacity
then determine dispatch, never activation omission.

When several reasons become true together, the retained reason uses this precedence:
`INCOMPLETE_GOVERNING_CONTEXT`, `EXPLICIT_REFERENCE_REQUIRED`,
`GLOBAL_CONTEXT_REQUIRED`, `AMBIGUOUS_ANCHOR`, `NO_SUPPORTED_ANCHOR`,
`RULE_LIKE_FALLBACK`, then `ROUTING_UNCERTAIN`. The complete allowed-reason tuple
remains on the immutable item. No activation reason may expand categories beyond
deterministic pre-extraction hints or indexed context edges.

Activation loops are impossible by contract: the activation ledger is append-only,
deduplicated, and evaluated to a fixed point over the finite item set after each
accounted outcome. Context-edge activation may name only existing plan items. A
fixed-point pass that adds zero activations terminates without a model call.

## 8. Scheduler contract

`SectionScheduler` consumes `SectionIndex`, `AcquisitionPlan`, `CoverageLedger`, and
the existing shared `LiveBudgetGuard`. It MUST execute plan items and MUST NOT
recompute every unattempted section/category Cartesian pair.

Its constructor becomes:

```python
SectionScheduler(
    index: SectionIndex,
    plan: AcquisitionPlan,
    ledger: CoverageLedger,
    budget: LiveBudgetGuard,
)
```

The scheduler's decision sequence is:

1. Refuse work for an already terminated run.
2. Refuse work when the existing runtime step bound is reached.
3. Apply deterministic conditional activations to a fixed point.
4. Select the lowest breadth depth among unresolved active mandatory items; break
   ties with the stored ranking and IDs.
5. If no mandatory item is eligible, do the same for activated conditional items.
6. Never select a category-free reserve item. It must first receive a valid
   deterministic promotion activation.
7. Before constructing an eighth extraction job, return `PLAN_EXHAUSTED` and record
   all remaining activated items as overflow.
8. For a selected job within plan capacity, preserve the existing physical budget
   check and request-time reservation. A genuine call-count or cost refusal before
   the seventh dispatch remains `BUDGET_BLOCKED`.

`ExtractionJob` retains its existing source, section, category, span, context, and
authority-revision fields and adds `plan_id`, `plan_item_id`, and `tier`. Its
`categories` bound remains one or two. Job identity additionally binds `plan_id` and
`plan_item_id`. A `(source_revision, section_id, category)` pair may be attempted at
most once. Repackaging, renamed focus, activation reason, or authority revision MUST
NOT permit a duplicate pair.

`NoExtractionReason` adds the internal acquisition reason `PLAN_EXHAUSTED`.
This is not a new successful runtime termination enum. `SectionAcquisition` maps it
to the existing `NO_PROGRESS` terminal reason and emits bounded plan diagnostics.
`SOURCE_EXHAUSTED` remains valid only when every indexed section is accounted for,
no activated or promotable governing obligation remains, all context is resolved,
and no uninspected reserve item remains. A reserve item's routing status is not proof
that its source text lacks a governing clause. In ordinary V1 runs,
`PLAN_EXHAUSTED` is expected to be more common than true source exhaustion.

When plan capacity is reached with activated obligations undispatched,
`pivot_eligible=False`: the current source was not exhausted, and this amendment does
not authorize another source or more calls. When a bounded plan completes without
overflow but lacks authority, pivot eligibility remains diagnostic under the prior
compiler design; no automatic search/fetch is added.

Within each tier the scheduler preserves breadth before depth across the nine
critical categories. Context sections are admitted exactly through the existing
transitive context graph. Ranking MUST NOT remove, truncate, or reorder required
context spans.

## 9. Coverage and source-accounting semantics

`CoverageLedger` is constructed as `CoverageLedger(index, plan)`. It no longer owns
relevance classification. It consumes plan inventory and owns activation, attempt,
outcome, and source-accounting state.

The existing `AcquisitionState` values remain. A separate internal state expresses
why acquisition did or did not account for a category:

```python
class CategoryAccountingState(StrEnum):
    PENDING = "PENDING"
    SUPPORTED = "SUPPORTED"
    EXHAUSTED_UNRESOLVED = "EXHAUSTED_UNRESOLVED"
    CONTEXT_UNRESOLVED = "CONTEXT_UNRESOLVED"
    OVERFLOW_UNRESOLVED = "OVERFLOW_UNRESOLVED"
```

Plan-item progress is retained separately:

```python
class PlanItemState(StrEnum):
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    EXTRACTION_ATTEMPTED = "EXTRACTION_ATTEMPTED"
    ACCOUNTED = "ACCOUNTED"
    CONTEXT_UNRESOLVED = "CONTEXT_UNRESOLVED"
    OVERFLOW_UNDISPATCHED = "OVERFLOW_UNDISPATCHED"
```

`ACCOUNTED` means the attempt and its actual semantic outcome were retained; it does
not mean supported. Existing `AcquisitionOutcome` remains the semantic record and
preserves `SUPPORTED`, `AMBIGUOUS`, `UNKNOWN`, and `UNSUPPORTED` distinctly.

For each category, `CategoryAccountingState.SUPPORTED` requires all of the following:

- every activated mandatory and conditional obligation for that category is
  `ACCOUNTED`;
- at least one accounted result contains supported canonical authority;
- no accounted result is ambiguous;
- every required governing context edge and admitted clause context is complete;
- no higher-priority activated potential governing clause for the category is
  unattempted, context-unresolved, or overflow-undispatched; and
- no retained contradiction invalidates the supported interpretation.

When these conditions hold, existing `AcquisitionState.SUPPORTED` is returned.
When an active safe job remains, it returns `SECTION_AVAILABLE`. During a dispatch it
returns `EXTRACTION_ATTEMPTED`. When the bounded plan has no dispatchable work but
support is incomplete, it returns `EXHAUSTED`, while `CategoryAccountingState`
retains the precise unresolved cause.

`EXHAUSTED_UNRESOLVED` means the category's finite activated plan was accounted for
without complete supported authority. `CONTEXT_UNRESOLVED` means required governing
context could not be safely admitted or resolved. `OVERFLOW_UNRESOLVED` means at
least one activated obligation was outside the seven-dispatch capacity. None is an
eligibility PASS, a proof of source absence, or a successful graph authority.

Inactive conditional items and category-free reserve items remain index-discoverable
but are not unfinished mandatory coverage. They may not be used to declare absence,
compliance, or source exhaustiveness. This is the central change that removes the
unbounded Cartesian completion requirement without silently discarding fallback.

Every transition retains source revision, plan ID, item ID where applicable,
category, before/after acquisition state, before/after accounting state, activation
reason, semantic outcome, authority revision, and safe cause code. Transition and
receipt payloads remain bounded and contain no raw prompt, full source body, model
response, credential, or private profile fact.

## 10. Bounded and fail-closed stopping

`QUALOR_5F` remains limited to 9 inference calls: 2 planning calls and at most 7
extraction dispatches. The plan's seven-job capacity is an acquisition limit inside
the existing physical guard, not a replacement budget authority.

The following stops are distinct:

| Condition | Acquisition reason | Existing runtime terminal reason | Source exhaustiveness claim |
| --- | --- | --- | --- |
| Seven extraction jobs consumed and activated work remains | `PLAN_EXHAUSTED` with overflow | `NO_PROGRESS` | no |
| No active jobs, bounded plan accounted, inactive/reserve inventory retained | `PLAN_EXHAUSTED` | `NO_PROGRESS` | no |
| Complete index and every deterministic governing path truly accounted | `SOURCE_EXHAUSTED` | existing `NO_PROGRESS` mapping | yes, only for this source revision |
| Physical guard refuses a permitted job before plan capacity | `BUDGET_BLOCKED` | `BUDGET_EXHAUSTED` | no |
| Context graph cannot safely supply a required job | `CONTEXT_UNRESOLVED` | existing `NO_PROGRESS` mapping | no |
| Existing step bound reached | `STEP_BOUND` | `MAX_STEPS` | no |

Reaching seven extractions MUST NOT be described as source exhaustion. If activated
mandatory or conditional items remain, their IDs/categories and
`OVERFLOW_UNRESOLVED` accounting are retained. Eligibility remains unresolved under
the existing evaluator because the coverage guard withholds effective authority.
No authority, PASS, successful completion, opportunity graph, or decision graph is
created from capacity exhaustion.

The successful runtime termination set is unchanged:

```text
SUFFICIENT_CRITICAL_EVIDENCE
HARD_FAIL_CONFIRMED
```

This design does not add `PLAN_EXHAUSTED` to that set. It does not convert
`REVIEW_REQUIRED`, `WATCH`, `UNKNOWN`, `AMBIGUOUS`, or `UNSUPPORTED` into a successful
completion. WorkspaceRunCapture continues to persist terminal telemetry and to reject
a fake partial-success graph under existing semantics.

## 11. Context invariants

The acquisition plan consumes, but does not redefine, the SectionIndex context graph.
All modes and implementation changes MUST preserve unchanged:

- `context_section_ids` and their order;
- parent ancestry and bounded-child parent linkage;
- resolved explicit references;
- expressly global-scope context;
- `context_complete`;
- unsafe-boundary fail-close behavior;
- exact span/source/revision capabilities;
- qualifier and exception visibility.

The logical heading used for child-local routing is not a replacement for the
existing context graph. A plan item includes all transitive required context when
constructing an ExtractionJob. If the context does not fit the existing 12-span or
12-context bounds, the item becomes `CONTEXT_UNRESOLVED`; ranking may not sever it to
buy a call. A referenced/global context item may be conditionally activated for
semantic inspection, but its source text remains context rather than invented factual
authority.

## 12. Authority invariants

This amendment preserves:

- `UNKNOWN != PASS`;
- `AMBIGUOUS != PASS`;
- `UNSUPPORTED != PASS`;
- model confidence is not support;
- LLM final eligibility authority is absent;
- the model proposes candidates only from plan-issued exact spans and allowed
  categories;
- local grounding, typed adapters, and deterministic evaluation remain mandatory;
- raw semantic authority remains distinct from effective coverage-guarded authority;
- supported raw rules may be retained while the coverage guard makes them
  non-executable due to unresolved plan obligations;
- no owner or project fact is inferred from opportunity rules;
- qualifiers, exceptions, evidence IDs, ClauseContext, and provenance remain intact;
- persistence consumes the single runtime-selected decision and does not recompute it.

Plan tier, activation, rank, accounting, and exhaustion are acquisition diagnostics.
They MUST NOT appear as RuleCandidate operands, applicant facts, project facts,
eligibility verdicts, strategy scores, or frontend recommendations.

## 13. Budget and policy invariants

No budget, request, or semantic limit changes:

| Policy | Required value |
| --- | ---: |
| `QUALOR_5F_INFERENCE_MAX_CALLS` | 9 |
| Planning calls reserved by current architecture | 2 |
| Maximum extraction dispatches | 7 |
| `QUALOR_5F_COST_CAP_USD` | 0.35 |
| `MAX_STEPS` | 24 |
| `MAX_EXTRACTED_CLAIMS_PER_CALL` | 2 |
| Conservative measured worst case | USD 0.306591 |
| Conservative measured headroom | USD 0.043409 |

Model IDs, model output bounds, extraction output bounds, search/fetch limits,
reservation calculation, reconciliation, and the tenth-call refusal remain unchanged.
The historical `QUALOR_03B3` USD 0.20 policy and diagnostic 6-call/USD 0.15 policy
remain unchanged. No plan decision may depend on a favorable token reconciliation.

## 14. Component boundaries

| Component | Bounded responsibility after this amendment | Prohibited responsibility |
| --- | --- | --- |
| `sections.py` | Child-local body categories, separately inherited heading categories, generic rule-like metadata, unchanged structure/context graph | Plan capacity, semantic support, eligibility, source-specific routing |
| `acquisition_plan.py` | Immutable inventory, tier assignment, IDs, ranking, activation predicates, seven-job capacity | Model calls, semantic outcomes, rules, eligibility, budget reservation |
| `section_scheduler.py` | Execute active plan items in deterministic breadth-first order, pack at most two categories, deduplicate, distinguish plan/budget/source stops | Recompute Cartesian relevance, activate network pivots, change limits |
| `acquisition_coverage.py` | Track discoverability, activation, attempts, semantic outcomes, per-category accounting, overflow | Category routing, plan rank, eligibility verdicts |
| `section_acquisition.py` | Build the plan once, orchestrate scheduled extraction, activate from retained outcomes, preserve guarded authority, emit truthful stop diagnostics | Add retries, alter adapters/evaluator/completion, fabricate source exhaustion |

The implementation MUST avoid moving all planning logic into CoverageLedger.
`acquisition_plan.py` is the sole plan-membership and rank authority. The scheduler
may consume stored rank but may not reconstruct it. Coverage may activate predeclared
items but may not invent membership.

## 15. Genericity

Production behavior MUST satisfy:

```text
DEVPOST_SPECIFIC_BRANCHES=0
AWS_AGENTS_FOR_HUMANS_SPECIFIC_BRANCHES=0
CONTEST_NAME_MATCHING=0
ARCHIVE_HASH_OUTCOME_BRANCHES=0
SOURCE_DOMAIN_OUTCOME_BRANCHES=0
```

Allowed vocabulary is generic semantics such as submission period, eligibility,
license, technology, reward, financial support, obligation, prohibition, qualifier,
and exception. The archived Task 15 sections are acceptance evidence only. Their
hostnames, IDs, offsets, hashes, contest wording, category counts, and known deadline
result MUST NOT appear in routing/ranking branches or production fixtures.

## 16. Acceptance contract

The completed production repair is accepted only when the hash-bound archived path
and independent generic tests prove all of the following without external network or
paid calls:

```text
PLANNING_CALLS=2
EXTRACTION_CALLS<=7
TOTAL_MODEL_CALLS<=9
OVER_BROAD_RELEVANCE_BUDGET_EXHAUSTED=NO
ALL_NINE_CATEGORIES_DISCOVERABLE=YES
ALL_NINE_CATEGORIES_ACCOUNTED_OR_EXPLICITLY_UNRESOLVED=YES
DEADLINE_RAW_AUTHORITY_SUPPORTED=YES
DEADLINE_RAW_AUTHORITY_EXECUTABLE=YES
HIDDEN_GOVERNING_CLAUSE_SILENTLY_SKIPPED=0
UNKNOWN_CATEGORIES_REMAIN_UNRESOLVED=YES
FAKE_SUCCESSFUL_GRAPH=NO
```

`ALL_NINE_CATEGORIES_ACCOUNTED_OR_EXPLICITLY_UNRESOLVED` means every category has a
retained `CategoryAccountingState` and reason. It does not require authority for all
nine, source exhaustiveness, eligibility PASS, or successful completion.

The run may truthfully classify as Task 14 `CASE_A`, `CASE_B`, or `OTHER_BLOCKER`.
The architecture MUST NOT tune rank or activation to force any case. A genuine cost,
step, operational, malformed-output, persistence, or context blocker remains the
exact blocker. Task 14's test is rerun unchanged after the repair.

The seven Task 15 potential hidden-clause sections receive a dedicated archive
acceptance assertion: each MUST be a mandatory/conditional item or an indexed context
dependency with an explicit accounting state before the acquisition stop. The test
reports safe section IDs/ranges only and MUST NOT hardcode those IDs into production.

## 17. TDD strategy for the later implementation

Implementation remains unauthorized by this document. Once separately authorized,
development uses RED/GREEN in dependency order.

The owning test files are fixed as follows:

| Production responsibility | Owning tests |
| --- | --- |
| Child-local and rule-like routing | `tests/runtime/test_sections.py` |
| Finite plan, tiers, activation, identity, and overflow | `tests/runtime/test_acquisition_plan.py` |
| Plan-aware acquisition/source accounting | `tests/runtime/test_acquisition_coverage.py` |
| Plan execution and bounded scheduling | `tests/runtime/test_section_scheduler.py` |
| Orchestration and truthful acquisition stops | `tests/runtime/test_section_acquisition.py` |
| Hash-bound compiler acceptance and hidden-clause accounting | `tests/runtime/test_archived_compiler_acceptance.py`, using the existing `tests/runtime/archived_compiler_support.py` |
| Call/cost envelope | `tests/runtime/test_compiler_cost_simulation.py` |
| Existing completion/persistence policy diagnosis | `tests/workspace/test_compiler_completion_gate.py` |

### 17.1 `sections.py`

- A category term in sibling body child B does not enter child A's body categories.
- The exact logical heading routes every bounded child separately from body routing.
- Body text physically containing the heading does not double-count it as local body
  evidence.
- Generic obligation, prohibition, limitation, submission/time, technology/license,
  funding/reward, and evaluation/selection markers are detected deterministically.
- Rule-like text with no category hint stays discoverable as reserve.
- Structural ancestry, references, global scope, `context_section_ids`, and
  `context_complete` remain byte-for-byte/equality equivalent to current behavior.
- Unsafe cuts, unresolved references, and context overflow continue to fail closed.

### 17.2 `acquisition_plan.py`

- Identical source/index/router/profile capacity yields identical item and plan IDs.
- Source revision, indexer version, routing version, context dependency, category,
  tier, or rank input changes identity.
- Model output, clock, run ID, and verdict cannot affect membership or order.
- Mandatory, conditional, and reserve classification is mutually exclusive.
- Every indexed section appears in inventory; reserve sections are not multiplied by
  nine.
- Stable ordering is independent of dictionary/set iteration.
- Maximum dispatch capacity is exactly seven and cannot be overridden by input.
- At most two categories are packed only under identical tier/context/activation.
- Conditional activation follows each bounded reason and reaches a finite fixed point.
- Activated items beyond capacity remain overflow obligations.

### 17.3 `acquisition_coverage.py`

- Indexed discoverability is distinct from plan membership and activation.
- Inactive conditional and reserve inventory do not become mandatory unfinished work.
- Mandatory and activated conditional items block supported accounting until
  accounted.
- `SUPPORTED` requires authority, complete context, no ambiguity, and no higher-
  priority unaccounted obligation.
- `AMBIGUOUS`, `UNKNOWN`, and `UNSUPPORTED` remain distinct and never become PASS.
- Context-unresolved and overflow-unresolved causes survive exhaustion.
- Source revision replacement constructs a new plan/accounting identity and cannot
  reuse stale attempts.

### 17.4 `section_scheduler.py`

- Scheduler consumes stored plan rank and never calls Cartesian `_is_relevant` logic.
- Mandatory work precedes conditional work; breadth precedes unnecessary depth.
- Jobs contain one or two categories and no duplicate pair can dispatch.
- Static rule-like fallback and triggered conditional activation are deterministic.
- Category-free reserve does not explode into nine pairs.
- The eighth extraction is refused as `PLAN_EXHAUSTED` before a budget-blocked slot
  is planned.
- A genuine physical guard refusal among the first seven remains `BUDGET_BLOCKED`.
- Context-unresolved work cannot be dispatched with truncated context.

### 17.5 `section_acquisition.py`

- Plan is built once before model extraction and reused for the source revision.
- The existing production extractor, adapters, canonical compiler, coverage guard,
  handoff, and decision authority remain on the path.
- A seven-dispatch stop with overflow maps to existing `NO_PROGRESS`, not
  `BUDGET_EXHAUSTED` or `SOURCE_EXHAUSTED`.
- Genuine budget, step, provider, schema, and context failures keep their current
  semantics.
- No extra terminal model call or hidden retry is introduced.
- Raw supported authority remains retained while effective authority fails closed on
  unresolved accounting.
- No fake source exhaustiveness or successful graph is emitted.

### 17.6 Archived and generic acceptance

- The archive remains hash-bound and external I/O remains denied.
- All nine categories have deterministic inventory/accounting states.
- The real deadline interval remains raw supported executable authority.
- Planning remains two calls; extraction is at most seven; total is at most nine.
- The seven rule-like Task 15 fallback examples are accounted without archive-specific
  production branches.
- Independent synthetic sources cover sibling smear, heading-only routing, hidden
  rule-like clauses, unresolved overflow, explicit/global context, qualifiers,
  exceptions, alternatives, ambiguity, and no-support anchors.
- Cost simulation still proves `QUALOR_5F` USD 0.35, the tenth-call count refusal, the
  historical USD 0.20 policy, and diagnostic USD 0.15 policy.
- Task 14 reruns unchanged and reports its real case.

Regression verification includes the owning runtime tests, archive acceptance, cost
simulation, Task 14 completion diagnostic, full Python suite, Ruff, schema/domain
drift checks, frontend tests/build, controlled Playwright configurations, and the
canonical offline verification script. No paid LIVE run is part of acceptance.

## 18. Migration and compatibility

This is an internal runtime amendment. No database migration, persisted-data
migration, public domain schema change, frontend schema change, or hosted API change
is expected.

Migration proceeds in these bounded steps:

1. Extend internal SourceSection routing metadata while retaining
   `candidate_categories` as the documented compatibility union.
2. Add `acquisition_plan.py` and its unit tests without activating it.
3. Change CoverageLedger to require `(index, plan)` and update its internal tests.
   Production construction changes in the same activating commit so no intermediate
   production path uses a legacy Cartesian fallback.
4. Change SectionScheduler to require the plan and execute plan items.
5. Activate one-plan-per-source-revision construction in SectionAcquisition.
6. Retain existing `AcquisitionState`, `AcquisitionOutcome`, extraction request,
   adapter, authority, evaluator, decision, and persistence contracts.

Existing tests that construct CoverageLedger or SectionScheduler must use a plan
built from their SectionIndex. Tests intended to prove legacy fallback multiplication
are replaced with assertions for reserve discoverability and non-multiplication;
their UNKNOWN/AMBIGUOUS/UNSUPPORTED and context safety guarantees remain.

Internal diagnostic fields may be added to bounded run events only if existing event
size/privacy limits are proven. The plan itself is reconstructed from source revision
and versioned routing; it is not stored in new database tables. Public workspace
read models do not expose raw plan inventory in V1.

## 19. Risks and mitigations

| Risk | Required mitigation |
| --- | --- |
| Under-routing a hidden governing clause | Separate child body from inherited heading; generic rule-like/category-hint detector; explicit/reference/global activation; archive proof for all seven diagnosed examples; reserve never proves absence. |
| Over-routing recreates call explosion | Mandatory requires local high-confidence evidence; heading-only and rule-like hints are conditional; reserve is section-level, not a nine-category Cartesian set; seven dispatches remain fixed. |
| Conditional activation loops | Immutable finite plan; append-only deduplicated activations; fixed-point evaluation adds each item/category at most once; no activation creates new membership. |
| Ambiguous context is treated as complete | Mandatory `context_complete`; transitive existing context graph; ambiguity/incomplete context blocks supported accounting and becomes `CONTEXT_UNRESOLVED`. |
| Plan ranking starves a critical category | Existing category order plus explicit breadth-depth key; strongest first item for each category before depth within a tier; overflow retained by category. |
| Capacity overflow is misreported as source exhaustion | Internal `PLAN_EXHAUSTED`, `PlanOverflow`, and `OVERFLOW_UNRESOLVED`; map to existing `NO_PROGRESS`; `SOURCE_EXHAUSTED` requires the stronger full-source predicate. |
| Source revision changes plan identity | Source revision, indexer version, routing version, capacity, and all item IDs bind plan ID; attempts/activations never carry across a different plan. |
| Rule-like detector becomes contest-specific | Fixed generic lexical/structural families, boundary-aware normalization, independent synthetic tests, and prohibited-literal scan of production changes. |
| Archive overfitting | Archive IDs/counts remain acceptance measurements only; no host/hash/name/known-result rank input; independent adversarial and synthetic routing cases are mandatory. |
| Static category hints miss a generic rule with no noun | Preserve it as reserve, never infer absence/PASS, expose unresolved discoverability diagnostics, and permit future source/revision or separately designed discovery expansion without silently promoting it. |
| Physical cost blocks before seven calls | Keep the shared LiveBudgetGuard and exact `BUDGET_BLOCKED` semantics; plan capacity never overrides cost reservations or reconciliation. |
| Supported raw rule becomes an unsafe effective hard failure | Existing coverage guard converts it to non-executable unresolved authority until all activated higher-priority obligations and context are accounted. |

## 20. Resolved design questions

### Is plan capacity selected per document?

No. V1 is bound to the approved `QUALOR_5F` profile: 9 total inference calls, 2
planning calls, and exactly 7 possible extraction dispatches. Document size changes
inventory and overflow, not policy limits.

### Can model output alter routing or activate a new category?

No. Retained semantic outcomes can trigger activation of an already declared
conditional item, but item membership, category hints, context edges, and rank are
entirely deterministic and pre-extraction.

### Does a reserve section block every category?

No. It remains discoverable and cannot prove absence, but it is not a mandatory
category pair. Only deterministic category-bearing promotion makes it an activated
obligation.

### Does `PLAN_EXHAUSTED` require a new runtime completion state?

No. It is an internal acquisition reason mapped to existing `NO_PROGRESS`. The
successful completion set and WorkspaceRunCapture terminal policy do not change.

### Can a category be source-accounted as supported after one supported anchor?

Only if every activated mandatory/conditional obligation for that category is
accounted, context is complete, no ambiguity/contradiction remains, and no
higher-priority activated item overflowed. A supported raw rule alone is insufficient.

### Is true source exhaustion required for a truthful stop?

No. A bounded plan may truthfully stop with explicit unresolved accounting. It must
not claim source exhaustiveness, but it also must not attempt an unauthorized eighth
extraction merely because reserve inventory remains discoverable.

### Are public schemas or persisted records changed?

No. Planning and source accounting remain internal. Bounded safe diagnostics may use
existing event payload extension points only if their current limits are preserved.

### Does this amendment change eligibility or successful completion policy?

No. It changes acquisition routing, scheduling, and coverage accounting. The existing
deterministic eligibility/decision engines and runtime successful-completion reasons
remain unchanged.

## 21. Non-goals and implementation boundary

This design does not redesign or authorize changes to:

- eligibility or decision engines;
- successful runtime completion semantics;
- WorkspaceRunCapture or WorkspaceStore persistence policy;
- frontend verdict or display policy;
- hosted API, approval, or Application Pack flow;
- model, provider, search/fetch admission, or automatic second-source acquisition;
- budget/cost/call/step/token/claim limits;
- typed adapter grammar or canonical authority semantics;
- external submission functionality.

No new model, increased limit, source-specific optimization, deployment, paid call,
or fourth LIVE run is authorized. The next permitted action is controller review and
owner approval of this written specification. Only then may a separate implementation
plan be authored and reviewed.
