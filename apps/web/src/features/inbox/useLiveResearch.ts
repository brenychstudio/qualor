import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, getLiveRunStatus, startLiveRun } from '../../api/client';
import type { LiveRunAccepted, LiveRunStatus } from '../../generated/domain';

const ACTIVE_RUN_KEY = 'qualor.activeLiveRunId';
const MAX_NETWORK_RETRIES = 3;
const DEFAULT_MAX_POLL_ATTEMPTS = 960;
const TERMINAL = new Set<LiveRunStatus['status']>(['COMPLETED', 'FAILED', 'BUDGET_STOPPED']);

type PresentedStatus = LiveRunStatus | Required<Pick<LiveRunAccepted, 'run_id' | 'status'>>;

function recoverRunId() {
  try {
    const value = sessionStorage.getItem(ACTIVE_RUN_KEY);
    return value && value.length <= 128 ? value : null;
  } catch {
    return null;
  }
}

function storeRunId(value: string | null) {
  try {
    if (value) sessionStorage.setItem(ACTIVE_RUN_KEY, value);
    else sessionStorage.removeItem(ACTIVE_RUN_KEY);
  } catch {
    // Recovery is useful but never required for execution authority.
  }
}

export function useLiveResearch({
  onOpportunityCreated,
  pollIntervalMs = 1250,
  maxPollAttempts = DEFAULT_MAX_POLL_ATTEMPTS,
}: {
  onOpportunityCreated: () => void;
  pollIntervalMs?: number;
  maxPollAttempts?: number;
}) {
  const navigate = useNavigate();
  const navigateTo = useRef(navigate);
  const completed = useRef(onOpportunityCreated);
  const submitLock = useRef(false);
  const [runId, setRunId] = useState(recoverRunId);
  const [status, setStatus] = useState<PresentedStatus | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [connectionUnavailable, setConnectionUnavailable] = useState(false);
  completed.current = onOpportunityCreated;
  navigateTo.current = navigate;

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let networkFailures = 0;
    let pollAttempts = 0;

    const poll = async () => {
      try {
        pollAttempts += 1;
        const next = await getLiveRunStatus(runId, controller.signal);
        if (controller.signal.aborted) return;
        networkFailures = 0;
        setConnectionUnavailable(false);
        if (next.status === 'COMPLETED' && !next.opportunity_id) {
          setStatus({ ...next, status: 'FAILED', error_code: 'LIVE_RUN_INCOMPLETE' });
          storeRunId(null);
          setRunId(null);
          return;
        }
        setStatus(next);
        if (TERMINAL.has(next.status)) {
          storeRunId(null);
          setRunId(null);
          if (next.status === 'COMPLETED' && next.opportunity_id) {
            completed.current();
            navigateTo.current(`/inbox/${encodeURIComponent(next.opportunity_id)}`);
          }
          return;
        }
        if (pollAttempts >= maxPollAttempts) {
          setConnectionUnavailable(true);
          return;
        }
        timer = setTimeout(poll, pollIntervalMs);
      } catch (reason) {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError
          && reason.code === 'LIVE_RUN_UNAVAILABLE'
          && reason.status === 404) {
          storeRunId(null);
          setRunId(null);
          setStatus(null);
          setConnectionUnavailable(true);
          return;
        }
        if (pollAttempts >= maxPollAttempts) {
          setConnectionUnavailable(true);
          return;
        }
        networkFailures += 1;
        if (networkFailures <= MAX_NETWORK_RETRIES) timer = setTimeout(poll, pollIntervalMs);
        else setConnectionUnavailable(true);
      }
    };
    void poll();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [maxPollAttempts, pollIntervalMs, runId]);

  const start = useCallback(async (officialUrl: string) => {
    if (submitLock.current || runId) return false;
    submitLock.current = true;
    setSubmitting(true);
    setError(null);
    setConnectionUnavailable(false);
    try {
      const accepted = await startLiveRun(officialUrl);
      const acceptedStatus: PresentedStatus = { run_id: accepted.run_id, status: 'STARTING' };
      setStatus(acceptedStatus);
      storeRunId(accepted.run_id);
      setRunId(accepted.run_id);
      return true;
    } catch (reason) {
      setError(reason instanceof ApiError ? reason : new ApiError('INTERNAL_LIVE_RUN_FAILURE'));
      return false;
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  }, [runId]);

  const reset = useCallback(() => {
    if (runId || submitting) return;
    setStatus(null);
    setError(null);
    setConnectionUnavailable(false);
  }, [runId, submitting]);

  return {
    status,
    submitting,
    error,
    connectionUnavailable,
    start,
    reset,
    active: submitting || Boolean(runId),
  };
}
