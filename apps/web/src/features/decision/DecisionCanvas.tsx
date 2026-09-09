import type {
  DeadlineView,
  EffortEstimate,
  OpportunityWorkspaceResponse,
  Recommendation,
} from '../../generated/domain';
import { DecisionTrace } from '../../layout/DecisionTrace';
import { DECISION_COPY, PRIMARY_CTA_LABELS, RECOMMENDATION_LABELS } from './decision-copy';

const incompleteRuns = new Set(['CREATED', 'RUNNING', 'PARTIAL', 'FAILED', 'CANCELLED', 'BUDGET_STOPPED']);

function humanize(value: string) {
  return value.toLowerCase().replaceAll('_', ' ').replace(/(^|\s)\S/g, letter => letter.toUpperCase());
}

function factText(value: string) {
  return value.replaceAll('_', ' ');
}

function effortText(effort: EffortEstimate | null) {
  if (effort?.min_total == null || effort.max_total == null) return DECISION_COPY.unavailableFact;
  return effort.min_total === effort.max_total ? `${effort.min_total} h` : `${effort.min_total}\u2013${effort.max_total} h`;
}

const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function calendarDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/.exec(value);
  if (!match) return null;
  const [, year, month, day] = match;
  const instant = new Date(`${year}-${month}-${day}T00:00:00Z`);
  if (Number.isNaN(instant.valueOf())
    || instant.getUTCFullYear() !== Number(year)
    || instant.getUTCMonth() + 1 !== Number(month)
    || instant.getUTCDate() !== Number(day)) return null;
  return { key: `${year}-${month}-${day}`, text: `${day} ${monthNames[Number(month) - 1]} ${year}` };
}

function deadlineText(deadline: DeadlineView) {
  if (deadline.timezone_status === 'UNKNOWN') {
    return { date: DECISION_COPY.unavailableFact, detail: DECISION_COPY.unavailableDeadline, dateTime: undefined };
  }
  if (deadline.timezone_status === 'CALENDAR_DATE_ONLY') {
    const date = deadline.values.map(calendarDate).filter((value): value is NonNullable<typeof value> => value != null).sort((left, right) => left.key.localeCompare(right.key))[0];
    if (!date) return { date: DECISION_COPY.unavailableFact, detail: DECISION_COPY.unavailableDeadline, dateTime: undefined };
    return { date: date.text, detail: DECISION_COPY.dateOnlyDeadline, dateTime: date.key };
  }
  const earliest = deadline.values
    .filter(value => /T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value))
    .map(value => ({ value, instant: new Date(value) }))
    .filter(({ instant }) => !Number.isNaN(instant.valueOf()))
    .sort((left, right) => left.instant.valueOf() - right.instant.valueOf())[0];
  if (!earliest) return { date: DECISION_COPY.unavailableFact, detail: DECISION_COPY.unavailableDeadline, dateTime: undefined };
  const { instant, value } = earliest;
  const monthName = monthNames[instant.getUTCMonth()];
  return {
    date: `${String(instant.getUTCDate()).padStart(2, '0')} ${monthName} ${instant.getUTCFullYear()}`,
    detail: `${String(instant.getUTCHours()).padStart(2, '0')}:${String(instant.getUTCMinutes()).padStart(2, '0')} UTC`,
    dateTime: value,
  };
}

function rewardText(workspace: OpportunityWorkspaceResponse) {
  const kinds = [...new Set(workspace.rewards.map(reward => humanize(reward.kind)))];
  return kinds.length ? kinds.join(' · ') : 'Unresolved';
}

function SignalIcon({ kind }: { kind: 'fit' | 'eligibility' | 'feasibility' | 'readiness' }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">{kind === 'fit' ? <><circle cx="10" cy="14" r="7" /><circle cx="10" cy="14" r="3" /><path d="m10 14 10-10m-5 0h5v5" /></> : kind === 'eligibility' ? <><path d="M6 2h8l4 4v16H6zM14 2v5h4M9 12h6M9 16h6" /></> : kind === 'feasibility' ? <><path d="m12 3 10 5-10 5L2 8zm-10 9 10 5 10-5M2 16l10 5 10-5" /></> : <><circle cx="12" cy="7" r="4" /><path d="M5 22v-4a7 7 0 0 1 14 0v4M2 22h20" /></>}</svg>;
}

function primaryActionFor(workspace: OpportunityWorkspaceResponse) {
  const recommendation = workspace.decision.recommendation;
  if (!recommendation || workspace.run_state == null || incompleteRuns.has(workspace.run_state)) return null;
  if ((recommendation === 'APPLY' || recommendation === 'PREPARE') && !workspace.decision.primary_action.available) return null;
  return PRIMARY_CTA_LABELS[recommendation];
}

export function DecisionCanvas({ workspace, onPrimaryAction, approvalOpen = false }: {
  workspace: OpportunityWorkspaceResponse;
  onPrimaryAction?: (recommendation: Recommendation) => void;
  approvalOpen?: boolean;
}) {
  const { decision } = workspace;
  const recommendation = decision.recommendation;
  const recommendationLabel = recommendation ? RECOMMENDATION_LABELS[recommendation] : DECISION_COPY.unresolvedRecommendation;
  const deadline = deadlineText(decision.deadline);
  const primaryAction = primaryActionFor(workspace);
  const readiness = decision.readiness;
  const readinessCount = readiness ? `${readiness.gaps.length} ${readiness.gaps.length === 1 ? 'gap' : 'gaps'}` : DECISION_COPY.unavailableFact;
  const decisionClass = recommendation?.toLowerCase() ?? 'unknown';
  const actionLimitation = !decision.primary_action.available && decision.primary_action.reason !== 'DECISION_NOT_ACTIONABLE' ? decision.primary_action.reason : null;
  return <section className={`decision-composition decision-${decisionClass}`} aria-labelledby="opportunity-title">
    <div className="opportunity-heading">
      <h2 id="opportunity-title">{workspace.program_name}</h2>
      <p className="opportunity-source">{workspace.organizer} · {factText(workspace.presentation_state)}</p>
    </div>
    <dl className="opportunity-metadata">
      <div><dt>Edition</dt><dd>{workspace.edition}</dd></div>
      <div><dt>Reward</dt><dd>{rewardText(workspace)}</dd></div>
      <div role="group" aria-label="Deadline"><dt>Deadline · {decision.deadline.timezone_status}</dt><dd>{deadline.dateTime ? <time dateTime={deadline.dateTime}>{deadline.date}</time> : deadline.date}<small>{deadline.detail}</small>{decision.primary_action.reason === 'DEADLINE_PASSED' && <small>Passed</small>}</dd></div>
      <div><dt>Freshness</dt><dd>{workspace.freshness}</dd></div>
    </dl>
    <div className="section-rule"><h3>Decision field</h3></div>
    <div className="decision-signature">
      <dl className="signal-lanes" role="group" aria-label="Decision signals">
        <div className="signal-lane"><span className="signal-icon"><SignalIcon kind="fit" /></span><div className="signal-meaning"><dt>Best project</dt><span>{decision.best_project ? 'Authoritative project fit' : 'Project fit unresolved'}</span></div><dd><strong className="signal-state">{decision.best_project?.name ?? DECISION_COPY.unresolvedProject}</strong><span className="signal-rule" aria-hidden="true" /></dd></div>
        <div className="signal-lane"><span className="signal-icon"><SignalIcon kind="eligibility" /></span><div className="signal-meaning"><dt>Eligibility</dt><span>{decision.eligibility ? 'Deterministic gate' : 'Eligibility unresolved'}</span></div><dd><strong className="signal-state">{decision.eligibility ? factText(decision.eligibility) : DECISION_COPY.unavailableFact}</strong><span className="signal-rule" aria-hidden="true" /></dd></div>
        <div className="signal-lane"><span className="signal-icon"><SignalIcon kind="feasibility" /></span><div className="signal-meaning"><dt>Effort</dt><span>{decision.effort ? 'Preparation estimate' : 'Effort unavailable'}</span></div><dd><strong>{effortText(decision.effort)}</strong><span className="signal-rule" aria-hidden="true" /></dd></div>
        <div role="group" aria-label="Readiness assessment" className="signal-lane signal-lane--readiness"><span className="signal-icon"><SignalIcon kind="readiness" /></span><div className="signal-meaning"><dt>Readiness</dt><span>{readiness ? factText(readiness.state) : 'Readiness unavailable'}</span></div><dd><strong>{readinessCount}</strong><span className="signal-rule" aria-hidden="true" /></dd></div>
      </dl>
      <svg className="decision-convergence" viewBox="0 0 1000 300" preserveAspectRatio="none" aria-hidden="true"><path d="M480 34 C570 34 565 150 686 150" /><path d="M480 111 C570 111 590 150 686 150" /><path d="M480 189 C570 189 590 150 686 150" /><path className="convergence-warm" d="M480 266 C570 266 565 150 686 150" /><path d="M686 150H692" /><circle cx="690" cy="150" r="3" /></svg>
      <svg className="mobile-convergence" viewBox="0 0 350 317" preserveAspectRatio="none" fill="none" aria-hidden="true"><path d="M329 31H349V285H175V317M329 102H349M329 173H349M329 244H349" /></svg>
      <section className="recommendation-surface" aria-label="Recommendation">
        <span className="section-index">Recommendation</span>
        <h1>{recommendationLabel}</h1>
        <span className="recommendation-rule" aria-hidden="true" />
        <p>{decision.summary ?? DECISION_COPY.unresolvedReason}</p>
        <div className="recommendation-strategy" role="group" aria-label="Strategy priority"><span className="section-index">Strategy priority</span><div>{decision.strategy.score == null ? <span className="strategy-unavailable">{DECISION_COPY.unavailableStrategy}</span> : <><strong>{decision.strategy.score}</strong><span>/ 100</span></>}</div><p className="strategy-boundary">Strategy is prioritization.</p></div>
      </section>
    </div>
    <p className="decision-semantics">Strategy is prioritization, not probability of winning.</p>
    <p className="decision-operational" aria-label="Current decision state"><span>Recommendation: {recommendationLabel}</span><span>Presentation state: {factText(workspace.presentation_state)}</span><span>Run state: {workspace.run_state ? factText(workspace.run_state) : 'Unavailable'}</span><span>Research mode: {workspace.mode ?? 'Unavailable'}</span><span>Freshness: {workspace.freshness}</span></p>
    {(decision.primary_blocker || decision.missing_information.length > 0 || actionLimitation) && <p className="decision-limitations">{decision.primary_blocker && <span>Primary blocker: {factText(decision.primary_blocker.toLowerCase())}</span>}{decision.missing_information.length > 0 && <span>Missing information: {decision.missing_information.map(item => factText(item.toLowerCase())).join(', ')}</span>}{actionLimitation && <span>Action state: {factText(actionLimitation)}</span>}</p>}
    <div className="section-rule trace-heading"><h3>Decision trace</h3></div>
    <DecisionTrace presentationState={workspace.presentation_state} runState={workspace.run_state} hasDecision={recommendation != null} actionAvailable={decision.primary_action.available} />
    <p className="human-boundary">Human boundary / {decision.primary_action.available ? 'approval available' : 'approval not available'}</p>
    {primaryAction && recommendation && <div className="decision-primary-action-row"><button type="button" className="primary-action" data-primary-action disabled={!onPrimaryAction} aria-expanded={recommendation === 'APPLY' || recommendation === 'PREPARE' ? approvalOpen : undefined} aria-describedby={!onPrimaryAction ? 'decision-action-unavailable' : undefined} onClick={onPrimaryAction ? () => onPrimaryAction(recommendation) : undefined}>{primaryAction}<span aria-hidden="true">↗</span></button>{!onPrimaryAction && <span id="decision-action-unavailable" className="visually-hidden">Action execution is not available in this workspace.</span>}</div>}
  </section>;
}
