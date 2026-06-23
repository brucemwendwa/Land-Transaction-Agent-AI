import { defineConfig, devices } from "@playwright/test";

const appBaseURL = "http://127.0.0.1:3002";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  expect: {
    timeout: 10_000
  },
  workers: 1,
  use: {
    baseURL: appBaseURL,
    navigationTimeout: 60_000,
    trace: "on-first-retry"
  },
  webServer: {
    command: "corepack pnpm exec next dev --webpack --hostname 127.0.0.1 --port 3002",
    env: {
      E2E_SIGNED_OUT_GUARD: "true",
      NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000",
      NEXT_PUBLIC_REPORT_UNLOCK_AMOUNT: "100"
    },
    url: appBaseURL,
    reuseExistingServer: true,
    timeout: 180_000
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chrome" } },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "chrome" } }
  ]
});
