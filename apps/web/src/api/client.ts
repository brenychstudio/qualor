import type { ProductError } from '../generated/domain';

type ErrorCode = ProductError['code'] | 'LOCAL_DISCONNECTED';
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
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const segments = path.slice(1).split('/');
  if (!path.startsWith('/') || segments.some(segment => {
    if (!/^(?:[a-zA-Z0-9_.!~*'()-]|%[0-9a-fA-F]{2})+$/.test(segment)) return true;
    try { return /^\.{1,2}$|[/\\\u0000-\u001f]/.test(decodeURIComponent(segment)); }
    catch { return true; }
  })) throw new ApiError('INVALID_REQUEST');
  const method = options.method ?? 'GET';
  if (method !== 'GET' && !options.actionToken) throw new ApiError('ACTION_FORBIDDEN', 403);
  const headers = new Headers({ Accept: 'application/json' });
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');
  if (method !== 'GET') headers.set('X-Qualor-Action-Token', options.actionToken!);
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
