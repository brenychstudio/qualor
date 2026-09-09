import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { App } from '../../App';
import type {
  ApprovalRequest,
  ApprovalView,
  InboxItem,
  InboxResponse,
  OpportunityWorkspaceResponse,
} from '../../generated/domain';
import { ApprovalPanel } from './ApprovalPanel';

const page = { offset: 0, limit: 50, total: 0, has_more: false };

const SUBMISSION_LANGUAGE = [
  /\bsubmit/i, /\bsend\b/i, /apply now/i, /\bpublish/i, /dispatch/i, /autofill/i, /\bemail\b/i,
];

function approvalRequest(): ApprovalRequest {
  return {
    opportunity_version: 4,
    opportunity_hash: 'a'.repeat(64),
    founder_profile_id: 'founder-1',
    founder_profile_version: 2,
    project_id: 'project-1',
    project_version: 3,
    decision_id: 'decision-1',
    decision_version: 2,
    policy_versions: { conflicts: 1, decisions: 1, effort: 1, eligibility: 1, matching: 1, strategy: 1 },
    action: 'GENERATE_DRAFT_PACK',
  };
}

function approval(changes: Partial<ApprovalView> = {}): ApprovalView {
  return {
    id: 'approval-1',
    version: 1,
    actor_id: 'founder-1',
    opportunity_id: 'selected',
    action: 'GENERATE_DRAFT_PACK',
    state: 'PENDING_APPROVAL',
    expires_at: '2026-09-10T12:00:00Z',
    actionable: true,
    reason: 'PENDING',
    approved_snapshot: approvalRequest(),
    draft_job: null,
    pack_id: null,
    ...changes,
  };
}

function workspace(changes: Partial<OpportunityWorkspaceResponse['decision']> = {}): OpportunityWorkspaceResponse {
  return {
    opportunity_id: 'selected',
    version: 4,
    program_name: 'Selected program',
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
    decision: {
      decision_id: 'decision-1',
      decision_version: 2,
      recommendation: 'APPLY',
      summary: 'The recorded rules and project facts support this decision.',
      reason_codes: [],
      strategy: { state: 'AVAILABLE', score: 82, semantics: 'PRIORITIZATION_NOT_WIN_PROBABILITY', breakdown: [], missing_factors: [] },
      best_project: { id: 'project-1', name: 'Recorded project', version: 3 },
      eligibility: 'PASS',
      primary_blocker: null,
      missing_information: [],
      effort: null,
      readiness: null,
      freshness: 'FRESH',
      deadline: { timezone_status: 'UTC', values: ['2026-11-30T23:59:00Z'] },
      primary_action: { available: true, reason: 'VALID', approval_request: approvalRequest() },
      ...changes,
    },
  } as unknown as OpportunityWorkspaceResponse;
}

interface Calls { request: number; confirm: number; keys: string[] }

function stub({ requested = approval(), confirmed = approval({ state: 'DRAFT_READY', reason: 'VALID', pack_id: 'pack-1' }), requestError, confirmError, readOnly = false }: {
  requested?: ApprovalView; confirmed?: ApprovalView;
  requestError?: string; confirmError?: string; readOnly?: boolean;
} = {}) {
  const calls: Calls = { request: 0, confirm: 0, keys: [] };
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL, init?: RequestInit) => {
    const url = String(request);
    if (url.endsWith('/session')) return Response.json({ read_only: readOnly, action_token: readOnly ? null : 'test-token' });
    if (url.endsWith('/approvals') && init?.method === 'POST') {
      calls.request += 1;
      if (requestError) return Response.json({ code: requestError }, { status: 409 });
      return Response.json(requested);
    }
    if (url.endsWith('/confirm') && init?.method === 'POST') {
      calls.confirm += 1;
      calls.keys.push(JSON.parse(String(init.body)).idempotency_key);
      if (confirmError) return Response.json({ code: confirmError }, { status: 409 });
      return Response.json(confirmed);
    }
    if (url.endsWith('/inbox')) return Response.json({ items: [inboxItem()], page, profile_present: true, generated_at: '2026-09-09T12:00:00Z' } as unknown as InboxResponse);
    if (url.includes('/workspace')) return Response.json(workspace());
    if (url.includes('/runs')) return Response.json({ runs: [], events: [], runs_page: page, events_page: page });
    if (url.includes('/evidence')) return Response.json({ code: 'NOT_FOUND' }, { status: 404 });
    return Response.json({ founder: null, projects: [] });
  }));
  return calls;
}

function inboxItem(): InboxItem {
  return {
    opportunity_id: 'selected',
    program_name: 'Selected program',
    organizer: 'Recorded organizer',
    edition: '2026',
    presentation_state: 'EVALUATED',
    priority_rank: 0,
    recommendation: 'APPLY',
    freshness: 'FRESH',
    deadline: { timezone_status: 'UTC', values: ['2026-11-30T23:59:00Z'] },
    discovered_at: '2026-09-01T00:00:00Z',
    best_project: { id: 'project-1', name: 'Recorded project', version: 3 },
    effort: null,
    mode: 'FIXTURE',
    human_action_available: true,
  } as unknown as InboxItem;
}

function renderPanel(recommendation: 'APPLY' | 'PREPARE' = 'APPLY') {
  const onClose = vi.fn();
  const view = render(<MemoryRouter><ApprovalPanel workspace={workspace()} recommendation={recommendation} onClose={onClose} /></MemoryRouter>);
  return { ...view, onClose };
}

const panel = () => screen.getByRole('region', { name: /human approval/i });
const confirmControl = () => screen.getByRole('button', { name: /confirm approval/i });

test('presents the version-bound approval awaiting explicit human confirmation', async () => {
  stub();
  renderPanel();
  const region = await screen.findByRole('region', { name: /human approval/i });
  expect(await within(region).findByText('PENDING_APPROVAL')).toBeVisible();
  expect(within(region).getByText('GENERATE_DRAFT_PACK')).toBeVisible();
  expect(within(region).getByText('founder-1')).toBeVisible();
  expect(within(region).getByText('Selected program')).toBeVisible();
  expect(within(region).getByText(/opportunity version 4/i)).toBeVisible();
  expect(within(region).getByText(/Recorded project/)).toBeVisible();
  expect(within(region).getByText(/project version 3/i)).toBeVisible();
});

test('states the approval expiry from the server rather than computing validity', async () => {
  stub();
  renderPanel();
  const region = await screen.findByRole('region', { name: /human approval/i });
  expect(await within(region).findByText(/expires/i)).toBeVisible();
  expect(within(region).getByText(/2026-09-10T12:00:00Z/)).toBeVisible();
});

test('shows NOT_REVIEWED until a version-bound approval exists', async () => {
  stub({ requested: approval({ state: 'NOT_REVIEWED', reason: 'PENDING', actionable: false }) });
  renderPanel();
  const region = await screen.findByRole('region', { name: /human approval/i });
  expect(await within(region).findByText('NOT_REVIEWED')).toBeVisible();
});

test('renders APPROVED_FOR_PREPARATION after the human confirms', async () => {
  stub({ confirmed: approval({ state: 'APPROVED_FOR_PREPARATION', reason: 'VALID' }) });
  renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  await userEvent.click(confirmControl());
  expect(await screen.findByText('APPROVED_FOR_PREPARATION')).toBeVisible();
});

test('renders REVOKED_APPROVAL with its distinct server-explained cause', async () => {
  stub({ requested: approval({ state: 'REVOKED_APPROVAL', reason: 'CHANGE_REVOKED', actionable: false }) });
  renderPanel();
  const region = await screen.findByRole('region', { name: /human approval/i });
  expect(await within(region).findByText('REVOKED_APPROVAL')).toBeVisible();
  expect(within(region).getByText(/changed since this approval was created/i)).toBeVisible();
  expect(within(region).queryByRole('button', { name: /confirm approval/i })).not.toBeInTheDocument();
});

test('renders DRAFT_READY with a bounded entry point and no document surface', async () => {
  stub();
  renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  await userEvent.click(confirmControl());
  const region = panel();
  expect(await within(region).findByText('DRAFT_READY')).toBeVisible();
  expect(within(region).getByRole('link', { name: /open draft pack/i })).toHaveAttribute('href', '/draft-packs/pack-1');
  expect(within(region).queryByText(/section 1/i)).not.toBeInTheDocument();
});

test('confirms through the keyboard alone', async () => {
  const calls = stub();
  renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  confirmControl().focus();
  await userEvent.keyboard('{Enter}');
  await waitFor(() => expect(calls.confirm).toBe(1));
  expect(await screen.findByText('DRAFT_READY')).toBeVisible();
});

test('cancels through the keyboard without approving anything', async () => {
  const calls = stub();
  const { onClose } = renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  screen.getByRole('button', { name: /cancel/i }).focus();
  await userEvent.keyboard('{Enter}');
  expect(onClose).toHaveBeenCalled();
  expect(calls.confirm).toBe(0);
});

test('closes on Escape without approving anything', async () => {
  const calls = stub();
  const { onClose } = renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  await userEvent.keyboard('{Escape}');
  expect(onClose).toHaveBeenCalled();
  expect(calls.confirm).toBe(0);
});

test('takes focus intentionally when the checkpoint opens', async () => {
  stub();
  renderPanel();
  const region = await screen.findByRole('region', { name: /human approval/i });
  await waitFor(() => expect(region).toHaveFocus());
});

test('suppresses duplicate activation so one intent creates one confirmation', async () => {
  const calls = stub();
  renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  const confirm = confirmControl();
  await userEvent.click(confirm);
  await userEvent.click(confirm).catch(() => undefined);
  await waitFor(() => expect(screen.getByText('DRAFT_READY')).toBeVisible());
  expect(calls.confirm).toBe(1);
});

test('reuses one idempotency key when the same intent is retried after a network failure', async () => {
  const calls = stub({ confirmError: 'INTERNAL_ERROR' });
  renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  await userEvent.click(confirmControl());
  await screen.findByRole('alert');
  await userEvent.click(confirmControl());
  await waitFor(() => expect(calls.confirm).toBe(2));
  expect(calls.keys[0]).toBe(calls.keys[1]);
  expect(calls.keys[0]).toBeTruthy();
});

test.each([
  ['EXPIRED', /approval expired/i],
  ['VERSION_MISMATCH', /version.*changed/i],
  ['REVOKED', /revoked/i],
  ['CONSUMED', /already been used/i],
  ['ACTION_MISMATCH', /different action/i],
  ['EVIDENCE_CHANGED', /evidence changed/i],
  ['DEADLINE_PASSED', /deadline has passed/i],
])('explains the %s server reason in its own words', async (code, copy) => {
  stub({ confirmError: code });
  renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  await userEvent.click(confirmControl());
  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent(copy);
  expect(alert).not.toHaveTextContent(/something went wrong/i);
});

test('announces a failed approval request without claiming approval succeeded', async () => {
  stub({ requestError: 'DECISION_NOT_ACTIONABLE' });
  renderPanel();
  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent(/not actionable/i);
  expect(screen.queryByText('APPROVED_FOR_PREPARATION')).not.toBeInTheDocument();
});

test('communicates a non-actionable state in text, never by colour alone', async () => {
  stub({ requested: approval({ state: 'REVOKED_APPROVAL', reason: 'EXPIRED', actionable: false }) });
  renderPanel();
  const region = await screen.findByRole('region', { name: /human approval/i });
  expect(await within(region).findByText(/approval expired/i)).toBeVisible();
});

test('offers no control that implies external submission, and says so plainly', async () => {
  stub();
  const { container } = renderPanel();
  await screen.findByText('PENDING_APPROVAL');
  const controls = [...screen.getAllByRole('button'), ...screen.queryAllByRole('link')];
  for (const control of controls) {
    for (const pattern of SUBMISSION_LANGUAGE) expect(control.textContent ?? '').not.toMatch(pattern);
  }
  const text = container.textContent ?? '';
  expect(text).toMatch(/nothing is submitted externally/i);
  expect(text).toMatch(/separate local preparation step/i);
  expect(text).toMatch(/no organizer is contacted/i);
  expect(text).not.toMatch(/apply now/i);
});

test('disables the checkpoint when the session cannot authorise an action', async () => {
  stub({ readOnly: true });
  renderPanel();
  const region = await screen.findByRole('region', { name: /human approval/i });
  expect(await within(region).findByRole('status')).toHaveTextContent(/read-only/i);
  expect(within(region).queryByRole('button', { name: /confirm approval/i })).not.toBeInTheDocument();
});

test('APPLY opens the approval checkpoint from the decision canvas', async () => {
  stub();
  render(<MemoryRouter initialEntries={['/inbox/selected']}><App /></MemoryRouter>);
  await userEvent.click(await screen.findByRole('button', { name: 'Approve application' }));
  expect(await screen.findByRole('region', { name: /human approval/i })).toBeVisible();
});

test('cancelling the checkpoint returns focus to the decision action', async () => {
  stub();
  render(<MemoryRouter initialEntries={['/inbox/selected']}><App /></MemoryRouter>);
  const cta = await screen.findByRole('button', { name: 'Approve application' });
  await userEvent.click(cta);
  await screen.findByText('PENDING_APPROVAL');
  await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
  await waitFor(() => expect(cta).toHaveFocus());
});

test.each(['WATCH', 'SKIP'] as const)('%s never opens the approval checkpoint', async recommendation => {
  const calls = stub();
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.endsWith('/inbox')) return Response.json({ items: [inboxItem()], page, profile_present: true, generated_at: '2026-09-09T12:00:00Z' });
    if (url.includes('/workspace')) return Response.json(workspace({ recommendation, primary_action: { available: false, reason: 'DECISION_NOT_ACTIONABLE', approval_request: null } }));
    if (url.includes('/runs')) return Response.json({ runs: [], events: [], runs_page: page, events_page: page });
    return Response.json({ founder: null, projects: [] });
  }));
  render(<MemoryRouter initialEntries={['/inbox/selected']}><App /></MemoryRouter>);
  const label = recommendation === 'WATCH' ? 'Resolve unknowns' : 'Review rejection';
  await userEvent.click(await screen.findByRole('button', { name: label }));
  expect(screen.queryByRole('region', { name: /human approval/i })).not.toBeInTheDocument();
  expect(calls.request).toBe(0);
});
