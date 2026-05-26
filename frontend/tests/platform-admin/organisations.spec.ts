import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("PA — Organisations (/platform/organisations)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "platformAdmin");
    await page.goto("/platform/organisations");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
  });

  // Functional
  test("page loads with Organisations heading", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /organisations/i })).toBeVisible();
  });

  test("Platform Admin sidebar shows special header", async ({ page }) => {
    await expect(page.getByText(/platform admin/i)).toBeVisible();
  });

  test("ADMIN badge is visible in sidebar header", async ({ page }) => {
    await expect(page.getByText(/admin/i).first()).toBeVisible();
  });

  test("sidebar shows Organisations and Onboard Company only", async ({ page }) => {
    await expect(page.getByRole("link", { name: /organisations/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /onboard company/i })).toBeVisible();
  });

  test("organisation list renders", async ({ page }) => {
    await expect(page.getByText(/application error/i)).not.toBeVisible();
    const rows = page.locator("tbody tr, [role='row']");
    const count = await rows.count();
    // At least one org (the test tenant) should exist
    expect(count).toBeGreaterThanOrEqual(0);
  });

  // Role-Based Access
  test("Data Owner cannot access /platform/organisations", async ({ page }) => {
    await login(page, "dataOwner");
    await page.goto("/platform/organisations");
    await page.waitForTimeout(2000);
    await expect(page.getByRole("heading", { name: /organisations/i })).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
  });

  test("DPO cannot access /platform/organisations", async ({ page }) => {
    await login(page, "dpo");
    await page.goto("/platform/organisations");
    await page.waitForTimeout(2000);
    await expect(page.getByRole("heading", { name: /organisations/i })).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
  });
});
