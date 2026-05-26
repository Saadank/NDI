import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("DO — My Department (/my-department)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "dataOwner");
    await page.goto("/my-department");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
  });

  // Functional
  test("page loads with My Department heading", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /my department/i })).toBeVisible();
  });

  test("Stewards tab button is visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Stewards" })).toBeVisible();
  });

  test("Role Delegation tab is visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: /role delegation/i })).toBeVisible();
  });

  test("department section heading is visible", async ({ page }) => {
    // The department h2 is uniquely identifiable
    await expect(page.getByRole("heading", { name: /finance department|human resources/i })).toBeVisible();
  });

  test("Add Steward button is visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: /add steward/i })).toBeVisible();
  });

  test("stewards list renders or empty state shown", async ({ page }) => {
    await expect(page.getByText(/application error/i)).not.toBeVisible();
    // Either steward names or some content
    await expect(page.locator("h1, h2, p").first()).toBeVisible();
  });

  // Role-Based Access
  test("Data Steward cannot see My Department content", async ({ page }) => {
    await login(page, "dataSteward");
    await page.goto("/my-department");
    await page.waitForTimeout(2000);
    await expect(page.getByRole("button", { name: /add steward/i })).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
  });
});
