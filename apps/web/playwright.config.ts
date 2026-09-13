import { execFileSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

/**
 * Browser acceptance against the real stack: the loopback QUALOR API over a temporary
 * SQLite database, the real Vite frontend, and one owned FIXTURE seeded through the same
 * production workspace services the product writes with. Nothing here mocks the API, and
 * no AWS or network provider is reachable from the flow.
 */
// The package is an ES module, so the config resolves its own directory explicitly.
const here = dirname(fileURLToPath(import.meta.url));
const repository = resolve(here, '../..');
const fixture = join(repository, 'tests/fixtures/workspace/W01_DECISION_TO_DRAFT_PACK.json');
const databasePath = join(mkdtempSync(join(tmpdir(), 'qualor-e2e-')), 'workspace.db');

// Seed before either server starts, so the browser only ever sees persisted state.
execFileSync('uv', ['run', 'qualor', 'seed-workspace-fixture', fixture], {
  cwd: repository,
  env: { ...process.env, DATABASE_PATH: databasePath, QUALOR_ENV: 'development' },
  stdio: 'inherit',
});

export default defineConfig({
  testDir: './e2e',
  testIgnore: ['live-research.spec.ts', 'hosted-approval.spec.ts'],
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [['list'], ['github']] : [['list']],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    // The judge flow is a desktop composition; the wide viewport is part of the contract.
    viewport: { width: 1440, height: 900 },
    ...devices['Desktop Chrome'],
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'uv run qualor serve --port 8000',
      cwd: repository,
      url: 'http://127.0.0.1:8000/api/v1/inbox',
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      env: { DATABASE_PATH: databasePath, QUALOR_ENV: 'development' },
    },
    {
      command: 'npm run dev',
      cwd: here,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
