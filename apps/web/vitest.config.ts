import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
    // Browser acceptance is a separate gate driven by Playwright, never by the unit runner.
    exclude: ['node_modules/**', 'dist/**', 'e2e/**'],
  },
});
