/**
 * Phase 1 exploratory spec — runs once to discover bugs.
 * Visits every route for every role, takes screenshots, logs console errors.
 */
import { test, expect } from "@playwright/test";

const USERS = {
  dataSteward: { email: "sara.fin@acme.local", password: "Test123!", routes: ["/data-sharing", "/data-sharing/new", "/prepare"] },
  dataOwner: { email: "ahmed.do@acme.local", password: "Test123!", routes: ["/approvals", "/my-department"] },
  dpo: { email: "nora.dpo@acme.local", password: "Test123!", routes: ["/dpo", "/dpo/workflows", "/dpo/templates", "/dpo/audit"] },
  orgAdmin: { email: "superadmin@datasharing.local", password: "SuperAdmin123!", routes: ["/admin/departments", "/admin/users", "/admin/holidays", "/admin/retention", "/admin/connections"] },
} as const;

async function loginAs(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: /sign in|log in|continue/i }).first().click();
  await page.waitForTimeout(2000);
}

for (const [role, cfg] of Object.entries(USERS)) {
  test.describe(`Explore — ${role}`, () => {
    test.beforeEach(async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      await loginAs(page, cfg.email, cfg.password);
    });

    for (const route of cfg.routes) {
      test(`${route} — loads without crash`, async ({ page }) => {
        const consoleErrors: string[] = [];
        page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });

        await page.goto(route);
        await page.waitForLoadState("networkidle");
        await page.waitForTimeout(1000);

        // Must not redirect to login
        expect(page.url()).not.toMatch(/\/login/);
        // Must not show unhandled crash
        await expect(page.getByText(/application error|something went wrong|unexpected error/i)).not.toBeVisible();

        // Screenshot for visual review
        await page.screenshot({ path: `playwright-report/screenshots/${role}-${route.replace(/\//g, "-")}.png`, fullPage: true });

        // Log errors (non-fatal — they're captured in report)
        if (consoleErrors.length > 0) {
          console.warn(`[${role}] ${route} console errors:`, consoleErrors.join(" | "));
        }
      });
    }
  });
}

test.describe("Explore — auth flows", () => {
  test("login page renders all fields", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in|log in/i })).toBeVisible();
  });

  test("unauthenticated /approvals redirects to login", async ({ page }) => {
    await page.goto("/approvals");
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });

  test("unauthenticated /dpo redirects to login", async ({ page }) => {
    await page.goto("/dpo");
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });

  test("unauthenticated /admin redirects to login", async ({ page }) => {
    await page.goto("/admin/departments");
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });
});
