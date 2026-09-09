import { useEffect, useRef, useState } from 'react';
import './decision-optical.css';


import { WorkspaceFrame } from '../layout/WorkspaceShell';
import { DecisionTrace } from '../layout/DecisionTrace';
import { ProfileForm } from '../features/portfolio/ProfileForm';
import type { DecisionFixture, DecisionOutput, EvidenceSheetView, ActivityResponse } from '../generated/domain';
import data from './decision-scenarios.json';


const label = 'DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY';
const scenarios = data.scenarios as unknown as { case_id: string; fixture: DecisionFixture; result: DecisionOutput; evidence: EvidenceSheetView; activity: ActivityResponse }[];
const humanize = (value: string) => value.toLowerCase().replaceAll('_', ' ');
const dateText = (value: string) => new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
const opticalPaths = ['M490 29 C574 29 568 118 686 118', 'M490 96 C570 96 602 118 686 118', 'M490 163 C570 163 602 118 686 118', 'M490 230 C574 230 568 118 686 118', 'M686 118H692'];

function SignalIcon({ kind }: { kind: 'fit' | 'eligibility' | 'feasibility' | 'readiness' }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">{kind === 'fit' ? <><circle cx="10" cy="14" r="7" /><circle cx="10" cy="14" r="3" /><path d="m10 14 10-10m-5 0h5v5" /></> : kind === 'eligibility' ? <><path d="M6 2h8l4 4v16H6zM14 2v5h4M9 12h6M9 16h6" /></> : kind === 'feasibility' ? <><path d="m12 3 10 5-10 5L2 8zm-10 9 10 5 10-5M2 16l10 5 10-5" /></> : <><circle cx="12" cy="7" r="4" /><path d="M5 22v-4a7 7 0 0 1 14 0v4M2 22h20" /></>}</svg>;
}

export function DesignPreview() {
  const [selected, setSelected] = useState(0);
  // FIX1 calibrates one approved frame; other viewport/scenario presentations stay unchanged.
  const [calibrationFrame, setCalibrationFrame] = useState(window.innerWidth === 1440 && window.innerHeight === 810);
  useEffect(() => {
    const resize = () => setCalibrationFrame(window.innerWidth === 1440 && window.innerHeight === 810);
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  const eligibilityProof = useRef<HTMLDivElement>(null);
  const readinessSignal = useRef<HTMLDivElement>(null);
  const { fixture, result, evidence: sheet, activity, case_id } = scenarios[selected];
  const opportunity = fixture.opportunity;
  const project = fixture.projects.find(item => item.project.id === result.best_project_id)?.project;
  const deadline = opportunity.deadlines?.[0];
  const fit = result.strategy?.breakdown.find(item => item.factor === 'product_fit')?.rating;
  const proof = sheet.proofs.find(item => item.category === 'ENTRANT_TYPE');
  const claim = proof && sheet.claims.find(item => item.evidence_refs.includes(proof.evidence_id));
  const view = new URLSearchParams(window.location.search).get('view');
  const opticalPreview = calibrationFrame && selected === 0 && !view;
  const proofContent = <>
    <p className="proof-introduction">{opportunity.program_name} / {case_id}<br />{result.explanation}</p>
    <div className="proof-claim-heading"><span className="section-index">Eligibility / entrant type</span><strong>{claim?.state ?? 'UNKNOWN'}</strong></div>
    <p className="proof-boundary">Deterministic fixture claim. Synthetic source material is not official verification.</p>
    <blockquote className="proof-excerpt">{proof?.excerpt ?? 'No supporting excerpt is available for this claim.'}</blockquote>
    <dl className="proof-metadata"><div><dt>Source</dt><dd>{proof?.domain ?? 'Unavailable'}</dd></div><div><dt>Authority role</dt><dd>Synthetic eligibility fixture</dd></div><div><dt>Source type</dt><dd>{proof?.source_type ?? 'Unavailable'}</dd></div><div><dt>Freshness at evaluation</dt><dd>{proof?.freshness ?? 'UNKNOWN'}</dd></div><div><dt>Retrieved</dt><dd>{proof ? `${dateText(proof.retrieved_at)} · ${proof.retrieved_at.slice(11, 16)} UTC` : 'Unavailable'}</dd></div><div><dt>Evaluated</dt><dd>{dateText(fixture.evaluated_at)} · FIXTURE</dd></div></dl>
    {proof && <p className="proof-source-url">{proof.original_url}</p>}
    <div className="proof-claims"><h3>Qualification record</h3>{sheet.claims.map(item => <div key={item.rule_id}><span>{humanize(item.rule_id.replace(/^r_/, ''))}</span><strong>{item.state}</strong><span>{item.evidence_refs.length} evidence {item.evidence_refs.length === 1 ? 'reference' : 'references'}</span></div>)}</div>
    <p className="proof-boundary">Project facts remain context. They are not official eligibility authority. Approval has not been requested.</p>
  </>;
  return <WorkspaceFrame previewLabel={label} opticalPreview={opticalPreview}
    queue={<><div className="zone-heading"><h2>Opportunity inbox</h2><span>04</span></div><p className="queue-caption">4 fixture scenarios / one test program</p><div className="scenario-queue">{scenarios.map((scenario, index) => <button key={scenario.case_id} className={`opportunity-row${selected === index ? ' opportunity-row--selected' : ''}`} aria-pressed={selected === index} onClick={() => setSelected(index)}><span className="queue-item-index">{scenario.case_id} / SYNTHETIC SCENARIO</span><strong>{scenario.fixture.opportunity.program_name}</strong><span className="queue-organizer">{scenario.fixture.opportunity.organizer}</span><span className="queue-decision-axis"><b>{scenario.result.recommendation}</b><span>{scenario.fixture.opportunity.deadlines?.[0] ? dateText(scenario.fixture.opportunity.deadlines[0]).slice(0, 6).toUpperCase() : 'UNKNOWN'}</span></span></button>)}</div><p className="queue-footnote">Independent evaluator cases.<br />No workspace records loaded.</p></>}
    context={<><section className="rail-section fixture-events"><h3>Recorded activity</h3><div className="event-axis">{activity.events.map(event => <div key={event.sequence}><span>{humanize(event.event_type)}</span><time>{event.occurred_at.slice(11, 16)} UTC</time></div>)}</div><p className="quiet">Synthetic history · {activity.events.length} events</p></section><section className="rail-section rail-runtime"><h3>{result.mode}</h3><p>{dateText(fixture.evaluated_at)}<br />{fixture.evaluated_at.slice(11, 16)} UTC</p><p className="quiet">Source verification unrecorded.<br />Approval not requested.</p></section></>}
    evidenceContent={view ? undefined : proofContent}
    proof={view ? null : <div className="proof-peek">
      <div className="proof-sheet-title"><h2>Evidence plane</h2><p>Synthetic fixture · read only</p></div>
      <div ref={eligibilityProof} tabIndex={-1} className="proof-document-section" role="group" aria-label="Eligibility rule"><span className="proof-document-icon"><SignalIcon kind="eligibility" /></span><div><span className="proof-provenance">Rule / entrant type</span><p>{proof?.excerpt ?? 'Supporting source unavailable.'}</p><small>Synthetic fixture · one eligibility claim</small></div></div>
      <div className="proof-document-section" role="group" aria-label="Source attribution"><span className="proof-document-icon"><SignalIcon kind="eligibility" /></span><div><span className="proof-provenance">{opticalPreview ? 'Document' : 'Source'}</span><p>{proof?.domain ?? 'Unavailable'}</p>{!opticalPreview && <small className="proof-source-address">{proof?.original_url ?? 'Source URL unavailable'}</small>}<small>No official verification</small></div></div>
      <div className="proof-document-section" role="group" aria-label="Profile context"><span className="proof-document-icon"><SignalIcon kind="readiness" /></span><div><span className="proof-provenance">Data</span><p>Team size · {fixture.founder.team_size?.value ?? 'UNKNOWN'}</p><small>Profile context · {fixture.founder.team_size?.evidence_refs?.length ? `${fixture.founder.team_size.evidence_refs?.length} evidence references` : 'no evidence references'}</small><small>{fixture.founder.team_size?.provenance ?? 'UNKNOWN'}</small></div></div>
      <div className="proof-sheet-freshness">{proof?.freshness ?? 'UNKNOWN'} at fixture evaluation<span>{dateText(fixture.evaluated_at)} · {fixture.evaluated_at.slice(11, 16)} UTC</span></div>
    </div>}
  >{view === 'portfolio' ? <section className="portfolio-view"><div className="portfolio-heading"><h1>Portfolio</h1><p>Synthetic context / read-only dossier</p></div><ProfileForm record={fixture.founder} kind="founder" session={null} onSaved={() => {}} />{fixture.projects.map(item => <ProfileForm key={item.project.id} record={item.project} kind="project" session={null} onSaved={() => {}} />)}</section> : view === 'activity' ? <section className="structural-state"><span className="section-index">Fixture history</span><h1>Recorded observations</h1><p>Two seeded events. No live research occurred.</p><div className="event-axis">{activity.events.map(event => <div key={event.sequence}><time>{event.occurred_at.slice(11, 16)}</time><span>{humanize(event.event_type)}</span></div>)}</div></section> : <section className={`decision-composition decision-${result.recommendation.toLowerCase()}`} aria-labelledby="opportunity-title">
    <div className="opportunity-heading"><h2 id="opportunity-title">{opportunity.program_name}</h2><p className="opportunity-source">{case_id} · {opportunity.organizer}</p><p className="opportunity-summary">{result.explanation}</p></div>
    <dl className="opportunity-metadata"><div><dt>Edition</dt><dd>{opportunity.edition}</dd></div><div><dt>Reward</dt><dd>Unrecorded</dd></div><div><dt>Deadline · UTC</dt><dd><time dateTime={deadline}>{deadline ? dateText(deadline) : 'UNKNOWN'}</time><small>{deadline ? `${deadline.slice(11, 16)} UTC` : 'Unavailable'}</small></dd></div><div><dt>Best project</dt><dd>{project?.name ?? 'Unresolved'}</dd></div></dl>
    <div className="section-rule"><h3>Decision field</h3></div>
    <div className="decision-signature">
      <dl className="signal-lanes" role="group" aria-label="Decision signals">
        <div className="signal-lane"><span className="signal-icon"><SignalIcon kind="fit" /></span><div className="signal-meaning"><dt>Fit</dt><span>Product alignment</span></div><dd><strong>{fit == null ? 'UNKNOWN' : `${fit} / 4`}</strong><span className="signal-bar" aria-hidden="true"><i style={{ width: fit == null ? '0%' : `${fit * 25}%` }} /></span></dd></div>
        <div className="signal-lane"><span className="signal-icon"><SignalIcon kind="eligibility" /></span><div className="signal-meaning"><dt><button className="signal-proof-link" aria-label="Show eligibility proof" onClick={() => { eligibilityProof.current?.focus(); eligibilityProof.current?.scrollIntoView?.({ block: 'nearest', behavior: 'instant' }); }}>Eligibility</button></dt><span>Fixture gate ↗</span></div><dd><strong className="signal-state">{result.eligibility?.replaceAll('_', ' ') ?? 'UNKNOWN'}</strong><span className="signal-rule" aria-hidden="true" /></dd></div>
        <div className="signal-lane"><span className="signal-icon"><SignalIcon kind="feasibility" /></span><div className="signal-meaning"><dt>Feasibility</dt><span>Preparation effort</span></div><dd><strong>{result.effort ? `${result.effort.min_total}–${result.effort.max_total} h` : 'UNKNOWN'}</strong><span className="signal-rule" aria-hidden="true" /></dd></div>
        <div ref={readinessSignal} tabIndex={-1} role="group" aria-label="Readiness assessment" className="signal-lane signal-lane--readiness"><span className="signal-icon"><SignalIcon kind="readiness" /></span><div className="signal-meaning"><dt>Readiness</dt><span>{result.readiness ? result.readiness.gaps.map(humanize).join(', ') || 'No recorded gaps' : 'Readiness unavailable'}</span></div><dd><strong>{result.readiness ? `${result.readiness.gaps.length} ${result.readiness.gaps.length === 1 ? 'gap' : 'gaps'}` : 'UNKNOWN'}</strong><span className="signal-rule" aria-hidden="true" /></dd></div>
      </dl>
      {opticalPreview ? <svg className="decision-convergence" viewBox="0 0 1000 260" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="optical-path-light"><stop stopColor="#6aa5c6" stopOpacity=".5" /><stop offset=".8" stopColor="#b9e8ff" /><stop offset="1" stopColor="#eefaff" /></linearGradient></defs><g className="convergence-base">{opticalPaths.map((path, index) => <path key={path} className={index === 3 ? 'convergence-warm' : undefined} d={path} />)}</g><g className="convergence-core">{opticalPaths.map((path, index) => <path key={path} className={index === 3 ? 'convergence-warm' : undefined} d={path} />)}</g><circle className="convergence-junction" cx="689" cy="118" r="4" /></svg> : <svg className="decision-convergence" viewBox="0 0 1000 300" preserveAspectRatio="none" aria-hidden="true"><path d="M480 34 C570 34 565 150 686 150" /><path d="M480 111 C570 111 590 150 686 150" /><path d="M480 189 C570 189 590 150 686 150" /><path className="convergence-warm" d="M480 266 C570 266 565 150 686 150" /><path d="M686 150H692" /><circle cx="690" cy="150" r="3" /></svg>}
      <svg className="mobile-convergence" viewBox="0 0 350 317" preserveAspectRatio="none" fill="none" aria-hidden="true"><path d="M329 31H349V285H175V317M329 102H349M329 173H349M329 244H349" /></svg>
      <section className="recommendation-surface" aria-label="Recommendation"><span className="section-index">Recommendation</span><h1 id="preview-decision-title">{result.recommendation}</h1><span className="recommendation-rule" aria-hidden="true" /><p>{result.recommendation === 'PREPARE' ? 'Close the recorded gaps and prepare materials.' : result.explanation}</p><div className="recommendation-strategy"><span className="section-index">Strategy priority</span><div>{result.strategy?.score == null ? <span className="strategy-unavailable">Not enough evidence</span> : <><strong>{result.strategy.score}</strong><span>/ 100</span><span className="signal-bar" aria-hidden="true"><i style={{ width: `${result.strategy.score}%` }} /></span></>}</div></div></section>
    </div>
    <p className="decision-semantics">Strategy is prioritization, not win probability.</p><div className="section-rule trace-heading"><h3>Decision trace</h3></div><DecisionTrace evaluated discoveryRecorded={activity.events.some(event => event.event_type === 'OPPORTUNITY_DISCOVERED')} /><p className="human-boundary">Human boundary / approval not requested</p>
    <div className="section-rule next-actions-heading"><h3>Next actions</h3></div><nav className="next-actions" aria-label="Next actions"><button onClick={() => { eligibilityProof.current?.focus(); eligibilityProof.current?.scrollIntoView?.({ block: 'nearest', behavior: 'instant' }); }}><span className="action-index" aria-hidden="true">01</span><span>Review eligibility proof<small>Inspect the synthetic rule</small></span><span aria-hidden="true">↗</span></button><button onClick={() => { readinessSignal.current?.focus(); readinessSignal.current?.scrollIntoView?.({ block: 'nearest', behavior: 'instant' }); }}><span className="action-index" aria-hidden="true">02</span><span>Review readiness gap<small>Inspect recorded materials</small></span><span aria-hidden="true">↗</span></button><a href="/design-preview.html?view=portfolio"><span className="action-index" aria-hidden="true">03</span><span>Review project<small>Read-only portfolio</small></span><span aria-hidden="true">↗</span></a></nav>
  </section>}</WorkspaceFrame>;
}
