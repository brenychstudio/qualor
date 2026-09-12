import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { beforeEach, expect, test, vi } from 'vitest';
import { App } from '../../App';
import type { InboxItem, InboxResponse } from '../../generated/domain';
import { OpportunityInbox } from './OpportunityInbox';

const item = (opportunity_id: string, priority_rank: number, changes: Partial<InboxItem> = {}): InboxItem => ({
  opportunity_id, priority_rank, program_name: `Program ${opportunity_id}`, organizer: 'Studio', edition: '2026',
  discovered_at: '2026-09-01T12:00:00Z', presentation_state: 'EVALUATED', recommendation: 'APPLY',
  best_project: null, deadline: { timezone_status: 'UNKNOWN', values: [] }, effort: null,
  freshness: 'FRESH', human_action_available: false, mode: 'FIXTURE', primary_blocker: null,
  readiness: null, run_state: 'COMPLETED', version: 1, ...changes,
});
const data = (items: InboxItem[], liveResearchAvailable = true): InboxResponse => ({
  items, profile_present: true, live_research_available: liveResearchAvailable,
  page: { offset: 0, limit: 50, total: items.length, has_more: false },
} as InboxResponse);
const rows = () => within(screen.getByRole('list', { name: 'Saved opportunities' })).getAllByRole('link');
const order = () => rows().map(row => within(row).getByText(/^Program /).textContent);
function Location() {
  const location = useLocation(); const navigate = useNavigate();
  return <><span aria-label="Current route">{location.pathname}</span><button onClick={() => navigate(-1)}>Back</button><button onClick={() => navigate(1)}>Forward</button></>;
}
function mount(items: InboxItem[], path = '/inbox') {
  return render(<MemoryRouter initialEntries={[path]}><Location /><Routes><Route path="/inbox/:opportunityId?" element={<OpportunityInbox inbox={data(items)} error={null} />} /></Routes></MemoryRouter>);
}
beforeEach(() => { vi.setSystemTime(new Date('2026-09-09T12:00:00Z')); });

test('offers one deliberate research acquisition control inside the Inbox', () => {
  mount([item('a', 0)]);
  expect(screen.getByRole('button', { name: 'Research opportunity' })).toBeVisible();
});

test('does not offer hosted research when the server has not advertised it', () => {
  render(<MemoryRouter initialEntries={['/inbox']}><Routes><Route path="/inbox" element={<OpportunityInbox inbox={data([], false)} error={null} />} /></Routes></MemoryRouter>);
  expect(screen.queryByRole('button', { name: 'Research opportunity' })).not.toBeInTheDocument();
});

test('default priority follows server ranks even when decision and IDs disagree, with stable identity ties', () => {
  mount([item('a', 9), item('z', 0, { recommendation: 'SKIP' }), item('c', 4), item('b', 4)]);
  expect(order()).toEqual(['Program z', 'Program b', 'Program c', 'Program a']);
  expect(rows().filter(row => row.tabIndex === 0)).toHaveLength(1);
  expect(rows().every(row => !row.hasAttribute('aria-current'))).toBe(true);
});

test('rank orders the queue but never surfaces as a visible score', () => {
  // 04B sharpens the selected row. Rank stays the server's ordering key, never a number the judge can read.
  mount([item('a', 7), item('b', 42)]);
  expect(order()).toEqual(['Program a', 'Program b']);
  for (const row of rows()) {
    expect(row.textContent).not.toMatch(/\b(?:7|42)\b/);
    expect(row.textContent).not.toMatch(/rank|score|priority\s*\d/i);
  }
});

test('deadline sort uses reliable earliest future, unknown/unreliable, then past with server-rank ties', async () => {
  mount([
    item('past-earlier', 4, { deadline: { timezone_status: 'UTC', values: ['2026-09-01T00:00:00Z'] } }),
    item('future-later', 1, { deadline: { timezone_status: 'UTC', values: ['2026-09-12T00:00:00Z'] } }),
    item('unknown', 2), item('calendar', 3, { deadline: { timezone_status: 'CALENDAR_DATE_ONLY', values: ['2026-09-10'] } }),
    item('past-now', 0, { deadline: { timezone_status: 'UTC', values: ['2026-09-09T12:00:00Z'] } }),
    item('future-first', 9, { deadline: { timezone_status: 'UTC', values: ['2026-09-20T00:00:00Z', '2026-09-11T00:00:00Z'] } }),
    item('future-tie', 8, { deadline: { timezone_status: 'UTC', values: ['2026-09-11T02:00:00+02:00'] } }),
  ]);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort opportunities' }), 'DEADLINE');
  expect(order()).toEqual(['Program future-tie', 'Program future-first', 'Program future-later', 'Program unknown', 'Program calendar', 'Program past-now', 'Program past-earlier']);
});

test('newest compares supplied instants and resolves equal instants by rank then identity', async () => {
  mount([item('old', 0), item('z', 3, { discovered_at: '2026-09-05T12:00:00Z' }), item('a', 3, { discovered_at: '2026-09-05T14:00:00+02:00' }), item('b', 1, { discovered_at: '2026-09-05T12:00:00Z' })]);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort opportunities' }), 'NEWEST');
  expect(order()).toEqual(['Program b', 'Program a', 'Program z', 'Program old']);
});

test('newest preserves microseconds before rank and treats equivalent offset instants as ties', async () => {
  mount([
    item('earlier', 0, { discovered_at: '2026-09-05T12:00:00.000001Z' }),
    item('later', 9, { discovered_at: '2026-09-05T12:00:00.000002Z' }),
    item('same-later', 8, { discovered_at: '2026-09-05T14:00:00.000002+02:00' }),
  ]);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort opportunities' }), 'NEWEST');
  expect(order()).toEqual(['Program same-later', 'Program later', 'Program earlier']);
});

test('deadline preserves microseconds within future ordering and across the present boundary', async () => {
  mount([
    item('later', 0, { deadline: { timezone_status: 'UTC', values: ['2026-09-09T12:00:00.000002Z'] } }),
    item('earlier', 9, { deadline: { timezone_status: 'UTC', values: ['2026-09-09T12:00:00.000001Z'] } }),
    item('past', 1, { deadline: { timezone_status: 'UTC', values: ['2026-09-09T12:00:00.000000Z'] } }),
    item('unknown', 2),
    item('same-earlier', 8, { deadline: { timezone_status: 'UTC', values: ['2026-09-09T14:00:00.000001+02:00'] } }),
  ]);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort opportunities' }), 'DEADLINE');
  expect(order()).toEqual(['Program same-earlier', 'Program earlier', 'Program later', 'Program unknown', 'Program past']);
});

const decisions = [
  item('skip', 0, { recommendation: 'SKIP' }), item('watch', 1, { recommendation: 'WATCH' }),
  item('prepare', 2, { recommendation: 'PREPARE' }), item('apply', 3),
  item('review', 4, { presentation_state: 'NEEDS_REVIEW' }),
  item('verifying', 5, { recommendation: null, presentation_state: 'VERIFYING', run_state: 'RUNNING' }),
  item('discovered', 6, { recommendation: null, presentation_state: 'DISCOVERED', run_state: null }),
];
test('decision sort groups persisted recommendations by canonical enum order and keeps unresolved last', async () => {
  mount([...decisions, item('apply-tie', 3)]);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort opportunities' }), 'DECISION');
  expect(order()).toEqual(['Program apply', 'Program apply-tie', 'Program review', 'Program prepare', 'Program watch', 'Program skip', 'Program verifying', 'Program discovered']);
});
test.each([
  ['ALL', ['skip', 'watch', 'prepare', 'apply', 'review', 'verifying', 'discovered']],
  ['APPLY', ['apply']], ['PREPARE', ['prepare']], ['WATCH', ['watch']], ['SKIP', ['skip']],
])('filter %s keeps only the actual evaluated decision, retaining unresolved states in ALL', async (filter, expected) => {
  mount(decisions);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filter opportunities' }), filter);
  expect(order()).toEqual(expected.map(id => `Program ${id}`));
});
test.each([['  pRoGrAm aLPHa  ', 'Program Alpha'], ['  aRtS council ', 'Program Beta']])('search %s matches bounded title/organizer data', async (query, expected) => {
  mount([item('Alpha', 1), item('Beta', 2, { organizer: 'Arts Council' })]);
  await userEvent.type(screen.getByRole('searchbox', { name: 'Search opportunities' }), query);
  expect(order()).toEqual([expected]);
});
test('NO_RESULTS describes only current page search/filter and leaves search focused', async () => {
  mount(decisions);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filter opportunities' }), 'SKIP');
  const search = screen.getByRole('searchbox', { name: 'Search opportunities' });
  await userEvent.type(search, 'missing');
  expect(screen.getByRole('status')).toHaveTextContent('No matches on this page');
  expect(screen.getByRole('status')).toHaveTextContent('Change your search or filter');
  expect(screen.queryByText('No saved opportunities.')).not.toBeInTheDocument();
  expect(search).toHaveFocus();
});
test('direct URL selects matching row; click and back/forward keep URL as selection authority', async () => {
  mount([item('a', 0), item('b', 1)], '/inbox/b');
  expect(rows()[1]).toHaveAttribute('aria-current', 'true');
  await userEvent.click(rows()[0]);
  expect(screen.getByLabelText('Current route')).toHaveTextContent('/inbox/a');
  expect(rows()[0]).toHaveAttribute('aria-current', 'true');
  await userEvent.click(screen.getByRole('button', { name: 'Back' }));
  expect(rows()[1]).toHaveAttribute('aria-current', 'true');
  await userEvent.click(screen.getByRole('button', { name: 'Forward' }));
  expect(rows()[0]).toHaveAttribute('aria-current', 'true');
});
test('missing selected ID and filtered selection do not select a substitute or rewrite the URL', async () => {
  mount(decisions, '/inbox/absent');
  expect(screen.getByText('Selected opportunity is not on this page.')).toBeVisible();
  expect(rows().every(row => !row.hasAttribute('aria-current'))).toBe(true);
  await userEvent.click(rows()[0]);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filter opportunities' }), 'APPLY');
  expect(screen.getByLabelText('Current route')).toHaveTextContent('/inbox/skip');
  expect(screen.getByText('Selected opportunity is hidden by your search or filter.')).toBeVisible();
  expect(rows()[0]).not.toHaveAttribute('aria-current');
  expect(rows()[0]).toHaveAttribute('tabindex', '0');
});
test.each(['default', 'filter', 'search'])('roving keyboard uses only the visible %s domain and updates URL', async (mode) => {
  mount([item('a', 0), item('b', 1, { recommendation: 'SKIP', organizer: 'Other' }), item('c', 2), item('d', 3)]);
  if (mode === 'filter') await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filter opportunities' }), 'APPLY');
  if (mode === 'search') await userEvent.type(screen.getByRole('searchbox', { name: 'Search opportunities' }), 'Studio');
  act(() => rows()[0].focus());
  await userEvent.keyboard('{ArrowDown}');
  expect(rows()[1]).toHaveFocus(); expect(rows()[1]).toHaveAttribute('aria-current', 'true');
  expect(screen.getByLabelText('Current route')).toHaveTextContent(mode === 'default' ? '/inbox/b' : '/inbox/c');
  await userEvent.keyboard('{End}'); expect(rows().at(-1)).toHaveFocus();
  await userEvent.keyboard('{ArrowUp}'); expect(rows().at(-2)).toHaveFocus();
  await userEvent.keyboard('{Home}'); expect(rows()[0]).toHaveFocus();
  await userEvent.keyboard('{ArrowUp}'); expect(rows()[0]).toHaveFocus();
  expect(rows().filter(row => row.tabIndex === 0)).toHaveLength(1);
});
test('sort controls keep focus and retain the selected row as the roving entry point', async () => {
  mount(decisions, '/inbox/skip');
  const sort = screen.getByRole('combobox', { name: 'Sort opportunities' });
  await userEvent.selectOptions(sort, 'DECISION');
  expect(sort).toHaveFocus();
  expect(rows().find(row => row.tabIndex === 0)).toHaveAttribute('aria-current', 'true');
});
test('rows preserve server review, partial, stale and unknown truth alongside the unchanged recommendation', () => {
  const original = item('review', 0, { presentation_state: 'NEEDS_REVIEW', freshness: 'STALE', run_state: 'PARTIAL' });
  mount([original, item('discovered', 1, { recommendation: null, freshness: 'UNKNOWN', presentation_state: 'DISCOVERED' })]);
  const review = within(rows()[0]);
  for (const label of ['APPLY', 'NEEDS REVIEW', 'PARTIAL', 'STALE', 'Project unresolved', 'Deadline unknown']) expect(review.getByText(label)).toBeVisible();
  expect(review.queryByText(/best fit|PASS|EVALUATED/)).not.toBeInTheDocument();
  expect(within(rows()[1]).getByText('Decision unresolved')).toBeVisible();
  expect(within(rows()[1]).getByText('Freshness unknown')).toBeVisible();
  expect(original.recommendation).toBe('APPLY');
});
test('shows the explicitly supplied project and date-only timezone limitation', () => {
  mount([item('known', 0, { best_project: { id: 'p', name: 'Actual project', version: 1 }, deadline: { timezone_status: 'CALENDAR_DATE_ONLY', values: ['2026-09-12'] } })]);
  expect(within(rows()[0]).getByText('Actual project')).toBeVisible();
  expect(within(rows()[0]).getByText(/2026-09-12.*time unknown/)).toBeVisible();
});
test('shell reuses its bounded Inbox read while selection/search changes, preserving keyboard focus', async () => {
  let inboxReads = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/inbox')) { inboxReads++; return Response.json(data([item('a', 0), item('b', 1)])); }
    return Response.json({ founder: null, projects: [] });
  }));
  render(<MemoryRouter initialEntries={['/inbox']}><App /></MemoryRouter>);
  await screen.findByRole('link', { name: /Program a/ });
  await userEvent.click(rows()[0]);
  await userEvent.keyboard('{ArrowDown}');
  expect(rows()[1]).toHaveFocus(); expect(rows()[1]).toHaveAttribute('aria-current', 'true');
  await userEvent.type(screen.getByRole('searchbox', { name: 'Search opportunities' }), 'Program');
  expect(inboxReads).toBe(1);
});
