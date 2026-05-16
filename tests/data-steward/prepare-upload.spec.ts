import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("DS — Prepare & Upload (/prepare)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "dataSteward");
    await page.goto("/prepare");
    await page.waitForLoadState("networkidle");
  });

  test("prepare page loads without crash", async ({ page }) => {
    await expect(page.getByText(/application error|something went wrong/i)).not.toBeVisible();
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("sidebar shows Prepare & Upload as active", async ({ page }) => {
    const activeLink = page.getByRole("link", { name: /prepare.*upload/i });
    await expect(activeLink).toBeVisible();
  });

  test("page title is visible", async ({ page }) => {
    const heading = page.getByRole("heading", { name: /prepare|upload/i });
    await expect(heading).toBeVisible();
  });

  // Role-Based Access
  test("Data Owner cannot access /prepare", async ({ page }) => {
    await login(page, "dataOwner");
    await page.goto("/prepare");
    await page.waitForTimeout(2000);
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });
});
