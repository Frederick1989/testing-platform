// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60_000,
  fullyParallel: true,
  reporter: [
    ['json', { outputFile: process.env.JSON_REPORT || 'reports/last/results.json' }],
    ['html', { outputFolder: process.env.HTML_REPORT_DIR || 'reports/last/html' }],
  ],
  outputDir: process.env.PW_OUTPUT || 'test-results',
  use: {
    baseURL: process.env.WEBAPP_URL || 'http://localhost:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
