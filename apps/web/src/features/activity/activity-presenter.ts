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
  | 'RUN_TERMINATED';

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
  time: string;
  /** Full recorded instant, so assistive technology is not limited to a clock reading. */
  instant: string;
  phase: string | null;
  label: string;
  detail: string | null;
  mode: RunEventView['mode'];
}

export function presentEvent(event: RunEventView): PresentedEvent {
  const label = isPublicRunEvent(event.event_type)
    ? EVENT_COPY[event.event_type]
    : stateText(event.event_type);
  const observations = [
    event.count > 0 ? `${event.count} recorded` : null,
    event.source_ids.length ? `${event.source_ids.length} source refs` : null,
    event.evidence_ids.length ? `${event.evidence_ids.length} evidence refs` : null,
  ].filter((value): value is string => value !== null);
  return {
    key: `${event.run_id}:${event.sequence}`,
    time: clockText(event.occurred_at),
    instant: event.occurred_at,
    phase: event.phase ? PHASE_COPY[event.phase] : null,
    label,
    detail: observations.length ? observations.join(' · ') : null,
    mode: event.mode,
  };
}

export interface PresentedRun {
  id: string;
  mode: RunView['mode'];
  state: RunView['state'];
  /** DISCONNECTED is shown only when the server recorded a disconnected live provider. */
  disconnected: boolean;
  usage: string;
  reservedCost: string | null;
  terminationReason: string | null;
  officialSources: number;
  verifiedClaims: number;
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
    officialSources: run.official_source_count,
    verifiedClaims: run.verified_claim_count,
  };
}

/** The most recently recorded run. Server ordering is preserved, never re-derived. */
export const latestRun = (runs: readonly RunView[]) => runs.at(-1) ?? null;
