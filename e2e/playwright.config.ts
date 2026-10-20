import { defineConfig, devices } from "@playwright/test";

// The target is whatever E2E_BASE_URL points at: the dev stack (default), the local
// prod stack (https://localhost:8443) or production (https://apex-cycling.net).
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173";

export default defineConfig({
  testDir: "./tests",
  // Signup/login/delete-account are rate limited per IP (5-10/min), so one file at a time.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL,
    locale: "en-US",
    // `DOMAIN=localhost` deployments use Caddy's private CA.
    ignoreHTTPSErrors: new URL(baseURL).hostname === "localhost",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
