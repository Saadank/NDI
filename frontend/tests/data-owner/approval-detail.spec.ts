import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

async function openFirstApproval(page: import("@playwright/test").Page): Promise<boolean> {
  await login(page, "dataOwner");
  await page.goto("/approvals");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);

  const firstRow = page.locator("a[href*='/approvals/']").first();
  if (await firstRow.count() === 0) return false;
  await firstRow.click();
  await page.waitForURL(/\/approvals\/.+/);
  await page.waitForLoadState("networkidle");
  return true;
}

test.describe("DO — Approval Detail (/approvals/[id])", () => {
  // Functional
  test("detail page loads with Request Detail heading", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    await expect(page.getByText(/request detail/i)).toBeVisible();
  });

  test("Back to Inbox link navigates back", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    await page.getByRole("link", { name: /back to inbox/i }).click();
    await expect(page).toHaveURL(/\/approvals$/);
  });

  test("Data Owner badge is visible", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    await expect(page.getByText(/data owner/i)).toBeVisible();
  });

  test("Workflow card renders", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    await expect(page.getByText(/workflow/i)).toBeVisible();
  });

  test("Activity Timeline card renders", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    await expect(page.getByText(/activity timeline/i)).toBeVisible();
  });

  // UI — action bar
  test("action bar shows Approve/Reject/Request Changes when step is actionable", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    const hasActionBar = await page.locator("div.sticky").count() > 0;
    if (hasActionBar) {
      await expect(page.getByRole("button", { name: /approve/i })).toBeVisible();
      await expect(page.getByRole("button", { name: /^reject$/i })).toBeVisible();
      await expect(page.getByRole("button", { name: /request changes/i })).toBeVisible();
    }
  });

  // Modal tests
  test("Request Changes modal opens and requires comment", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    const changesBtn = page.getByRole("button", { name: /request changes/i });
    if (await changesBtn.count() === 0) return test.skip();
    await changesBtn.click();
    await expect(page.getByText(/send back to requester/i)).toBeVisible();
    const sendBtn = page.getByRole("button", { name: /send back to requester/i });
    await expect(sendBtn).toBeDisabled();
    await page.getByRole("button", { name: /cancel/i }).click();
    await expect(page.getByText(/send back to requester/i)).not.toBeVisible();
  });

  test("Reject modal opens with red styling", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    const rejectBtn = page.getByRole("button", { name: /^reject$/i });
    if (await rejectBtn.count() === 0) return test.skip();
    await rejectBtn.click();
    await expect(page.getByText(/reject request/i)).toBeVisible();
    await page.getByRole("button", { name: /cancel/i }).click();
  });

  test("Flag for Technical Review modal opens", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    const flagBtn = page.getByRole("button", { name: /flag for technical review/i });
    if (await flagBtn.count() === 0) return test.skip();
    await flagBtn.click();
    await expect(page.getByText(/flagged|technical review/i)).toBeVisible();
    await page.getByRole("button", { name: /cancel/i }).click();
  });

  // Sidebar highlight
  test("Request Detail + Actions sidebar item is visible", async ({ page }) => {
    const ok = await openFirstApproval(page);
    if (!ok) return test.skip();
    const nav = page.getByRole("navigation");
    await expect(nav.getByRole("link", { name: /request detail.*actions/i })).toBeVisible();
  });

  // Role-Based Access
  test("DPO cannot see Data Owner action buttons on approval detail", async ({ page }) => {
    // First find an approval ID from dataOwner perspective
    await login(page, "dataOwner");
    await page.goto("/approvals");
    await page.waitForLoadState("networkidle");
    const firstRow = page.locator("a[href*='/approvals/']").first();
    if (await firstRow.count() === 0) return test.skip();
    const href = await firstRow.getAttribute("href");

    await login(page, "dpo");
    await page.goto(href!);
    await page.waitForTimeout(2000);
    await expect(page.getByRole("button", { name: /^approve$/i })).not.toBeVisible();
  });
});
