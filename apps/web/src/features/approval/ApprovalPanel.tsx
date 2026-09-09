import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, apiRequest, confirmApproval, requestApproval } from '../../api/client';
import type {
  ApprovalView,
  OpportunityWorkspaceResponse,
  Recommendation,
  SessionView,
} from '../../generated/domain';
import { APPROVAL_COPY, REASON_COPY, STATE_COPY, failureCopy } from './approval-copy';

/**
 * The human consequential-action checkpoint.
 *
 * Every judgement shown here is the server's: state, reason, expiry and actionability all
 * come from ApprovalView. This component decides nothing about validity — it presents what
 * the workspace recorded and asks one person for one explicit confirmation.
 */
export function ApprovalPanel({ workspace, recommendation, onClose }: {
  workspace: OpportunityWorkspaceResponse;
  recommendation: Extract<Recommendation, 'APPLY' | 'PREPARE'>;
  onClose: () => void;
}) {
  const snapshot = workspace.decision.primary_action.approval_request;
  const [session, setSession] = useState<SessionView | null>(null);
  const [approval, setApproval] = useState<ApprovalView | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [working, setWorking] = useState(true);
  const region = useRef<HTMLElement>(null);
  // One key per human intent, created once and reused for every retry of that same intent.
  const intentKey = useRef<string>('');
  // A ref, not state: two activations in one tick must never both pass the guard.
  const inFlight = useRef(false);

  useEffect(() => { region.current?.focus(); }, []);

  useEffect(() => {
    const controller = new AbortController();
    if (!snapshot) { setWorking(false); setFailure(failureCopy('DECISION_NOT_ACTIONABLE')); return; }
    apiRequest<SessionView>('/session', { signal: controller.signal })
      .then(current => {
        if (controller.signal.aborted) return null;
        setSession(current);
        if (current.read_only || !current.action_token) return null;
        return requestApproval(workspace.opportunity_id, snapshot, current.action_token, controller.signal);
      })
      .then(view => { if (!controller.signal.aborted && view) setApproval(view); })
      .catch(error => { if (!controller.signal.aborted) setFailure(explain(error)); })
      .finally(() => { if (!controller.signal.aborted) setWorking(false); });
    return () => controller.abort();
  }, [workspace.opportunity_id, snapshot]);

  const confirm = useCallback(async () => {
    if (inFlight.current || !approval || !snapshot || !session?.action_token) return;
    inFlight.current = true;
    if (!intentKey.current) intentKey.current = crypto.randomUUID();
    setWorking(true);
    setFailure(null);
    try {
      setApproval(await confirmApproval(approval.id, snapshot, intentKey.current, session.action_token));
    } catch (error) {
      setFailure(explain(error));
    } finally {
      inFlight.current = false;
      setWorking(false);
    }
  }, [approval, snapshot, session]);

  const readOnly = !!session && (session.read_only || !session.action_token);
  const state = approval?.state ?? 'NOT_REVIEWED';
  const confirmable = !!approval && approval.state === 'PENDING_APPROVAL' && approval.actionable && !readOnly;

  return <section
    ref={region}
    tabIndex={-1}
    className="approval-checkpoint"
    aria-label="Human approval"
    onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); } }}
  >
    <div className="approval-heading">
      <span className="section-index">{APPROVAL_COPY.heading}</span>
      <strong className="approval-state">{state}</strong>
    </div>
    <p className="approval-statement">{STATE_COPY[state]}</p>
    <p className="approval-statement">{APPROVAL_COPY.actionSummary}</p>

    <dl className="approval-bindings">
      <div><dt>Approved action</dt><dd>{approval?.action ?? snapshot?.action ?? 'GENERATE_DRAFT_PACK'}</dd></div>
      <div><dt>Actor</dt><dd>{approval?.actor_id ?? snapshot?.founder_profile_id ?? 'Unresolved'}</dd></div>
      <div><dt>Opportunity</dt><dd>{workspace.program_name}<small>Opportunity version {snapshot?.opportunity_version ?? workspace.version}</small></dd></div>
      <div><dt>Project</dt><dd>{workspace.decision.best_project?.name ?? 'Unresolved'}<small>Project version {snapshot?.project_version ?? 'unrecorded'}</small></dd></div>
      <div><dt>Recommendation</dt><dd>{recommendation}</dd></div>
      <div><dt>Expires</dt><dd>{approval ? <time dateTime={approval.expires_at}>{approval.expires_at}</time> : 'Unrecorded'}</dd></div>
    </dl>

    {approval && approval.reason !== 'VALID' && approval.reason !== 'PENDING' &&
      <p className="approval-statement approval-reason">{REASON_COPY[approval.reason]}</p>}

    <p className="approval-boundary">{APPROVAL_COPY.boundary}</p>
    <p className="approval-boundary">{APPROVAL_COPY.notGuaranteed}</p>

    {failure && <p className="approval-failure" role="alert">{failure}</p>}
    {readOnly && <p className="approval-statement" role="status">{APPROVAL_COPY.readOnly}</p>}
    {working && !failure && <p className="quiet" role="status">{approval ? APPROVAL_COPY.working : APPROVAL_COPY.requesting}</p>}

    {approval?.state === 'DRAFT_READY' && approval.pack_id &&
      <Link className="inline-link" to={`/draft-packs/${approval.pack_id}`}>{APPROVAL_COPY.openPack} <span aria-hidden="true">↗</span></Link>}

    <div className="approval-controls">
      {(confirmable || (failure && approval?.state === 'PENDING_APPROVAL')) &&
        <button type="button" className="primary-action" disabled={working} onClick={confirm}>
          {APPROVAL_COPY.confirm}
        </button>}
      <button type="button" className="text-button" onClick={onClose}>{APPROVAL_COPY.cancel}</button>
    </div>
  </section>;
}

function explain(error: unknown): string {
  return error instanceof ApiError ? failureCopy(error.code) : APPROVAL_COPY.unavailable;
}
