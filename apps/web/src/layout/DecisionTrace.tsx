import type { InboxPresentationState, RunState } from '../generated/domain';

interface DecisionTraceProps {
  evaluated?: boolean;
  discoveryRecorded?: boolean;
  presentationState?: InboxPresentationState;
  runState?: RunState | null;
  hasDecision?: boolean;
  actionAvailable?: boolean;
}

function currentPhases({ runState, hasDecision, actionAvailable }: DecisionTraceProps) {
  if (runState == null) return [
    ['Discover', 'Recorded'], ['Verify', 'Unavailable'], ['Qualify', 'Unavailable'],
    ['Decide', 'Unavailable'], ['Approve', 'Not requested'],
  ];
  if (runState === 'CREATED' || runState === 'RUNNING') return [
    ['Discover', 'Recorded'], ['Verify', runState], ['Qualify', 'Awaiting current run'],
    ['Decide', hasDecision ? 'Prior decision retained' : 'Unavailable'], ['Approve', 'Unavailable'],
  ];
  if (runState !== 'COMPLETED') return [
    ['Discover', 'Recorded'], ['Verify', runState], ['Qualify', 'Current run incomplete'],
    ['Decide', hasDecision ? 'Prior decision retained' : 'Unresolved'], ['Approve', 'Unavailable'],
  ];
  return [
    ['Discover', 'Recorded'], ['Verify', 'Unavailable'],
    ['Qualify', hasDecision ? 'Recorded' : 'Unresolved'],
    ['Decide', hasDecision ? 'Recorded' : 'Unresolved'],
    ['Approve', actionAvailable ? 'Awaiting human' : 'Not available'],
  ];
}

// Presentation only. Callers supply current server truth; absence is never completion.
export function DecisionTrace(props: DecisionTraceProps) {
  const phases = props.presentationState === undefined ? [
    ['Discover', props.discoveryRecorded ? 'Fixture recorded' : 'Unavailable'], ['Verify', 'Unavailable'],
    ['Qualify', props.evaluated ? 'Fixture evaluated' : 'Unavailable'],
    ['Decide', props.evaluated ? 'Fixture evaluated' : 'Unavailable'], ['Approve', 'Not requested'],
  ] : currentPhases(props);
  return <ol className="decision-trace" aria-label="Decision trace">{phases.map(([phase, state]) => <li key={phase} className={['Recorded', 'Fixture recorded', 'Fixture evaluated'].includes(state) ? 'trace-evaluated' : ''}><span className="trace-phase">{phase}</span><span className="trace-mark" aria-hidden="true" /><span className="trace-state">{state}</span></li>)}</ol>;
}
