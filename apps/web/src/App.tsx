import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { WorkspaceShell, useWorkspace } from './layout/WorkspaceShell';
import { PortfolioView } from './features/portfolio/PortfolioView';

function InboxFoundation() {
  const { inbox, error } = useWorkspace();
  const { opportunityId } = useParams();
  if (opportunityId) return <div className="structural-state"><span className="eyebrow">Opportunity workspace</span><h1>A place for<br /><em>the decision.</em></h1><p>No decision is open. Return to your inbox to review your workspace.</p><Link className="inline-link" to="/inbox">Back to inbox ↗</Link></div>;
  return <section className="empty-decision" aria-labelledby="welcome-title">
    <div className="empty-kicker"><span className="section-index">01 / YOUR FOUNDATION</span><span className="quiet">A considered beginning</span></div>
    <h1 id="welcome-title">Good decisions<br /><em>start with you.</em></h1>
    <p className="hero-description">Give QUALOR the context that matters.<br className="desktop-break" /> Your projects, your constraints, your next ambition.</p>
    <div className="hero-action"><Link className="primary-action" to="/portfolio">{inbox?.profile_present ? 'Review portfolio' : 'Complete profile'}<span aria-hidden="true">↗</span></Link><span className="quiet">{error ? 'Reconnect the local controller to edit.' : 'Only the facts you choose to share.'}</span></div>
    <div className="foundation-note"><span className="small-mark" aria-hidden="true">↳</span><p>{inbox?.profile_present ? 'Your foundation is saved.' : 'A profile before a recommendation.'}<br /><span className="quiet">Unknown facts remain UNKNOWN until you provide them.</span></p></div>
  </section>;
}
function StructuralView({ kind }: { kind: 'activity' | 'pack' }) {
  return <section className="structural-state"><span className="eyebrow">{kind === 'activity' ? 'Recorded activity' : 'Application document'}</span><h1>{kind === 'activity' ? 'A record of' : 'A space for'}<br /><em>{kind === 'activity' ? 'what happened.' : 'prepared work.'}</em></h1><p>{kind === 'activity' ? 'No run is open. Research history keeps its recorded mode, sources, and outcome.' : 'No application document is open. Preparation requires your approval; submission stays with you.'}</p><Link className="inline-link" to="/inbox">Return to inbox ↗</Link></section>;
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
