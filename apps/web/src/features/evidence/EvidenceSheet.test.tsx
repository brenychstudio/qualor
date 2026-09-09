import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { App } from '../../App';
import type {
  EvidenceClaimView,
  EvidenceProofView,
  EvidenceSheetView,
  InboxItem,
  InboxResponse,
  OpportunityWorkspaceResponse,
} from '../../generated/domain';
import { EvidenceSheet } from './EvidenceSheet';

const page = { offset: 0, limit: 50, total: 0, has_more: false };

const EXACT_EXCERPT =
  'Applicants must be incorporated in the region  before the closing date, and "sole traders" are excluded.';

function proof(changes: Partial<EvidenceProofView> = {}): EvidenceProofView {
  return {
    category: 'ENTRANT_TYPE',
    domain: 'official-domain.example',
    evidence_id: 'evidence-entrant',
    evidence_version: 2,
    excerpt: EXACT_EXCERPT,
    freshness: 'FRESH',
    original_url: 'https://official-domain.example/rules#entrant',
    retrieved_at: '2026-09-08T09:15:00Z',
    source_id: 'source-official',
    source_type: 'OFFICIAL_RULES',
    source_version: 'v3',
    url: 'https://reader.example/proxy/rules',
    ...changes,
  };
}

function claim(changes: Partial<EvidenceClaimView> = {}): EvidenceClaimView {
  return {
    rule_id: 'r_entrant_type',
    state: 'PASS',
    reason_codes: ['ENTRANT_TYPE_SUPPORTED'],
    evidence_refs: ['evidence-entrant'],
    ...changes,
  };
}

function sheet(changes: Partial<EvidenceSheetView> = {}): EvidenceSheetView {
  return {
    opportunity_id: 'selected',
    opportunity_version: 4,
    freshness: 'FRESH',
    coverage: [{ category: 'ENTRANT_TYPE', state: 'EVALUATED' }],
    claims: [claim()],
    claims_page: page,
    proofs: [proof()],
    proofs_page: page,
    eligibility: { evaluated_at: '2026-09-08T10:00:00Z', policy_version: 1, state: 'PASS' },
    project_fit: {
      blocking_gaps: [],
      evaluated_at: '2026-09-08T10:00:00Z',
      factor_results: [
        { factor: 'product_fit', rating: 3, reasons: ['MATCHED_REQUIREMENT'], fact_refs: [], requirement_refs: ['req-1'] },
      ],
      match_status: 'STRONG',
      matched_requirement_refs: ['req-1'],
      missing_facts: [],
      policy_version: 1,
      project: { id: 'project-1', name: 'Recorded project', version: 4 },
    },
    constraints_conflicts: {
      checked_rule_categories: [],
      evaluated_at: '2026-09-08T10:00:00Z',
      evidence_refs: [],
      founder_constraints: ['NO_EQUITY'],
      missing_rule_categories: [],
      policy_version: 1,
      reasons: [],
      status: 'NO_CONFLICT_DETECTED_IN_CHECKED_RULES',
    },
    reward_deadline: {
      deadline: { timezone_status: 'UTC', values: ['2026-11-30T23:59:00Z'] },
      evidence_refs: ['evidence-entrant'],
      evidence_refs_scope: 'CURRENT_PROOF_PAGE',
      rewards: [
        {
          id: 'reward-1',
          kind: 'CASH_PRIZE',
          amount: { amount: '50000', currency: 'EUR' },
          provenance: 'DOCUMENTED',
          schema_version: '1',
          created_at: '2026-09-01T00:00:00Z',
          updated_at: '2026-09-01T00:00:00Z',
          version: 1,
        },
      ],
    },
    ...changes,
  };
}

function inbox(): InboxResponse {
  const item = {
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
    best_project: { id: 'project-1', name: 'Recorded project', version: 4 },
    effort: null,
    mode: 'FIXTURE',
    human_action_available: false,
  } as unknown as InboxItem;
  return { items: [item], page, profile_present: true, generated_at: '2026-09-08T10:00:00Z' } as unknown as InboxResponse;
}

function workspace(): OpportunityWorkspaceResponse {
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
      best_project: { id: 'project-1', name: 'Recorded project', version: 4 },
      eligibility: 'PASS',
      primary_blocker: null,
      missing_information: [],
      effort: null,
      readiness: null,
      freshness: 'FRESH',
      deadline: { timezone_status: 'UTC', values: ['2026-11-30T23:59:00Z'] },
      primary_action: { available: false, reason: 'VALID', approval_request: null },
    },
  } as unknown as OpportunityWorkspaceResponse;
}

function stubWorkspace(view: EvidenceSheetView) {
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.endsWith('/inbox')) return Response.json(inbox());
    if (url.endsWith('/opportunities/selected/workspace')) return Response.json(workspace());
    if (url.includes('/opportunities/selected/evidence')) return Response.json(view);
    return Response.json({ founder: null, projects: [] });
  }));
}

async function openSheet(view: EvidenceSheetView = sheet()) {
  stubWorkspace(view);
  render(<MemoryRouter initialEntries={['/inbox/selected']}><App /></MemoryRouter>);
  const trigger = await screen.findByRole('button', { name: /why this decision/i });
  await userEvent.click(trigger);
  const plane = await screen.findByRole('region', { name: 'Decision proof' });
  return { plane, trigger };
}

function renderSheet(view: EvidenceSheetView = sheet()) {
  stubWorkspace(view);
  return render(<MemoryRouter><EvidenceSheet opportunityId="selected" /></MemoryRouter>);
}

test('orders the four evidence sections as Eligibility, Project Fit, Constraints & Conflicts, Reward & Deadline', async () => {
  renderSheet(sheet());
  await screen.findByRole('region', { name: 'Eligibility' });
  const sections = screen.getAllByRole('region').map(section => section.getAttribute('aria-label'));
  expect(sections).toEqual(['Eligibility', 'Project Fit', 'Constraints & Conflicts', 'Reward & Deadline']);
});

test('separates QUALOR interpretation from the exact, unmodified source excerpt', async () => {
  const view = renderSheet(sheet());
  await screen.findByRole('region', { name: 'Eligibility' });
  const excerpt = view.container.querySelector('blockquote');
  expect(excerpt).not.toBeNull();
  expect(excerpt!.textContent).toBe(EXACT_EXCERPT);
  expect(excerpt!.textContent).not.toContain('PASS');
  const eligibility = screen.getByRole('region', { name: 'Eligibility' });
  expect(within(eligibility).getAllByText('PASS').length).toBeGreaterThan(0);
});

test('presents each first-class evidence state as recorded', async () => {
  renderSheet(sheet({
    claims: [
      claim({ rule_id: 'r_pass', state: 'PASS' }),
      claim({ rule_id: 'r_fail', state: 'FAIL' }),
      claim({ rule_id: 'r_unknown', state: 'UNKNOWN', evidence_refs: [] }),
      claim({ rule_id: 'r_conflict', state: 'CONFLICT', evidence_refs: ['evidence-entrant', 'evidence-other'] }),
      claim({ rule_id: 'r_stale', state: 'STALE' }),
    ],
    proofs: [
      proof(),
      proof({ evidence_id: 'evidence-other', domain: 'other-domain.example', excerpt: 'Opposing official statement.', original_url: 'https://other-domain.example/faq' }),
    ],
  }));
  await screen.findByRole('region', { name: 'Eligibility' });
  for (const state of ['PASS', 'FAIL', 'UNKNOWN', 'CONFLICT', 'STALE']) {
    expect(screen.getByRole('group', { name: `${state.toLowerCase()} claim, ${state}` })).toBeVisible();
  }
});

test('states what remains unresolved for UNKNOWN instead of implying a resolved fact', async () => {
  renderSheet(sheet({
    claims: [claim({ rule_id: 'r_legal_form', state: 'UNKNOWN', evidence_refs: [], reason_codes: ['NO_ADMISSIBLE_SOURCE'] })],
    proofs: [],
  }));
  const block = await screen.findByRole('group', { name: 'legal form claim, UNKNOWN' });
  expect(within(block).getByText(/no admissible evidence resolves/i)).toBeVisible();
  expect(within(block).queryByRole('link', { name: /view original/i })).not.toBeInTheDocument();
});

test('presents opposing evidence and the review requirement for CONFLICT without choosing a side', async () => {
  renderSheet(sheet({
    claims: [claim({ rule_id: 'r_entrant_type', state: 'CONFLICT', evidence_refs: ['evidence-entrant', 'evidence-other'] })],
    proofs: [
      proof(),
      proof({ evidence_id: 'evidence-other', domain: 'other-domain.example', excerpt: 'Sole traders may apply.', original_url: 'https://other-domain.example/faq', source_type: 'OFFICIAL_FAQ' }),
    ],
  }));
  const block = await screen.findByRole('group', { name: 'entrant type claim, CONFLICT' });
  expect(within(block).getAllByRole('link', { name: /view original/i })).toHaveLength(2);
  expect(within(block).getByText('official-domain.example')).toBeVisible();
  expect(within(block).getByText('other-domain.example')).toBeVisible();
  expect(within(block).getByText(/needs human review/i)).toBeVisible();
});

test('retains the STALE snapshot without presenting it as currently verified', async () => {
  renderSheet(sheet({
    freshness: 'STALE',
    claims: [claim({ rule_id: 'r_entrant_type', state: 'STALE' })],
    proofs: [proof({ freshness: 'STALE' })],
  }));
  const block = await screen.findByRole('group', { name: 'entrant type claim, STALE' });
  expect(block.querySelector('blockquote')).toHaveTextContent(EXACT_EXCERPT, { normalizeWhitespace: false });
  expect(within(block).getByText(/requires renewed verification/i)).toBeVisible();
  expect(within(block).queryByText(/^Verified/)).not.toBeInTheDocument();
});

test('points View original at the preserved official citation with safe link attributes', async () => {
  renderSheet(sheet());
  const link = await screen.findByRole('link', { name: /view original/i });
  expect(link).toHaveAttribute('href', 'https://official-domain.example/rules#entrant');
  expect(link).toHaveAttribute('target', '_blank');
  expect(link.getAttribute('rel')?.split(/\s+/)).toEqual(expect.arrayContaining(['noopener', 'noreferrer']));
});

test('hides technical identifiers until the technical provenance disclosure is opened', async () => {
  renderSheet(sheet({
    proofs: [proof({ technical_provenance: { source_id: 'source-official', policy_version: 1, extraction_state: 'REVIEWED' } })],
  }));
  await screen.findByRole('region', { name: 'Eligibility' });
  expect(screen.queryByText('source-official')).not.toBeInTheDocument();
  expect(screen.queryByText('REVIEWED')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /technical provenance/i }));
  expect(await screen.findByText('source-official')).toBeVisible();
  expect(screen.getByText('REVIEWED')).toBeVisible();
  expect(screen.getByText('evidence-entrant')).toBeVisible();
});

test('opens from the trigger, takes initial focus, and returns focus to the trigger on Escape', async () => {
  const { plane, trigger } = await openSheet();
  await screen.findByRole('region', { name: 'Eligibility' });
  expect(plane).toHaveFocus();
  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('region', { name: 'Decision proof' })).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

test('keeps keyboard focus inside the narrow evidence sheet while it is open', async () => {
  vi.stubGlobal('innerWidth', 390);
  const { plane } = await openSheet();
  await screen.findByRole('region', { name: 'Eligibility' });
  const close = screen.getByRole('button', { name: /close proof/i });
  close.focus();
  await userEvent.tab({ shift: true });
  expect(plane.contains(document.activeElement)).toBe(true);
  expect(close).not.toHaveFocus();
  plane.focus();
  await userEvent.tab();
  expect(plane.contains(document.activeElement)).toBe(true);
  expect(close).toHaveFocus();
});

test('keeps the sheet open when the de-emphasized workspace behind it is clicked', async () => {
  await openSheet();
  await screen.findByRole('region', { name: 'Eligibility' });
  await userEvent.click(screen.getByRole('main'));
  expect(screen.getByRole('region', { name: 'Decision proof' })).toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Eligibility' })).toBeVisible();
});

test('honours the reduced-motion preference while the evidence sheet is open', async () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener() {}, removeEventListener() {} })));
  await openSheet();
  await screen.findByRole('region', { name: 'Eligibility' });
  expect(screen.getByRole('banner').parentElement).toHaveClass('reduce-motion');
});

test('reports an unavailable evidence read without inventing proof', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ code: 'NOT_FOUND' }, { status: 404 })));
  render(<MemoryRouter><EvidenceSheet opportunityId="selected" /></MemoryRouter>);
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/unavailable/i));
  expect(screen.queryByRole('region', { name: 'Eligibility' })).not.toBeInTheDocument();
});
