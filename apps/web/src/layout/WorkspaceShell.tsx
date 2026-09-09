import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom';
import { apiRequest, ApiError } from '../api/client';
import type { InboxResponse } from '../generated/domain';

interface WorkspaceContext { inbox: InboxResponse | null; error: string | null; }
export function useWorkspace() { return useOutletContext<WorkspaceContext>(); }

// Shared presentation frame; the isolated design proof supplies read-only content.
export function WorkspaceFrame({ children, queue, context, proof, previewLabel, evidenceContent, previewNav, qaLabel, opticalPreview = false }: {
  children: ReactNode; queue: ReactNode; context: ReactNode; proof: ReactNode; previewLabel?: string; evidenceContent?: ReactNode; previewNav?: ReactNode; qaLabel?: string; opticalPreview?: boolean;
}) {
  const [proofOpen, setProofOpen] = useState(false);
  const [narrow, setNarrow] = useState(window.innerWidth < 768);
  const proofButton = useRef<HTMLButtonElement>(null);
  const proofPlane = useRef<HTMLElement>(null);
  const proofWasOpen = useRef(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const contextButton = useRef<HTMLButtonElement>(null);
  const contextPanel = useRef<HTMLElement>(null);
  useEffect(() => {
    const resize = () => setNarrow(window.innerWidth < 768);
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  useEffect(() => {
    if (proofOpen) { proofWasOpen.current = true; proofPlane.current?.focus(); }
    else if (proofWasOpen.current) { proofWasOpen.current = false; proofButton.current?.focus(); }
  }, [proofOpen]);
  useEffect(() => {
    if (!proofOpen || !narrow) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previousOverflow; };
  }, [proofOpen, narrow]);
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
  function closeContext() { setContextOpen(false); contextButton.current?.focus(); }
  function closeProof() { setProofOpen(false); }
  return <div className={`workspace${opticalPreview ? ' workspace--optical-preview' : ''}${reducedMotion ? ' reduce-motion' : ''}${proofOpen ? ' proof-is-open' : ''}`} onKeyDown={event => {
    if (event.key === 'Escape' && proofOpen) closeProof();
    else if (event.key === 'Escape' && contextOpen) closeContext();
  }}>
    <a className="skip-link" href="#decision">Skip to workspace</a>
    {previewLabel && !opticalPreview && <div className="design-preview-label">{previewLabel}</div>}
    {qaLabel && <div className="design-preview-label local-qa-label">{qaLabel}</div>}
    <header className="workspace-header" inert={proofOpen && narrow}>
      <div className="identity">{previewLabel ? <a className="wordmark" href="/design-preview.html" aria-label="QUALOR home">QUALOR</a> : <Link className="wordmark" to="/inbox" aria-label="QUALOR home">QUALOR</Link>}<span className="identity-caption">Opportunity intelligence</span></div>
      <nav aria-label="Primary">{previewNav ?? (previewLabel ? <><a href="/design-preview.html" aria-current="page">Inbox</a><a href="/design-preview.html?view=portfolio">Portfolio</a><a href="/design-preview.html?view=activity">Activity</a></> : <><NavLink to="/inbox">Inbox</NavLink><NavLink to="/portfolio">Portfolio</NavLink><NavLink to="/activity">Activity</NavLink></>)}</nav>
      <div className="header-utilities"><label className="header-search"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></svg><input disabled aria-label="Search unavailable" placeholder="Search unavailable" /></label><span className="workspace-label"><span className="runtime-marker" aria-hidden="true" />{previewLabel ? opticalPreview ? 'DESIGN PREVIEW · SYNTHETIC · READ ONLY' : 'FIXTURE' : <><span>LOCAL</span><span className="visually-hidden">Local workspace</span></>}</span></div>
    </header>
    <div className="workspace-grid workspace-grid--four-zone" inert={proofOpen && narrow}>
      <aside className="workspace-queue" aria-label="Opportunity inbox">{queue}</aside>
      <main id="decision" className="workspace-canvas" tabIndex={-1}>
        <div className="canvas-topline"><span className="eyebrow">Decision workspace</span><button ref={contextButton} className="context-toggle text-button" aria-expanded={contextOpen} aria-controls="workspace-context" onClick={() => setContextOpen(!contextOpen)}>Workspace context</button></div>
        {children}
      </main>
      <section className={`proof-context${evidenceContent ? ' proof-context--available' : ''}`} aria-label="Why & proof">{proof}{evidenceContent && <button ref={proofButton} className="proof-trigger" aria-expanded={proofOpen} aria-controls="decision-proof" onClick={() => setProofOpen(true)}>Why this decision <span aria-hidden="true">↗</span></button>}</section>
      <aside ref={contextPanel} tabIndex={-1} id="workspace-context" className={`workspace-rail${contextOpen ? ' workspace-rail--open' : ''}`} aria-label="Workspace context">
        <div className="zone-heading"><h2>Intelligence</h2><button className="context-close text-button" onClick={closeContext}>Close</button></div>
        {context}
      </aside>
    </div>
    {proofOpen && <section id="decision-proof" ref={proofPlane} tabIndex={-1} className="evidence-plane" aria-label="Decision proof" onKeyDown={event => {
      if (!narrow || event.key !== 'Tab') return;
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'));
      const first = controls[0]; const last = controls.at(-1);
      if (event.shiftKey && (document.activeElement === first || document.activeElement === event.currentTarget)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}><div className="evidence-plane-heading"><span className="section-index">Decision / documentary proof</span><button className="text-button" onClick={closeProof}>Close proof ↙</button></div><h2>Why this decision</h2>{previewLabel && <p className="evidence-mode">{previewLabel}</p>}{evidenceContent}</section>}
  </div>;
}

export function WorkspaceShell() {
  const [inbox, setInbox] = useState<InboxResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const location = useLocation();
  useEffect(() => {
    const controller = new AbortController();
    setInbox(null); setError(null);
    apiRequest<InboxResponse>('/inbox', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) { setInbox(value); setError(null); }
    }).catch(error => {
      if (!controller.signal.aborted) setError(error instanceof ApiError ? error.message : 'Local workspace unavailable');
    });
    return () => controller.abort();
  }, [location.pathname]);
  const modes = [...new Set(inbox?.items.flatMap(item => item.mode ? [item.mode] : []) ?? [])];
  const qaLabel = import.meta.env.DEV && new URLSearchParams(location.search).get('qa') === 'synthetic-fixture'
    ? 'LOCAL API QA · SYNTHETIC FIXTURE DATA · NO LIVE DATA' : undefined;
  return <WorkspaceFrame
    qaLabel={qaLabel}
    queue={<>
      <div className="zone-heading"><h2>Opportunities</h2><span>{inbox ? inbox.page.total : '—'}</span></div>
      <div className="queue-empty"><p>{error ? 'Queue unavailable' : !inbox ? 'Opening workspace…' : inbox.page.total ? 'Your saved opportunities' : 'No saved opportunities.'}</p></div>
      <p className="queue-footnote">Saved in this workspace</p>
    </>}
    context={<>
      <section className="rail-section"><h3>Local controller</h3><p className="connection-state" role="status">{error ?? (inbox ? 'Local controller connected' : 'Connecting to local controller…')}</p><p className="quiet">A local connection does not indicate LIVE research.</p></section>
      <section className="rail-section"><h3>Selected run</h3><p>No run selected</p><dl className="context-facts"><div><dt>Research mode</dt><dd>{modes.length ? modes.join(' · ') : 'Unavailable'}</dd></div><div><dt>Source context</dt><dd>Unavailable</dd></div></dl>{modes.length > 0 && <p className="quiet">Recorded research modes in your shortlist.</p>}<Link className="inline-link" to="/activity">View activity <span aria-hidden="true">↗</span></Link></section>
    </>}
    proof={<><span className="section-index">Why & proof</span><p>No decision selected.<br /><span className="quiet">Evidence context is unavailable.</span></p></>}
  ><Outlet context={{ inbox, error } satisfies WorkspaceContext} /></WorkspaceFrame>;
}
