import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { DesignPreview } from './DecisionPreview';
import data from './decision-scenarios.json';

test('integrates the populated desktop disclosure into the header and restores the existing disclosure below desktop', () => {
  vi.stubGlobal('innerWidth', 1440);
  vi.stubGlobal('innerHeight', 810);
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  const header = screen.getByRole('banner');
  expect(within(header).getByText('DESIGN PREVIEW · SYNTHETIC · READ ONLY')).toBeVisible();
  expect(screen.queryByText('DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY')).not.toBeInTheDocument();
  expect(within(screen.getByRole('group', { name: 'Source attribution' })).getByText('Document')).toBeVisible();
  act(() => { vi.stubGlobal('innerWidth', 1279); window.dispatchEvent(new Event('resize')); });
  expect(within(header).queryByText('DESIGN PREVIEW · SYNTHETIC · READ ONLY')).not.toBeInTheDocument();
  expect(screen.getByText('DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY').closest('header')).toBeNull();
  expect(within(screen.getByRole('group', { name: 'Source attribution' })).getByText('Source')).toBeVisible();
});

test.each(['portfolio', 'activity'])('keeps the existing disclosure outside the header on the desktop %s preview', view => {
  vi.stubGlobal('innerWidth', 1440);
  vi.stubGlobal('innerHeight', 810);
  window.history.replaceState({}, '', `/?view=${view}`);
  try {
    render(<MemoryRouter><DesignPreview /></MemoryRouter>);
    expect(screen.getByText('DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY').closest('header')).toBeNull();
    expect(screen.queryByText('DESIGN PREVIEW · SYNTHETIC · READ ONLY')).not.toBeInTheDocument();
  } finally { window.history.replaceState({}, '', '/'); }
});

test('keeps the complete synthetic source available in expanded proof when the desktop peek is condensed', async () => {
  vi.stubGlobal('innerWidth', 1440);
  vi.stubGlobal('innerHeight', 810);
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  const source = screen.getByRole('group', { name: 'Source attribution' });
  expect(within(source).queryByText('https://synthetic.example/rules')).not.toBeInTheDocument();
  expect(within(source).getByText('synthetic.example')).toBeVisible();
  expect(within(source).getByText('No official verification')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: /why this decision/i }));
  expect(within(screen.getByRole('region', { name: 'Decision proof' })).getByText('https://synthetic.example/rules')).toBeVisible();
});

test('limits the optical calibration to the selected D02 frame and restores the existing presentation on height resize', async () => {
  vi.stubGlobal('innerWidth', 1440);
  vi.stubGlobal('innerHeight', 810);
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  await userEvent.click(screen.getByRole('button', { name: /D01.*APPLY/i }));
  expect(screen.getByText('DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY').closest('header')).toBeNull();
  expect(screen.queryByText('DESIGN PREVIEW · SYNTHETIC · READ ONLY')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /D02.*PREPARE/i }));
  expect(within(screen.getByRole('banner')).getByText('DESIGN PREVIEW · SYNTHETIC · READ ONLY')).toBeVisible();
  act(() => { vi.stubGlobal('innerHeight', 900); window.dispatchEvent(new Event('resize')); });
  expect(screen.getByText('DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY').closest('header')).toBeNull();
  expect(within(screen.getByRole('group', { name: 'Source attribution' })).getByText('Source')).toBeVisible();
});

test('preserves the existing populated presentation at other desktop widths', () => {
  vi.stubGlobal('innerWidth', 1280);
  vi.stubGlobal('innerHeight', 810);
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  expect(screen.getByText('DESIGN PREVIEW · SYNTHETIC FIXTURE · READ ONLY').closest('header')).toBeNull();
  expect(screen.queryByText('DESIGN PREVIEW · SYNTHETIC · READ ONLY')).not.toBeInTheDocument();
});

test('keeps missing readiness distinct from a known empty gap list', () => {
  const result = data.scenarios[0].result as { readiness: unknown };
  const original = result.readiness;
  try {
    result.readiness = null;
    render(<MemoryRouter><DesignPreview /></MemoryRouter>);
    const readiness = screen.getByRole('group', { name: 'Readiness assessment' });
    expect(within(readiness).getByText('Readiness unavailable')).toBeVisible();
    expect(within(readiness).getByText('UNKNOWN')).toBeVisible();
    expect(within(readiness).queryByText('No recorded gaps')).not.toBeInTheDocument();
  } finally { result.readiness = original; }
});

test('shows insufficient strategy evidence without a denominator or percentage bar', () => {
  const result = data.scenarios[0].result as { strategy: unknown };
  const original = result.strategy;
  try {
    result.strategy = null;
    render(<MemoryRouter><DesignPreview /></MemoryRouter>);
    const recommendation = screen.getByRole('region', { name: 'Recommendation' });
    expect(within(recommendation).getByText('Not enough evidence')).toBeVisible();
    expect(within(recommendation).queryByText('/ 100')).not.toBeInTheDocument();
    expect(within(recommendation).queryByText('71')).not.toBeInTheDocument();
  } finally { result.strategy = original; }
});

test('presents four decision signals using their recorded units rather than invented percentage scores', () => {
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  const signals = screen.getByRole('group', { name: 'Decision signals' });
  expect(within(signals).getAllByRole('term').map(item => item.textContent)).toEqual(['Fit', 'Eligibility', 'Feasibility', 'Readiness']);
  expect(within(signals).getByText('3 / 4')).toBeVisible();
  expect(within(signals).getByText('PASS')).toBeVisible();
  expect(within(signals).getByText('8–14 h')).toBeVisible();
  expect(within(signals).getByText('1 gap')).toBeVisible();
  expect(within(signals).queryByText(/\/ 100/)).not.toBeInTheDocument();
  const recommendation = screen.getByRole('region', { name: 'Recommendation' });
  expect(within(recommendation).getByRole('heading', { name: 'PREPARE' })).toBeVisible();
  expect(within(recommendation).getByText('71')).toBeVisible();
});

test('connects eligibility to its synthetic rule while keeping source and profile context distinct', async () => {
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  await userEvent.click(screen.getByRole('button', { name: 'Show eligibility proof' }));
  const rule = screen.getByRole('group', { name: 'Eligibility rule' });
  expect(rule).toHaveFocus();
  expect(within(rule).getByText('Synthetic teams must have at least one member.')).toBeVisible();
  expect(within(rule).getByText('Synthetic fixture · one eligibility claim')).toBeVisible();
  const source = screen.getByRole('group', { name: 'Source attribution' });
  expect(within(source).getByText('synthetic.example')).toBeVisible();
  expect(within(source).getByText('No official verification')).toBeVisible();
  const context = screen.getByRole('group', { name: 'Profile context' });
  expect(within(context).getByText('Team size · 2')).toBeVisible();
  expect(within(context).getByText('Profile context · no evidence references')).toBeVisible();
});

test('offers three read-only review actions and focuses the recorded readiness gap', async () => {
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  const actions = screen.getByRole('navigation', { name: 'Next actions' });
  expect(within(actions).getAllByRole('button')).toHaveLength(2);
  expect(within(actions).getByRole('link', { name: /review project/i })).toHaveAttribute('href', '/design-preview.html?view=portfolio');
  await userEvent.click(within(actions).getByRole('button', { name: /review readiness gap/i }));
  const readiness = screen.getByRole('group', { name: 'Readiness assessment' });
  expect(readiness).toHaveFocus();
  expect(within(readiness).getByText('repository')).toBeVisible();
  await userEvent.click(within(actions).getByRole('button', { name: /review eligibility proof/i }));
  expect(screen.getByRole('group', { name: 'Eligibility rule' })).toHaveFocus();
  expect(screen.getByRole('textbox', { name: 'Search unavailable' })).toBeDisabled();
});

test('keeps the selected mobile scenario focused and the queue scrolled while updating the decision', async () => {
  vi.stubGlobal('innerWidth', 390);
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  const row = screen.getByRole('button', { name: /D04.*WATCH/i });
  const queue = row.parentElement!;
  queue.scrollLeft = 394;
  row.focus();
  await userEvent.keyboard('{Enter}');
  expect(screen.getByRole('heading', { name: 'WATCH' })).toBeVisible();
  expect(screen.getByRole('button', { name: /D04.*WATCH/i })).toHaveFocus();
  expect(screen.getByRole('button', { name: /D04.*WATCH/i }).parentElement?.scrollLeft).toBe(394);
});

test('presents long eligibility states as readable words at the minimum mobile width', async () => {
  vi.stubGlobal('innerWidth', 320);
  render(<MemoryRouter><DesignPreview /></MemoryRouter>);
  await userEvent.click(screen.getByRole('button', { name: /D04.*WATCH/i }));
  expect(screen.getByText('REVIEW REQUIRED')).toBeVisible();
});
