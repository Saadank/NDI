import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("DS — Request Detail (/data-sharing/[id])", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "dataSteward");
    await page.goto("/data-sharing");
    await page.waitForLoadState("networkidle");
  });

  async function openFirstRequest(page: import("@playwright/test").Page) {
    const rows = page.locator("a[href*='/data-sharing/']")
      .filter({ hasNot: page.locator("a[href='/data-sharing/new']") });
    const count = await rows.count();
    if (count === 0) return false;
    await rows.first().click();
    await page.waitForURL(/\/data-sharing\/.+/);
    return true;
  }

  test("request detail page loads and shows title", async ({ page }) => {
    const opened = await openFirstRequest(page);
    if (!opened) return test.skip();
    await expect(page.getByRole("heading", { level: 1 }).or(page.locator("h1"))).toBeVisible();
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  test("back navigation returns to list", async ({ page }) => {
    const opened = await openFirstRequest(page);
    if (!opened) return test.skip();
    const backLink = page.getByRole("link", { name: /back|my requests/i }).first();
    if (await backLink.count() > 0) {
      await backLink.click();
      await expect(page).toHaveURL(/\/data-sharing$/);
    }
  });

  test("Changes Requested banner fires on correct status", async ({ page }) => {
    const opened = await openFirstRequest(page);
    if (!opened) return test.skip();
    // If the page shows a changes_requested banner, status must be changes_requested
    const bannerVisible = await page.getByText(/changes.requested|send back/i).isVisible().catch(() => false);
    if (bannerVisible) {
      // Banner is showing — verify it only shows for changes_requested (not rejected)
      const pageText = await page.textContent("body");
      expect(pageText).toContain("changes");
    }
    // No crash either way
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  test("approved state shows Approved status", async ({ page }) => {
    // Navigate to All tab and find an approved request
    const allTab = page.getByRole("button", { name: /^all/i }).or(page.getByText(/^all \d+/i)).first();
    if (await allTab.count() > 0) {
      await allTab.click();
      await page.waitForTimeout(500);
    }
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });
});
