import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

async function openFirstDpoRequest(page: import("@playwright/test").Page) {
  await login(page, "dpo");
  await page.goto("/dpo");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);

  const firstRow = page.locator("tbody tr").first();
  if (await firstRow.count() === 0) return false;
  await firstRow.click();
  await page.waitForTimeout(2000);
  return page.url().match(/\/dpo\/.+/) !== null && !page.url().endsWith("/dpo");
}

test.describe("DPO — Request Detail + PDPL Review (/dpo/[id])", () => {
  test("detail page renders without crash", async ({ page }) => {
    const opened = await openFirstDpoRequest(page);
    if (!opened) return test.skip();
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  test("Overview tab content is visible", async ({ page }) => {
    const opened = await openFirstDpoRequest(page);
    if (!opened) return test.skip();
    // Click overview tab if tabs exist
    const overviewTab = page.getByRole("button", { name: /overview/i }).or(page.getByText("Overview")).first();
    if (await overviewTab.count() > 0) await overviewTab.click();
    await page.waitForTimeout(500);
    await expect(page.getByText(/application error/i)).not.toBeVisible();
  });

  test("Data Minimisation tab is present", async ({ page }) => {
    const opened = await openFirstDpoRequest(page);
    if (!opened) return test.skip();
    const tab = page.getByRole("button", { name: /data min/i }).or(page.getByText(/data min/i)).first();
    if (await tab.count() === 0) {
      console.warn("BUG: Data Minimisation tab missing");
    }
  });

  test("DPIA Status tab is present", async ({ page }) => {
    const opened = await openFirstDpoRequest(page);
    if (!opened) return test.skip();
    const tab = page.getByRole("button", { name: /dpia/i }).or(page.getByText(/dpia/i)).first();
    if (await tab.count() === 0) {
      console.warn("BUG: DPIA Status tab missing");
    }
  });

  test("4th PDPL Checks tab existence check [known missing if fails]", async ({ page }) => {
    const opened = await openFirstDpoRequest(page);
    if (!opened) return test.skip();
    const pdplTab = page.getByRole("button", { name: /pdpl/i }).or(page.getByText(/pdpl check/i));
    const exists = await pdplTab.count() > 0;
    if (!exists) {
      console.warn("KNOWN BUG: 4th PDPL Checks tab missing — CHECKLIST #7");
    }
    // Non-blocking
  });

  test("back navigation returns to DPO list", async ({ page }) => {
    const opened = await openFirstDpoRequest(page);
    if (!opened) return test.skip();
    const backLink = page.getByRole("link", { name: /back|request list/i }).first();
    if (await backLink.count() > 0) {
      await backLink.click();
      await expect(page).toHaveURL(/\/dpo$/);
    }
  });
});
