import { useState } from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, renderHook, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { App } from '../App';
import type { InboxItem, InboxResponse, OpportunityWorkspaceResponse } from '../generated/domain';
import { useFocusReturn } from './useFocusReturn';
import { useReducedMotion } from './useReducedMotion';

const page = { offset: 0, limit: 50, total: 0, has_more: false };
const CANONICAL_WIDTHS = [320, 768, 1024, 1440];

function inboxItem(id: string, rank: number): InboxItem {
  return {
    opportunity_id: id,
    priority_rank: rank,
    program_name: `Programme ${id}`,
    organizer: 'Recorded organizer',
    edition: '2026',
    discovered_at: '2026-09-01T12:00:00Z',
    presentation_state: 'EVALUATED',
    recommendation: 'APPLY',
    best_project: { id: 'project-1', name: 'Recorded project', version: 1 },
    deadline: { timezone_status: 'UTC', values: ['2026-09-14T17:00:00Z'] },
    effort: null,
    freshness: 'FRESH',
    human_action_available: true,
    mode: 'FIXTURE',
    primary_blocker: null,
    readiness: null,
    run_state: 'COMPLETED',
    version: 1,
  } as unknown as InboxItem;
}

function inbox(): InboxResponse {
  const items = [inboxItem('one', 0), inboxItem('two', 1), inboxItem('three', 2)];
  return {
    items,
    profile_present: true,
    page: { ...page, total: items.length },
    product_state: null,
  } as unknown as InboxResponse;
}

function workspace(): OpportunityWorkspaceResponse {
  return {
    opportunity_id: 'one',
    version: 1,
    program_name: 'Programme one',
    organizer: 'Recorded organizer',
    edition: '2026',
    presentation_state: 'EVALUATED',
    run_state: 'COMPLETED',
    mode: 'FIXTURE',
    freshness: 'FRESH',
    last_refresh_failed_at: null,
    rewards: [],
    coverage: [],
    run_ids: [],
    runs_page: page,
    approvals: [],
    approvals_page: page,
    product_state: {
      state: 'STALE_EVIDENCE', primary_action: 'REFRESH_EVIDENCE', reason: null,
      evidence_available: true, approval_available: false, draft_pack_available: false,
      coverage_complete: true, recommendation_visible: true, pack_id: null,
    },
    decision: {
      decision_id: 'decision-1',
      decision_version: 2,
      recommendation: 'APPLY',
      summary: 'The recorded rules and project facts support this decision.',
      reason_codes: [],
      strategy: { state: 'AVAILABLE', score: 82, semantics: 'PRIORITIZATION_NOT_WIN_PROBABILITY', breakdown: [], missing_factors: [] },
      best_project: { id: 'project-1', name: 'Recorded project', version: 1 },
      eligibility: 'PASS',
      effort: null,
      deadline: { timezone_status: 'UTC', values: ['2026-09-14T17:00:00Z'] },
      readiness: null,
      freshness: 'FRESH',
      primary_blocker: null,
      missing_information: [],
      primary_action: { available: true, reason: 'VALID', approval_request: null },
    },
  } as unknown as OpportunityWorkspaceResponse;
}

function evidenceSheet() {
  return {
    opportunity_id: 'one',
    opportunity_version: 1,
    freshness: 'FRESH',
    coverage: [],
    claims: [{ rule_id: 'r_entrant_type', state: 'PASS', reason_codes: [], evidence_refs: ['evidence-1'] }],
    claims_page: page,
    proofs: [{
      category: 'ENTRANT_TYPE', domain: 'official-domain.example', evidence_id: 'evidence-1',
      evidence_version: 1, excerpt: 'Applicants must be incorporated in the region.',
      freshness: 'FRESH', original_url: 'https://official-domain.example/rules',
      retrieved_at: '2026-09-08T09:15:00Z', source_id: 'source-1', source_type: 'OFFICIAL_RULES',
      source_version: 'v1', url: 'https://official-domain.example/rules',
    }],
    proofs_page: page,
    eligibility: { evaluated_at: '2026-09-08T10:00:00Z', policy_version: 1, state: 'PASS' },
    project_fit: { blocking_gaps: [], evaluated_at: null, factor_results: [], match_status: 'STRONG', matched_requirement_refs: [], missing_facts: [], policy_version: 1, project: null },
    constraints_conflicts: { checked_rule_categories: [], evaluated_at: null, evidence_refs: [], founder_constraints: [], missing_rule_categories: [], policy_version: 1, reasons: [], status: 'NO_CONFLICT_DETECTED_IN_CHECKED_RULES' },
    reward_deadline: { deadline: { timezone_status: 'UTC', values: [] }, evidence_refs: [], rewards: [] },
  };
}

function stub() {
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.endsWith('/inbox')) return Response.json(inbox());
    if (url.includes('/workspace')) return Response.json(workspace());
    if (url.includes('/evidence')) return Response.json(evidenceSheet());
    if (url.includes('/runs')) return Response.json({ runs: [], events: [], runs_page: page, events_page: page });
    if (url.endsWith('/session')) return Response.json({ read_only: false, action_token: 'test-token' });
    return Response.json({ founder: null, projects: [] });
  }));
}

function openWorkspace(width = 1440, path = '/inbox/one') {
  vi.stubGlobal('innerWidth', width);
  stub();
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

// --- landmarks and headings --------------------------------------------------------------

test('the workspace exposes its regions as semantic landmarks', async () => {
  openWorkspace();
  await screen.findByRole('banner');
  expect(screen.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  expect(screen.getByRole('main')).toBeVisible();
  expect(screen.getByRole('complementary', { name: 'Opportunity inbox' })).toBeVisible();
  expect(screen.getByRole('complementary', { name: 'Workspace context' })).toBeVisible();
});

test('every landmark carries an accessible name so regions are distinguishable', async () => {
  openWorkspace();
  await screen.findByRole('banner');
  for (const landmark of screen.getAllByRole('complementary')) {
    expect(landmark).toHaveAccessibleName();
  }
  for (const region of screen.getAllByRole('region')) {
    expect(region).toHaveAccessibleName();
  }
});

test('a decision view has exactly one first-level heading', async () => {
  const { container } = openWorkspace();
  await screen.findByRole('heading', { name: 'APPLY', level: 1 });
  expect(container.querySelectorAll('h1')).toHaveLength(1);
});

test('the application pack document has exactly one first-level heading', async () => {
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.includes('/draft-packs/')) return Response.json({ code: 'NOT_FOUND' }, { status: 404 });
    if (url.endsWith('/inbox')) return Response.json(inbox());
    if (url.includes('/runs')) return Response.json({ runs: [], events: [], runs_page: page, events_page: page });
    return Response.json({ founder: null, projects: [] });
  }));
  const { container } = render(<MemoryRouter initialEntries={['/draft-packs/pack-1']}><App /></MemoryRouter>);
  await screen.findByRole('heading', { name: /application pack unavailable/i });
  expect(container.querySelectorAll('h1')).toHaveLength(1);
});

test('heading levels never skip a level anywhere in the workspace', async () => {
  const { container } = openWorkspace();
  await screen.findByRole('heading', { name: 'APPLY', level: 1 });
  const levels = [...container.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(node => Number(node.tagName[1]));
  let previous = levels[0];
  for (const level of levels) {
    expect(level - previous).toBeLessThanOrEqual(1);
    previous = Math.max(previous, level);
  }
});

// --- keyboard ----------------------------------------------------------------------------

test('primary navigation is reachable and operable from the keyboard', async () => {
  openWorkspace();
  await screen.findByRole('banner');
  const nav = screen.getByRole('navigation', { name: 'Primary' });
  for (const label of ['Inbox', 'Portfolio', 'Activity']) {
    const link = within(nav).getByRole('link', { name: label });
    link.focus();
    expect(link).toHaveFocus();
  }
});

test('a skip link lets keyboard users reach the workspace directly', async () => {
  openWorkspace();
  await screen.findByRole('banner');
  const skip = screen.getByRole('link', { name: /skip to workspace/i });
  expect(skip).toHaveAttribute('href', '#decision');
  expect(screen.getByRole('main')).toHaveAttribute('id', 'decision');
});

test('exactly one opportunity row takes part in normal Tab order at every width', async () => {
  for (const width of CANONICAL_WIDTHS) {
    const view = openWorkspace(width);
    await screen.findAllByRole('link', { name: /Programme one/ });
    const queue = screen.getByRole('complementary', { name: 'Opportunity inbox' });
    const rows = within(queue).getAllByRole('link').filter(row => row.classList.contains('opportunity-row'));
    expect(rows.filter(row => row.getAttribute('tabindex') === '0')).toHaveLength(1);
    view.unmount();
  }
});

test('arrow, Home and End move roving focus deterministically', async () => {
  openWorkspace();
  await screen.findAllByRole('link', { name: /Programme one/ });
  const queue = screen.getByRole('complementary', { name: 'Opportunity inbox' });
  const rows = within(queue).getAllByRole('link').filter(row => row.classList.contains('opportunity-row'));
  rows[0].focus();
  await userEvent.keyboard('{ArrowDown}');
  expect(rows[1]).toHaveFocus();
  await userEvent.keyboard('{End}');
  expect(rows.at(-1)).toHaveFocus();
  await userEvent.keyboard('{Home}');
  expect(rows[0]).toHaveFocus();
  await userEvent.keyboard('{ArrowUp}');
  expect(rows[0]).toHaveFocus();
});

test('every control in the workspace has an accessible name', async () => {
  openWorkspace();
  await screen.findByRole('heading', { name: 'APPLY', level: 1 });
  for (const control of [...screen.getAllByRole('button'), ...screen.getAllByRole('link')]) {
    expect(control).toHaveAccessibleName();
  }
});

test('every control in the proof layer has an accessible name', async () => {
  openWorkspace();
  await userEvent.click(await screen.findByRole('button', { name: /why this decision/i }));
  const plane = await screen.findByRole('region', { name: 'Decision proof' });
  for (const control of [...within(plane).getAllByRole('button'), ...within(plane).getAllByRole('link')]) {
    expect(control).toHaveAccessibleName();
  }
});

test('recorded activity timestamps carry their full machine-readable instant', async () => {
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.includes('/runs')) return Response.json({
      runs: [], events: [{
        run_id: 'run-1', sequence: 1, event_type: 'SEARCH_REQUESTED', mode: 'FIXTURE',
        occurred_at: '2026-09-09T12:41:00Z', reason_code: 'SEARCH_STARTED', phase: 'DISCOVERING',
        count: 0, source_ids: [], evidence_ids: [], estimated_cost_usd: null, reported_cost_usd: null,
      }], runs_page: page, events_page: page,
    });
    if (url.endsWith('/inbox')) return Response.json(inbox());
    return Response.json({ founder: null, projects: [] });
  }));
  render(<MemoryRouter initialEntries={['/inbox']}><App /></MemoryRouter>);
  const timeline = await screen.findByRole('list', { name: /recorded activity/i });
  const stamp = within(timeline).getByText('12:41');
  expect(stamp.tagName).toBe('TIME');
  expect(stamp).toHaveAttribute('datetime', '2026-09-09T12:41:00Z');
});

test('the decision primary action is reachable and named', async () => {
  openWorkspace();
  const action = await screen.findByRole('button', { name: 'Approve application' });
  action.focus();
  expect(action).toHaveFocus();
  expect(action).toBeEnabled();
});

// --- evidence sheet focus ----------------------------------------------------------------

test('the evidence sheet takes focus, traps it, and returns it to its trigger', async () => {
  openWorkspace(320);
  const trigger = await screen.findByRole('button', { name: /why this decision/i });
  await userEvent.click(trigger);
  const plane = await screen.findByRole('region', { name: 'Decision proof' });
  await waitFor(() => expect(plane).toHaveFocus());

  const close = screen.getByRole('button', { name: /close proof/i });
  close.focus();
  await userEvent.tab({ shift: true });
  expect(plane.contains(document.activeElement)).toBe(true);

  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('region', { name: 'Decision proof' })).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

test('the evidence sheet locks background scrolling only while it is narrow and open', async () => {
  const view = openWorkspace(320);
  const trigger = await screen.findByRole('button', { name: /why this decision/i });
  await userEvent.click(trigger);
  await screen.findByRole('region', { name: 'Decision proof' });
  expect(view.baseElement.style.overflow).toBe('hidden');
  await userEvent.keyboard('{Escape}');
  expect(view.baseElement.style.overflow).not.toBe('hidden');
});

// --- status is never carried by colour alone ---------------------------------------------

test('the recommendation is readable as text, not only as a tone', async () => {
  openWorkspace();
  expect(await screen.findByRole('heading', { name: 'APPLY', level: 1 })).toBeVisible();
  expect(screen.getByText('Recommendation: APPLY')).toBeVisible();
});

test('runtime mode, presentation state and freshness all appear as words', async () => {
  openWorkspace();
  await screen.findByRole('heading', { name: 'APPLY', level: 1 });
  const operational = screen.getByLabelText('Current decision state');
  expect(operational).toHaveTextContent('FIXTURE');
  expect(operational).toHaveTextContent('EVALUATED');
  expect(operational).toHaveTextContent('FRESH');
});

test('the product state names itself in words', async () => {
  openWorkspace();
  await screen.findByRole('heading', { name: 'APPLY', level: 1 });
  const state = screen.getByRole('status', { name: /workspace state/i });
  expect(within(state).getByText('STALE_EVIDENCE')).toBeVisible();
});

test('evidence claim states are spelled out in the proof layer', async () => {
  openWorkspace();
  await userEvent.click(await screen.findByRole('button', { name: /why this decision/i }));
  const eligibility = await screen.findByRole('region', { name: 'Eligibility' });
  expect(within(eligibility).getAllByText('PASS').length).toBeGreaterThan(0);
});

// --- reduced motion ----------------------------------------------------------------------

test('useReducedMotion reports the browser preference', () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener() {}, removeEventListener() {} })));
  const { result } = renderHook(() => useReducedMotion());
  expect(result.current).toBe(true);
});

test('useReducedMotion reports no preference when the browser reports none', () => {
  const { result } = renderHook(() => useReducedMotion());
  expect(result.current).toBe(false);
});

test('the workspace marks reduced motion without changing what it says', async () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener() {}, removeEventListener() {} })));
  openWorkspace();
  await screen.findByRole('heading', { name: 'APPLY', level: 1 });
  expect(screen.getByRole('banner').parentElement).toHaveClass('reduce-motion');
  expect(screen.getByText('Recommendation: APPLY')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Approve application' })).toBeEnabled();
});

// --- focus return hook -------------------------------------------------------------------

function FocusReturnHarness() {
  const [open, setOpen] = useState(false);
  useFocusReturn(open);
  return <>
    <button type="button" onClick={() => setOpen(true)}>Open layer</button>
    {open && <button type="button" onClick={() => setOpen(false)}>Close layer</button>}
  </>;
}

test('useFocusReturn restores focus to the element that opened a layer', async () => {
  render(<FocusReturnHarness />);
  const open = screen.getByRole('button', { name: 'Open layer' });
  open.focus();
  await userEvent.click(open);
  await userEvent.click(screen.getByRole('button', { name: 'Close layer' }));
  await waitFor(() => expect(open).toHaveFocus());
});

// --- responsive projection ---------------------------------------------------------------

test.each(CANONICAL_WIDTHS)('every workspace region is present at %ipx', async width => {
  openWorkspace(width);
  await screen.findByRole('heading', { name: 'APPLY', level: 1 });
  expect(screen.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  expect(screen.getByRole('complementary', { name: 'Opportunity inbox' })).toBeVisible();
  expect(screen.getByRole('main')).toBeVisible();
  expect(screen.getByRole('complementary', { name: 'Workspace context' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Approve application' })).toBeVisible();
  expect(screen.getByRole('button', { name: /why this decision/i })).toBeVisible();
});

test('the reading order of the workspace is identical at 320 and 1440', async () => {
  const order = async (width: number) => {
    const view = openWorkspace(width);
    await screen.findByRole('heading', { name: 'APPLY', level: 1 });
    const landmarks = [...view.container.querySelectorAll('header, nav, aside, main')]
      .map(node => node.getAttribute('aria-label') ?? node.tagName.toLowerCase());
    view.unmount();
    return landmarks;
  };
  expect(await order(320)).toEqual(await order(1440));
});

test('no consequential action is removed at the narrowest canonical width', async () => {
  openWorkspace(320);
  await screen.findByRole('heading', { name: 'APPLY', level: 1 });
  expect(screen.getByRole('button', { name: 'Approve application' })).toBeVisible();
  expect(screen.getByRole('button', { name: /why this decision/i })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Activity' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Portfolio' })).toBeVisible();
});

test('the inbox never renders a duplicate tabbable representation of one opportunity', async () => {
  for (const width of CANONICAL_WIDTHS) {
    const view = openWorkspace(width);
    await screen.findAllByRole('link', { name: /Programme one/ });
    const matching = screen.getAllByRole('link', { name: /Programme one/ });
    expect(matching).toHaveLength(1);
    view.unmount();
  }
});

// --- contrast ----------------------------------------------------------------------------

const TOKENS = (() => {
  const source = readFileSync(resolve(process.cwd(), 'src/styles/tokens.css'), 'utf8');
  return Object.fromEntries([...source.matchAll(/--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})/g)].map(m => [m[1], m[2]]));
})();

function relativeLuminance(hex: string) {
  const channel = (value: number) => {
    const c = value / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(foreground: string, background: string) {
  const [a, b] = [relativeLuminance(foreground), relativeLuminance(background)];
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

test.each([
  ['text-primary', 'workspace'],
  ['text-secondary', 'workspace'],
  ['text-muted', 'workspace'],
  ['text-primary', 'surface-canvas'],
  ['text-secondary', 'surface-canvas'],
  ['text-muted', 'surface-canvas'],
  ['text-primary', 'surface-raised'],
  ['text-secondary', 'surface-raised'],
  ['text-muted', 'surface-raised'],
  ['proof-ink', 'proof-paper'],
  ['proof-citation', 'proof-paper'],
  ['proof-muted', 'proof-paper'],
  ['citation', 'surface-canvas'],
])('%s on %s meets WCAG AA for normal text', (foreground, background) => {
  expect(TOKENS[foreground]).toBeDefined();
  expect(TOKENS[background]).toBeDefined();
  expect(contrastRatio(TOKENS[foreground], TOKENS[background])).toBeGreaterThanOrEqual(4.5);
});

test.each([
  ['recommendation-apply', 'surface-canvas'],
  ['recommendation-prepare', 'surface-canvas'],
  ['recommendation-watch', 'surface-canvas'],
  ['recommendation-skip', 'surface-canvas'],
])('the %s tone stays legible without carrying the meaning alone', (tone, background) => {
  expect(contrastRatio(TOKENS[tone], TOKENS[background])).toBeGreaterThanOrEqual(4.5);
});

test.each([['focus', 'workspace'], ['focus', 'surface-canvas'], ['focus', 'surface-raised']])(
  'the %s indicator is clearly visible against %s',
  (indicator, background) => {
    expect(contrastRatio(TOKENS[indicator], TOKENS[background])).toBeGreaterThanOrEqual(3);
  },
);

test('a visible focus treatment is defined and never simply removed', () => {
  const base = readFileSync(resolve(process.cwd(), 'src/styles/base.css'), 'utf8');
  expect(base).toMatch(/:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--focus\)/);
  const suppressed = [...base.matchAll(/([^{}]+)\{[^}]*outline:\s*none[^}]*\}/g)].map(m => m[1].trim());
  // Only containers that receive programmatic focus may suppress the ring; controls never do.
  for (const selector of suppressed) expect(selector).toMatch(/:focus$/);
});
