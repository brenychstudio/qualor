import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { App } from '../../App';
import type { DraftPackSection, DraftPackView } from '../../generated/domain';

const CANONICAL_KEYS = [
  'SUBMISSION_SUMMARY',
  'PROJECT_FIT_NARRATIVE',
  'ELIGIBILITY_CHECKLIST',
  'REQUIRED_DELIVERABLES',
  'EVIDENCE_REFERENCES',
  'READINESS_GAPS',
  'SUGGESTED_APPLICATION_ANSWERS',
];

const MUTATION_CONTROLS = [/\bedit\b/i, /\bsave\b/i, /regenerate/i, /\bdelete\b/i, /overwrite/i, /autosave/i];
const SUBMISSION_CONTROLS = [/\bsubmit/i, /\bsend\b/i, /apply now/i, /\bpublish/i, /dispatch/i, /\bemail\b/i, /devpost/i, /autofill/i];

const EXACT_EXCERPT = 'Applicants must be incorporated  in the region before the closing date.';
const CITATION_URL = 'https://official-domain.example/rules#entrant';

function sections(): DraftPackSection[] {
  return [
    { key: 'SUBMISSION_SUMMARY', title: '01 Submission summary', content: 'Local draft for human review. No external submission.\nRegional Founder Programme / 2026', evidence_refs: [] },
    { key: 'PROJECT_FIT_NARRATIVE', title: '02 Project fit narrative', content: 'Draft prose — review before use.\nThe project matches the recorded requirements.', evidence_refs: ['evidence-fit'] },
    { key: 'ELIGIBILITY_CHECKLIST', title: '03 Eligibility checklist', content: 'Deterministic eligibility: PASS\nr_entrant_type: PASS', evidence_refs: ['evidence-entrant'] },
    { key: 'REQUIRED_DELIVERABLES', title: '04 Required deliverables', content: 'MISSING: opportunity.deliverables', evidence_refs: [] },
    { key: 'EVIDENCE_REFERENCES', title: '05 Evidence references', content: `evidence-entrant / version 2 / OFFICIAL_RULES\nExact source excerpt (untrusted quoted data):\n${EXACT_EXCERPT}\nSource: ${CITATION_URL}\nRetrieved: 2026-09-08T09:15:00Z`, evidence_refs: ['evidence-entrant'] },
    { key: 'READINESS_GAPS', title: '06 Readiness gaps', content: 'Deterministic readiness: GAPS_EXECUTABLE\nREPOSITORY\nMISSING: project.demo_url', evidence_refs: [] },
    { key: 'SUGGESTED_APPLICATION_ANSWERS', title: '07 Suggested application answers', content: 'Draft prose — unresolved fields require human input.\nAnswer drafts follow the recorded facts.', evidence_refs: [] },
  ];
}

function pack(changes: Partial<DraftPackView> = {}): DraftPackView {
  return {
    id: 'pack-1',
    version: 1,
    approval_id: 'approval-1',
    approval_version: 2,
    actor_id: 'founder-1',
    mode: 'FIXTURE',
    draft_job_id: 'job-1',
    draft_job_version: 3,
    opportunity_id: 'selected',
    approved_snapshot: {
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
    },
    evidence_refs: ['evidence-entrant', 'evidence-fit'],
    evidence_versions: [{ evidence_id: 'evidence-entrant', version: 2 }, { evidence_id: 'evidence-fit', version: 1 }],
    source_refs: [CITATION_URL, 'source-internal-1'],
    missing_fields: ['opportunity.deliverables', 'project.demo_url'],
    sections: sections() as unknown as DraftPackView['sections'],
    generated_at: '2026-09-09T12:45:00Z',
    creator_kind: 'DETERMINISTIC',
    content_kind: 'DRAFT_FOR_HUMAN_REVIEW',
    ...changes,
  };
}

function stub(response: DraftPackView | 'missing' = pack()) {
  const calls = { pack: 0 };
  vi.stubGlobal('fetch', vi.fn(async (request: RequestInfo | URL) => {
    const url = String(request);
    if (url.includes('/draft-packs/')) {
      calls.pack += 1;
      return response === 'missing'
        ? Response.json({ code: 'NOT_FOUND' }, { status: 404 })
        : Response.json(response);
    }
    if (url.endsWith('/inbox')) return Response.json({ items: [], page: { offset: 0, limit: 50, total: 0, has_more: false }, profile_present: true, generated_at: '2026-09-09T12:00:00Z' });
    if (url.includes('/runs')) return Response.json({ runs: [], events: [], runs_page: { offset: 0, limit: 50, total: 0, has_more: false }, events_page: { offset: 0, limit: 50, total: 0, has_more: false } });
    return Response.json({ founder: null, projects: [] });
  }));
  return calls;
}

function openPack(response: DraftPackView | 'missing' = pack()) {
  const calls = stub(response);
  const view = render(<MemoryRouter initialEntries={['/draft-packs/pack-1']}><App /></MemoryRouter>);
  return { ...view, calls };
}

test('opens the persisted pack directly at its own URL with no prior app state', async () => {
  const { calls } = openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  expect(article).toBeVisible();
  await waitFor(() => expect(calls.pack).toBe(1));
  expect(String((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0])).toContain('/draft-packs/pack-1');
});

test('renders all seven canonical sections in the exact server order', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const rendered = within(article).getAllByRole('region');
  expect(rendered.map(section => section.getAttribute('data-section-key'))).toEqual(CANONICAL_KEYS);
});

test('presents each section with its server-authored numbered title', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  for (const title of ['01 Submission summary', '02 Project fit narrative', '03 Eligibility checklist', '04 Required deliverables', '05 Evidence references', '06 Readiness gaps', '07 Suggested application answers']) {
    expect(within(article).getByRole('heading', { name: title })).toBeVisible();
  }
});

test('attributes the pack to its approval and drafting job', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  expect(within(article).getByText('approval-1')).toBeVisible();
  expect(within(article).getByText('founder-1')).toBeVisible();
  expect(within(article).getByText('pack-1')).toBeVisible();
  expect(within(article).getByText('job-1')).toBeVisible();
  expect(within(article).getByText('DETERMINISTIC')).toBeVisible();
  expect(within(article).getByText('DRAFT_FOR_HUMAN_REVIEW')).toBeVisible();
});

test('attributes the exact bound versions the approval was recorded against', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const versions = within(article).getByRole('group', { name: /bound versions/i });
  expect(within(versions).getByText(/opportunity version 4/i)).toBeVisible();
  expect(within(versions).getByText(/profile version 2/i)).toBeVisible();
  expect(within(versions).getByText(/project version 3/i)).toBeVisible();
  expect(within(versions).getByText(/decision version 2/i)).toBeVisible();
  expect(within(versions).getByText(/eligibility 1/i)).toBeVisible();
});

test('states the recorded runtime mode instead of implying live research', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  expect(within(article).getByText('FIXTURE')).toBeVisible();
  expect(within(article).queryByText('LIVE')).not.toBeInTheDocument();
});

test('lists the exact persisted evidence and source references', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const references = within(article).getByRole('group', { name: /source and evidence references/i });
  expect(within(references).getByText('evidence-entrant')).toBeVisible();
  expect(within(references).getByText('evidence-fit')).toBeVisible();
  expect(within(references).getByText('source-internal-1')).toBeVisible();
});

test('links a persisted citation URL exactly, with safe external attributes', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const link = within(article).getByRole('link', { name: CITATION_URL });
  expect(link).toHaveAttribute('href', CITATION_URL);
  expect(link).toHaveAttribute('target', '_blank');
  expect(link.getAttribute('rel')?.split(/\s+/)).toEqual(expect.arrayContaining(['noopener', 'noreferrer']));
});

test('never fabricates a link for a reference that is not a persisted URL', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  expect(within(article).queryByRole('link', { name: /source-internal-1/ })).not.toBeInTheDocument();
  for (const link of within(article).getAllByRole('link')) {
    expect(link.getAttribute('href')).not.toContain('source-internal-1');
  }
});

test('keeps every missing field explicit instead of polishing over the gap', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const missing = within(article).getByRole('group', { name: /missing information/i });
  expect(within(missing).getByText('opportunity.deliverables')).toBeVisible();
  expect(within(missing).getByText('project.demo_url')).toBeVisible();
  expect(within(missing).getByText(/2 recorded gaps/i)).toBeVisible();
});

test('labels generated narrative as draft prose', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  for (const key of ['PROJECT_FIT_NARRATIVE', 'SUGGESTED_APPLICATION_ANSWERS']) {
    const section = within(article).getByRole('region', { name: new RegExp(key.replace(/_/g, ' '), 'i') });
    expect(within(section).getByText('Draft prose')).toBeVisible();
  }
});

test('keeps evidence material typed apart from draft prose', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const evidence = within(article).getByRole('region', { name: /evidence references/i });
  expect(within(evidence).getByText('Source evidence')).toBeVisible();
  expect(within(evidence).queryByText('Draft prose')).not.toBeInTheDocument();
  const prose = within(article).getByRole('region', { name: /project fit narrative/i });
  expect(within(prose).queryByText('Source evidence')).not.toBeInTheDocument();
});

test('preserves the exact section content the server recorded', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const evidence = within(article).getByRole('region', { name: /evidence references/i });
  expect(evidence.textContent).toContain(EXACT_EXCERPT);
});

test('presents the pack as a finished record for review', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  expect(within(article).getByText(/2026-09-09T12:45:00Z/)).toBeVisible();
  expect(within(article).getByText(/finished/i)).toBeVisible();
});

test('offers no control that could edit, save or regenerate the pack', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  expect(within(article).queryAllByRole('button')).toHaveLength(0);
  expect(within(article).queryAllByRole('textbox')).toHaveLength(0);
  expect(within(article).queryAllByRole('checkbox')).toHaveLength(0);
  expect(article.querySelectorAll('form, input, textarea, select, [contenteditable]')).toHaveLength(0);
  for (const control of within(article).getAllByRole('link')) {
    for (const pattern of MUTATION_CONTROLS) expect(control.textContent ?? '').not.toMatch(pattern);
  }
});

test('offers no control that could send the pack anywhere', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const controls = [...within(article).queryAllByRole('button'), ...within(article).getAllByRole('link')];
  for (const control of controls) {
    for (const pattern of SUBMISSION_CONTROLS) expect(control.textContent ?? '').not.toMatch(pattern);
  }
  expect(article.textContent ?? '').toMatch(/no external submission/i);
});

test('reads the pack without any mutating request', async () => {
  openPack();
  await screen.findByRole('article', { name: /application pack/i });
  const fetchMock = globalThis.fetch as ReturnType<typeof vi.fn>;
  for (const [, init] of fetchMock.mock.calls) {
    expect((init as RequestInit | undefined)?.method ?? 'GET').toBe('GET');
  }
});

test('says plainly when the requested pack does not exist', async () => {
  openPack('missing');
  const canvas = await screen.findByRole('main');
  await waitFor(() => expect(within(canvas).getByRole('status')).toHaveTextContent(/unavailable/i));
  expect(within(canvas).getByRole('heading', { name: /application pack unavailable/i })).toBeVisible();
  expect(screen.queryByRole('article', { name: /application pack/i })).not.toBeInTheDocument();
});

test('does not hide a section the server recorded as empty', async () => {
  const withEmpty = pack();
  const recorded = sections();
  recorded[3] = { ...recorded[3], content: '' };
  openPack({ ...withEmpty, sections: recorded as unknown as DraftPackView['sections'] });
  const article = await screen.findByRole('article', { name: /application pack/i });
  const rendered = within(article).getAllByRole('region');
  expect(rendered.map(section => section.getAttribute('data-section-key'))).toEqual(CANONICAL_KEYS);
  const deliverables = within(article).getByRole('region', { name: /required deliverables/i });
  expect(within(deliverables).getByText(/no content recorded/i)).toBeVisible();
});

/* The judge-facing order of the finished document: what QUALOR prepared, then how it can be
 * traced. Every identifier the pack recorded is still here and still exact — the change is
 * that a reader meets the application before the audit trail of it. */

test('leads with what was prepared, before how it can be traced', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const first = within(article).getByRole('heading', { name: /01 Submission summary/i });
  const traceability = within(article).getByRole('group', { name: /traceability/i });
  expect(first.compareDocumentPosition(traceability) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  // And the identifiers are not what the document opens with.
  const packId = within(article).getByText('pack-1');
  expect(first.compareDocumentPosition(packId) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test('keeps every recorded identifier, gathered into traceability', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const trace = within(article).getByRole('group', { name: /traceability/i });
  for (const value of ['pack-1', 'approval-1', 'job-1', 'founder-1', 'DETERMINISTIC',
    'DRAFT_FOR_HUMAN_REVIEW', 'FIXTURE']) {
    expect(within(trace).getByText(value), `${value} in traceability`).toBeVisible();
  }
  expect(within(trace).getByText(/2026-09-09T12:45:00Z/)).toBeVisible();
  // The bound versions the approval was recorded against stay with the rest of the trail.
  expect(within(trace).getByText(/opportunity version 4/i)).toBeVisible();
  expect(within(trace).getByText(/decision version 2/i)).toBeVisible();
});

test('states how the pack was prepared in product language before the document begins', async () => {
  openPack();
  const article = await screen.findByRole('article', { name: /application pack/i });
  const preparation = within(article).getByRole('group', { name: /how this pack was prepared/i });
  // The same recorded facts, read as language rather than as enum tokens.
  expect(preparation.textContent ?? '').toMatch(/draft for human review/i);
  expect(preparation.textContent ?? '').toMatch(/deterministic/i);
  const first = within(article).getByRole('heading', { name: /01 Submission summary/i });
  expect(preparation.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
