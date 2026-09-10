import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { App } from '../../App';
import type {
  DeadlineView,
  InboxItem,
  InboxResponse,
  OpportunityWorkspaceResponse,
  Recommendation,
  RunState,
} from '../../generated/domain';
import { DecisionCanvas } from './DecisionCanvas';

const page = { offset: 0, limit: 50, total: 0, has_more: false };

function workspace(changes: Partial<OpportunityWorkspaceResponse> = {}): OpportunityWorkspaceResponse {
  const base: OpportunityWorkspaceResponse = {
    opportunity_id: 'opportunity-authoritative',
    version: 3,
    program_name: 'Authoritative opportunity',
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
      state: null, primary_action: null, reason: null,
      evidence_available: true, approval_available: true, draft_pack_available: false,
      coverage_complete: true, recommendation_visible: true, pack_id: null,
    },
    decision: {
      decision_id: 'decision-1',
      decision_version: 2,
      recommendation: 'APPLY',
      summary: 'The recorded rules and project facts support this decision.',
      reason_codes: ['POLICY_RULE_3'],
      strategy: {
        state: 'AVAILABLE',
        score: 82,
        semantics: 'PRIORITIZATION_NOT_WIN_PROBABILITY',
        breakdown: [],
        missing_factors: [],
      },
      best_project: { id: 'project-1', name: 'Recorded project', version: 4 },
      eligibility: 'PASS',
      effort: {
        adaptation_range: null,
        breakdown: [],
        evaluated_at: '2026-09-09T12:00:00Z',
        min_total: '8',
        max_total: '14',
        missing_information: [],
        reasons: ['Recorded estimate'],
        policy_version: 1,
      },
      deadline: { timezone_status: 'UTC', values: ['2026-09-14T17:00:00Z'] },
      readiness: {
        evaluated_at: '2026-09-09T12:00:00Z',
        factor_results: [],
        gaps: ['REPOSITORY', 'DEMO'],
        missing_information: [],
        policy_version: 1,
        state: 'GAPS_EXECUTABLE',
      },
      freshness: 'FRESH',
      primary_blocker: 'repository_publication',
      missing_information: [],
      primary_action: { available: true, reason: 'VALID', approval_request: null },
    },
  };
  return { ...base, ...changes, decision: { ...base.decision, ...changes.decision } };
}

function inboxItem(opportunity_id: string, priority_rank: number): InboxItem {
  return {
    opportunity_id,
    priority_rank,
    program_name: `Program ${opportunity_id}`,
    organizer: 'Recorded organizer',
    edition: '2026',
    discovered_at: '2026-09-01T12:00:00Z',
    presentation_state: 'EVALUATED',
    recommendation: 'APPLY',
    best_project: { id: `project-${opportunity_id}`, name: `Project ${opportunity_id}`, version: 1 },
    deadline: { timezone_status: 'UTC', values: ['2026-09-14T17:00:00Z'] },
    effort: null,
    freshness: 'FRESH',
    human_action_available: true,
    mode: 'FIXTURE',
    primary_blocker: null,
    readiness: null,
    run_state: 'COMPLETED',
    version: 1,
  };
}

function inbox(items: InboxItem[]): InboxResponse {
  return { items, profile_present: true, page: { ...page, total: items.length } };
}

const primaryActions = () => screen.queryAllByRole('button').filter(button => button.hasAttribute('data-primary-action'));

test.each([
  ['APPLY', 'Approve application', true],
  ['PREPARE', 'Approve preparation', true],
  ['WATCH', 'Resolve unknowns', false],
  ['SKIP', 'Review rejection', false],
] satisfies [Recommendation, string, boolean][])('%s preserves the recommendation and exact primary action', async (recommendation, label, approvalAvailable) => {
  const onPrimaryAction = vi.fn();
  render(<DecisionCanvas workspace={workspace({ decision: { ...workspace().decision, recommendation, primary_action: { available: approvalAvailable, reason: approvalAvailable ? 'VALID' : 'DECISION_NOT_ACTIONABLE', approval_request: null } } })} onPrimaryAction={onPrimaryAction} />);
  expect(screen.getByRole('heading', { name: recommendation, level: 1 })).toBeVisible();
  expect(screen.getByText(`Recommendation: ${recommendation}`)).toBeVisible();
  const action = screen.getByRole('button', { name: label });
  expect(primaryActions()).toHaveLength(1);
  await userEvent.click(action);
  expect(onPrimaryAction).toHaveBeenCalledWith(recommendation);
});

test('unknown Strategy stays unresolved and never becomes zero or probability language', () => {
  render(<DecisionCanvas workspace={workspace({ decision: { ...workspace().decision, strategy: { state: 'NOT_ENOUGH_EVIDENCE', score: null, breakdown: [], missing_factors: ['strategic_value'] } } })} />);
  const strategy = screen.getByRole('group', { name: 'Strategy priority' });
  expect(within(strategy).getByText('Not enough evidence')).toBeVisible();
  expect(within(strategy).queryByText(/^0(?:%|\s*\/\s*100)?$/)).not.toBeInTheDocument();
  expect(strategy).toHaveTextContent('prioritization');
  expect(strategy).not.toHaveTextContent(/win probability|chance/i);
});

test('unresolved project and typed effort truth never receive synthetic substitutes', () => {
  render(<DecisionCanvas workspace={workspace({
    program_name: 'Production-only record',
    decision: { ...workspace().decision, best_project: null, effort: null },
  })} />);
  expect(screen.getByRole('heading', { name: 'Production-only record' })).toBeVisible();
  expect(within(screen.getByRole('group', { name: 'Decision signals' })).getByText('Unresolved')).toBeVisible();
  expect(screen.getByText('Effort unavailable')).toBeVisible();
  expect(screen.queryByText(/synthetic|71|QUALOR/i)).not.toBeInTheDocument();
});

test.each([
  ['8', '14', '8\u201314 h'],
  ['9.5', '9.5', '9.5 h'],
] as const)('renders the exact typed effort range %s to %s', (min, max, expected) => {
  render(<DecisionCanvas workspace={workspace({ decision: { ...workspace().decision, effort: { ...workspace().decision.effort!, min_total: min, max_total: max } } })} />);
  expect(screen.getByText(expected)).toBeVisible();
});

test.each([
  [{ timezone_status: 'UTC', values: ['2026-09-14T17:00:00Z'] }, '14 Sep 2026', '17:00 UTC'],
  [{ timezone_status: 'CALENDAR_DATE_ONLY', values: ['2026-09-14'] }, '14 Sep 2026', 'Time unknown \u00b7 date only'],
  [{ timezone_status: 'UNKNOWN', values: [] }, 'UNKNOWN', 'Deadline unavailable'],
] satisfies [DeadlineView, string, string][])('renders deadline truth for $0.timezone_status', (deadline, date, detail) => {
  render(<DecisionCanvas workspace={workspace({ decision: { ...workspace().decision, deadline } })} />);
  const deadlineFact = screen.getByRole('group', { name: 'Deadline' });
  expect(within(deadlineFact).getByText(date)).toBeVisible();
  expect(within(deadlineFact).getByText(detail)).toBeVisible();
});

test('uses the earliest valid authoritative UTC instant when deadline values are unsorted', () => {
  render(<DecisionCanvas workspace={workspace({ decision: {
    ...workspace().decision,
    deadline: { timezone_status: 'UTC', values: ['2026-09-20T17:00:00Z', 'not-a-date', '2026-09-12T09:30:00Z'] },
  } })} />);
  const deadlineFact = screen.getByRole('group', { name: 'Deadline' });
  expect(within(deadlineFact).getByText('12 Sep 2026')).toBeVisible();
  expect(within(deadlineFact).getByText('09:30 UTC')).toBeVisible();
});

test('uses the earliest represented calendar date for mixed date-only deadline values', () => {
  render(<DecisionCanvas workspace={workspace({ decision: {
    ...workspace().decision,
    deadline: { timezone_status: 'CALENDAR_DATE_ONLY', values: ['2026-09-20', '2026-09-12T23:30:00-07:00', '2026-09-14'] },
  } })} />);
  const deadlineFact = screen.getByRole('group', { name: 'Deadline' });
  expect(within(deadlineFact).getByText('12 Sep 2026')).toBeVisible();
  expect(within(deadlineFact).getByText('Time unknown · date only')).toBeVisible();
  expect(deadlineFact).not.toHaveTextContent(/23:30|UTC/);
});

test('uses server deadline reason for a passed deadline without calculating a new policy state', () => {
  render(<DecisionCanvas workspace={workspace({ decision: { ...workspace().decision, primary_action: { available: false, reason: 'DEADLINE_PASSED', approval_request: null } } })} />);
  expect(within(screen.getByRole('group', { name: 'Deadline' })).getByText('Passed')).toBeVisible();
  expect(primaryActions()).toHaveLength(0);
});

test('NEEDS_REVIEW preserves APPLY while unavailable approval stays absent', () => {
  render(<DecisionCanvas workspace={workspace({
    presentation_state: 'NEEDS_REVIEW',
    freshness: 'STALE',
    decision: { ...workspace().decision, recommendation: 'APPLY', freshness: 'STALE', primary_action: { available: false, reason: 'EVIDENCE_CHANGED', approval_request: null } },
  })} />);
  expect(screen.getByRole('heading', { name: 'APPLY', level: 1 })).toBeVisible();
  expect(screen.getByText('Presentation state: NEEDS REVIEW')).toBeVisible();
  expect(screen.getByText('Freshness: STALE')).toBeVisible();
  expect(screen.getByText('Action state: EVIDENCE CHANGED')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Approve application' })).not.toBeInTheDocument();
  expect(primaryActions()).toHaveLength(0);
});

test.each([
  ['CREATED', 'VERIFYING'],
  ['RUNNING', 'VERIFYING'],
  ['PARTIAL', 'NEEDS_REVIEW'],
  ['FAILED', 'NEEDS_REVIEW'],
  ['CANCELLED', 'NEEDS_REVIEW'],
  ['BUDGET_STOPPED', 'NEEDS_REVIEW'],
] satisfies [RunState, OpportunityWorkspaceResponse['presentation_state']][])('current %s run remains visible and blocks the old approval affordance', (run_state, presentation_state) => {
  render(<DecisionCanvas workspace={workspace({ run_state, presentation_state })} />);
  expect(screen.getByText(`Run state: ${run_state.replaceAll('_', ' ')}`)).toBeVisible();
  expect(screen.getByRole('heading', { name: 'APPLY', level: 1 })).toBeVisible();
  expect(primaryActions()).toHaveLength(0);
});

test('completed current run exposes the authoritative action', () => {
  render(<DecisionCanvas workspace={workspace()} />);
  expect(screen.getByText('Run state: COMPLETED')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Approve application' })).toBeVisible();
});

test.each(['FIXTURE', 'REPLAY', 'LIVE'] as const)('renders server mode %s explicitly', mode => {
  render(<DecisionCanvas workspace={workspace({ mode })} />);
  expect(screen.getByText(`Research mode: ${mode}`)).toBeVisible();
});

test('null mode remains unavailable and LOCAL never implies LIVE', () => {
  render(<DecisionCanvas workspace={workspace({ mode: null, run_state: null, presentation_state: 'DISCOVERED', decision: { ...workspace().decision, recommendation: null } })} />);
  expect(screen.getByText('Research mode: Unavailable')).toBeVisible();
  expect(screen.queryByText('Research mode: LIVE')).not.toBeInTheDocument();
});

test('unresolved recommendation, eligibility and readiness remain explicit and render no primary action', () => {
  render(<DecisionCanvas workspace={workspace({ decision: {
    ...workspace().decision,
    recommendation: null,
    summary: null,
    eligibility: null,
    readiness: null,
    primary_action: { available: false, reason: 'DECISION_NOT_ACTIONABLE', approval_request: null },
  } })} />);
  expect(screen.getByRole('heading', { name: 'UNKNOWN', level: 1 })).toBeVisible();
  expect(screen.getByText('No deterministic decision reason is available.')).toBeVisible();
  expect(screen.getByText('Eligibility unresolved')).toBeVisible();
  expect(screen.getByText('Readiness unavailable')).toBeVisible();
  expect(primaryActions()).toHaveLength(0);
});

test('readiness keeps exact gap count, blocker and unresolved information visible', () => {
  render(<DecisionCanvas workspace={workspace({ decision: { ...workspace().decision, missing_information: ['license_intent'] } })} />);
  expect(screen.getByText('2 gaps')).toBeVisible();
  expect(screen.getByText('GAPS EXECUTABLE')).toBeVisible();
  expect(screen.getByText('Primary blocker: repository publication')).toBeVisible();
  expect(screen.getByText('Missing information: license intent')).toBeVisible();
});

test('Decision Trace keeps five named stages and does not fabricate completion for an incomplete current run', () => {
  render(<DecisionCanvas workspace={workspace({ run_state: 'PARTIAL', presentation_state: 'NEEDS_REVIEW' })} />);
  const trace = screen.getByRole('list', { name: 'Decision trace' });
  for (const phase of ['Discover', 'Verify', 'Qualify', 'Decide', 'Approve']) expect(within(trace).getByText(phase)).toBeVisible();
  expect(within(trace).getByText('PARTIAL')).toBeVisible();
  expect(within(trace).getByText('Current run incomplete')).toBeVisible();
  expect(within(trace).getByText('Prior decision retained')).toBeVisible();
  expect(within(trace).queryByText(/fixture evaluated/i)).not.toBeInTheDocument();
});

test('a completed run does not claim that the Verify phase completed without decision evidence', () => {
  render(<DecisionCanvas workspace={workspace({
    run_state: 'COMPLETED',
    presentation_state: 'NEEDS_REVIEW',
    decision: { ...workspace().decision, recommendation: null, summary: null },
  })} />);
  const trace = screen.getByRole('list', { name: 'Decision trace' });
  const verifyPhase = within(trace).getByText('Verify').closest('li');
  expect(verifyPhase).not.toBeNull();
  expect(within(verifyPhase!).getByText('Unavailable')).toBeVisible();
  expect(within(verifyPhase!).queryByText('Completed')).not.toBeInTheDocument();
});

test('direct selected URL fetches and renders an opportunity outside the bounded inbox page', async () => {
  const offPage = workspace({ opportunity_id: 'off-page', program_name: 'Direct off-page decision' });
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.endsWith('/inbox')) return Response.json(inbox([inboxItem('loaded', 0)]));
    if (url.endsWith('/opportunities/off-page/workspace')) return Response.json(offPage);
    return Response.json({ founder: null, projects: [] });
  }));
  render(<MemoryRouter initialEntries={['/inbox/off-page']}><App /></MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'Direct off-page decision' })).toBeVisible();
  expect(screen.getByText('Selected opportunity is not on this page.')).toBeVisible();
  expect(screen.getByText('Run state: COMPLETED')).toBeVisible();
});

test('the canvas action stays disabled and explained when no executor is supplied', async () => {
  render(<DecisionCanvas workspace={workspace()} />);
  const action = screen.getByRole('button', { name: 'Approve application' });
  expect(action).toBeDisabled();
  expect(action).toHaveAccessibleDescription('Action execution is not available in this workspace.');
  expect(action).toHaveTextContent('↗');
  expect(action).not.toHaveTextContent(String.raw`\u2197`);
});

test('production App integration enables the action once the approval executor is supplied', async () => {
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.endsWith('/inbox')) return Response.json(inbox([inboxItem('selected', 0)]));
    if (url.endsWith('/opportunities/selected/workspace')) return Response.json(workspace({ opportunity_id: 'selected' }));
    return Response.json({ founder: null, projects: [] });
  }));
  render(<MemoryRouter initialEntries={['/inbox/selected']}><App /></MemoryRouter>);
  const action = await screen.findByRole('button', { name: 'Approve application' });
  expect(action).toBeEnabled();
  expect(action).toHaveTextContent('↗');
  expect(action).not.toHaveTextContent(String.raw`\u2197`);
  expect(screen.getByText('Recorded organizer · EVALUATED')).toBeVisible();
});

test('inbox URL selection changes the selected workspace response', async () => {
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.endsWith('/inbox')) return Response.json(inbox([inboxItem('one', 0), inboxItem('two', 1)]));
    if (url.endsWith('/opportunities/one/workspace')) return Response.json(workspace({ opportunity_id: 'one', program_name: 'Decision one' }));
    if (url.endsWith('/opportunities/two/workspace')) return Response.json(workspace({ opportunity_id: 'two', program_name: 'Decision two' }));
    return Response.json({ founder: null, projects: [] });
  }));
  render(<MemoryRouter initialEntries={['/inbox/one']}><App /></MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'Decision one' })).toBeVisible();
  await userEvent.click(await screen.findByRole('link', { name: /Program two/ }));
  expect(await screen.findByRole('heading', { name: 'Decision two' })).toBeVisible();
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Decision one' })).not.toBeInTheDocument());
});

test('/inbox keeps the truthful dormant A1.2 workspace and does not fetch a selected workspace', async () => {
  const fetchMock = vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.endsWith('/inbox')) return Response.json(inbox([]));
    return Response.json({ founder: null, projects: [] });
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<MemoryRouter initialEntries={['/inbox']}><App /></MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'No active decision' })).toBeVisible();
  expect(screen.queryByText('APPLY')).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([request]) => String(request).includes('/opportunities/'))).toBe(false);
});

test('typed not-found error remains distinct from loading and an unresolved decision', async () => {
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.endsWith('/inbox')) return Response.json(inbox([]));
    if (url.endsWith('/opportunities/missing/workspace')) return Response.json({ code: 'NOT_FOUND' }, { status: 404 });
    return Response.json({ founder: null, projects: [] });
  }));
  render(<MemoryRouter initialEntries={['/inbox/missing']}><App /></MemoryRouter>);
  expect(screen.getByRole('heading', { name: 'Opening decision' })).toBeVisible();
  expect(await screen.findByRole('heading', { name: 'Opportunity unavailable' })).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'UNKNOWN' })).not.toBeInTheDocument();
});
