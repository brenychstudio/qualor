# QUALOR Live Opportunity Graph and Workspace Persistence Design

**Task:** `QUALOR-LIVE-PRODUCTION-TASK-1`

**Canonical base:** `b8cecc51eba5771784759376b95949f9460f7fe9`

## Goal

Turn one real LIVE Strands research run into one source-grounded, versioned
opportunity graph that the existing Workspace service and read API can consume.
The deterministic decision produced by the runtime is the only decision authority.

## Runtime authority

The handoff compiles a single runtime-owned bundle containing the canonical
`OpportunityRecord`, the admitted `EvidenceRecord` objects, the canonical
`DecisionInput`, and its `DecisionOutput`. The runtime caches that bundle for the
current admitted-evidence revision. Finalization reuses it when no evidence changed;
workspace persistence never calls `decide()`.

Opportunity organizer, program, and edition may be promoted only from a claim that
was admitted against a fetched hard-authority source and whose normalized value is
supported by the exact quoted span. Multiple distinct values are a contradiction and
leave that field `UNKNOWN`. Other unsupported fields remain unknown rather than being
inferred. The existing `opportunity_identity(organizer, program_name, edition)` and
semantic digest policy remain authoritative.

Deadline promotion accepts only a deterministic timezone-aware absolute instant.
Naive dates, naive datetimes, named-timezone prose outside the explicit generic
normalizer, invalid instants, and conflicting instants remain unknown. The exact
excerpt, original/final URL, source hash, and `retrieved_at` remain on the evidence
record; no clock rebasing occurs in LIVE or REPLAY.

## Version boundary

The runtime accepts an optional opportunity version resolver. Without persistence it
keeps version 1. `WorkspaceRunCapture` implements the resolver using the existing
semantic digest and repository history: unchanged semantics reuse the existing
version; changed semantics receive the next version. Resolution happens before the
single call to `decide()`, so every produced `DecisionRecord` already points at the
authoritative opportunity version. The capture verifies that resolution again inside
the final transaction and fails closed on a race or mismatch.

## Persistence boundary

`WorkspaceRunCapture` receives the original `StudioInput`, buffers bounded events,
and atomically writes a successful graph: founder profile, project profiles,
opportunity/version, evidence, every legitimate candidate decision, one linked
`RunRecord`, and its events. The run's decision link binds only to
`DecisionOutput.selected_decision`; later approval authority therefore follows only
the selected decision.

Completed runtime outcomes are eligible for a graph only when the bundle and selected
decision are present and consistent. Budget stops, provider disconnections, partial
termination, extraction failure, or any other run without a sufficient authoritative
graph write terminal run telemetry with null graph links. They never create a fake
successful opportunity or decision.

Runtime observer isolation remains intact. Capture callbacks retain a bounded
persistence exception instead of raising into the agent. When an operator explicitly
requested `--workspace-database`, `run_command` calls a capture verification method
after `run_agent()` returns; the command fails closed if the graph or terminal
telemetry was not persisted.

## CLI and scope

`qualor run-live-opportunity` gains only an explicit optional
`--workspace-database PATH` option. No persistence default, hosted endpoint, frontend
change, cloud resource, or AWS call is introduced. Automated coverage uses controlled
offline providers and LIVE-shaped results without contacting AWS.

## Acceptance

Tests prove source-grounded metadata, conservative unknowns, absolute deadline and
provenance retention, one deterministic decision computation, no persistence-side
decision computation, graph/link persistence, restart reconstruction through the
existing service/API, truthful failure telemetry, and unchanged FIXTURE/REPLAY
behavior.
