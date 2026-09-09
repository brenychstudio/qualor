import { useEffect, useState } from 'react';
import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { apiRequest } from './api/client';
import type { PortfolioView as Portfolio } from './generated/domain';
import { WorkspaceShell, useWorkspace } from './layout/WorkspaceShell';
import { PortfolioView } from './features/portfolio/PortfolioView';
import { DecisionTrace } from './layout/DecisionTrace';

function InboxFoundation() {
  const { inbox, error } = useWorkspace();
  const { opportunityId } = useParams();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [portfolioError, setPortfolioError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    apiRequest<Portfolio>('/portfolio', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setPortfolio(value);
    }).catch(() => { if (!controller.signal.aborted) setPortfolioError(true); });
    return () => controller.abort();
  }, []);
  if (opportunityId) return <UnavailableView title="Decision view not yet available" description="This workspace foundation does not yet display individual opportunity decisions." />;
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
    {portfolioError && <p className="quiet" role="status">Portfolio context unavailable</p>}
    <div className="stage-action"><Link className="primary-action" to="/portfolio">{profilePresent === false ? 'Complete profile' : 'Review portfolio'}<span aria-hidden="true">↗</span></Link><p className="quiet">Unknown facts remain UNKNOWN.</p></div>
    <DecisionTrace />
  </section>;
}
function UnavailableView({ title, description }: { title: string; description: string }) {
  return <section className="structural-state"><span className="eyebrow">Workspace foundation</span><h1>{title}</h1><p>{description}</p><Link className="inline-link" to="/inbox">Return to inbox ↗</Link></section>;
}
function StructuralView({ kind }: { kind: 'activity' | 'pack' }) {
  return <UnavailableView title={kind === 'activity' ? 'Activity view not yet available' : 'Draft pack view not yet available'} description={kind === 'activity' ? 'Recorded research history will be available in a later workspace task.' : 'This workspace foundation does not yet display prepared application documents.'} />;
}
export function App() {
  return <Routes><Route element={<WorkspaceShell />}>
    <Route index element={<Navigate to="/inbox" replace />} />
    <Route path="inbox" element={<InboxFoundation />} />
    <Route path="inbox/:opportunityId" element={<InboxFoundation />} />
    <Route path="portfolio" element={<PortfolioView />} />
    <Route path="activity" element={<StructuralView kind="activity" />} />
    <Route path="draft-packs/:packId" element={<StructuralView kind="pack" />} />
    <Route path="*" element={<Navigate to="/inbox" replace />} />
  </Route></Routes>;
}
