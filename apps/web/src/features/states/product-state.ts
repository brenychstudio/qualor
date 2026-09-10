import type { ProductAction, ProductState } from '../../generated/domain';

/**
 * Presentation copy for the server's product states.
 *
 * This file derives nothing. It does not decide whether evidence is readable, whether an
 * approval is valid, whether a run was complete or what the recommendation should be — the
 * server answered all of that. Adding a public product state without copy fails typecheck.
 */
export const PRODUCT_STATE_COPY: Record<ProductState, { title: string; detail: string }> = {
  EMPTY_PROFILE: {
    title: 'Profile required',
    detail: 'Qualification needs a founder profile and at least one project before anything can be evaluated.',
  },
  NO_RESULTS: {
    title: 'No opportunities recorded',
    detail: 'Discovery returned nothing for the current workspace. No opportunity has been invented to fill the gap.',
  },
  DISCONNECTED_LIVE_PROVIDER: {
    title: 'Provider disconnected',
    detail: 'The last persisted snapshot is shown. Nothing on this screen is current, and no work is happening now.',
  },
  BUDGET_STOPPED: {
    title: 'Run stopped at its budget',
    detail: 'The run halted at a recorded limit. Facts admitted before the stop are kept; the rest was never gathered.',
  },
  STALE_EVIDENCE: {
    title: 'Evidence is stale',
    detail: 'The previous decision is retained as a historical snapshot. Freshness policy requires renewed verification before it counts as current.',
  },
  PARTIAL_SOURCE_FAILURE: {
    title: 'Some sources failed',
    detail: 'The recorded decision is preserved exactly as the deterministic engine produced it. Source work was only partly successful.',
  },
  UNKNOWN_ELIGIBILITY: {
    title: 'Eligibility unresolved',
    detail: 'No admissible evidence resolves the eligibility gate. Unresolved is not the same as eligible.',
  },
  REVOKED_APPROVAL: {
    title: 'Approval revoked',
    detail: 'A recorded input changed after the approval was created, so the workspace revoked it.',
  },
  PENDING_APPROVAL: {
    title: 'Approval awaiting confirmation',
    detail: 'A version-bound approval exists and needs an explicit human confirmation. Preparation has not started.',
  },
  FINISHED_PACK: {
    title: 'Application pack prepared',
    detail: 'Preparation finished and the resulting document is recorded for review. Nothing was sent anywhere.',
  },
};

/** Canonical action labels. The action names what to do next, not what may execute. */
export const PRIMARY_ACTION_LABELS: Record<ProductAction, string> = {
  CREATE_PROFILE: 'Create profile',
  ADJUST_SEARCH: 'Adjust search',
  REVIEW_AVAILABLE_EVIDENCE: 'Review available evidence',
  RESOLVE_UNKNOWNS: 'Resolve unknowns',
  REFRESH_EVIDENCE: 'Refresh evidence',
  RECONNECT_PROVIDER: 'Reconnect provider',
  REVIEW_APPROVAL: 'Review approval',
  REVIEW_CHANGES: 'Review changes',
  OPEN_APPLICATION_PACK: 'Open application pack',
};

export const AVAILABILITY_COPY = {
  evidenceAvailable: 'Evidence remains readable with its recorded freshness.',
  evidenceUnavailable: 'Evidence sheet unavailable for this state.',
  coverageIncomplete: 'Critical coverage is incomplete. Missing categories stay unresolved.',
  approvalUnavailable: 'Approval unavailable until the workspace validates it again.',
  openPack: 'Open application pack',
  heading: 'Workspace state',
} as const;
