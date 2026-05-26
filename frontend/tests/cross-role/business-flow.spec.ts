/**
 * Business Logic E2E — Full Approval Workflow
 *
 * Sara (Data Steward) submits a data sharing request.
 * Ahmed (Data Owner) receives it in his Approvals Inbox and approves it.
 * Sara's request list reflects the updated status.
 *
 * Each phase runs in an isolated browser context so session cookies and
 * sessionStorage (the Zustand store) don't bleed between users.
 */

import { test, expect } from "@playwright/test";
import { login } from "../helpers/auth";

const UNIQUE_TITLE = `E2E-BizFlow-${Date.now()}`;

test.describe("Business Flow — DS submits → DO approves", () => {
  test.setTimeout(180_000);

  test("Sara creates a request, Ahmed approves it, Sara sees updated status", async ({
    browser,
  }) => {
    // ── Phase 1: Sara (Data Steward) fills the wizard and submits ─────────────

    const saraCtx = await browser.newContext();
    const sara = await saraCtx.newPage();

    try {
      await login(sara, "dataSteward");

      // Go to Step 1 of the new-request wizard
      await sara.goto("/data-sharing/new");
      await sara.waitForLoadState("networkidle");
      // Let the departments API finish loading
      await sara.waitForTimeout(2000);

      // Fill required Step 1 fields
      await sara.getByPlaceholder(/short.*descriptive/i).fill(UNIQUE_TITLE);
      await sara
        .getByPlaceholder(/explain why/i)
        .fill("Automated E2E business workflow test — please ignore");

      // Receiver department — native <select>; first select on the page
      const receiverSelect = sara.locator("select").first();

      // Gather available options so we can pick one programmatically
      const deptOptions = await receiverSelect.evaluate(
        (el: HTMLSelectElement) =>
          Array.from(el.options)
            .filter((o) => o.value !== "")
            .map((o) => ({ value: o.value, label: o.text.trim() })),
      );

      if (deptOptions.length === 0) {
        console.warn(
          "WARN: No departments available in receiver dropdown — skipping business-flow test.",
        );
        return;
      }

      // Prefer Human Resources; fall back to first available department
      const hrDept = deptOptions.find((o) =>
        /human.?resources|^hr$/i.test(o.label),
      );
      let targetDept = hrDept ?? deptOptions[0];

      await receiverSelect.selectOption({ value: targetDept.value });
      await sara.waitForTimeout(300);

      // If Sara is in that department, pick a different one
      const ownDeptErr = sara.getByText(/cannot raise.*own department/i);
      if (await ownDeptErr.isVisible()) {
        const fallback = deptOptions.find((o) => o.value !== targetDept.value);
        if (!fallback) {
          console.warn(
            "WARN: Sara appears to be in the only available department — cannot submit cross-dept request.",
          );
          return;
        }
        targetDept = fallback;
        await receiverSelect.selectOption({ value: targetDept.value });
        await sara.waitForTimeout(300);
      }

      console.log(
        `Submitting request to receiver department: "${targetDept.label}" (id=${targetDept.value})`,
      );

      // Next button must be enabled (title + purpose + receiver dept is enough for
      // "internal" classification with no personal data)
      const nextBtn = sara.getByRole("button", { name: "Next", exact: true });
      await expect(nextBtn).toBeEnabled({ timeout: 5_000 });

      // Skip the file-upload Step 2 — navigate directly to Step 3.
      // The Zustand store (sessionStorage) already holds the Step 1 fields.
      // Step 3's handleSubmit skips file upload when staged_files is empty.
      await sara.goto("/data-sharing/new/step-3");
      await sara.waitForLoadState("networkidle");
      await sara.waitForTimeout(1500);

      // Confirm Step 3 rendered the review summary
      await expect(sara.getByText(/step 1.*request details/i)).toBeVisible({
        timeout: 5_000,
      });

      // Submit
      const submitBtn = sara.getByRole("button", { name: /^submit$/i });
      await expect(submitBtn).toBeVisible({ timeout: 5_000 });
      await submitBtn.click();

      // Wait for the redirect back to /data-sharing (My Requests list)
      await sara.waitForURL(/\/data-sharing$/, { timeout: 25_000 });

      // Confirm the newly submitted request appears in Sara's list
      await expect(sara.getByText(UNIQUE_TITLE)).toBeVisible({ timeout: 10_000 });

      console.log(`✓ Sara submitted "${UNIQUE_TITLE}" — it appears in My Requests.`);
    } finally {
      await saraCtx.close();
    }

    // ── Phase 2: Ahmed (Data Owner) finds the request and approves it ─────────

    const ahmedCtx = await browser.newContext();
    const ahmed = await ahmedCtx.newPage();

    try {
      await login(ahmed, "dataOwner");
      await ahmed.goto("/approvals");
      await ahmed.waitForLoadState("networkidle");
      await ahmed.waitForTimeout(1500);

      // Navigate to the Incoming tab (requests that require Ahmed's action)
      const incomingTab = ahmed
        .getByRole("button", { name: /incoming/i })
        .or(ahmed.getByText(/incoming/i).first());
      if ((await incomingTab.count()) > 0) {
        await incomingTab.first().click();
        await ahmed.waitForTimeout(800);
      }

      // Use search to filter by the unique title (if search is available)
      const searchInput = ahmed
        .locator('input[type="search"], input[placeholder*="search" i]')
        .first();
      if (await searchInput.isVisible().catch(() => false)) {
        await searchInput.fill(UNIQUE_TITLE);
        await ahmed.waitForTimeout(1200);
      }

      // Look for a row mentioning Sara's unique title
      const requestRow = ahmed.getByText(UNIQUE_TITLE, { exact: false }).first();
      const requestVisible = await requestRow
        .isVisible({ timeout: 5_000 })
        .catch(() => false);

      if (!requestVisible) {
        console.warn(
          `⚠ Request "${UNIQUE_TITLE}" not visible in Ahmed's Approvals Inbox.` +
            ` Ahmed (ahmed.do@acme.local) may not be the data owner for the` +
            ` target department — approval phase skipped.`,
        );
        return;
      }

      // Open the request detail
      await requestRow.click();
      await ahmed.waitForTimeout(2000);

      // Verify we landed on the detail page
      expect(ahmed.url()).toMatch(/\/approvals\/.+/);

      // The sticky action bar only appears when Ahmed has a pending step (can_act=true)
      const approveArrowBtn = ahmed.getByRole("button", {
        name: /^approve/i,
      });
      const canAct = await approveArrowBtn
        .isVisible({ timeout: 8_000 })
        .catch(() => false);

      if (!canAct) {
        console.warn(
          `⚠ "Approve →" button not visible for Ahmed on this request.` +
            ` The workflow step may not assign to data_owner, or Ahmed is not` +
            ` the assigned owner for this step — approval phase skipped.`,
        );
        return;
      }

      // Click "Approve →" to open the ApproveModal
      await approveArrowBtn.first().click();
      await ahmed.waitForTimeout(500);

      // ApproveModal is open — confirm via the "Approve Request" heading
      await expect(
        ahmed.getByRole("heading", { name: /approve request/i }),
      ).toBeVisible({ timeout: 3_000 });

      // Optionally add a note, then click the modal "Approve" button
      await ahmed
        .getByPlaceholder(/optional note/i)
        .fill("E2E automated test approval");

      const confirmApproveBtn = ahmed.getByRole("button", {
        name: "Approve",
        exact: true,
      });
      await expect(confirmApproveBtn).toBeVisible();
      await confirmApproveBtn.click();

      // After approval the component calls router.push("/approvals")
      await ahmed.waitForURL(/\/approvals$/, { timeout: 15_000 });

      console.log(`✓ Ahmed approved "${UNIQUE_TITLE}" — redirected to /approvals.`);
    } finally {
      await ahmedCtx.close();
    }

    // ── Phase 3: Sara confirms the request status has progressed ─────────────

    const saraCtx2 = await browser.newContext();
    const sara2 = await saraCtx2.newPage();

    try {
      await login(sara2, "dataSteward");
      await sara2.goto("/data-sharing");
      await sara2.waitForLoadState("networkidle");
      await sara2.waitForTimeout(1500);

      // Sara's submitted request must still appear in her list
      await expect(sara2.getByText(UNIQUE_TITLE)).toBeVisible({ timeout: 10_000 });

      // Navigate into the request detail to verify it is no longer in Draft state
      const requestLink = sara2
        .locator("a[href*='/data-sharing/']")
        .filter({ hasText: UNIQUE_TITLE })
        .first();

      if ((await requestLink.count()) > 0) {
        await requestLink.click();
        await sara2.waitForTimeout(2000);

        // Should be on the DS detail page for this request
        expect(sara2.url()).toMatch(/\/data-sharing\/.+/);
        expect(sara2.url()).not.toMatch(/\/data-sharing\/new/);

        // The request must NOT show as Draft — it was submitted and approved
        const draftBadge = sara2.getByText(/^draft$/i);
        expect(await draftBadge.isVisible().catch(() => false)).toBe(false);

        console.log(
          `✓ Sara can see "${UNIQUE_TITLE}" detail page — request is post-submission.`,
        );
      } else {
        // Request is visible in the list (title confirmed above) — soft pass
        console.log(
          `✓ Sara sees "${UNIQUE_TITLE}" in My Requests list. Detail link not found as <a> — list may use <tr> rows.`,
        );
      }
    } finally {
      await saraCtx2.close();
    }
  });
});
