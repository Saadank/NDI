/**
 * End-to-end cross-role flows — exercises full user journeys.
 */
import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("E2E Flow 1 — Data Steward raises a request", () => {
  test("steward can navigate to raise new request wizard", async ({ page }) => {
    await login(page, "dataSteward");
    await page.goto("/data-sharing");
    await page.waitForLoadState("networkidle");
    await page.getByRole("navigation").getByRole("link", { name: /raise new request/i }).click();
    await expect(page).toHaveURL(/\/data-sharing\/new/);
    await expect(page.getByText(/request details/i)).toBeVisible();
  });

  test("steward fills Step 1 and it does not crash (no hooks error)", async ({ page }) => {
    await login(page, "dataSteward");
    await page.goto("/data-sharing/new");
    await page.waitForLoadState("networkidle");

    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error" && m.text().includes("Hooks")) errors.push(m.text());
    });

    await page.getByPlaceholder(/short.*descriptive/i).fill("E2E Test Request");
    await page.getByPlaceholder(/explain why/i).fill("Automated test purpose");
    await page.waitForTimeout(500);

    expect(errors).toHaveLength(0);
  });
});

test.describe("E2E Flow 2 — Data Owner reviews approvals", () => {
  test("data owner can view and navigate approval list", async ({ page }) => {
    await login(page, "dataOwner");
    await page.goto("/approvals");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: /approvals inbox/i })).toBeVisible();
    const rows = page.locator("a[href*='/approvals/']");
    if (await rows.count() > 0) {
      await rows.first().click();
      await expect(page).toHaveURL(/\/approvals\/.+/);
      await expect(page.getByText(/request detail/i)).toBeVisible();
      await page.getByRole("link", { name: /back to inbox/i }).click();
      await expect(page).toHaveURL(/\/approvals$/);
    }
  });
});

test.describe("E2E Flow 3 — DPO reviews organisation requests", () => {
  test("DPO can view request list and navigate to detail", async ({ page }) => {
    await login(page, "dpo");
    await page.goto("/dpo");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: /organisation request list/i })).toBeVisible();

    const firstRow = page.locator("tbody tr").first();
    if (await firstRow.count() > 0) {
      await firstRow.click();
      await page.waitForTimeout(2000);
      // DPO uses UUID-based IDs
      expect(page.url()).toMatch(/\/dpo\/.+/);
      expect(page.url()).not.toMatch(/\/dpo$/);
      await expect(page.getByText(/application error/i)).not.toBeVisible();
    }
  });

  test("DPO can use workflow editor", async ({ page }) => {
    await login(page, "dpo");
    await page.goto("/dpo/workflows");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("h1, h2").filter({ hasText: /workflow/i }).first()).toBeVisible();
  });
});

test.describe("E2E Flow 4 — Org Admin manages departments", () => {
  test("admin can view department list and open add department flow", async ({ page }) => {
    await login(page, "orgAdmin");
    await page.goto("/admin/departments");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: /departments/i })).toBeVisible();
    await page.getByRole("button", { name: /add department/i }).click();
    await page.waitForTimeout(800);
    // Modal contains "Department name (English)" label
    await expect(page.getByText(/department name.*english/i)).toBeVisible();
    await page.keyboard.press("Escape");
  });
});

test.describe("E2E Flow 5 — Platform Admin onboards a company", () => {
  test("platform admin can reach onboard wizard step 1", async ({ page }) => {
    await login(page, "platformAdmin");
    await page.goto("/platform/onboard");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/application error/i)).not.toBeVisible();
    await expect(page.getByRole("button", { name: /continue|next/i }).first()).toBeVisible();
  });

  test("platform admin sidebar shows PLATFORM ADMIN header", async ({ page }) => {
    await login(page, "platformAdmin");
    await page.goto("/platform/organisations");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/platform admin/i)).toBeVisible();
  });
});
