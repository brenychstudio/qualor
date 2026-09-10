import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import type { ProductState, ProductStateView } from '../../generated/domain';
import { PRODUCT_STATE_COPY, PRIMARY_ACTION_LABELS } from './product-state';
import { ProductStateSurface } from './ProductStateSurface';

const SUBMISSION_LANGUAGE = [/\bsubmit/i, /\bsend\b/i, /apply now/i, /\bpublish/i, /dispatch/i];

const ALL_STATES: ProductState[] = [
  'EMPTY_PROFILE',
  'NO_RESULTS',
  'DISCONNECTED_LIVE_PROVIDER',
  'BUDGET_STOPPED',
  'STALE_EVIDENCE',
  'PARTIAL_SOURCE_FAILURE',
  'UNKNOWN_ELIGIBILITY',
  'REVOKED_APPROVAL',
  'PENDING_APPROVAL',
  'FINISHED_PACK',
];

function view(changes: Partial<ProductStateView> = {}): ProductStateView {
  return {
    state: 'STALE_EVIDENCE',
    primary_action: 'REFRESH_EVIDENCE',
    reason: null,
    evidence_available: true,
    approval_available: false,
    draft_pack_available: false,
    coverage_complete: true,
    recommendation_visible: true,
    pack_id: null,
    ...changes,
  };
}

function renderSurface(changes: Partial<ProductStateView> = {}) {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({})));
  return render(<MemoryRouter><ProductStateSurface productState={view(changes)} /></MemoryRouter>);
}

const surface = () => screen.getByRole('status', { name: /workspace state/i });

test('renders nothing at all when the workspace is healthy', () => {
  const { container } = render(<MemoryRouter><ProductStateSurface productState={view({ state: null, primary_action: null })} /></MemoryRouter>);
  expect(container).toBeEmptyDOMElement();
});

test('renders nothing when the server supplied no product state', () => {
  const { container } = render(<MemoryRouter><ProductStateSurface productState={null} /></MemoryRouter>);
  expect(container).toBeEmptyDOMElement();
});

test.each(ALL_STATES)('%s names itself in words, not by colour alone', state => {
  renderSurface({ state, primary_action: null });
  const region = surface();
  expect(within(region).getByText(state)).toBeVisible();
  expect(within(region).getByText(PRODUCT_STATE_COPY[state].title)).toBeVisible();
  expect(within(region).getByText(PRODUCT_STATE_COPY[state].detail)).toBeVisible();
});

test.each([
  ['EMPTY_PROFILE', 'CREATE_PROFILE', 'Create profile'],
  ['NO_RESULTS', 'ADJUST_SEARCH', 'Adjust search'],
  ['PARTIAL_SOURCE_FAILURE', 'REVIEW_AVAILABLE_EVIDENCE', 'Review available evidence'],
  ['STALE_EVIDENCE', 'REFRESH_EVIDENCE', 'Refresh evidence'],
  ['UNKNOWN_ELIGIBILITY', 'RESOLVE_UNKNOWNS', 'Resolve unknowns'],
  ['BUDGET_STOPPED', 'REVIEW_AVAILABLE_EVIDENCE', 'Review available evidence'],
  ['DISCONNECTED_LIVE_PROVIDER', 'RECONNECT_PROVIDER', 'Reconnect provider'],
  ['PENDING_APPROVAL', 'REVIEW_APPROVAL', 'Review approval'],
  ['REVOKED_APPROVAL', 'REVIEW_CHANGES', 'Review changes'],
  ['FINISHED_PACK', 'OPEN_APPLICATION_PACK', 'Open application pack'],
] as const)('%s presents the canonical primary action %s', (state, action, label) => {
  renderSurface({ state, primary_action: action, pack_id: state === 'FINISHED_PACK' ? 'pack-1' : null, draft_pack_available: state === 'FINISHED_PACK' });
  expect(within(surface()).getByText(label)).toBeVisible();
  expect(PRIMARY_ACTION_LABELS[action]).toBe(label);
});

test('shows the bounded server reason code without inventing prose', () => {
  renderSurface({ state: 'BUDGET_STOPPED', primary_action: 'REVIEW_AVAILABLE_EVIDENCE', reason: 'BUDGET_EXHAUSTED' });
  expect(within(surface()).getByText('BUDGET_EXHAUSTED')).toBeVisible();
});

test('omits the reason line entirely when the server recorded none', () => {
  renderSurface({ state: 'PENDING_APPROVAL', primary_action: 'REVIEW_APPROVAL', reason: null });
  expect(within(surface()).queryByText(/reason/i)).not.toBeInTheDocument();
});

test('states that the evidence sheet is unavailable when the server says so', () => {
  renderSurface({ state: 'EMPTY_PROFILE', primary_action: 'CREATE_PROFILE', evidence_available: false });
  expect(within(surface()).getByText(/evidence sheet unavailable/i)).toBeVisible();
});

test('states that proof remains readable when the server keeps it available', () => {
  renderSurface({ state: 'STALE_EVIDENCE', primary_action: 'REFRESH_EVIDENCE', evidence_available: true });
  expect(within(surface()).getByText(/evidence remains readable/i)).toBeVisible();
});

test('marks incomplete coverage separately from the decision itself', () => {
  renderSurface({ state: 'PARTIAL_SOURCE_FAILURE', primary_action: 'REVIEW_AVAILABLE_EVIDENCE', coverage_complete: false });
  expect(within(surface()).getByText(/coverage is incomplete/i)).toBeVisible();
});

test('a partial run with complete coverage does not claim incomplete coverage', () => {
  renderSurface({ state: 'PARTIAL_SOURCE_FAILURE', primary_action: 'REVIEW_AVAILABLE_EVIDENCE', coverage_complete: true });
  expect(within(surface()).queryByText(/coverage is incomplete/i)).not.toBeInTheDocument();
});

test('never renders a recommendation, eligibility verdict or strategy score of its own', () => {
  for (const state of ALL_STATES) {
    const { unmount } = renderSurface({ state, primary_action: null });
    const text = surface().textContent ?? '';
    expect(text).not.toMatch(/\bAPPLY\b|\bPREPARE\b|\bWATCH\b|\bSKIP\b/);
    expect(text).not.toMatch(/\bPASS\b/);
    expect(text).not.toMatch(/\/\s*100|score/i);
    unmount();
  }
});

test('never implies live activity in a degraded state', () => {
  for (const state of ALL_STATES) {
    const { unmount } = renderSurface({ state, primary_action: null });
    const text = surface().textContent ?? '';
    expect(text).not.toMatch(/\bLIVE\b/);
    expect(text).not.toMatch(/searching|in progress|running now/i);
    unmount();
  }
});

test('offers no external submission affordance in any state', () => {
  for (const state of ALL_STATES) {
    const { unmount } = renderSurface({ state, primary_action: null });
    const text = surface().textContent ?? '';
    for (const pattern of SUBMISSION_LANGUAGE) expect(text).not.toMatch(pattern);
    unmount();
  }
});

test('links an existing pack whenever the server keeps it available', () => {
  renderSurface({
    state: 'DISCONNECTED_LIVE_PROVIDER',
    primary_action: 'RECONNECT_PROVIDER',
    draft_pack_available: true,
    pack_id: 'pack-1',
  });
  const link = within(surface()).getByRole('link', { name: /open application pack/i });
  expect(link).toHaveAttribute('href', '/draft-packs/pack-1');
});

test('offers no pack link when the server reports none', () => {
  renderSurface({ state: 'PENDING_APPROVAL', primary_action: 'REVIEW_APPROVAL', draft_pack_available: false, pack_id: null });
  expect(within(surface()).queryByRole('link', { name: /application pack/i })).not.toBeInTheDocument();
});

test('says approval is unavailable only because the server said so', () => {
  renderSurface({ state: 'REVOKED_APPROVAL', primary_action: 'REVIEW_CHANGES', approval_available: false, reason: 'CHANGE_REVOKED' });
  const region = surface();
  expect(within(region).getByText(/approval unavailable/i)).toBeVisible();
  expect(within(region).getByText('CHANGE_REVOKED')).toBeVisible();
});

test('does not claim approval is blocked when the server still permits it', () => {
  renderSurface({ state: 'PARTIAL_SOURCE_FAILURE', primary_action: 'REVIEW_AVAILABLE_EVIDENCE', approval_available: true });
  expect(within(surface()).queryByText(/approval unavailable/i)).not.toBeInTheDocument();
});

test('exposes the state to assistive technology without relying on styling', () => {
  renderSurface({ state: 'STALE_EVIDENCE', primary_action: 'REFRESH_EVIDENCE' });
  const region = surface();
  expect(region).toHaveAttribute('role', 'status');
  expect(region).toHaveAccessibleName(/workspace state/i);
});
