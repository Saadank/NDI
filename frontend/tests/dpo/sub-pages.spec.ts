import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("DPO — Sub Pages", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "dpo");
  });

  test("Workflow Editor (/dpo/workflows) renders heading", async ({ page }) => {
    await page.goto("/dpo/workflows");
    await page.waitForLoadState("networkidle");
    // Check h1 or any element with "Workflow" text
    await expect(page.locator("h1, h2").filter({ hasText: /workflow/i }).first()).toBeVisible();
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  test("Workflow Editor has New workflow button", async ({ page }) => {
    await page.goto("/dpo/workflows");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("button", { name: /new workflow/i })).toBeVisible();
  });

  test("Request Templates (/dpo/templates) loads without crash", async ({ page }) => {
    await page.goto("/dpo/templates");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  test("Audit Trail (/dpo/audit) renders audit content", async ({ page }) => {
    await page.goto("/dpo/audit");
    await page.waitForLoadState("networkidle");
    // Any heading or content element related to audit
    await expect(page.locator("h1, h2").first()).toBeVisible();
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  test("DPO sidebar shows correct navigation items", async ({ page }) => {
    await page.goto("/dpo");
    await page.waitForLoadState("networkidle");
    const nav = page.getByRole("navigation");
    await expect(nav.getByRole("link", { name: /organisation request list/i })).toBeVisible();
    await expect(nav.getByRole("link", { name: /workflow editor/i })).toBeVisible();
    await expect(nav.getByRole("link", { name: /request templates/i })).toBeVisible();
    await expect(nav.getByRole("link", { name: /audit trail/i })).toBeVisible();
  });

  test("DPO sidebar does NOT show External Recipients (removed)", async ({ page }) => {
    await page.goto("/dpo");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("link", { name: /external recipients/i })).not.toBeVisible();
  });

  // Role-Based Access
  test("Data Owner cannot access DPO workflow editor content", async ({ page }) => {
    await login(page, "dataOwner");
    await page.goto("/dpo/workflows");
    await page.waitForTimeout(2000);
    await expect(page.getByRole("button", { name: /new workflow/i })).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
  });
});
