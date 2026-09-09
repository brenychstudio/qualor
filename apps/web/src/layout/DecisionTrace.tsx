// Presentation only. Callers must supply recorded observations; absence is never completion.
export function DecisionTrace({ evaluated = false, discoveryRecorded = false }: { evaluated?: boolean; discoveryRecorded?: boolean }) {
  const phases = [
    ['Discover', discoveryRecorded ? 'Fixture recorded' : 'Unavailable'], ['Verify', 'Unavailable'],
    ['Qualify', evaluated ? 'Fixture evaluated' : 'Unavailable'],
    ['Decide', evaluated ? 'Fixture evaluated' : 'Unavailable'], ['Approve', 'Not requested'],
  ];
  return <ol className="decision-trace" aria-label="Decision trace">{phases.map(([phase, state]) => <li key={phase} className={state.startsWith('Fixture') ? 'trace-evaluated' : ''}><span className="trace-phase">{phase}</span><span className="trace-mark" aria-hidden="true" /><span className="trace-state">{state}</span></li>)}</ol>;
}
