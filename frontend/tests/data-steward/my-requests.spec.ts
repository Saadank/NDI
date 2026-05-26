import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("DS — My Requests list (/data-sharing)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "dataSteward");
    await page.goto("/data-sharing");
    await page.waitForLoadState("networkidle");
  });

  test("page loads without error", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /my requests/i })).toBeVisible();
    await expect(page.getByText(/failed to load/i)).not.toBeVisible();
  });

  test("sidebar shows Data Steward nav items", async ({ page }) => {
    // Scope to the nav element to avoid matching the main page button
    const nav = page.getByRole("navigation");
    await expect(nav.getByRole("link", { name: /my requests/i })).toBeVisible();
    await expect(nav.getByRole("link", { name: /raise new request/i })).toBeVisible();
    await expect(nav.getByRole("link", { name: /prepare.*upload/i })).toBeVisible();
  });

  test("Raise New Request button visible and navigates", async ({ page }) => {
    // The button in the main content area
    const btn = page.getByRole("link", { name: /raise new request/i }).last();
    await expect(btn).toBeVisible();
    await btn.click();
    await expect(page).toHaveURL(/\/data-sharing\/new/);
  });

  test("search input is visible", async ({ page }) => {
    await expect(page.locator('input[type="search"], input[placeholder*="search" i]')).toBeVisible();
  });

  test("request tabs (I Raised / My Department Owes / All) are visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: /i raised/i }).or(page.getByText(/i raised/i)).first()).toBeVisible();
    await expect(page.getByText(/my department owes/i).first()).toBeVisible();
  });

  test("clicking a request row navigates to detail page", async ({ page }) => {
    // CSS :not selector excludes the /new link
    const rows = page.locator("a[href*='/data-sharing/']:not([href='/data-sharing/new'])");
    const count = await rows.count();
    if (count > 0) {
      await rows.first().click();
      await page.waitForTimeout(1000);
      expect(page.url()).not.toMatch(/\/data-sharing\/new$/);
      expect(page.url()).toMatch(/\/data-sharing\//);
    }
  });

  test("empty state renders when no requests or list shows rows", async ({ page }) => {
    const hasRows = await page.locator("a[href*='/data-sharing/']")
      .filter({ hasNot: page.locator("a[href='/data-sharing/new']") }).count();
    if (hasRows === 0) {
      await expect(page.getByText(/no requests|empty/i)).toBeVisible();
    } else {
      await expect(page.locator("a[href*='/data-sharing/']").first()).toBeVisible();
    }
  });
});
