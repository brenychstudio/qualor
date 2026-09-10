import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { apiRequest } from './api/client';
import type { OpportunityWorkspaceResponse, PortfolioView as Portfolio, Recommendation } from './generated/domain';
import { WorkspaceShell, useWorkspace } from './layout/WorkspaceShell';
import { PortfolioView } from './features/portfolio/PortfolioView';
import { DecisionTrace } from './layout/DecisionTrace';
import { DecisionCanvas } from './features/decision/DecisionCanvas';
import { ActivityHistory } from './features/activity/ActivityHistory';
import { ApprovalPanel } from './features/approval/ApprovalPanel';
import { ApplicationPack } from './features/draft-pack/ApplicationPack';
import { ProductStateSurface } from './features/states/ProductStateSurface';

function InboxFoundation() {
  const { inbox, error, selectedWorkspace, selectedWorkspaceError, selectedWorkspaceLoading } = useWorkspace();
  const { opportunityId } = useParams();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [portfolioError, setPortfolioError] = useState(false);
  useEffect(() => {
    if (opportunityId) return;
    const controller = new AbortController();
    apiRequest<Portfolio>('/portfolio', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setPortfolio(value);
    }).catch(() => { if (!controller.signal.aborted) setPortfolioError(true); });
    return () => controller.abort();
  }, [opportunityId]);
  if (opportunityId) {
    if (selectedWorkspace?.opportunity_id === opportunityId) return <SelectedDecision workspace={selectedWorkspace} />;
    if (selectedWorkspaceError) return <UnavailableView title={selectedWorkspaceError.code === 'NOT_FOUND' ? 'Opportunity unavailable' : 'Decision workspace unavailable'} description={selectedWorkspaceError.message} />;
    if (selectedWorkspaceLoading || !selectedWorkspace) return <section className="structural-state" aria-live="polite"><span className="eyebrow">Selected opportunity</span><h1>Opening decision</h1><p>Reading the saved decision workspace…</p></section>;
  }
  const profilePresent = portfolio ? !!portfolio.founder : inbox?.profile_present;
  return <section className="empty-decision" aria-labelledby="welcome-title">
    <div className="decision-context"><span className="section-index">Inbox</span><span className="quiet">{error ? 'Connection unavailable' : !inbox ? 'Loading saved state' : 'No selection'}</span></div>
    <div className="decision-state">
      <h1 id="welcome-title">{error ? 'Workspace unavailable' : !inbox ? 'Opening workspace' : 'No active decision'}</h1>
      <p className="state-description">{error ? 'Reconnect the local controller to read your saved opportunities and portfolio.' : !inbox ? 'Reading your saved workspace context…' : portfolio?.founder && portfolio.projects.length > 0 ? 'Portfolio context is available. No opportunity decision is selected.' : 'Add your profile and a project to establish the context for qualification.'}</p>
    </div>
    <dl className="decision-readouts" role="group" aria-label="Portfolio context">
      <div><dt>Founder profile</dt><dd>{profilePresent === undefined ? '—' : profilePresent ? 'Added' : 'Not added'}</dd></div>
      <div><dt>Projects</dt><dd>{portfolio?.projects ? `${portfolio.projects.length} ${portfolio.projects.length === 1 ? 'project' : 'projects'}` : '—'}</dd></div>
      <div><dt>Qualification</dt><dd>{portfolio ? portfolio.founder && portfolio.projects.length ? 'No evaluation' : 'Locked' : 'Unavailable'}</dd></div>
    </dl>
    <ProductStateSurface productState={inbox?.product_state ?? null} />
    {portfolioError && <p className="quiet" role="status">Portfolio context unavailable</p>}
    <div className="stage-action"><Link className="primary-action" to="/portfolio">{profilePresent === false ? 'Complete profile' : 'Review portfolio'}<span aria-hidden="true">↗</span></Link><p className="quiet">Unknown facts remain UNKNOWN.</p></div>
    <DecisionTrace />
  </section>;
}
// Only APPLY and PREPARE carry approval authority. WATCH and SKIP keep their Task 9 intent.
const APPROVABLE = new Set<Recommendation>(['APPLY', 'PREPARE']);

function SelectedDecision({ workspace }: { workspace: OpportunityWorkspaceResponse }) {
  const [intent, setIntent] = useState<'APPLY' | 'PREPARE' | null>(null);
  const canvas = useRef<HTMLDivElement>(null);
  useEffect(() => { setIntent(null); }, [workspace.opportunity_id]);
  function close() {
    setIntent(null);
    canvas.current?.querySelector<HTMLButtonElement>('button[data-primary-action]')?.focus();
  }
  return <div ref={canvas}>
    <ProductStateSurface productState={workspace.product_state} />
    <DecisionCanvas
      workspace={workspace}
      approvalOpen={intent !== null}
      onPrimaryAction={recommendation => {
        if (APPROVABLE.has(recommendation)) setIntent(recommendation as 'APPLY' | 'PREPARE');
      }}
    />
    {intent && <ApprovalPanel workspace={workspace} recommendation={intent} onClose={close} />}
  </div>;
}

function UnavailableView({ title, description }: { title: string; description: string }) {
  return <section className="structural-state"><span className="eyebrow">Workspace foundation</span><h1>{title}</h1><p>{description}</p><Link className="inline-link" to="/inbox">Return to inbox ↗</Link></section>;
}
export function App() {
  return <Routes><Route element={<WorkspaceShell />}>
    <Route index element={<Navigate to="/inbox" replace />} />
    <Route path="inbox" element={<InboxFoundation />} />
    <Route path="inbox/:opportunityId" element={<InboxFoundation />} />
    <Route path="portfolio" element={<PortfolioView />} />
    <Route path="activity" element={<ActivityHistory />} />
    <Route path="draft-packs/:packId" element={<ApplicationPack />} />
    <Route path="*" element={<Navigate to="/inbox" replace />} />
  </Route></Routes>;
}
