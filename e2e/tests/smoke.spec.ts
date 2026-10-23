import { expect, test, type Page } from "@playwright/test";

// Run a real user journey against a deployed instance. Every account it creates is
// deleted again at the end (and by `afterAll` if the journey fails half-way), so it is
// safe to point at production. Set E2E_EDGE=1 when the target sits behind the prod
// Caddy edge, to also check the security headers and caching rules it is responsible for.

const EDGE = process.env.E2E_EDGE === "1";
const stamp = Date.now().toString(36);
const EMAIL = `e2e-${stamp}@example.com`;
const PASSWORD = "Smoke-test-pw-1";
const NAME = "Smoke Tester";

// A `DOMAIN=localhost` deployment uses Caddy's private CA, which Chromium refuses to
// register the service worker over; a real certificate never produces this message.
const SELF_SIGNED_TARGET = new URL(process.env.E2E_BASE_URL ?? "http://localhost:5173").hostname === "localhost";
const IGNORED_CONSOLE_ERRORS = SELF_SIGNED_TARGET ? [/SSL certificate error/] : [];

/** Collects anything that would make a user's page broken: JS errors, CSP violations, 5xx. */
function watchForProblems(page: Page): string[] {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() !== "error" || IGNORED_CONSOLE_ERRORS.some((ignored) => ignored.test(message.text()))) return;
    problems.push(`console: ${message.text()}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 500) problems.push(`${response.status()} ${response.url()}`);
  });
  return problems;
}

test.describe("deployment", () => {
  test("health endpoint reports a working database", async ({ request }) => {
    const response = await request.get("/api/health");
    expect(response.status()).toBe(200);
    expect(response.headers()["x-request-id"] ?? "").not.toBe("");
  });

  test("unknown API routes are JSON 404s, not the SPA", async ({ request }) => {
    const response = await request.get("/api/does-not-exist");
    expect(response.status()).toBe(404);
    expect(response.headers()["content-type"]).toContain("application/json");
  });

  test("the edge sets security and caching headers", async ({ request, baseURL }) => {
    test.skip(!EDGE, "only the prod Caddy edge sets these (E2E_EDGE=1)");
    const index = await request.get("/");
    const headers = index.headers();
    expect(headers["content-security-policy"]).toContain("script-src 'self'");
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["cache-control"]).toContain("no-cache");
    if (baseURL?.startsWith("https://")) expect(headers["strict-transport-security"]).toBeTruthy();

    const manifest = await request.get("/manifest.webmanifest");
    expect(manifest.status()).toBe(200);
    const sw = await request.get("/sw.js");
    expect(sw.status()).toBe(200);
    expect(sw.headers()["cache-control"]).toContain("no-cache");

    // A missing hashed asset must be a real 404 that is not cached for a year.
    const missing = await request.get("/assets/nope-00000000.js");
    expect(missing.status()).toBe(404);
    expect(missing.headers()["cache-control"] ?? "").not.toContain("immutable");
  });
});

test.describe("user journey", () => {
  test.describe.configure({ mode: "serial" });

  let page: Page;
  let problems: string[];
  let created = false;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    problems = watchForProblems(page);
  });

  test.afterAll(async ({ request }) => {
    // Best effort: remove the account when a failed run left it behind.
    if (created) {
      const login = await request.post("/api/auth/login", { data: { email: EMAIL, password: PASSWORD } });
      if (login.ok()) await request.post("/api/auth/delete-account", { data: { password: PASSWORD } });
    }
    await page?.close();
  });

  test("signed-out visitors are sent to the login page", async () => {
    await page.goto("/records");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
  });

  test("a wrong password is rejected with a message", async () => {
    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Password").fill("Not-the-password-1");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("alert")).toHaveText("Wrong email or password.");
    // The browser logs the 401 itself; it is the expected outcome here.
    problems.length = 0;
  });

  test("sign up lands on the dashboard", async () => {
    await page.goto("/signup");
    await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
    await page.getByLabel("Display name").fill(NAME);
    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Confirm password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign up" }).click();
    created = true;
    await expect(page).toHaveURL(/\/$/);
    // A new account has no data, so Home shows the first-run checklist (the "Welcome" empty
    // state only appears once that checklist is hidden or complete).
    await expect(page.getByRole("heading", { name: "Set up ApexCycling" })).toBeVisible();
  });

  test("the main pages render", async () => {
    for (const [name, path] of [
      ["Log", "/log"],
      ["Records", "/records"],
      ["Progress", "/progress"],
    ] as const) {
      await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name }).first().click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(page.locator("#main-content")).not.toBeEmpty();
    }
  });

  test("the session survives a reload", async () => {
    await page.getByRole("link", { name: "Settings" }).first().click();
    await expect(page).toHaveURL(/\/settings\/profile$/);
    await page.reload();
    await expect(page).toHaveURL(/\/settings\/profile$/);
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  });

  test("log out and log back in", async () => {
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/);

    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  });

  test("delete the account", async () => {
    await page.goto("/settings/account");
    await page.getByRole("button", { name: "Delete my account…" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Password").fill(PASSWORD);
    await dialog.getByRole("button", { name: "Delete forever" }).click();
    await expect(page).toHaveURL(/\/login$/);
    created = false;

    // The credentials no longer work.
    const login = await page.request.post("/api/auth/login", { data: { email: EMAIL, password: PASSWORD } });
    expect(login.status()).toBe(401);
  });

  test("nothing broke along the way", () => {
    expect(problems).toEqual([]);
  });
});
