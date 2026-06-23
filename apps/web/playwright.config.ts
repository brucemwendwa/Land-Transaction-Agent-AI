import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  expect: {
    timeout: 10_000
  },
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:3002",
    navigationTimeout: 60_000,
    trace: "on-first-retry"
  },
  webServer: {
    command: "corepack pnpm exec next dev --webpack --hostname 127.0.0.1 --port 3002",
    env: {
      NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000",
      NEXT_PUBLIC_REPORT_UNLOCK_AMOUNT: "100"
    },
    url: "http://127.0.0.1:3002",
    reuseExistingServer: true,
    timeout: 180_000
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chrome" } },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "chrome" } }
  ]
});
