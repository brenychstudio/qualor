import { presentRun } from './activity-presenter';
import { ActivityTimeline, useActivity } from './IntelligenceRail';

/** Full recorded history for the /activity route. Runs and events are the only source. */
export function ActivityHistory() {
  const { activity, error } = useActivity();
  if (error) return <section className="structural-state">
    <span className="eyebrow">Activity</span>
    <h1>Recorded activity unavailable</h1>
    <p role="status">Recorded activity is unavailable. {error}</p>
  </section>;
  if (!activity) return <section className="structural-state" aria-live="polite">
    <span className="eyebrow">Activity</span><h1>Recorded activity</h1><p>Reading recorded run history…</p>
  </section>;

  return <section className="structural-state">
    <span className="eyebrow">Activity</span>
    <h1>Recorded activity</h1>
    {activity.runs.length === 0
      ? <p>No run has been recorded in this workspace. Nothing is inferred from an absent run.</p>
      : <ul className="activity-runs" aria-label="Recorded runs">
        {activity.runs.map(presentRun).map(run => <li key={run.id}>
          <span className="section-index">{run.id}</span>
          <span className="workspace-label">{run.mode}</span>
          <strong>{run.state}</strong>
          {run.disconnected && <span className="state-stale">DISCONNECTED</span>}
          <span className="quiet">{run.usage}{run.reservedCost ? ` · ${run.reservedCost} reserved` : ''}</span>
          {run.terminationReason && <span className="quiet">{run.terminationReason}</span>}
        </li>)}
      </ul>}
    <ActivityTimeline activity={activity} label="Recorded run events" />
  </section>;
}
