import { useEffect, useState } from 'react';
import { ApiError, apiRequest } from '../../api/client';
import type { ActivityResponse } from '../../generated/domain';
import { latestRun, presentEvents, presentRun } from './activity-presenter';

/** Structured operational telemetry read from persisted run history. Never a chat. */
export function useActivity() {
  const [activity, setActivity] = useState<ActivityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ActivityResponse>('/runs', { signal: controller.signal })
      .then(value => {
        if (controller.signal.aborted) return;
        // An unrecognised payload is unavailable history, never inferred activity.
        if (!value || !Array.isArray(value.runs) || !Array.isArray(value.events)) {
          throw new ApiError('INTERNAL_ERROR');
        }
        setActivity(value);
      })
      .catch(readError => {
        if (controller.signal.aborted) return;
        setError(readError instanceof ApiError ? readError.message : 'Recorded activity is unavailable.');
      });
    return () => controller.abort();
  }, []);
  return { activity, error };
}

/** Renders nothing when no event was recorded; callers own the honest empty copy. */
export function ActivityTimeline({ activity, label }: { activity: ActivityResponse; label: string }) {
  if (activity.events.length === 0) return null;
  // Two children per row, because the wide history renders `.event-axis` as a two-column grid.
  // The recorded position leads, since a seeded run stamps every observation with one instant.
  return <ol className="event-axis" aria-label={label}>
    {presentEvents(activity.events).map(event => <li key={event.key} data-outcome={event.outcome ? 'true' : undefined}>
      <span className="event-stamp"><span className="event-order">{event.order}</span><time dateTime={event.instant}>{event.time}</time></span>
      <span className="event-record">
        <b className="event-title">{event.label}</b>
        {(event.phase || event.detail) && <span className="event-meta">{[event.phase, event.detail].filter(Boolean).join(' · ')}</span>}
      </span>
    </li>)}
  </ol>;
}

export function IntelligenceRail() {
  const { activity, error } = useActivity();
  if (error) return <section className="rail-section" aria-label="Intelligence">
    <h3>Activity</h3><p className="connection-state" role="status">Recorded activity is unavailable. {error}</p>
  </section>;
  if (!activity) return <section className="rail-section" aria-label="Intelligence">
    <h3>Activity</h3><p className="quiet" role="status">Reading recorded activity…</p>
  </section>;

  const run = latestRun(activity.runs);
  const current = run ? presentRun(run) : null;
  return <section className="rail-section fixture-events" aria-label="Intelligence">
    <h3>Activity</h3>
    {current ? <>
      <p className="runtime-mode"><span className="workspace-label">{current.mode}</span><b className="run-state">{current.state}</b>{current.disconnected && <span className="state-stale"> DISCONNECTED</span>}</p>
      {current.terminationCopy && <p className="quiet run-termination" title={current.terminationReason ?? undefined}>{current.terminationCopy}</p>}
    </> : null}
    {activity.events.length === 0
      ? <p className="quiet">No recorded activity.</p>
      : <ActivityTimeline activity={activity} label="Recorded activity" />}
    {/* These four counters are this run's own retrieval work, not the evidence base behind the
        decision: the server derives them from what the run fetched and validated. They are
        scoped explicitly so a recorded fixture run reads as having done no retrieval, rather
        than as a decision with no evidence. Nothing here is borrowed from the evidence sheet. */}
    {current ? <div className="run-metrics" role="group" aria-labelledby="run-metrics-scope">
      <p className="section-index" id="run-metrics-scope">Recorded in this run</p>
      <dl className="context-facts">
        <div><dt>Search calls</dt><dd>{current.searchCalls}</dd></div>
        <div><dt>Documents fetched</dt><dd>{current.fetchedDocuments}</dd></div>
        <div><dt>Official sources</dt><dd>{current.officialSources}</dd></div>
        <div><dt>Claims verified</dt><dd>{current.verifiedClaims}</dd></div>
      </dl>
      {current.noRecordedCalls && <p className="quiet">No retrieval or verification call is recorded for this run.</p>}
      {/* Budget can be reserved by a run that then records no call at all — a live provider that
          disconnects is exactly that. Committed spend is reported either way. */}
      {current.reservedCost && <p className="quiet run-spend">{current.reservedCost} reserved</p>}
    </div> : null}
  </section>;
}
