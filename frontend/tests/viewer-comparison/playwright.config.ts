import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: '.',
  testMatch: 'comparison.spec.ts',
  timeout: 120000,
  workers: 1,
  outputDir: '../../test-results/viewer-comparison',
  use: { baseURL: 'http://127.0.0.1:4175', trace: 'retain-on-failure' },
  webServer: {
    command: 'npm run viewer:preview',
    url: 'http://127.0.0.1:4175/workspace/tests/viewer-comparison/harness.html',
    reuseExistingServer: !process.env.CI,
  },
});
