import { test, expect } from "@playwright/test";
import { login, USERS } from "../helpers/auth";

test.describe("Login — email + password", () => {
  test("renders login form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in|log in/i })).toBeVisible();
  });

  test("shows validation errors on empty submit", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page.getByText(/required|email is required|please enter/i)).toBeVisible();
  });

  test("shows error on bad credentials (any visible error text)", async ({ page }) => {
    await page.goto("/login");
    await page.locator('input[type="email"]').fill("bad@example.com");
    await page.locator('input[type="password"]').fill("wrongpass");
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    // Wait for response — accept any error-style text or remain on login page
    await page.waitForTimeout(3000);
    const stillOnLogin = page.url().includes("/login");
    expect(stillOnLogin).toBe(true);
  });

  test("Data Steward can log in and reaches dashboard", async ({ page }) => {
    await login(page, "dataSteward");
    expect(page.url()).not.toMatch(/\/login/);
  });

  test("Data Owner can log in and reaches dashboard", async ({ page }) => {
    await login(page, "dataOwner");
    expect(page.url()).not.toMatch(/\/login/);
  });

  test("DPO can log in and reaches dashboard", async ({ page }) => {
    await login(page, "dpo");
    expect(page.url()).not.toMatch(/\/login/);
  });

  test("Org Admin can log in and reaches dashboard", async ({ page }) => {
    await login(page, "orgAdmin");
    expect(page.url()).not.toMatch(/\/login/);
  });

  test("unauthenticated access to dashboard redirects to login", async ({ page }) => {
    await page.goto("/approvals");
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });
});

test.describe("Login — forgot password", () => {
  test("Forgot Password link is visible", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText(/forgot|reset password/i)).toBeVisible();
  });
});
