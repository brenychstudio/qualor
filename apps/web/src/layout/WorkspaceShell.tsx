import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom';
import { apiRequest, ApiError } from '../api/client';
import type { InboxResponse } from '../generated/domain';

interface WorkspaceContext { inbox: InboxResponse | null; error: string | null; }
export function useWorkspace() { return useOutletContext<WorkspaceContext>(); }
export function WorkspaceShell() {
  const [inbox, setInbox] = useState<InboxResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const contextButton = useRef<HTMLButtonElement>(null);
  const contextPanel = useRef<HTMLElement>(null);
  const location = useLocation();
  useEffect(() => {
    const controller = new AbortController();
    apiRequest<InboxResponse>('/inbox', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) { setInbox(value); setError(null); }
    }).catch(error => {
      if (!controller.signal.aborted) setError(error instanceof ApiError ? error.message : 'Local workspace unavailable');
    });
    return () => controller.abort();
  }, [location.pathname]);
  useEffect(() => {
    if (contextOpen) {
      contextPanel.current?.focus();
      contextPanel.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' });
    }
  }, [contextOpen]);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const modes = [...new Set(inbox?.items.flatMap(item => item.mode ? [item.mode] : []) ?? [])];
  function closeContext() { setContextOpen(false); contextButton.current?.focus(); }
  return <div className={`workspace${reducedMotion ? ' reduce-motion' : ''}`} onKeyDown={event => {
    if (event.key === 'Escape' && contextOpen) closeContext();
  }}>
    <a className="skip-link" href="#decision">Skip to workspace</a>
    <header className="workspace-header">
      <Link className="wordmark" to="/inbox" aria-label="QUALOR home">QUALOR<span aria-hidden="true">/</span></Link>
      <nav aria-label="Primary">
        <NavLink to="/inbox">Inbox</NavLink>
        <NavLink to="/portfolio">Portfolio</NavLink>
        <NavLink to="/activity">Activity</NavLink>
      </nav>
      <span className="workspace-label">Local workspace</span>
    </header>
    <div className="workspace-grid workspace-grid--three-zone">
      <aside className="workspace-queue" aria-label="Opportunity inbox">
        <div className="zone-heading"><h2>Opportunities</h2><span>{inbox ? String(inbox.page.total).padStart(2, '0') : '—'}</span></div>
        <div className="queue-empty"><span className="eyebrow">Your shortlist</span><p>{error ? 'Queue unavailable' : !inbox ? 'Opening workspace…' : inbox.page.total ? 'Your saved opportunities' : 'Room for what matters.'}</p>
          <span className="quiet">{inbox?.page.total ? 'Saved in your local workspace.' : 'Opportunities will gather here as they are discovered and evaluated.'}</span>
        </div>
        <p className="queue-footnote">Find what qualifies.<br />Pursue what matters.</p>
      </aside>
      <main id="decision" className="workspace-canvas" tabIndex={-1}>
        <div className="canvas-topline"><span className="eyebrow">Decision workspace</span><button ref={contextButton} className="context-toggle text-button" aria-expanded={contextOpen} aria-controls="workspace-context" onClick={() => setContextOpen(!contextOpen)}>Workspace context</button></div>
        <Outlet context={{ inbox, error } satisfies WorkspaceContext} />
        <section className="proof-context" aria-label="Why & proof"><span className="section-index">WHY & PROOF</span><p>Every recommendation starts with evidence.<br /><span className="quiet">Source proof belongs beside the decision it supports.</span></p></section>
      </main>
      <aside ref={contextPanel} tabIndex={-1} id="workspace-context" className={`workspace-rail${contextOpen ? ' workspace-rail--open' : ''}`} aria-label="Workspace context">
        <div className="zone-heading"><h2>Context</h2><button className="context-close text-button" onClick={closeContext}>Close</button></div>
        <section className="rail-section"><span className="eyebrow">Connection</span><p className="connection-state" role="status">{error ?? (inbox ? 'Local controller connected' : 'Connecting to local controller…')}</p><p className="quiet">Your profiles and saved work stay in this local workspace.</p></section>
        <section className="rail-section"><h3>Activity</h3><p className="mode-label">{modes.length ? modes.join(' · ') : 'No run selected'}</p><p className="quiet">{modes.length ? 'Recorded research modes in your shortlist. A local connection does not indicate live research.' : 'Research activity appears with its recorded mode and source context.'}</p><Link className="inline-link" to="/activity">View activity <span aria-hidden="true">↗</span></Link></section>
        <div className="human-boundary"><span className="eyebrow">The human boundary</span><p>Intelligence informs.<br />You decide.</p></div>
      </aside>
    </div>
  </div>;
}
