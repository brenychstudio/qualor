import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, test, vi } from 'vitest';
import { App } from '../App';

function mount(path = '/inbox') { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); }
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(url.endsWith('/inbox')
    ? { items: [], profile_present: false, page: { offset: 0, limit: 50, total: 0, has_more: false } }
    : url.endsWith('/session') ? { read_only: true, action_token: null }
    : { founder: null, projects: [] })));
});
test('keeps queue, decision, proof and activity in semantic reading order', async () => {
  mount();
  await screen.findByRole('link', { name: /complete profile/i });
  const queue = screen.getByRole('complementary', { name: 'Opportunity inbox' });
  const decision = screen.getByRole('main');
  const proof = screen.getByRole('region', { name: 'Why & proof' });
  const activity = screen.getByRole('complementary', { name: 'Workspace context' });
  expect(queue.compareDocumentPosition(decision) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(decision.compareDocumentPosition(proof) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(proof.compareDocumentPosition(activity) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(decision.closest('.workspace-grid')).toHaveClass('workspace-grid--three-zone');
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
  expect(await screen.findByRole('heading', { name: 'Your foundation.' })).toBeVisible();
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
  const items: import('../generated/domain').InboxItem[] = modes.map(mode => ({
    opportunity_id: `test-${mode}`, version: 1, organizer: 'Test organizer', program_name: 'Test program', edition: 'Test edition',
    best_project: null, deadline: { timezone_status: 'UNKNOWN', values: [] }, effort: null, freshness: 'UNKNOWN',
    human_action_available: false, mode, primary_blocker: null, readiness: null, recommendation: null, run_state: 'COMPLETED',
  }));
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ items, profile_present: true, page: { offset: 0, limit: 50, total: 3, has_more: false } })));
  mount();
  expect(await screen.findByText('LIVE · REPLAY · FIXTURE')).toBeVisible();
  expect(screen.getByText('Local controller connected')).toBeVisible();
});
