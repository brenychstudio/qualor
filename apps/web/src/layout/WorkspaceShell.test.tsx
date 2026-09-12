import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, test, vi } from 'vitest';
import { App } from '../App';
import { selectedProof, WorkspaceFrame } from './WorkspaceShell';
import { DecisionTrace } from './DecisionTrace';

function mount(path = '/inbox') { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); }
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(url.endsWith('/inbox')
    ? { items: [], profile_present: false, page: { offset: 0, limit: 50, total: 0, has_more: false } }
    : url.endsWith('/session') ? { read_only: true, action_token: null }
    : { founder: null, projects: [] })));
});
test('projects opportunity, decision, proof and intelligence in sequential reading order', async () => {
  mount();
  await screen.findByRole('link', { name: /complete profile/i });
  const queue = screen.getByRole('complementary', { name: 'Opportunity inbox' });
  const decision = screen.getByRole('main');
  const proof = screen.getByRole('region', { name: 'Why & proof' });
  const activity = screen.getByRole('complementary', { name: 'Workspace context' });
  expect(queue.compareDocumentPosition(decision) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(decision.compareDocumentPosition(proof) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(proof.compareDocumentPosition(activity) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(proof.parentElement).toBe(decision.parentElement);
  expect(decision.contains(proof)).toBe(false);
});
test('selects Portfolio through working keyboard navigation', async () => {
  mount();
  const nav = screen.getByRole('navigation', { name: 'Primary' });
  const inbox = within(nav).getByRole('link', { name: 'Inbox' });
  expect(inbox).toHaveAttribute('aria-current', 'page');
  inbox.focus();
  await userEvent.tab();
  expect(within(nav).getByRole('link', { name: 'Portfolio' })).toHaveFocus();
  await userEvent.keyboard('{Enter}');
  expect(await screen.findByRole('heading', { name: 'Portfolio' })).toBeVisible();
  expect(within(nav).getByRole('link', { name: 'Portfolio' })).toHaveAttribute('aria-current', 'page');
});
test('retains the primary action and user-invoked context at 320 pixels', async () => {
  vi.stubGlobal('innerWidth', 320);
  mount();
  expect(await screen.findByRole('link', { name: /complete profile/i })).toBeVisible();
  const toggle = screen.getByRole('button', { name: 'Workspace context' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await userEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('complementary', { name: 'Workspace context' })).toHaveClass('workspace-rail--open');
  await userEvent.keyboard('{Escape}');
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(toggle).toHaveFocus();
});
test('applies the reduced-motion preference to the workspace', () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener() {}, removeEventListener() {} })));
  mount();
  expect(screen.getByRole('banner').parentElement).toHaveClass('reduce-motion');
});
test.each(['/activity', '/draft-packs/pack-1', '/inbox/opportunity-1'])('keeps the registered %s route inside the shell', async (path) => {
  mount(path);
  expect(screen.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  expect(screen.getByRole('main')).toBeVisible();
  expect(await screen.findByText('Local workspace')).toBeVisible();
});
test('labels local API absence without claiming cloud or LIVE state', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('private detail'); }));
  mount();
  expect(await screen.findByText('Local controller disconnected')).toBeVisible();
  expect(screen.queryByText('LIVE')).not.toBeInTheDocument();
  expect(screen.queryByText('private detail')).not.toBeInTheDocument();
});

test('brings an opened context panel into keyboard focus and view', async () => {
  vi.stubGlobal('innerWidth', 1024);
  mount();
  await userEvent.click(screen.getByRole('button', { name: 'Workspace context' }));
  expect(screen.getByRole('complementary', { name: 'Workspace context' })).toHaveFocus();
});
test('clears a disconnected state after a successful route-triggered reload', async () => {
  let connected = false;
  vi.stubGlobal('fetch', vi.fn(async () => {
    if (!connected) throw new TypeError('offline');
    return Response.json({ items: [], profile_present: false, page: { offset: 0, limit: 50, total: 0, has_more: false } });
  }));
  mount();
  await screen.findByText('Local controller disconnected');
  connected = true;
  await userEvent.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'Activity' }));
  expect(await screen.findByText('Local controller connected')).toBeVisible();
  expect(screen.queryByText('Local controller disconnected')).not.toBeInTheDocument();
});
test('ignores an older read that resolves after navigation', async () => {
  let resolveOld!: (response: Response) => void;
  let request = 0;
  vi.stubGlobal('fetch', vi.fn(async () => {
    request++;
    if (request === 1) return new Promise<Response>(resolve => { resolveOld = resolve; });
    return Response.json({ items: [], profile_present: false, page: { offset: 0, limit: 50, total: 0, has_more: false } });
  }));
  mount();
  await userEvent.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'Activity' }));
  await screen.findByText('Local controller connected');
  await act(async () => resolveOld(Response.json({ items: [], profile_present: false, page: { offset: 0, limit: 50, total: 99, has_more: false } })));
  expect(within(screen.getByRole('complementary', { name: 'Opportunity inbox' })).queryByText('99')).not.toBeInTheDocument();
});

test('keeps every returned research mode explicit in a mixed shortlist', async () => {
  const modes: import('../generated/domain').RuntimeMode[] = ['LIVE', 'REPLAY', 'FIXTURE'];
  const items: import('../generated/domain').InboxItem[] = modes.map((mode, priority_rank) => ({
    priority_rank, discovered_at: '2026-09-05T12:00:00Z',
    presentation_state: 'NEEDS_REVIEW',
    opportunity_id: `test-${mode}`, version: 1, organizer: 'Test organizer', program_name: 'Test program', edition: 'Test edition',
    best_project: null, deadline: { timezone_status: 'UNKNOWN', values: [] }, effort: null, freshness: 'UNKNOWN',
    human_action_available: false, mode, primary_blocker: null, readiness: null, recommendation: null, run_state: 'COMPLETED',
  }));
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ items, profile_present: true, page: { offset: 0, limit: 50, total: 3, has_more: false } })));
  mount();
  expect(await screen.findByText('LIVE · REPLAY · FIXTURE')).toBeVisible();
  expect(screen.getByText('Local controller connected')).toBeVisible();
});

test('shows actual setup facts from the protected portfolio read', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(url.endsWith('/portfolio')
    ? { founder: null, projects: [{ id: 'project-1', name: 'Saved project', version: 1 }] }
    : { items: [], profile_present: false, page: { offset: 0, limit: 50, total: 0, has_more: false } })));
  mount();
  expect(await screen.findByRole('heading', { name: 'No active decision' })).toBeVisible();
  const facts = screen.getByRole('group', { name: 'Portfolio context' });
  expect(await within(facts).findByText('1 project')).toBeVisible();
  expect(within(facts).getByText('Not added')).toBeVisible();
});
test('uses the server-advertised hosted research context instead of asking for a local profile', async () => {
  const fetchMock = vi.fn(async (url: string) => Response.json(url.endsWith('/inbox')
    ? { items: [], profile_present: false, live_research_available: true, page: { offset: 0, limit: 50, total: 0, has_more: false } }
    : url.endsWith('/runs') ? { runs: [], events: [], runs_page: { offset: 0, limit: 50, total: 0, has_more: false }, events_page: { offset: 0, limit: 50, total: 0, has_more: false } }
    : { founder: null, projects: [] }));
  vi.stubGlobal('fetch', fetchMock);
  mount();
  expect(await screen.findByText('Research an opportunity to create an evaluated workspace.')).toBeVisible();
  expect(screen.queryByText('Profile required')).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /complete profile/i })).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([request]) => String(request).endsWith('/portfolio'))).toBe(false);
});
test('proof summary never falls back to a raw missing-information path', () => {
  const workspace = {
    presentation_state: 'NEEDS_REVIEW', freshness: 'FRESH', mode: 'LIVE', run_state: 'COMPLETED',
    decision: {
      recommendation: 'WATCH', summary: 'Evidence remains unresolved.', primary_blocker: null,
      missing_information: ['opportunity.matching.requirements.stages'],
    },
  } as import('../generated/domain').OpportunityWorkspaceResponse;
  render(<MemoryRouter><WorkspaceFrame queue={null} context={null} proof={selectedProof(workspace)}><h1>Decision</h1></WorkspaceFrame></MemoryRouter>);
  expect(screen.queryByText('opportunity.matching.requirements.stages')).not.toBeInTheDocument();
  expect(screen.getByText('No primary blocker recorded')).toBeVisible();
  expect(screen.getByText('1 unresolved field')).toBeVisible();
});
test('keeps loading and failed reads distinct from a successful empty workspace', async () => {
  let rejectRead!: (reason: Error) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((_resolve, reject) => { rejectRead = reject; })));
  mount();
  expect(screen.getByRole('heading', { name: 'Opening workspace' })).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'No active decision' })).not.toBeInTheDocument();
  await act(async () => rejectRead(new TypeError('offline')));
  expect(await screen.findByRole('heading', { name: 'Workspace unavailable' })).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'No active decision' })).not.toBeInTheDocument();
});
test('does not turn unavailable portfolio facts into zero projects', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/portfolio')) throw new TypeError('offline');
    return Response.json({ items: [], profile_present: false, page: { offset: 0, limit: 50, total: 0, has_more: false } });
  }));
  mount();
  expect(await screen.findByText('Portfolio context unavailable')).toBeVisible();
  expect(screen.queryByText('0 projects')).not.toBeInTheDocument();
});

test('labels explicitly flagged local API synthetic QA without changing the LOCAL runtime identity', async () => {
  mount('/portfolio?qa=synthetic-fixture');
  expect(await screen.findByText('LOCAL API QA · SYNTHETIC FIXTURE DATA · NO LIVE DATA')).toBeVisible();
  expect(screen.getByText('LOCAL')).toBeVisible();
  expect(screen.queryByText('DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY')).not.toBeInTheDocument();
});

test('does not expose the local synthetic QA presentation flag in production', async () => {
  vi.stubEnv('DEV', false);
  try {
    mount('/portfolio?qa=synthetic-fixture');
    await screen.findByRole('heading', { name: 'Portfolio' });
    expect(screen.queryByText('LOCAL API QA · SYNTHETIC FIXTURE DATA · NO LIVE DATA')).not.toBeInTheDocument();
  } finally { vi.unstubAllEnvs(); }
});

test('keeps dormant trace phases unavailable without implying research or approval', async () => {
  mount();
  await screen.findByRole('heading', { name: 'No active decision' });
  const trace = screen.getByRole('list', { name: 'Decision trace' });
  expect(within(trace).getAllByRole('listitem')).toHaveLength(5);
  expect(within(trace).getAllByText('Unavailable')).toHaveLength(4);
  expect(within(trace).getByText('Not requested')).toBeVisible();
  expect(within(trace).queryByText(/completed|verified/i)).not.toBeInTheDocument();
});

test('expands proof material, focuses it and restores the exact trigger on Escape', async () => {
  render(<MemoryRouter><WorkspaceFrame queue={null} context={null} proof={<p>Source peek</p>} evidenceContent={<p>Actual source material</p>}><h1>PREPARE</h1></WorkspaceFrame></MemoryRouter>);
  const trigger = screen.getByRole('button', { name: /why this decision/i });
  await userEvent.click(trigger);
  const plane = screen.getByRole('region', { name: 'Decision proof' });
  expect(plane).toHaveFocus();
  expect(within(plane).getByText('Actual source material')).toBeVisible();
  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('region', { name: 'Decision proof' })).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

/* The open proof is one integrated reader: a non-scrolling context strip over a single warm
   document. The structure is asserted here because it is what the CSS composition depends on —
   a stylesheet cannot group the close control out of the scroll region on its own. */
test('groups the open proof into a context strip and one document region', async () => {
  render(<MemoryRouter><WorkspaceFrame queue={null} context={null} proof={null}
    proofSubject={{ title: 'Recorded programme', mode: 'FIXTURE' }}
    evidenceContent={<p>Actual source material</p>}><h1>PREPARE</h1></WorkspaceFrame></MemoryRouter>);
  await userEvent.click(screen.getByRole('button', { name: /why this decision/i }));
  const plane = screen.getByRole('region', { name: 'Decision proof' });
  const strip = plane.querySelector<HTMLElement>('.evidence-plane-heading')!;
  const document_ = plane.querySelector<HTMLElement>('.evidence-document')!;
  expect(strip).not.toBeNull();
  expect(document_).not.toBeNull();

  // Exactly one close control, its accessible name unchanged, kept out of the scroll region.
  const close = within(plane).getByRole('button', { name: /close proof/i });
  expect(within(plane).getAllByRole('button', { name: /close proof/i })).toHaveLength(1);
  expect(strip.contains(close)).toBe(true);
  expect(document_.contains(close)).toBe(false);
  expect(document_.contains(strip)).toBe(false);

  // The document carries the reading order and starts at Why this decision.
  const heading = within(plane).getByRole('heading', { level: 2, name: 'Why this decision' });
  expect(document_.contains(heading)).toBe(true);
  expect(within(document_).getByText('Actual source material')).toBeVisible();

  // The strip states the already-selected opportunity and its recorded mode, and nothing else:
  // no proof count, no recommendation, nothing that would need a second read to produce.
  // Asserting the exact rendered leaves catches an invented value wherever it is added.
  expect([...strip.querySelectorAll('*')].filter(node => !node.children.length).map(node => node.textContent))
    .toEqual(['Decision / documentary proof', 'Recorded programme', 'FIXTURE', 'Close proof ↙']);
});

test('keeps the existing truthful proof context when no selected subject is available', async () => {
  render(<MemoryRouter><WorkspaceFrame queue={null} context={null} proof={null}
    evidenceContent={<p>Actual source material</p>}><h1>PREPARE</h1></WorkspaceFrame></MemoryRouter>);
  await userEvent.click(screen.getByRole('button', { name: /why this decision/i }));
  const strip = screen.getByRole('region', { name: 'Decision proof' }).querySelector<HTMLElement>('.evidence-plane-heading')!;
  expect(strip).toHaveTextContent('Decision / documentary proof');
  expect(within(strip).getByRole('button', { name: /close proof/i })).toBeVisible();
  expect(strip.querySelector('.evidence-plane-subject')).toBeNull();
});

test('keeps keyboard navigation inside full-screen proof until it closes', async () => {
  vi.stubGlobal('innerWidth', 390);
  render(<MemoryRouter><WorkspaceFrame queue={null} context={null} proof={null} evidenceContent={<a href="https://example.org">Proof source</a>}><h1>PREPARE</h1></WorkspaceFrame></MemoryRouter>);
  await userEvent.click(screen.getByRole('button', { name: /why this decision/i }));
  const source = screen.getByRole('link', { name: 'Proof source' });
  source.focus();
  await userEvent.tab();
  expect(screen.getByRole('button', { name: /close proof/i })).toHaveFocus();
  await userEvent.tab({ shift: true });
  expect(source).toHaveFocus();
});

test('locks background scrolling only while the narrow proof plane is open and restores it on close', async () => {
  vi.stubGlobal('innerWidth', 390);
  document.body.style.overflow = 'auto';
  const view = render(<MemoryRouter><WorkspaceFrame queue={null} context={null} proof={null} evidenceContent={<p>Proof</p>}><h1>PREPARE</h1></WorkspaceFrame></MemoryRouter>);
  await userEvent.click(screen.getByRole('button', { name: /why this decision/i }));
  expect(document.body.style.overflow).toBe('hidden');
  await userEvent.keyboard('{Escape}');
  expect(document.body.style.overflow).toBe('auto');
  await userEvent.click(screen.getByRole('button', { name: /why this decision/i }));
  view.unmount();
  expect(document.body.style.overflow).toBe('auto');
  document.body.style.overflow = '';
});

test('restores proof focus only after the mobile background becomes interactive again', async () => {
  vi.stubGlobal('innerWidth', 390);
  render(<MemoryRouter><WorkspaceFrame queue={null} context={null} proof={null} evidenceContent={<p>Proof</p>}><h1>PREPARE</h1></WorkspaceFrame></MemoryRouter>);
  const trigger = screen.getByRole('button', { name: /why this decision/i });
  await userEvent.click(trigger);
  expect(trigger.closest('[inert]')).not.toBeNull();
  let inertOnFocus: boolean | undefined;
  trigger.addEventListener('focus', () => { inertOnFocus = !!trigger.closest('[inert]'); });
  await userEvent.keyboard('{Escape}');
  expect(inertOnFocus).toBe(false);
  expect(trigger).toHaveFocus();
});

test('separates recorded fixture discovery from evaluated result and unrecorded verification', () => {
  render(<DecisionTrace evaluated discoveryRecorded />);
  const trace = screen.getByRole('list', { name: 'Decision trace' });
  expect(within(trace).getByText('Fixture recorded')).toBeVisible();
  expect(within(trace).getAllByText('Fixture evaluated')).toHaveLength(2);
  expect(within(trace).getByText('Unavailable')).toBeVisible();
});

test('acknowledges existing founder and project context without asking to add them again', async () => {
  const record = { id: 'saved-founder', version: 1, schema_version: '1', provenance: 'USER_ASSERTED', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(url.endsWith('/portfolio')
    ? { founder: record, projects: [{ ...record, id: 'saved-project', name: 'Saved project' }] }
    : { items: [], profile_present: true, page: { offset: 0, limit: 50, total: 0, has_more: false } })));
  mount();
  expect(await screen.findByText('Portfolio context is available. No opportunity decision is selected.')).toBeVisible();
  expect(screen.getByRole('link', { name: /review portfolio/i })).toBeVisible();
  expect(screen.queryByText('Add your profile and a project to establish the context for qualification.')).not.toBeInTheDocument();
});
