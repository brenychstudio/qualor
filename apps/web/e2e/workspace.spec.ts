import { expect, test } from '@playwright/test';

/**
 * The approved judge flow, driven through the real API in a real browser.
 *
 * Everything asserted here was produced by the server from one owned FIXTURE file:
 * the recommendation, the evidence, the approval and the pack are all read back over
 * HTTP. The test never stubs a response and never asserts a value it supplied itself.
 */

const SUBMISSION_WORDS = /\bsubmit|\bsend\b|apply now|\bpublish|dispatch|\bemail\b|devpost|autofill/i;

test.beforeEach(async ({ page }) => {
  await page.goto('/inbox');
});

test('the first screen shows the decision hierarchy before any detail is opened', async ({ page }) => {
  const row = page.getByRole('link', { name: /AWS Agents for Humans/ });
  await expect(row).toBeVisible();

  await row.click();
  await expect(page).toHaveURL(/\/inbox\/opp_/);

  // First-five-seconds hierarchy: recommendation, project, effort and deadline are all
  // legible without opening the proof layer.
  await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
  await expect(page.getByText('Recommendation: APPLY')).toBeVisible();
  const facts = page.getByRole('group', { name: 'Decision signals' });
  await expect(facts).toBeVisible();
  await expect(page.getByRole('group', { name: 'Deadline' })).toBeVisible();

  // Strategy is prioritisation, never a probability of winning.
  const strategy = page.getByRole('group', { name: 'Strategy priority' });
  await expect(strategy).toContainText(/prioritization/i);
  await expect(strategy).not.toContainText(/win probability|chance/i);

  // The proof layer is still closed at this point.
  await expect(page.getByRole('region', { name: 'Decision proof' })).toHaveCount(0);
});

test('fixture work is labelled FIXTURE and never presented as live research', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  const operational = page.getByLabel('Current decision state');
  await expect(operational).toContainText('FIXTURE');
  await expect(operational).not.toContainText('LIVE');
  await expect(page.locator('body')).not.toContainText(/Bedrock|AgentCore/i);
});

test('Why this decision opens source-grounded proof and returns to the dark workspace', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();

  const trigger = page.getByRole('button', { name: /why this decision/i });
  await trigger.click();

  const plane = page.getByRole('region', { name: 'Decision proof' });
  await expect(plane).toBeVisible();
  await expect(plane.getByRole('region', { name: 'Eligibility' })).toBeVisible();

  // The exact official citation the Evidence Sheet contract preserves.
  const citation = plane.getByRole('link', { name: /view original/i }).first();
  await expect(citation).toBeVisible();
  await expect(citation).toHaveAttribute('href', /^https:\/\/rules\.aws-agents-for-humans\.example\//);
  await expect(citation).toHaveAttribute('target', '_blank');
  await expect(citation).toHaveAttribute('rel', /noopener/);

  // An exact excerpt is quoted rather than paraphrased.
  await expect(plane.locator('blockquote').first()).not.toBeEmpty();

  await page.keyboard.press('Escape');
  await expect(plane).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
});

test('recorded activity is visible and claims no progress it did not make', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  const rail = page.getByRole('region', { name: 'Intelligence' });
  await expect(rail).toBeVisible();
  await expect(rail).toContainText('FIXTURE');
  await expect(rail.getByRole('list', { name: /recorded activity/i })).toBeVisible();
  await expect(rail).not.toContainText(/searching now|in progress/i);
});

test('the whole approved story ends at a prepared pack, never at a submission', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();

  // The approval entry point offered by the deterministic result.
  const action = page.getByRole('button', { name: 'Approve application' });
  await expect(action).toBeEnabled();
  await action.click();

  const checkpoint = page.getByRole('region', { name: 'Human approval' });
  await expect(checkpoint).toBeVisible();
  await expect(checkpoint).toContainText('PENDING_APPROVAL');
  await expect(checkpoint).toContainText('GENERATE_DRAFT_PACK');
  await expect(checkpoint).toContainText(/nothing is submitted externally/i);
  await expect(checkpoint).toContainText(/opportunity version/i);

  // No control anywhere in the checkpoint implies sending anything outward.
  for (const control of await checkpoint.getByRole('button').all()) {
    expect(await control.textContent() ?? '').not.toMatch(SUBMISSION_WORDS);
  }

  await checkpoint.getByRole('button', { name: /confirm approval/i }).click();
  await expect(checkpoint).toContainText('DRAFT_READY');

  const openPack = checkpoint.getByRole('link', { name: /open draft pack/i });
  await expect(openPack).toBeVisible();
  await openPack.click();

  const pack = page.getByRole('article', { name: 'Application pack' });
  await expect(pack).toBeVisible();
  await expect(page).toHaveURL(/\/draft-packs\/.+/);

  const packUrl = page.url();
  const sections = pack.getByRole('region');
  await expect(sections).toHaveCount(7);
  await expect(sections.nth(0)).toHaveAttribute('data-section-key', 'SUBMISSION_SUMMARY');
  await expect(sections.nth(6)).toHaveAttribute('data-section-key', 'SUGGESTED_APPLICATION_ANSWERS');

  await expect(pack.getByRole('group', { name: /bound versions/i })).toBeVisible();
  await expect(pack.getByRole('group', { name: /missing information/i })).toBeVisible();
  await expect(pack.getByRole('group', { name: /source and evidence references/i })).toBeVisible();
  await expect(pack).toContainText('DRAFT_FOR_HUMAN_REVIEW');
  await expect(pack).toContainText('FIXTURE');

  // Nothing in the finished document offers an external action.
  for (const control of await pack.getByRole('link').all()) {
    expect(await control.textContent() ?? '').not.toMatch(SUBMISSION_WORDS);
  }
  await expect(pack.getByRole('button')).toHaveCount(0);

  // A direct reload rebuilds the same persisted pack with no prior app state.
  await page.goto(packUrl);
  const reloaded = page.getByRole('article', { name: 'Application pack' });
  await expect(reloaded).toBeVisible();
  await expect(reloaded.getByRole('region')).toHaveCount(7);
  await expect(reloaded).toContainText('DRAFT_FOR_HUMAN_REVIEW');
});

test('the wide workspace body keeps its canonical four zones', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();

  // ADR 0004: at 1280px and above the body is inbox, canvas, proof and rail. Proof and
  // telemetry are separate authorities, so the Evidence Plane holds its own zone and is
  // never folded back into the Intelligence Rail.
  await expect(page.getByRole('complementary', { name: 'Opportunity inbox' })).toBeVisible();
  await expect(page.getByRole('main')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Why & proof' })).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Workspace context' })).toBeVisible();

  // The workspace body is the grid; the header is navigation, not a zone. Asserting the
  // computed area projection rather than a child count means a regression to
  // `queue canvas rail` fails here instead of passing quietly.
  const areas = await page
    .locator('.workspace-grid')
    .evaluate(element => getComputedStyle(element).gridTemplateAreas);
  expect(areas.replace(/"/g, ' ').replace(/\s+/g, ' ').trim()).toBe('queue canvas proof rail');

  // Each zone is a direct child of the body grid, so proof sits beside the rail, not inside it.
  for (const zone of ['Opportunity inbox', 'Why & proof', 'Workspace context']) {
    await expect(page.locator(`.workspace-grid > [aria-label="${zone}"]`)).toBeVisible();
  }
});

test('the browser never receives an action token it could leak', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  await page.getByRole('button', { name: 'Approve application' }).click();
  await expect(page.getByRole('region', { name: 'Human approval' })).toContainText('PENDING_APPROVAL');

  // The token travels in a request header only: never a URL, never browser storage.
  expect(page.url()).not.toMatch(/token/i);
  const stored = await page.evaluate(() => ({
    local: JSON.stringify(window.localStorage),
    session: JSON.stringify(window.sessionStorage),
  }));
  expect(stored.local).not.toMatch(/token/i);
  expect(stored.session).not.toMatch(/token/i);
});
