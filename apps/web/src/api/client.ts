import type {
  ApprovalConfirmRequest,
  ApprovalRequest,
  ApprovalView,
  DraftPackView,
  LiveRunAccepted,
  LiveRunError,
  LiveRunRequest,
  LiveRunStatus,
  ProductError,
} from '../generated/domain';

type ErrorCode = ProductError['code'] | LiveRunError['code'] | 'LOCAL_DISCONNECTED';
const messages: Record<ErrorCode, string | null> = {
  ACTION_MISMATCH: null,
  ACTOR_MISMATCH: null,
  AMBIGUOUS_EVIDENCE_REFERENCE: null,
  AMBIGUOUS_SOURCE_RUN: null,
  BUDGET_STOPPED: null,
  CHANGE_REVOKED: null,
  CONSUMED: null,
  CONSUMPTION_WITHOUT_JOB_INTENT: null,
  DEADLINE_MISMATCH: null,
  DEADLINE_PASSED: null,
  DEADLINE_UNKNOWN: null,
  DECISION_NOT_ACTIONABLE: null,
  DRAFT_INPUT_LIMIT: null,
  DRAFT_STATE_INCONSISTENT: null,
  EVIDENCE_CHANGED: null,
  EVIDENCE_NOT_ACTIONABLE: null,
  EVIDENCE_REFERENCE_UNAVAILABLE: null,
  EXPIRED: null,
  GRAPH_MISMATCH: null,
  IDEMPOTENCY_CONFLICT: null,
  IDENTITY_MISMATCH: null,
  INTERNAL_ERROR: null,
  MODE_MISMATCH: null,
  PENDING: null,
  POLICY_MISMATCH: null,
  READ_LIMIT_EXCEEDED: null,
  REVIEW_REQUIRED: null,
  REVOKED: null,
  SNAPSHOT_UNAVAILABLE: null,
  SOURCE_RUN_MISMATCH: null,
  SOURCE_RUN_NOT_COMPLETED: null,
  STALE: null,
  TIME_INVALID: null,
  VALID: null,

  VERSION_MISMATCH: 'A newer version exists. Your edits are still here. Review the latest saved record before trying again.',
  INVALID_REQUEST: 'Check the entered values. The controller could not accept this update.',
  ACTION_FORBIDDEN: 'Editing is unavailable in this session. Reopen the portfolio to reconnect.',
  PROJECT_LIMIT: 'This portfolio already contains five projects.',
  LOCAL_DISCONNECTED: 'Local controller disconnected',
  NOT_FOUND: 'This record is unavailable in the local workspace.',
  LIVE_RUN_BUSY: 'Another research run is already active.',
  LIVE_RUN_LIMIT_REACHED: 'The hosted research limit has been reached.',
  LIVE_RUN_COOLDOWN: 'Research is temporarily unavailable. Try again shortly.',
  LIVE_RUN_UNAVAILABLE: 'Live research is unavailable.',
  LIVE_PERSISTENCE_FAILED: 'Research could not complete.',
  LIVE_PROVIDER_FAILED: 'Research could not complete.',
  INTERNAL_LIVE_RUN_FAILURE: 'Research could not complete.',
  LIVE_RUN_INCOMPLETE: 'Research could not complete.',
};
export class ApiError extends Error {
  constructor(public readonly code: ErrorCode, public readonly status = 0) {
    super(messages[code] ?? 'The local controller could not complete this request. Your edits are preserved.');
    this.name = 'ApiError';
  }
}
interface RequestOptions {
  method?: 'GET' | 'PUT' | 'POST';
  body?: unknown;
  actionToken?: string | null;
  signal?: AbortSignal;
}
async function requestJson<T>(path: string, options: RequestOptions, actionRequired: boolean): Promise<T> {
  const segments = path.slice(1).split('/');
  if (!path.startsWith('/') || segments.some(segment => {
    if (!/^(?:[a-zA-Z0-9_.!~*'()-]|%[0-9a-fA-F]{2})+$/.test(segment)) return true;
    try { return /^\.{1,2}$|[/\\\u0000-\u001f]/.test(decodeURIComponent(segment)); }
    catch { return true; }
  })) throw new ApiError('INVALID_REQUEST');
  const method = options.method ?? 'GET';
  if (method !== 'GET' && actionRequired && !options.actionToken) throw new ApiError('ACTION_FORBIDDEN', 403);
  const headers = new Headers({ Accept: 'application/json' });
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');
  if (method !== 'GET' && options.actionToken) headers.set('X-Qualor-Action-Token', options.actionToken);
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method, headers, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      signal: options.signal, body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError('LOCAL_DISCONNECTED');
  }
  if (!response.ok) {
    let code: ErrorCode = response.status === 403 ? 'ACTION_FORBIDDEN' : response.status === 422 ? 'INVALID_REQUEST' : 'INTERNAL_ERROR';
    try {
      const data: unknown = await response.json();
      if (data && typeof data === 'object' && 'code' in data && typeof data.code === 'string' && Object.hasOwn(messages, data.code)) code = data.code as ErrorCode;
    } catch { /* Non-JSON upstream failures never expose a raw response. */ }
    throw new ApiError(code, response.status);
  }
  try { return await response.json() as T; }
  catch { throw new ApiError('INTERNAL_ERROR', response.status); }
}

export function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return requestJson<T>(path, options, true);
}

/** Hosted origin trust is injected by the same-origin edge; its proxy secret stays server-side. */
export function startLiveRun(officialUrl: string, signal?: AbortSignal) {
  const body: LiveRunRequest = { official_url: officialUrl };
  return requestJson<LiveRunAccepted>('/live-runs', { method: 'POST', body, signal }, false);
}

export function getLiveRunStatus(runId: string, signal?: AbortSignal) {
  return requestJson<LiveRunStatus>(`/live-runs/${encodeURIComponent(runId)}`, { signal }, false);
}

/**
 * The two protected approval calls. Both reuse the single apiRequest transport, so the
 * process-local action token travels only in its header and never in a URL or storage.
 */
export function requestApproval(opportunityId: string, body: ApprovalRequest, actionToken: string, signal?: AbortSignal) {
  return apiRequest<ApprovalView>(`/opportunities/${encodeURIComponent(opportunityId)}/approvals`, {
    method: 'POST', actionToken, body, signal,
  });
}

/**
 * `idempotencyKey` identifies one human approval intent. Callers create it once for that
 * intent and pass the same value when retrying, so a retry can never approve twice.
 */
export function confirmApproval(approvalId: string, expectedVersions: ApprovalRequest, idempotencyKey: string, actionToken: string, signal?: AbortSignal) {
  const body: ApprovalConfirmRequest = { expected_versions: expectedVersions, idempotency_key: idempotencyKey };
  return apiRequest<ApprovalView>(`/approvals/${encodeURIComponent(approvalId)}/confirm`, {
    method: 'POST', actionToken, body, signal,
  });
}

/** The Draft Pack is immutable, so its only client operation is an ordinary read. */
export function fetchDraftPack(packId: string, signal?: AbortSignal) {
  return apiRequest<DraftPackView>(`/draft-packs/${encodeURIComponent(packId)}`, { signal });
}
