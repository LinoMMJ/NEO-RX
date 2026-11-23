import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const baseURL = process.env.NEORX_BASE_URL || 'http://localhost:8080'

export default defineConfig({
  testDir: './e2e',
  outputDir: path.join(here, '../qa/playwright-artifacts'),
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  forbidOnly: true,
  retries: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(here, '../qa/playwright-report'), open: 'never' }],
    ['json', { outputFile: path.join(here, '../qa/playwright-results.json') }],
  ],
  use: {
    baseURL,
    channel: 'chrome',
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'es-BO',
    timezoneId: 'America/La_Paz',
  },
  projects: [
    { name: 'chromium-escritorio', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
  ],
})
