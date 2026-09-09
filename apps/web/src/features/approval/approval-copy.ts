import type { ApprovalReason, ApprovalState } from '../../generated/domain';

/**
 * Server reason codes translated into English. This map derives no validity of its own:
 * the server decides whether an approval is valid, expired, revoked or consumed, and this
 * only explains the answer it gave. Adding a public reason code without copy fails typecheck.
 */
export const REASON_COPY: Record<ApprovalReason, string> = {
  VALID: 'This approval is valid for the bounded preparation action.',
  NOT_FOUND: 'This approval is no longer available in the local workspace.',
  PENDING: 'This approval is waiting for your explicit confirmation.',
  REVOKED: 'This approval was revoked and can no longer start preparation.',
  EXPIRED: 'This approval expired. Review the decision again to create a current one.',
  CONSUMED: 'This approval has already been used to prepare a draft pack.',
  ACTOR_MISMATCH: 'This approval belongs to a different person and cannot be used here.',
  ACTION_MISMATCH: 'This approval was created for a different action than the one requested.',
  IDENTITY_MISMATCH: 'The approved records no longer match the ones in this workspace.',
  VERSION_MISMATCH: 'A recorded version changed since this approval was created.',
  POLICY_MISMATCH: 'The deterministic policy version changed since this approval was created.',
  GRAPH_MISMATCH: 'The linked opportunity, profile and project records no longer agree.',
  MODE_MISMATCH: 'This approval was recorded in a different research mode.',
  DEADLINE_UNKNOWN: 'No verified deadline is recorded, so preparation stays unavailable.',
  DEADLINE_PASSED: 'The recorded deadline has passed.',
  DEADLINE_MISMATCH: 'The recorded deadline changed since this approval was created.',
  DECISION_NOT_ACTIONABLE: 'This decision is not actionable, so preparation cannot be approved.',
  EVIDENCE_NOT_ACTIONABLE: 'The recorded evidence is not actionable, so preparation stays unavailable.',
  EVIDENCE_CHANGED: 'The supporting evidence changed since this approval was created.',
  IDEMPOTENCY_CONFLICT: 'A different approval intent already used this confirmation key.',
  CHANGE_REVOKED: 'A recorded input changed since this approval was created, so it was revoked.',
  TIME_INVALID: 'The recorded approval time could not be validated.',
  SOURCE_RUN_NOT_COMPLETED: 'The research run behind this decision has not completed.',
  SOURCE_RUN_MISMATCH: 'The research run behind this decision no longer matches the approval.',
  AMBIGUOUS_SOURCE_RUN: 'More than one research run could back this decision, so it stays unresolved.',
};

/** What each server-owned approval state means for the person reading it. */
export const STATE_COPY: Record<ApprovalState, string> = {
  NOT_REVIEWED: 'No approval has been requested for this decision.',
  PENDING_APPROVAL: 'A version-bound approval exists and needs your explicit confirmation.',
  APPROVED_FOR_PREPARATION: 'You approved the bounded preparation action.',
  REVOKED_APPROVAL: 'This approval is no longer valid and cannot start preparation.',
  DRAFT_READY: 'Preparation finished. A draft pack is recorded for your review.',
};

export const APPROVAL_COPY = {
  heading: 'Human approval',
  actionSummary: 'You are approving one bounded action: prepare a draft pack from the recorded decision.',
  boundary:
    'This starts a separate local preparation step. Nothing is submitted externally, no organizer is contacted, and no external form is filled.',
  notGuaranteed: 'Approval does not guarantee eligibility.',
  confirm: 'Confirm approval',
  cancel: 'Cancel',
  working: 'Recording your approval…',
  requesting: 'Reading the version-bound approval…',
  readOnly: 'This is a read-only session, so no approval can be recorded.',
  openPack: 'Open draft pack',
  unavailable: 'The local controller could not complete this approval. Nothing was approved.',
} as const;

/** Transport-level failures are not approval reasons, but still deserve distinct copy. */
const TRANSPORT_COPY: Record<string, string> = {
  ACTION_FORBIDDEN: 'This session can no longer authorise actions. Reopen the workspace and review the decision again.',
  LOCAL_DISCONNECTED: 'The local controller is unreachable. Nothing was approved.',
  INVALID_REQUEST: 'The local controller could not accept this approval request. Nothing was approved.',
  NOT_FOUND: 'This approval is no longer available in the local workspace.',
};

/** Server codes translated to copy. Approval reasons win; transport failures fall back. */
export function failureCopy(code: string): string {
  if (code in REASON_COPY) return REASON_COPY[code as ApprovalReason];
  return TRANSPORT_COPY[code] ?? APPROVAL_COPY.unavailable;
}
