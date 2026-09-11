import type { RunEventView, RunView } from '../../generated/domain';

// The public runtime event vocabulary. Adding a member here without adding its copy
// below fails typecheck, so a new public event can never render as a bare code.
export type PublicRunEvent =
  | 'SEARCH_REQUESTED'
  | 'SEARCH_RESULTS_RECEIVED'
  | 'CANDIDATE_SELECTED'
  | 'SOURCE_SELECTED'
  | 'SOURCE_FETCHED'
  | 'SOURCE_REFERENCE_CREATED'
  | 'EVIDENCE_SPANS_CREATED'
  | 'STRUCTURED_EXTRACTION'
  | 'SOURCE_SPAN_SELECTED'
  | 'CLAIM_EXTRACTED'
  | 'CLAIM_NORMALIZATION_RESULT'
  | 'EVIDENCE_RECORDED'
  | 'ELIGIBILITY_EVALUATED'
  | 'DECISION_EVALUATED'
  | 'HUMAN_REVIEW_NEEDED'
  | 'RUN_TERMINATED'
  // Written by the workspace fixture seeder rather than by the runtime loop. Without copy of
  // their own they reached the rail as spaced-out enum text next to properly presented events.
  | 'OPPORTUNITY_DISCOVERED'
  | 'DECISION_UPDATED';

const EVENT_COPY: Record<PublicRunEvent, string> = {
  SEARCH_REQUESTED: 'Official sources searched',
  SEARCH_RESULTS_RECEIVED: 'Search results received',
  CANDIDATE_SELECTED: 'Candidate source selected',
  SOURCE_SELECTED: 'Official source selected',
  SOURCE_FETCHED: 'Official source retrieved',
  SOURCE_REFERENCE_CREATED: 'Source reference recorded',
  EVIDENCE_SPANS_CREATED: 'Evidence spans recorded',
  STRUCTURED_EXTRACTION: 'Structured extraction run',
  SOURCE_SPAN_SELECTED: 'Source span selected',
  CLAIM_EXTRACTED: 'Claim extracted',
  CLAIM_NORMALIZATION_RESULT: 'Claim normalization recorded',
  EVIDENCE_RECORDED: 'Evidence recorded',
  ELIGIBILITY_EVALUATED: 'Eligibility evaluated',
  DECISION_EVALUATED: 'Decision updated',
  HUMAN_REVIEW_NEEDED: 'Human review needed',
  RUN_TERMINATED: 'Run ended',
  OPPORTUNITY_DISCOVERED: 'Opportunity discovered',
  DECISION_UPDATED: 'Decision updated',
};

/* Why a run stopped, in the reader's language. The runtime's own codes are short enough for the
   wide history page but not for a 187px rail, where `SUFFICIENT_CRITICAL_EVIDENCE` is one
   unbreakable token that overflows the zone. Each canonical reason gets copy; anything the
   runtime adds later still reaches the reader through `stateText`, and every caller keeps the
   recorded code alongside, so nothing is hidden by being made readable. */
const TERMINATION_COPY: Record<string, string> = {
  SUFFICIENT_CRITICAL_EVIDENCE: 'Stopped once critical evidence was sufficient',
  HARD_FAIL_CONFIRMED: 'Stopped on a confirmed hard failure',
  BUDGET_EXHAUSTED: 'Stopped because the run budget was exhausted',
  NO_PROGRESS: 'Stopped after the run made no further progress',
  TOOL_FAILURE_BOUND_REACHED: 'Stopped at the recorded tool-failure limit',
  MAX_STEPS: 'Stopped at the recorded step limit',
  PROVIDER_DISCONNECTED: 'Stopped because the live provider disconnected',
};

const PHASE_COPY = {
  DISCOVERING: 'Discovering',
  VERIFYING: 'Verifying',
  EVALUATING: 'Evaluating',
  DECISION_UPDATED: 'Decision updated',
} as const;

const isPublicRunEvent = (value: string): value is PublicRunEvent => value in EVENT_COPY;

export const stateText = (value: string) => value.replaceAll('_', ' ');

/** Recorded UTC clock time. No duration is inferred and no timestamp is invented. */
export const clockText = (value: string) => value.slice(11, 16);

export interface PresentedEvent {
  key: string;
  /** The server's own sequence. A seeded run records every observation at one instant, so the
   *  clock cannot carry the order and this is what the reader counts by. */
  order: string;
  time: string;
  /** Full recorded instant, so assistive technology is not limited to a clock reading. */
  instant: string;
  phase: string | null;
  label: string;
  detail: string | null;
  /** This is the run's last recorded decision evaluation — the one the workspace now shows.
   *  Set by `presentEvents`, which is the only place with the list context to know. */
  outcome: boolean;
  mode: RunEventView['mode'];
}

/** The runtime re-evaluates whenever a claim or source is admitted, and `finish()` evaluates
 *  once more, so a real run records several of these. `run_capture` maps DECISION_EVALUATED onto
 *  the DECISION_UPDATED phase, and the fixture seeder writes the type directly. */
const isDecisionEvaluation = (event: RunEventView) => event.phase === 'DECISION_UPDATED'
  || event.event_type === 'DECISION_UPDATED'
  || event.event_type === 'DECISION_EVALUATED';

export function presentEvent(event: RunEventView): PresentedEvent {
  const label = isPublicRunEvent(event.event_type)
    ? EVENT_COPY[event.event_type]
    : stateText(event.event_type);
  const observations = [
    event.count > 0 ? `${event.count} recorded` : null,
    event.source_ids.length ? `${event.source_ids.length} source refs` : null,
    event.evidence_ids.length ? `${event.evidence_ids.length} evidence refs` : null,
  ].filter((value): value is string => value !== null);
  // A runtime decision event carries the DECISION_UPDATED phase and reads "Decision updated" in
  // both slots; showing the phase again adds no information, so it is dropped when it repeats.
  const phase = event.phase && PHASE_COPY[event.phase] !== label ? PHASE_COPY[event.phase] : null;
  return {
    key: `${event.run_id}:${event.sequence}`,
    order: String(event.sequence).padStart(2, '0'),
    time: clockText(event.occurred_at),
    instant: event.occurred_at,
    phase,
    label,
    detail: observations.length ? observations.join(' · ') : null,
    outcome: false,
    mode: event.mode,
  };
}

/** Presents a recorded sequence. Every event is kept, in the order the server returned it; the
 *  only list-level judgement is which single row is the decision the workspace now shows. */
export function presentEvents(events: readonly RunEventView[]): PresentedEvent[] {
  const lastEvaluation = events.reduce(
    (found, event, index) => isDecisionEvaluation(event) ? index : found, -1);
  return events.map((event, index) => ({ ...presentEvent(event), outcome: index === lastEvaluation }));
}

export interface PresentedRun {
  id: string;
  mode: RunView['mode'];
  state: RunView['state'];
  /** DISCONNECTED is shown only when the server recorded a disconnected live provider. */
  disconnected: boolean;
  usage: string;
  reservedCost: string | null;
  /** The recorded code, unchanged. The full history page shows it; the rail keeps it as the
   *  title behind `terminationCopy`, so the canonical value is never lost. */
  terminationReason: string | null;
  terminationCopy: string | null;
  searchCalls: number;
  fetchedDocuments: number;
  officialSources: number;
  verifiedClaims: number;
  /** Every retrieval counter is zero. True of the seeded W01 run, whose evidence was persisted
   *  from an owned fixture file rather than fetched: the zeros are the fact, not a gap. */
  noRecordedCalls: boolean;
}

export function presentRun(run: RunView): PresentedRun {
  return {
    id: run.id,
    mode: run.mode,
    state: run.state,
    disconnected: run.provider_state === 'DISCONNECTED_LIVE_PROVIDER',
    usage: `${run.search_calls} search calls · ${run.fetched_documents} fetched`,
    reservedCost: Number(run.reserved_cost_usd) > 0 ? `$${run.reserved_cost_usd}` : null,
    terminationReason: run.termination_reason,
    terminationCopy: run.termination_reason
      ? TERMINATION_COPY[run.termination_reason] ?? stateText(run.termination_reason)
      : null,
    searchCalls: run.search_calls,
    fetchedDocuments: run.fetched_documents,
    officialSources: run.official_source_count,
    verifiedClaims: run.verified_claim_count,
    noRecordedCalls: run.search_calls === 0
      && run.fetched_documents === 0
      && run.official_source_count === 0
      && run.verified_claim_count === 0,
  };
}

/** The most recently recorded run. Server ordering is preserved, never re-derived. */
export const latestRun = (runs: readonly RunView[]) => runs.at(-1) ?? null;
