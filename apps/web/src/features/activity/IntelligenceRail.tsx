import { useEffect, useState } from 'react';
import { ApiError, apiRequest } from '../../api/client';
import type { ActivityResponse } from '../../generated/domain';
import { latestRun, presentEvent, presentRun } from './activity-presenter';

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
  return <ol className="event-axis" aria-label={label}>
    {activity.events.map(presentEvent).map(event => <li key={event.key}>
      <time dateTime={event.instant}>{event.time}</time>
      <span>{event.phase ? `${event.phase} · ` : ''}{event.label}{event.detail ? ` · ${event.detail}` : ''}</span>
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
      <p className="runtime-mode"><span className="workspace-label">{current.mode}</span>{current.disconnected && <span className="state-stale"> DISCONNECTED</span>}</p>
      <dl className="context-facts">
        <div><dt>Official sources</dt><dd>{current.officialSources}</dd></div>
        <div><dt>Verified claims</dt><dd>{current.verifiedClaims}</dd></div>
        <div><dt>Recorded state</dt><dd>{current.state}</dd></div>
      </dl>
      <p className="quiet">{current.usage}{current.reservedCost ? ` · ${current.reservedCost} reserved` : ''}</p>
      {current.terminationReason && <p className="quiet">{current.terminationReason}</p>}
    </> : null}
    {activity.events.length === 0
      ? <p className="quiet">No recorded activity.</p>
      : <ActivityTimeline activity={activity} label="Recorded activity" />}
  </section>;
}
