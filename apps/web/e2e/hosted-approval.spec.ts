import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';

test('controlled hosted LIVE decision reaches one durable application pack', async ({ page }) => {
  const capturedHeaders: Record<string, string>[] = [];
  page.on('request', request => {
    if (request.url().includes('/api/v1/')) capturedHeaders.push(request.headers());
  });

  await page.goto('/inbox');
  await expect(page.getByText('HOSTED DEMO', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Research opportunity' }).click();
  await page.getByLabel('Official opportunity URL').fill('https://example.org/official-rules');
  await page.getByRole('button', { name: 'Start research' }).click();
  await expect(page).toHaveURL(/\/inbox\/opp_/);
  await expect(page.getByText('LIVE', { exact: true }).first()).toBeVisible();

  await page.getByRole('button', { name: /Approve application|Approve preparation/ }).click();
  const checkpoint = page.getByRole('region', { name: 'Human approval' });
  await expect(checkpoint).toContainText('PENDING_APPROVAL');
  await expect(checkpoint).toContainText('Nothing is submitted externally');
  const captures = process.env.QUALOR_TASK4_CAPTURE_DIR;
  if (!captures) throw new Error('QUALOR_TASK4_CAPTURE_DIR_REQUIRED');
  await page.screenshot({ path: resolve(captures, '01-live-approval-1440x900.png'), fullPage: false });

  await checkpoint.getByRole('button', { name: 'Confirm approval' }).click();
  await expect(checkpoint).toContainText('DRAFT_READY');
  await checkpoint.getByRole('link', { name: /Open draft pack/ }).click();
  const pack = page.getByRole('article', { name: 'Application pack' });
  await expect(pack).toBeVisible();
  await expect(pack.locator('.pack-section')).toHaveCount(7);
  await expect(pack.getByRole('heading', { name: '01 Submission summary' })).toBeVisible();
  await expect(pack).toContainText('No external submission has occurred');
  await page.screenshot({ path: resolve(captures, '02-live-pack-1440x900.png'), fullPage: false });

  const packUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(packUrl);
  await expect(page.getByRole('article', { name: 'Application pack' }).locator('.pack-section')).toHaveCount(7);
  await expect(page.getByText('LIVE research mode')).toBeVisible();

  expect(capturedHeaders.some(headers => headers['x-qualor-action-token'])).toBe(true);
  expect(capturedHeaders.every(headers => !headers['x-qualor-origin-auth'])).toBe(true);
  expect(await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } })))
    .toEqual({ local: {}, session: {} });
  await expect(page.getByText('FIXTURE', { exact: true })).toHaveCount(0);
  await expect(page.getByText('REPLAY', { exact: true })).toHaveCount(0);
});
