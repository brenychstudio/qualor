import { expect, test } from '@playwright/test';

test('a controlled LIVE run moves from Inbox acquisition to persisted decision authority', async ({ page }, testInfo) => {
  expect(page.viewportSize()).toEqual({ width: 1440, height: 900 });
  const leakedOriginAuth: string[] = [];
  page.on('request', request => {
    if (request.url().includes('/api/v1/') && request.headers()['x-qualor-origin-auth']) {
      leakedOriginAuth.push(request.headers()['x-qualor-origin-auth']);
    }
  });

  await page.goto('/inbox');
  await expect(page.getByRole('button', { name: 'Research opportunity' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No active decision' })).toBeVisible();
  await expect(page.getByText('Profile required')).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Complete profile/i })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('01-inbox-research-control-1440x900.png') });

  await page.getByRole('button', { name: 'Research opportunity' }).click();
  await expect(page.getByRole('textbox', { name: 'Official opportunity URL' })).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath('02-research-input-1440x900.png') });

  await page.getByRole('textbox', { name: 'Official opportunity URL' }).fill('https://example.org/rules');
  await page.getByRole('button', { name: 'Start research' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Starting research' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Researching official sources' })).toBeVisible();
  await expect(page.getByText('Profile required')).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Complete profile/i })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('03-live-researching-1440x900.png') });
  await expect(page.getByRole('status').filter({ hasText: 'Evaluating evidence' })).toBeVisible();

  await expect(page).toHaveURL(/\/inbox\/opp_[a-f0-9]+$/);
  await expect(page.getByRole('heading', { name: 'SKIP', level: 1 })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Research complete' })).toBeVisible();
  await expect(page.locator('.research-activity')).toHaveCount(0);
  await expect(page.getByText('Open Builders Challenge').first()).toBeVisible();
  await expect(page.locator('.queue-item-index', { hasText: 'LIVE' })).toBeVisible();
  await expect(page.locator('.context-facts').filter({ hasText: 'Research mode' })).toContainText('LIVE');
  await expect(page.getByRole('complementary', { name: 'Workspace context' }).getByRole('list', { name: 'Recorded activity' })).toBeVisible();
  await expect(page.getByText('Missing information: 49 unresolved fields')).toBeVisible();
  await expect(page.getByText(/opportunity\.matching/)).toHaveCount(0);
  await page.waitForTimeout(600);
  await page.screenshot({ path: testInfo.outputPath('04-live-completed-decision-1440x900.png') });

  await page.getByRole('button', { name: /Why this decision/ }).click();
  await expect(page.getByText('Projects must use Widget SDK.', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: /View original/ }).first()).toHaveAttribute('href', 'https://example.org/rules');
  await page.getByRole('button', { name: /Close proof/ }).click();
  await page.getByRole('link', { name: 'Activity', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Recorded activity', level: 1 })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Recorded runs' })).toContainText('LIVE');

  expect(leakedOriginAuth).toEqual([]);
  expect(await page.evaluate(() => Object.keys(sessionStorage))).toEqual([]);
  await expect(page.getByText(/FIXTURE|REPLAY/)).toHaveCount(0);
});
