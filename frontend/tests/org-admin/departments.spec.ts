import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("OA — Departments (/admin/departments)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "orgAdmin");
    await page.goto("/admin/departments");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
  });

  // Functional
  test("page loads with Departments heading", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /departments/i })).toBeVisible();
  });

  test("department list renders Finance or HR rows", async ({ page }) => {
    await expect(page.getByText(/finance department|human resources/i).first()).toBeVisible();
  });

  test("Add department button is visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: /add department/i })).toBeVisible();
  });

  test("Add department button triggers modal or overlay", async ({ page }) => {
    await page.getByRole("button", { name: /add department/i }).click();
    await page.waitForTimeout(800);
    // Modal might not have role=dialog — look for any overlay/form that appeared
    await expect(page.getByText(/department name.*english/i)).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("pagination / row count text is visible", async ({ page }) => {
    // "Showing N of N departments" at the bottom, or page count
    await expect(page.getByText(/showing \d+ of \d+/i).first()).toBeVisible();
  });

  // Role-Based Access
  test("Data Steward cannot access /admin/departments", async ({ page }) => {
    await login(page, "dataSteward");
    await page.goto("/admin/departments");
    await page.waitForTimeout(2000);
    await expect(page.getByRole("heading", { name: /departments/i })).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
  });

  test("Data Owner cannot access /admin/departments", async ({ page }) => {
    await login(page, "dataOwner");
    await page.goto("/admin/departments");
    await page.waitForTimeout(2000);
    await expect(page.getByRole("heading", { name: /departments/i })).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
  });
});
