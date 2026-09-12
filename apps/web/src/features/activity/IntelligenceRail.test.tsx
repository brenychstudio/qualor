import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { App } from '../../App';
import type { ComponentType } from 'react';
import type { ActivityResponse, RunEventView, RunView } from '../../generated/domain';
import { ActivityHistory } from './ActivityHistory';
import { presentEvent, presentRun } from './activity-presenter';
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

test('reloads persisted activity when the workspace authority revision advances', async () => {
  let reads = 0;
  vi.stubGlobal('fetch', vi.fn(async () => {
    reads += 1;
    return Response.json(reads === 1 ? activity({ runs: [], events: [] }) : activity({
      runs: [run({ mode: 'LIVE' })],
      events: [event(1, { mode: 'LIVE' })],
    }));
  }));
  const RefreshableRail = IntelligenceRail as unknown as ComponentType<{ revision: number }>;
  const view = render(<MemoryRouter><RefreshableRail revision={0} /></MemoryRouter>);
  expect(await screen.findByText('No recorded activity.')).toBeVisible();

  view.rerender(<MemoryRouter><RefreshableRail revision={1} /></MemoryRouter>);

  expect(await screen.findByRole('list', { name: 'Recorded activity' })).toBeVisible();
  expect(screen.getByText('LIVE')).toBeVisible();
  expect(screen.queryByText('No recorded activity.')).not.toBeInTheDocument();
  expect(reads).toBe(2);
});

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
  // Each count is asserted against the label it belongs to. The rail used to repeat two of them
  // as a prose line under the same numbers; it now states each once, scoped to the run.
  const metrics = within(rail).getByRole('group', { name: /recorded in this run/i });
  for (const [label, value] of [['Search calls', '2'], ['Documents fetched', '1'], ['Official sources', '3'], ['Claims verified', '7']]) {
    const fact = within(metrics).getByText(label).closest('div')!;
    expect(within(fact).getByText(value)).toBeVisible();
  }
  expect(within(rail).getByText(/\$0\.021 reserved/)).toBeVisible();
});

test('renders a budget stop as the canonical persisted state with its bounded usage', async () => {
  renderRail(activity({ runs: [run({ state: 'BUDGET_STOPPED', termination_reason: 'BUDGET_EXHAUSTED' })] }));
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText('BUDGET_STOPPED')).toBeVisible();
  const metrics = within(rail).getByRole('group', { name: /recorded in this run/i });
  expect(within(within(metrics).getByText('Search calls').closest('div')!).getByText('2')).toBeVisible();
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

/* --------------------------------------------------------------------------------------------
 * Truthful intelligence presence.
 *
 * The rail reports one thing: what the persisted run actually recorded. These tests pin the two
 * ways that can go wrong — a recorded code leaking out as the judge-facing label, and a count
 * being read as something other than what the server means by it.
 * ------------------------------------------------------------------------------------------ */

/** Every event type the product actually persists, read from the server contract rather than
 *  restated here: the runtime's own TraceEvent vocabulary plus the types the fixture seeder
 *  writes. A new persisted event with no recorded copy fails this test. */
function persistedEventTypes(): string[] {
  const root = resolve(process.cwd(), '../..');
  const runtime = readFileSync(resolve(root, 'src/qualor/runtime/run_models.py'), 'utf8');
  const literal = /class TraceEvent\(Contract\):\s*event: Literal\[([^\]]*)\]/.exec(runtime);
  expect(literal).not.toBeNull();
  const runtimeEvents = [...literal![1].matchAll(/"([A-Z_]+)"/g)].map(match => match[1]);
  const seeder = readFileSync(resolve(root, 'src/qualor/cli.py'), 'utf8');
  const seeded = /for event in \(([^)]*)\):/.exec(seeder);
  expect(seeded).not.toBeNull();
  const seededEvents = [...seeded![1].matchAll(/"([A-Z_]+)"/g)].map(match => match[1]);
  expect(runtimeEvents.length).toBeGreaterThan(10);
  expect(seededEvents).toContain('OPPORTUNITY_DISCOVERED');
  return [...new Set([...runtimeEvents, ...seededEvents])];
}

test('presents every persisted event type as recorded copy, never as a machine code', () => {
  const types = persistedEventTypes();
  const leaked = types
    .map(type => ({ type, label: presentEvent(event(1, { event_type: type })).label }))
    .filter(entry => /^[A-Z][A-Z0-9 _]*$/.test(entry.label));
  expect(leaked).toEqual([]);
});

test('renders the seeded fixture history as readable observations rather than enum text', async () => {
  renderRail(activity({
    events: [
      event(1, { event_type: 'OPPORTUNITY_DISCOVERED', phase: null, count: 1 }),
      event(2, { event_type: 'EVIDENCE_RECORDED', phase: null, count: 1 }),
      event(3, { event_type: 'DECISION_UPDATED', phase: null, count: 1 }),
    ],
  }));
  const timeline = await screen.findByRole('list', { name: /recorded activity/i });
  const entries = within(timeline).getAllByRole('listitem');
  expect(entries.map(entry => entry.textContent)).toEqual([
    expect.stringContaining('Opportunity discovered'),
    expect.stringContaining('Evidence recorded'),
    expect.stringContaining('Decision updated'),
  ]);
  expect(timeline.textContent).not.toMatch(/OPPORTUNITY DISCOVERED|DECISION UPDATED|OPPORTUNITY_DISCOVERED/);
});

test('keeps the recorded sequence authoritative when every event shares one timestamp', async () => {
  // The seeded W01 run records all three observations at the same instant, so the clock cannot
  // carry the order. The persisted sequence can, and it is the server's own ordering.
  renderRail(activity({
    events: [
      event(1, { event_type: 'OPPORTUNITY_DISCOVERED', phase: null, occurred_at: '2026-09-09T12:41:00Z' }),
      event(2, { event_type: 'EVIDENCE_RECORDED', phase: null, occurred_at: '2026-09-09T12:41:00Z' }),
      event(3, { event_type: 'DECISION_UPDATED', phase: null, occurred_at: '2026-09-09T12:41:00Z' }),
    ],
  }));
  const timeline = await screen.findByRole('list', { name: /recorded activity/i });
  const entries = within(timeline).getAllByRole('listitem');
  expect(entries.map(entry => entry.querySelector('.event-order')?.textContent)).toEqual(['01', '02', '03']);
  expect(entries.every(entry => entry.textContent?.includes('12:41'))).toBe(true);
});

test('marks the recorded decision update and nothing else as the decision outcome', async () => {
  renderRail();
  const timeline = await screen.findByRole('list', { name: /recorded activity/i });
  const entries = within(timeline).getAllByRole('listitem');
  expect(entries.filter(entry => entry.dataset.outcome === 'true')).toHaveLength(1);
  expect(entries.at(-1)?.dataset.outcome).toBe('true');
  expect(entries.at(-1)?.textContent).toContain('Decision updated');
});

test('marks only the last recorded decision evaluation when a run re-evaluated several times', async () => {
  // A run re-evaluates whenever a claim or source is admitted, and `finish()` evaluates once
  // more, so several DECISION_EVALUATED events are normal for any real run. The decision the
  // workspace shows is the last one recorded; marking all of them would claim several outcomes.
  renderRail(activity({
    events: [
      event(1, { event_type: 'CLAIM_EXTRACTED', phase: 'VERIFYING' }),
      event(2, { event_type: 'DECISION_EVALUATED', phase: 'DECISION_UPDATED' }),
      event(3, { event_type: 'CLAIM_EXTRACTED', phase: 'VERIFYING' }),
      event(4, { event_type: 'DECISION_EVALUATED', phase: 'DECISION_UPDATED' }),
      event(5, { event_type: 'RUN_TERMINATED', phase: null }),
    ],
  }));
  const timeline = await screen.findByRole('list', { name: /recorded activity/i });
  const entries = within(timeline).getAllByRole('listitem');
  expect(entries.map(entry => entry.dataset.outcome)).toEqual([
    undefined, undefined, undefined, 'true', undefined,
  ]);
  // Every recorded evaluation is still listed; only the marker is singular.
  expect(entries.filter(entry => entry.textContent?.includes('Decision updated'))).toHaveLength(2);
});

test('keeps recorded spend visible on a degraded run that made no calls', async () => {
  // A live provider that disconnects reserves real budget and records no call at all, so the
  // all-zero counters must not take the committed spend down with them.
  renderRail(activity({
    runs: [run({
      mode: 'LIVE', state: 'FAILED', provider_state: 'DISCONNECTED_LIVE_PROVIDER',
      termination_reason: 'PROVIDER_DISCONNECTED', reserved_cost_usd: '0.043',
      search_calls: 0, fetched_documents: 0, official_source_count: 0, verified_claim_count: 0,
    })],
    events: [event(1, { mode: 'LIVE' })],
  }));
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  expect(within(rail).getByText(/no retrieval or verification call is recorded/i)).toBeVisible();
  expect(within(rail).getByText(/\$0\.043 reserved/)).toBeVisible();
  expect(within(rail).getByText('DISCONNECTED')).toBeVisible();
  expect(within(rail).getByText(/live provider disconnected/i)).toBeVisible();
});

test('reads a long termination reason as copy while keeping the recorded code available', async () => {
  renderRail();
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  const termination = rail.querySelector<HTMLElement>('.run-termination')!;
  expect(termination.textContent).not.toMatch(/SUFFICIENT_CRITICAL_EVIDENCE|SUFFICIENT CRITICAL EVIDENCE/);
  expect(termination.textContent).toMatch(/critical evidence/i);
  // The canonical code is never lost, only demoted out of the judge-facing label.
  expect(termination).toHaveAttribute('title', 'SUFFICIENT_CRITICAL_EVIDENCE');
});

test('has readable copy for every canonical termination reason the runtime can record', () => {
  const root = resolve(process.cwd(), '../..');
  const models = readFileSync(resolve(root, 'src/qualor/runtime/run_models.py'), 'utf8');
  const literal = /termination_reason: Literal\[([^\]]*)\]/.exec(models);
  expect(literal).not.toBeNull();
  const reasons = [...literal![1].matchAll(/"([A-Z_]+)"/g)].map(match => match[1]);
  expect(reasons).toContain('SUFFICIENT_CRITICAL_EVIDENCE');
  // PROVIDER_DISCONNECTED is written by the live CLI rather than by the runtime loop.
  for (const reason of [...reasons, 'PROVIDER_DISCONNECTED']) {
    const copy = presentRun(run({ termination_reason: reason })).terminationCopy;
    expect(copy, reason).not.toBeNull();
    expect(copy, reason).not.toMatch(/^[A-Z][A-Z0-9 _]*$/);
  }
  // An unrecognised code still reaches the reader rather than vanishing.
  expect(presentRun(run({ termination_reason: 'FUTURE_REASON' })).terminationCopy).toContain('FUTURE REASON');
});

test('scopes the run counters to the run and states an all-zero run plainly', async () => {
  // The seeded W01 run genuinely performed no retrieval: its evidence was persisted from an
  // owned fixture file, not fetched. Zero is the truth, and it has to read as the truth rather
  // than as a broken counter — without borrowing the evidence sheet's own numbers.
  renderRail(activity({
    runs: [run({ search_calls: 0, fetched_documents: 0, official_source_count: 0, verified_claim_count: 0 })],
  }));
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  const metrics = within(rail).getByRole('group', { name: /recorded in this run/i });
  for (const label of ['Search calls', 'Documents fetched', 'Official sources', 'Claims verified']) {
    expect(within(metrics).getByText(label)).toBeVisible();
  }
  expect(within(metrics).getAllByText('0')).toHaveLength(4);
  expect(within(metrics).getByText(/no retrieval or verification call is recorded/i)).toBeVisible();
  // No count is borrowed from the evidence base to make the rail look busier.
  for (const inflated of ['16', '9', '1']) {
    expect(within(metrics).queryByText(inflated)).not.toBeInTheDocument();
  }
});

test('reports recorded retrieval work as recorded when the run actually performed it', async () => {
  renderRail();
  const rail = await screen.findByRole('region', { name: /intelligence/i });
  const metrics = within(rail).getByRole('group', { name: /recorded in this run/i });
  expect(within(metrics).getByText('2')).toBeVisible();
  expect(within(metrics).getByText('1')).toBeVisible();
  expect(within(metrics).getByText('3')).toBeVisible();
  expect(within(metrics).getByText('7')).toBeVisible();
  expect(within(metrics).queryByText(/no retrieval or verification call is recorded/i)).not.toBeInTheDocument();
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
