# Truthful Review Graph Completion Semantics

## Decision

`NO_PROGRESS` continues to map to `PARTIAL`; `SUCCESS_TERMINATIONS` and the
meaning of `COMPLETED` are unchanged. A completed run and a review-persistable
graph are separate concepts.

## Reviewable partial graph

`WorkspaceRunCapture` may atomically persist the runtime-owned bundle for a
reviewable graph only when all of these hold:

- capture mode and result mode are `LIVE`;
- termination is `NO_PROGRESS` and the terminal run state is `PARTIAL`;
- the existing deterministic result eligibility is `REVIEW_REQUIRED`;
- the runtime bundle is present and passes the existing graph, input-snapshot,
  opportunity, candidate, and official-rules evidence validation.

No fact, evidence, rule, candidate, recommendation, or selected decision is
created by persistence. The existing runtime bundle is the sole authority, and
persistence never invokes `decide`.

## Linkage and integrity

The run links to the bundle's exact opportunity ID/version. All existing
evidence, decision candidates, and input snapshots are persisted through the
existing immutable graph transaction. If the runtime has a selected decision,
the run links to that exact ID/version. If it has none, the run keeps a null
decision link; persistence never fabricates a selection.

Successful graph persistence keeps its current selected-decision requirement.
Reviewable partial graph validation deliberately permits an absent selection but
retains every other existing validation and official-evidence requirement.

## Idempotency and failure boundaries

The run-capture callback remains immutable after its first committed terminal
record. A repeated callback cannot create another graph or invoke authority;
the existing immutable-callback error leaves persisted counts unchanged.

`BUDGET_EXHAUSTED`, `MAX_STEPS`, and `TOOL_FAILURE_BOUND_REACHED` do not meet
the reviewable predicate and continue to persist telemetry without a graph.
