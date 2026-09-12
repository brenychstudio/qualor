import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { LiveResearchPanel } from './LiveResearchPanel';

const URL = 'https://example.org/opportunity/rules';
const STATUS = {
  run_id: 'run-live-one', mode: 'LIVE', started_at: '2026-09-12T12:00:00Z',
} as const;

function Location() {
  const location = useLocation();
  const navigate = useNavigate();
  return <><span aria-label="Current route">{location.pathname}</span><button onClick={() => navigate('/activity')}>Open activity</button></>;
}

function mount(onOpportunityCreated = vi.fn(), pollIntervalMs = 1000, maxPollAttempts?: number) {
  return render(<MemoryRouter initialEntries={['/inbox']}>
    <LiveResearchPanel onOpportunityCreated={onOpportunityCreated} pollIntervalMs={pollIntervalMs} maxPollAttempts={maxPollAttempts} />
    <Routes><Route path="*" element={<Location />} /></Routes>
  </MemoryRouter>);
}

function response(body: object, status = 200) {
  return Response.json(body, { status });
}

async function openAndSubmit() {
  await userEvent.click(screen.getByRole('button', { name: 'Research opportunity' }));
  await userEvent.type(screen.getByRole('textbox', { name: 'Official opportunity URL' }), URL);
  await userEvent.click(screen.getByRole('button', { name: 'Start research' }));
}

beforeEach(() => {
  sessionStorage.clear(); localStorage.clear(); vi.restoreAllMocks();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

test('opens one restrained URL-only acquisition surface and cancel closes it', async () => {
  mount();
  expect(screen.getByRole('button', { name: 'Research opportunity' })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Research opportunity' }));
  expect(screen.getByRole('heading', { name: 'Research opportunity' })).toBeVisible();
  expect(screen.getByText('QUALOR will verify official evidence before evaluating the opportunity.')).toBeVisible();
  expect(screen.getByRole('textbox', { name: 'Official opportunity URL' })).toHaveAttribute('placeholder', 'https://example.org/opportunity/rules');
  expect(screen.queryByLabelText(/goal|founder|project|budget|gateway|model/i)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('textbox', { name: 'Official opportunity URL' })).not.toBeInTheDocument();
});

test('requires an HTTPS-looking URL before any request', async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); mount();
  await userEvent.click(screen.getByRole('button', { name: 'Research opportunity' }));
  const start = screen.getByRole('button', { name: 'Start research' });
  expect(start).toBeDisabled();
  await userEvent.type(screen.getByRole('textbox', { name: 'Official opportunity URL' }), 'http://example.org/rules');
  expect(start).toBeEnabled();
  await userEvent.click(start);
  expect(screen.getByRole('alert')).toHaveTextContent('Enter an official HTTPS URL.');
  expect(fetcher).not.toHaveBeenCalled();
});

test('a valid URL starts once, stores only run identity, and disables duplicate submission', async () => {
  let release!: (value: Response) => void;
  const pending = new Promise<Response>(resolve => { release = resolve; });
  const fetcher = vi.fn(async () => pending);
  vi.stubGlobal('fetch', fetcher); mount();
  await userEvent.click(screen.getByRole('button', { name: 'Research opportunity' }));
  await userEvent.type(screen.getByRole('textbox', { name: 'Official opportunity URL' }), URL);
  fireEvent.click(screen.getByRole('button', { name: 'Start research' }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  expect(screen.getByRole('button', { name: 'Starting research' })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: 'Starting research' }));
  expect(fetcher).toHaveBeenCalledTimes(1);
  release(response({ run_id: 'run-live-one', status: 'STARTING' }, 202));
  expect(await screen.findByRole('status')).toHaveTextContent('Starting research');
  expect(sessionStorage).toHaveLength(1);
  expect(sessionStorage.getItem('qualor.activeLiveRunId')).toBe('run-live-one');
  expect(JSON.stringify(sessionStorage)).not.toMatch(/secret|token|aws|profile/i);
});

test.each([
  ['STARTING', 'Starting research'],
  ['RESEARCHING', 'Researching official sources'],
  ['EVALUATING', 'Evaluating evidence'],
] as const)('recovers and renders truthful %s status without progress fiction', async (status, copy) => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  vi.stubGlobal('fetch', vi.fn(async () => response({ ...STATUS, status })));
  mount();
  expect(await screen.findByRole('status')).toHaveTextContent(copy);
  expect(screen.queryByText(/\d+%|almost done|steps? remaining|estimated/i)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Research opportunity' })).toBeDisabled();
});

test('completion stops polling, clears recovery state, refreshes Inbox, and opens persisted workspace', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  const fetcher = vi.fn(async () => response({
    ...STATUS, status: 'COMPLETED', completed_at: '2026-09-12T12:01:00Z',
    opportunity_id: 'opportunity/live one', recommendation: 'SKIP',
  }));
  vi.stubGlobal('fetch', fetcher);
  const refresh = vi.fn(); mount(refresh, 5);
  await waitFor(() => expect(screen.getByLabelText('Current route')).toHaveTextContent('/inbox/opportunity%2Flive%20one'));
  expect(refresh).toHaveBeenCalledTimes(1);
  expect(sessionStorage.getItem('qualor.activeLiveRunId')).toBeNull();
  await new Promise(resolve => setTimeout(resolve, 25));
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test('a completed response without persisted opportunity authority fails closed', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  vi.stubGlobal('fetch', vi.fn(async () => response({
    ...STATUS, status: 'COMPLETED', completed_at: '2026-09-12T12:01:00Z',
  })));
  mount();
  expect(await screen.findByRole('status')).toHaveTextContent('Research could not complete');
  expect(screen.getByLabelText('Current route')).toHaveTextContent('/inbox');
});

test('FAILED is bounded, stops polling, and offers retry only after terminal state', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  const fetcher = vi.fn(async () => response({
    ...STATUS, status: 'FAILED', completed_at: '2026-09-12T12:01:00Z',
    error_code: 'LIVE_PROVIDER_FAILED', detail: 'raw provider request id',
  }));
  vi.stubGlobal('fetch', fetcher); mount(vi.fn(), 5);
  expect(await screen.findByRole('status')).toHaveTextContent('Research could not complete');
  expect(screen.queryByText(/raw provider|request id/i)).not.toBeInTheDocument();
  expect(document.querySelector('.research-activity')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible();
  await new Promise(resolve => setTimeout(resolve, 25));
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test('BUDGET_STOPPED is a distinct terminal safety state', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  vi.stubGlobal('fetch', vi.fn(async () => response({
    ...STATUS, status: 'BUDGET_STOPPED', completed_at: '2026-09-12T12:01:00Z',
    error_code: 'BUDGET_STOPPED', termination_reason: 'BUDGET_EXHAUSTED',
  })));
  mount();
  expect(await screen.findByRole('status')).toHaveTextContent('Research stopped at the configured safety budget.');
  expect(screen.queryByText(/application error/i)).not.toBeInTheDocument();
  expect(document.querySelector('.research-activity')).not.toBeInTheDocument();
});

test('busy admission is bounded and does not create a UI job', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ code: 'LIVE_RUN_BUSY' }, 409)));
  mount(); await openAndSubmit();
  expect(await screen.findByRole('alert')).toHaveTextContent('Another research run is already active.');
  expect(sessionStorage).toHaveLength(0);
  expect(screen.getByRole('button', { name: 'Start research' })).toBeEnabled();
});

test('raw server failures never render and retry is absent before a terminal run', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({
    code: 'INTERNAL_LIVE_RUN_FAILURE', detail: 'AWS endpoint private trace',
  }, 500)));
  mount(); await openAndSubmit();
  expect(await screen.findByRole('alert')).toHaveTextContent('Research could not complete.');
  expect(screen.queryByText(/AWS endpoint|private trace/i)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
});

test('unmount aborts the one active status request', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  let signal: AbortSignal | undefined;
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    signal = init?.signal as AbortSignal;
    return await new Promise<Response>(() => undefined);
  }));
  const view = mount();
  await waitFor(() => expect(signal).toBeDefined());
  view.unmount();
  expect(signal?.aborted).toBe(true);
});

test('network retries are sequential and bounded without changing the last real status', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  let inFlight = 0; let maximum = 0;
  const fetcher = vi.fn(async () => {
    inFlight += 1; maximum = Math.max(maximum, inFlight);
    await new Promise(resolve => setTimeout(resolve, 2));
    inFlight -= 1;
    throw new Error('private network diagnostics');
  });
  vi.stubGlobal('fetch', fetcher); mount(vi.fn(), 5);
  expect(await screen.findByRole('status')).toHaveTextContent('Research status is temporarily unavailable.');
  expect(fetcher).toHaveBeenCalledTimes(4);
  expect(maximum).toBe(1);
  await new Promise(resolve => setTimeout(resolve, 25));
  expect(fetcher).toHaveBeenCalledTimes(4);
});

test('a nonterminal server status has a bounded polling lifecycle', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  const fetcher = vi.fn(async () => response({ ...STATUS, status: 'RESEARCHING' }));
  vi.stubGlobal('fetch', fetcher); mount(vi.fn(), 5, 2);
  expect(await screen.findByRole('status')).toHaveTextContent('Research status is temporarily unavailable.');
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(sessionStorage.getItem('qualor.activeLiveRunId')).toBe('run-live-one');
  expect(screen.getByRole('button', { name: 'Research opportunity' })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: 'Open activity' }));
  await new Promise(resolve => setTimeout(resolve, 25));
  expect(fetcher).toHaveBeenCalledTimes(2);
});

test('a definitively unavailable recovered run is cleared and permits a fresh deliberate start', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'stale-run');
  const fetcher = vi.fn(async () => response({ code: 'LIVE_RUN_UNAVAILABLE' }, 404));
  vi.stubGlobal('fetch', fetcher); mount(vi.fn(), 5);
  expect(await screen.findByRole('status')).toHaveTextContent('Research status is temporarily unavailable.');
  expect(sessionStorage.getItem('qualor.activeLiveRunId')).toBeNull();
  expect(screen.getByRole('button', { name: 'Research opportunity' })).toBeEnabled();
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test('successful and failed requests share the same overall polling bound', async () => {
  sessionStorage.setItem('qualor.activeLiveRunId', 'run-live-one');
  const fetcher = vi.fn()
    .mockResolvedValueOnce(response({ ...STATUS, status: 'RESEARCHING' }))
    .mockRejectedValue(new Error('private transport detail'));
  vi.stubGlobal('fetch', fetcher); mount(vi.fn(), 5, 2);
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Research status is temporarily unavailable.'));
  expect(fetcher).toHaveBeenCalledTimes(2);
  await new Promise(resolve => setTimeout(resolve, 25));
  expect(fetcher).toHaveBeenCalledTimes(2);
});
