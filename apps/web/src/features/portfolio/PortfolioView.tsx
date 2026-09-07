import { useEffect, useState } from 'react';
import { apiRequest, ApiError } from '../../api/client';
import type { FounderProfile, ProjectProfile, PortfolioView as Portfolio, SessionView } from '../../generated/domain';
import { ProfileForm } from './ProfileForm';

function newRecord(): FounderProfile {
  const now = new Date().toISOString();
  return { id: crypto.randomUUID(), version: 1, schema_version: '1', created_at: now, updated_at: now, provenance: 'USER_ASSERTED' };
}
export function PortfolioView() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [session, setSession] = useState<SessionView | null>(null);
  const [error, setError] = useState('');
  const [newFounder] = useState(newRecord);
  const [newProjects, setNewProjects] = useState<ProjectProfile[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([
      apiRequest<Portfolio>('/portfolio', { signal: controller.signal }),
      apiRequest<SessionView>('/session', { signal: controller.signal }),
    ]).then(([loaded, connected]) => {
      if (controller.signal.aborted) return;
      if (loaded.status === 'fulfilled') setPortfolio(loaded.value);
      else setError(loaded.reason instanceof ApiError ? loaded.reason.message : 'Portfolio unavailable');
      if (connected.status === 'fulfilled') setSession(connected.value);
      else if (loaded.status === 'fulfilled') setError('Editing is unavailable. Your saved portfolio remains readable.');
    });
    return () => controller.abort();
  }, []);
  function saved(value: Portfolio) {
    setPortfolio(value);
    // Keep the draft component mounted after its first save to retain its status.
  }
  const persistedIds = new Set(portfolio?.projects.map(project => project.id));
  const allProjects = [...(portfolio?.projects ?? []), ...newProjects.filter(project => !persistedIds.has(project.id))];
  const canEdit = !!session && !session.read_only && !!session.action_token;
  return <section className="portfolio-view">
    <div className="portfolio-heading"><h1>Your foundation.</h1><p>A clear picture of you and your work.<br />Provide what you know. Keep uncertainty explicit.</p></div>
    {error && <p className="form-feedback" role="alert">{error}</p>}
    {!portfolio && !error && <p role="status">Loading your saved portfolio…</p>}
    {portfolio && <>
      {!canEdit && <p className="form-note">Read-only workspace. Saved facts remain available for review.</p>}
      <ProfileForm key="founder" record={portfolio.founder ?? newFounder} kind="founder" isNew={!portfolio.founder} session={session} onSaved={saved} />
      <div className="project-section-heading"><h2>Projects <span className="quiet">{allProjects.length} / 5</span></h2>{canEdit && allProjects.length < 5 && <button className="text-button" onClick={() => setNewProjects(previous => [...previous, { ...newRecord(), name: '' }])}>Add project</button>}</div>
      {allProjects.length === 0 && <p className="project-empty">Your portfolio is open. Add a project to describe its fit, stage, and constraints.</p>}
      {allProjects.map(project => <ProfileForm key={project.id} record={project} kind="project" isNew={newProjects.some(draft => draft.id === project.id)} session={session} onSaved={saved} />)}
    </>}
  </section>;
}
