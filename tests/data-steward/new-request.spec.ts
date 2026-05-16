import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

test.describe("DS — New Request Wizard (/data-sharing/new)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "dataSteward");
    await page.goto("/data-sharing/new");
    await page.waitForLoadState("networkidle");
  });

  // Functional
  test("Step 1 renders without React hooks error", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error" && m.text().includes("order of Hooks")) errors.push(m.text());
    });
    await page.waitForTimeout(1000);
    expect(errors).toHaveLength(0);
  });

  test("Step 1 title and purpose fields are visible", async ({ page }) => {
    await expect(page.getByPlaceholder(/short.*descriptive/i)).toBeVisible();
    await expect(page.getByPlaceholder(/explain why/i)).toBeVisible();
  });

  test("Receiver department dropdown is visible", async ({ page }) => {
    await expect(page.getByText(/receiver department/i)).toBeVisible();
  });

  test("Data classification options are visible", async ({ page }) => {
    await expect(page.getByText(/data classification/i)).toBeVisible();
  });

  test("Legal basis label is visible", async ({ page }) => {
    await expect(page.getByText("Legal basis", { exact: true })).toBeVisible();
  });

  test("Next button is present on Step 1", async ({ page }) => {
    // Use exact match to avoid matching Next.js devtools button
    const nextBtn = page.getByRole("button", { name: "Next", exact: true });
    await expect(nextBtn).toBeVisible();
  });

  test("Save as Draft button is present", async ({ page }) => {
    await expect(page.getByRole("button", { name: /save as draft/i })).toBeVisible();
  });

  // Validation
  test("Help me pick modal opens and closes", async ({ page }) => {
    await page.getByText(/help me pick/i).click();
    await expect(page.getByText(/which legal basis applies/i)).toBeVisible();
    await page.getByRole("button", { name: /close/i }).click();
    await expect(page.getByText(/which legal basis applies/i)).not.toBeVisible();
  });

  test("Legal basis modal: clicking an option closes modal", async ({ page }) => {
    await page.getByText(/help me pick/i).click();
    await page.getByRole("button", { name: /consent/i }).first().click();
    await expect(page.getByText(/which legal basis applies/i)).not.toBeVisible();
  });

  // UI
  test("Sharing type toggling does not crash", async ({ page }) => {
    // Use the radio button containers specifically (capitalize radio labels)
    const externalBtn = page.getByRole("button").filter({ hasText: "external" });
    const internalBtn = page.getByRole("button").filter({ hasText: "internal" });
    if (await externalBtn.count() > 0) await externalBtn.first().click();
    await page.waitForTimeout(200);
    if (await internalBtn.count() > 0) await internalBtn.first().click();
    await page.waitForTimeout(200);
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  test("Personal data toggle shows extra fields", async ({ page }) => {
    // Toggle "Yes"
    await page.getByText("Yes").first().click();
    await expect(page.getByText(/estimated number of data subjects/i)).toBeVisible();
  });

  // Negative
  test("Non-steward (DPO) is redirected from /data-sharing/new", async ({ page }) => {
    await login(page, "dpo");
    await page.goto("/data-sharing/new");
    await page.waitForTimeout(2000);
    // Role guard returns null — page blank or redirected
    const hasForm = await page.getByPlaceholder(/short.*descriptive/i).isVisible().catch(() => false);
    expect(hasForm).toBe(false);
  });
});
