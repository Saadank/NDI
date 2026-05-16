import type { Page } from "@playwright/test";

export const USERS = {
  dataSteward: { email: "sara.fin@acme.local", password: "Test123!" },
  dataOwner: { email: "ahmed.do@acme.local", password: "Test123!" },
  dpo: { email: "nora.dpo@acme.local", password: "Test123!" },
  orgAdmin: { email: "superadmin@datasharing.local", password: "SuperAdmin123!" },
  platformAdmin: { email: "superadmin@datasharing.local", password: "SuperAdmin123!" },
} as const;

export type UserKey = keyof typeof USERS;

export async function login(page: Page, userKey: UserKey) {
  const user = USERS[userKey];
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  await page.locator('input[type="email"]').fill(user.email);
  await page.locator('input[type="password"]').fill(user.password);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  // Wait for navigation away from /login
  await page.waitForFunction(() => !window.location.pathname.startsWith("/login"), { timeout: 15_000 });
}

export async function logout(page: Page) {
  await page.goto("/login");
}
