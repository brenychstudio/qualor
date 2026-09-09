import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { App } from '../../App';
import type { ActivityResponse, RunEventView, RunView } from '../../generated/domain';
import { ActivityHistory } from './ActivityHistory';
import { IntelligenceRail } from './IntelligenceRail';

const page = { offset: 0, limit: 50, total: 0, has_more: false };

const CHAT_VOCABULARY = [
  /\bI\s|\bI'm|\bI'll|\bme\b/,
  /assistant/i,
  /thinking/i,
  /let me\b/i,
  /chat/i,
  /\bprompt\b/i,
  /reasoning/i,
];

function run(changes: Partial<RunView> = {}): RunView {
  return {
    id: 'run-1',
    mode: 'FIXTURE',
    state: 'COMPLETED',
    provider_state: null,
    opportunity_id: 'selected',
    opportunity_version: 4,
    started_at: '2026-09-09T12:41:00Z',
    completed_at: '2026-09-09T12:43:00Z',
    search_calls: 2,
    fetched_documents: 1,
    official_source_count: 3,
    verified_claim_count: 7,
    reserved_cost_usd: '0.021',
    reported_cost_usd: '0.019',
    termination_reason: 'SUFFICIENT_CRITICAL_EVIDENCE',
    ...changes,
  };
}

function event(sequence: number, changes: Partial<RunEventView> = {}): RunEventView {
  return {
    run_id: 'run-1',
    sequence,
    event_type: 'SEARCH_REQUESTED',
    mode: 'FIXTURE',
    occurred_at: `2026-09-09T12:4${sequence}:00Z`,
    reason_code: 'SEARCH_STARTED',
    phase: 'DISCOVERING',
    count: 0,
    source_ids: [],
    evidence_ids: [],
    estimated_cost_usd: null,
    reported_cost_usd: null,
    ...changes,
  };
}

function activity(changes: Partial<ActivityResponse> = {}): ActivityResponse {
  return {
    runs: [run()],
    events: [
      event(1),
      event(2, { event_type: 'SOURCE_FETCHED', reason_code: 'SOURCE_RETRIEVED', phase: 'VERIFYING', count: 2 }),
      event(3, { event_type: 'ELIGIBILITY_EVALUATED', reason_code: 'GATE_EVALUATED', phase: 'EVALUATING' }),
      event(4, { event_type: 'DECISION_EVALUATED', reason_code: 'DECISION_RECORDED', phase: 'DECISION_UPDATED' }),
    ],
    runs_page: page,
    events_page: page,
    ...changes,
  };
}

function stub(response: ActivityResponse | 'error' = activity()) {
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.includes('/runs')) {
      return response === 'error'
        ? Response.json({ code: 'LOCAL_DISCONNECTED' }, { status: 503 })
        : Response.json(response);
    }
    if (url.endsWith('/inbox')) return Response.json({ items: [], page, profile_present: true, generated_at: '2026-09-09T12:00:00Z' });
    return Response.json({ founder: null, projects: [] });
  }));
}

function renderRail(response: ActivityResponse | 'error' = activity()) {
  stub(response);
  return render(<MemoryRouter><IntelligenceRail /></MemoryRouter>);
}

test('renders persisted events in their recorded order without inventing any', async () => {
  renderRail();
  const timeline = await screen.findByRole('list', { name: /recorded activity/i });
  const entries = within(timeline).getAllByRole('listitem');
  expect(entries).toHaveLength(4);
  expect(entries.map(entry => entry.textContent)).toEqual([
    expect.stringContaining('Discovering'),
    expect.stringContaining('Verifying'),
    expect.stringContaining('Evaluating'),
    expect.stringContaining('Decision updated'),
  ]);
});

test('labels the recorded runtime mode explicitly and never presents fixture work as live', async () => {
  renderRail();
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText('FIXTURE')).toBeVisible();
  expect(within(rail).queryByText('LIVE')).not.toBeInTheDocument();
});

test('presents a replayed run as REPLAY rather than as current live research', async () => {
  renderRail(activity({
    runs: [run({ mode: 'REPLAY' })],
    events: [event(1, { mode: 'REPLAY' })],
  }));
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText('REPLAY')).toBeVisible();
  expect(within(rail).queryByText('LIVE')).not.toBeInTheDocument();
});

test('shows the bounded call counts and recorded spend already present in the run record', async () => {
  renderRail();
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText('3')).toBeVisible();
  expect(within(rail).getByText('7')).toBeVisible();
  expect(within(rail).getByText(/2 search calls/i)).toBeVisible();
  expect(within(rail).getByText(/\$0\.021/)).toBeVisible();
});

test('renders a budget stop as the canonical persisted state with its bounded usage', async () => {
  renderRail(activity({ runs: [run({ state: 'BUDGET_STOPPED', termination_reason: 'BUDGET_EXHAUSTED' })] }));
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText('BUDGET_STOPPED')).toBeVisible();
  expect(within(rail).getByText(/2 search calls/i)).toBeVisible();
});

test('renders a disconnected live provider with its last recorded event', async () => {
  renderRail(activity({
    runs: [run({ mode: 'LIVE', state: 'FAILED', provider_state: 'DISCONNECTED_LIVE_PROVIDER', termination_reason: 'PROVIDER_DISCONNECTED' })],
    events: [event(1, { mode: 'LIVE' })],
  }));
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText('DISCONNECTED')).toBeVisible();
  expect(within(rail).getByText('FAILED')).toBeVisible();
  expect(within(rail).getByText(/Discovering/)).toBeVisible();
});

test('retains a partial run state exactly as recorded', async () => {
  renderRail(activity({ runs: [run({ state: 'PARTIAL', termination_reason: 'NO_PROGRESS' })] }));
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText('PARTIAL')).toBeVisible();
});

test('states that no activity is recorded rather than fabricating events', async () => {
  renderRail(activity({ runs: [], events: [] }));
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText(/no recorded activity/i)).toBeVisible();
  expect(within(rail).queryByRole('list', { name: /recorded activity/i })).not.toBeInTheDocument();
});

test('reports an unavailable activity read without inventing a run', async () => {
  renderRail('error');
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/unavailable/i));
  expect(screen.queryByRole('list', { name: /recorded activity/i })).not.toBeInTheDocument();
});

test('uses structured operational telemetry and never chat vocabulary', async () => {
  const view = renderRail();
  await screen.findByRole('list', { name: /recorded activity/i });
  const text = view.container.textContent ?? '';
  for (const pattern of CHAT_VOCABULARY) expect(text).not.toMatch(pattern);
});

test('opens the full recorded history directly at /activity', async () => {
  stub();
  render(<MemoryRouter initialEntries={['/activity']}><App /></MemoryRouter>);
  const canvas = await screen.findByRole('main');
  expect(await within(canvas).findByRole('heading', { name: /recorded activity/i })).toBeVisible();
  expect(within(canvas).getByText('SUFFICIENT_CRITICAL_EVIDENCE')).toBeVisible();
  expect(within(canvas).getByText(/2 search calls/i)).toBeVisible();
});

test('the full history lists every recorded run with its own mode and state', async () => {
  stub(activity({
    runs: [run(), run({ id: 'run-2', mode: 'LIVE', state: 'PARTIAL', termination_reason: 'MAX_STEPS' })],
  }));
  render(<MemoryRouter><ActivityHistory /></MemoryRouter>);
  const runs = await screen.findByRole('list', { name: /recorded runs/i });
  const entries = within(runs).getAllByRole('listitem');
  expect(entries).toHaveLength(2);
  expect(entries[0]).toHaveTextContent('FIXTURE');
  expect(entries[1]).toHaveTextContent('LIVE');
  expect(entries[1]).toHaveTextContent('PARTIAL');
});

test('the full history says so plainly when no run has been recorded', async () => {
  stub(activity({ runs: [], events: [] }));
  render(<MemoryRouter><ActivityHistory /></MemoryRouter>);
  expect(await screen.findByText(/no run has been recorded/i)).toBeVisible();
  expect(screen.queryByRole('list', { name: /recorded runs/i })).not.toBeInTheDocument();
});
