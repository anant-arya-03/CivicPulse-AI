import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// path.join gives backslashes on Windows, which cmd.exe needs to run the program.
const venvPython =
  process.platform === "win32"
    ? path.join(".venv", "Scripts", "python.exe")
    : path.join(".venv", "bin", "python");

/**
 * End-to-end tests run against the real stack: Next.js -> FastAPI -> PostgreSQL.
 * Playwright starts both servers automatically (or reuses ones you already have running).
 * Note: these tests create users in your development database (unique e2e-* emails).
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts", // compiles each page once before the tests start
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  // The tests run in parallel against one `next dev` server and one backend process (which
  // hashes every new password with Argon2 on purpose). Under that load 5 s is sometimes too
  // short for a page change, so assertions may wait up to 10 s, and a whole journey 60 s.
  expect: { timeout: 10_000 },
  timeout: 60_000,
  // Two browsers at a time: with more, `next dev` (unminified, compiled on demand) becomes so
  // slow on an ordinary laptop that long journeys time out. Slower overall, but reliable.
  workers: 2,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `${venvPython} -m uvicorn app.main:app --port 8000`,
      cwd: "../backend",
      // Only applies when Playwright starts the backend itself. A dev server you already
      // have running keeps its rate limits, so very quick re-runs can hit "Too many attempts".
      env: {
        RATE_LIMIT_ENABLED: "false",
        GEOCODER: "mock",
        AI_PROVIDER: "mock",
        MOCK_AI_SCENARIO: "pothole",
        EMAIL_PROVIDER: "mock",
        MOCK_EMAIL_SCENARIO: "success",
        ENABLE_SIMULATION: "true", // demo tools: simulated replies, "skip ahead" in time
      },
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
