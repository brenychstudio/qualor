import { randomBytes } from 'node:crypto';
import { mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const here = dirname(fileURLToPath(import.meta.url));
const repository = resolve(here, '../..');
const runtime = mkdtempSync(join(tmpdir(), 'qualor-live-task4-'));
const captures = resolve(repository, '.qualor/local/live-task4');
const originAuth = randomBytes(32).toString('hex');
mkdirSync(captures, { recursive: true });
process.env.QUALOR_TASK4_CAPTURE_DIR = captures;

export default defineConfig({
  testDir: './e2e',
  testMatch: 'hosted-approval.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: [['list']],
  outputDir: join(captures, 'playwright-output'),
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'chromium' }],
  webServer: [
    {
      command: 'uv run uvicorn --app-dir tests task4_controlled_server:app --host 127.0.0.1 --port 8000 --no-access-log --log-level error',
      cwd: repository,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        ...process.env,
        QUALOR_TASK4_E2E_DIR: runtime,
        QUALOR_TASK4_E2E_ORIGIN_AUTH: originAuth,
        QUALOR_TASK4_E2E_PHASE_SECONDS: '.2',
      },
    },
    {
      command: 'npm run dev',
      cwd: here,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      timeout: 120_000,
      env: { ...process.env, QUALOR_DEV_ORIGIN_AUTH: originAuth },
    },
  ],
});
