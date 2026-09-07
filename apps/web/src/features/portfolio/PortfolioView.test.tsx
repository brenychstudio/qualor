import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';
import { PortfolioView } from './PortfolioView';
import type { FounderProfile, ProjectProfile, PortfolioView as Portfolio } from '../../generated/domain';
const founder: FounderProfile = { id: 'founder-1', version: 3, schema_version: '1', provenance: 'USER_ASSERTED', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-02T00:00:00Z', country_of_residence: { value: 'Spain', provenance: 'DOCUMENTED', evidence_refs: ['proof-1'] }, team_size: { value: 2, provenance: 'USER_ASSERTED' }, constraints: ['Keep my private code private'], citizenship: { value: 'Ukraine', provenance: 'DOCUMENTED', evidence_refs: ['proof-2'] } };
const project: ProjectProfile = { id: 'project-1', version: 2, schema_version: '1', provenance: 'USER_ASSERTED', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-02T00:00:00Z', name: 'Test project', problem: { value: 'Research overhead', provenance: 'USER_ASSERTED' }, material_readiness: [{ kind: 'DEMO', ready: { value: true, provenance: 'DOCUMENTED', evidence_refs: ['demo-proof'] } }] };
let saved: { url: string; body: Record<string, unknown>; token: string | null }[];
let portfolio: Portfolio;
let failSave: number;
let readOnly: boolean;
beforeEach(() => {
  saved = []; failSave = 0; readOnly = false;
  portfolio = structuredClone({ founder, projects: [project] });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/session')) return Response.json({ read_only: readOnly, action_token: readOnly ? null : 'test-token' });
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body));
      saved.push({ url, body, token: new Headers(init.headers).get('X-Qualor-Action-Token') });
      if (failSave) return Response.json({ code: failSave === 409 ? 'VERSION_MISMATCH' : 'INVALID_REQUEST' }, { status: failSave });
      if (body.profile) portfolio = { ...portfolio, founder: { ...body.profile, version: body.expected_version + 1 } };
      if (body.project) portfolio = { ...portfolio, projects: [{ ...body.project, version: body.expected_version + 1 }] };
    }
    return Response.json(portfolio);
  }));
});
async function open() { render(<PortfolioView />); await screen.findByDisplayValue('Spain'); }
test('loads persisted founder and project versions and shows absent facts as UNKNOWN', async () => {
  await open();
  expect(screen.getByText('Version 3')).toBeVisible();
  expect(screen.getByText('Version 2')).toBeVisible();
  expect(screen.getByLabelText('Legal form')).toHaveValue('');
  expect(within(screen.getByLabelText('Legal form')).getByRole('option', { name: 'UNKNOWN' })).toBeInTheDocument();
  expect(screen.getByLabelText('Project name')).toHaveValue('Test project');
});
test('saves canonical fields with the loaded version and action token, preserving untouched facts', async () => {
  await open();
  await userEvent.clear(screen.getByLabelText('Country of residence'));
  await userEvent.type(screen.getByLabelText('Country of residence'), 'Portugal');
  await userEvent.click(screen.getByRole('button', { name: 'Save founder profile' }));
  expect(await screen.findByText('Founder profile saved.')).toBeVisible();
  expect(saved[0]).toMatchObject({ url: '/api/v1/profile', token: 'test-token', body: { expected_version: 3, profile: { country_of_residence: { value: 'Portugal', provenance: 'USER_ASSERTED', evidence_refs: [] }, citizenship: { value: 'Ukraine', provenance: 'DOCUMENTED', evidence_refs: ['proof-2'] }, constraints: ['Keep my private code private'] } } });
  expect(screen.getByText('Version 4')).toBeVisible();
});
test('saves a project without discarding non-edited material readiness', async () => {
  await open();
  await userEvent.clear(screen.getByLabelText('Project name'));
  await userEvent.type(screen.getByLabelText('Project name'), 'Updated project');
  await userEvent.click(screen.getByRole('button', { name: 'Save project' }));
  expect(await screen.findByText('Project saved.')).toBeVisible();
  expect(saved[0]).toMatchObject({ url: '/api/v1/projects/project-1', body: { expected_version: 2, project: { name: 'Updated project', material_readiness: [{ kind: 'DEMO', ready: { value: true, provenance: 'DOCUMENTED', evidence_refs: ['demo-proof'] } }] } } });
});
test('refuses invalid field values locally and retains input after server validation errors', async () => {
  await open();
  await userEvent.clear(screen.getByLabelText('Team size'));
  await userEvent.type(screen.getByLabelText('Team size'), '0');
  await userEvent.click(screen.getByRole('button', { name: 'Save founder profile' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/team size/i);
  expect(saved).toHaveLength(0);
  await userEvent.clear(screen.getByLabelText('Team size'));
  await userEvent.type(screen.getByLabelText('Team size'), '4');
  failSave = 422;
  await userEvent.click(screen.getByRole('button', { name: 'Save founder profile' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/check/i);
  expect(screen.getByLabelText('Team size')).toHaveValue('4');
});
test('reports stale-version conflict without overwriting newer state or losing edits', async () => {
  await open(); failSave = 409;
  await userEvent.type(screen.getByLabelText('Country of residence'), ' edited');
  await userEvent.click(screen.getByRole('button', { name: 'Save founder profile' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/newer version/i);
  expect(screen.getByLabelText('Country of residence')).toHaveValue('Spain edited');
  expect(screen.getByText('Version 3')).toBeVisible();
  expect(saved).toHaveLength(1);
});
test('a project save does not reset unsaved founder changes', async () => {
  await open();
  await userEvent.type(screen.getByLabelText('Country of residence'), ' edited');
  await userEvent.type(screen.getByLabelText('Project name'), ' updated');
  await userEvent.click(screen.getByRole('button', { name: 'Save project' }));
  await screen.findByText('Project saved.');
  expect(screen.getByLabelText('Country of residence')).toHaveValue('Spain edited');
});
test('read-only sessions expose facts without mutation controls', async () => {
  readOnly = true; await open();
  expect(screen.getByText(/read-only workspace/i)).toBeVisible();
  expect(screen.getByLabelText('Country of residence')).toHaveAttribute('readonly');
  expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add project' })).not.toBeInTheDocument();
});
test('creates an empty founder with expected version zero and preserves UNKNOWN', async () => {
  portfolio = { founder: null, projects: [] };
  render(<PortfolioView />);
  await screen.findByRole('button', { name: 'Save founder profile' });
  await userEvent.type(screen.getByLabelText('Country of residence'), 'Spain');
  await userEvent.click(screen.getByRole('button', { name: 'Save founder profile' }));
  await waitFor(() => expect(saved).toHaveLength(1));
  expect(saved[0]).toMatchObject({ body: { expected_version: 0, profile: { country_of_residence: { value: 'Spain', provenance: 'USER_ASSERTED' } } } });
  const profile = saved[0].body.profile as FounderProfile;
  expect(profile.legal_form?.value ?? null).toBeNull();
});

test('moves focus to the new project name when adding a project', async () => {
  await open();
  await userEvent.click(screen.getByRole('button', { name: 'Add project' }));
  const names = screen.getAllByLabelText('Project name');
  expect(names[1]).toHaveFocus();
});
test('explains invalid calendar dates while preserving the entered value', async () => {
  await open();
  await userEvent.type(screen.getByLabelText('Incorporation date'), '2026-99-12');
  await userEvent.click(screen.getByRole('button', { name: 'Save founder profile' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/incorporation date.*valid calendar date/i);
  expect(screen.getByLabelText('Incorporation date')).toHaveValue('2026-99-12');
  expect(saved).toHaveLength(0);
});

test('preserves documented cash after both cash inputs are restored while saving another field', async () => {
  portfolio.founder!.max_cash_commitment = { value: { amount: '100', currency: 'EUR' }, provenance: 'DOCUMENTED', evidence_refs: ['cash-proof'] };
  await open();
  const amount = screen.getByLabelText('Maximum cash commitment');
  const currency = screen.getByLabelText('Currency');
  await userEvent.clear(amount);
  await userEvent.type(amount, '101');
  await userEvent.clear(amount);
  await userEvent.type(amount, '100');
  await userEvent.clear(currency);
  await userEvent.type(currency, 'USD');
  await userEvent.clear(currency);
  await userEvent.type(currency, 'EUR');
  await userEvent.type(screen.getByLabelText('Country of residence'), ' edited');
  await userEvent.click(screen.getByRole('button', { name: 'Save founder profile' }));
  await screen.findByText('Founder profile saved.');
  expect(saved[0]).toMatchObject({ body: { expected_version: 3, profile: {
    country_of_residence: { value: 'Spain edited', provenance: 'USER_ASSERTED', evidence_refs: [] },
    max_cash_commitment: { value: { amount: '100', currency: 'EUR' }, provenance: 'DOCUMENTED', evidence_refs: ['cash-proof'] },
  } } });
});
test('marks changed cash as user asserted without retaining evidence for the prior amount', async () => {
  portfolio.founder!.max_cash_commitment = { value: { amount: '100', currency: 'EUR' }, provenance: 'DOCUMENTED', evidence_refs: ['cash-proof'] };
  await open();
  await userEvent.clear(screen.getByLabelText('Maximum cash commitment'));
  await userEvent.type(screen.getByLabelText('Maximum cash commitment'), '125.50');
  await userEvent.click(screen.getByRole('button', { name: 'Save founder profile' }));
  await screen.findByText('Founder profile saved.');
  expect(saved[0]).toMatchObject({ body: { profile: {
    max_cash_commitment: { value: { amount: '125.50', currency: 'EUR' }, provenance: 'USER_ASSERTED', evidence_refs: [] },
  } } });
});
