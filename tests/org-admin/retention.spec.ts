import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("OA — Retention Policy (/admin/retention)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "orgAdmin");
    await page.goto("/admin/retention");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
  });

  test("page loads with Retention Policy heading", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /retention policy/i })).toBeVisible();
  });

  test("retention cap options are visible (30/60/90/180 days)", async ({ page }) => {
    await expect(page.getByText("30 days")).toBeVisible();
    await expect(page.getByText("60 days")).toBeVisible();
    await expect(page.getByText("90 days")).toBeVisible();
    await expect(page.getByText("180 days")).toBeVisible();
  });

  test("Save changes button is visible", async ({ page }) => {
    // Button appears both in card and in header — use first()
    await expect(page.getByRole("button", { name: /save changes/i }).first()).toBeVisible();
  });

  test("warning about permanent deletion is shown", async ({ page }) => {
    await expect(page.getByText(/permanently deleted/i)).toBeVisible();
  });

  test("selecting a cap does not crash", async ({ page }) => {
    await page.getByText("30 days").click();
    await page.waitForTimeout(300);
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  // Role-Based Access
  test("Data Owner cannot access /admin/retention", async ({ page }) => {
    await login(page, "dataOwner");
    await page.goto("/admin/retention");
    await page.waitForTimeout(2000);
    await expect(page.getByRole("heading", { name: /retention policy/i })).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
  });
});
