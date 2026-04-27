"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuthStore } from "@/lib/store/auth.store";

// Role keys used across the codebase. Backend returns:
//   user.platform_role:  "platform_admin" | "org_admin" | "user"
//   user.product_role:   "requester" | "data_owner" | "dpo" | null
export type Role =
  | "platform_admin"
  | "org_admin"
  | "dpo"
  | "data_owner"
  | "requester";

interface UseRoleGuardOptions {
  // Any user holding ONE of these roles is allowed in. If undefined, only
  // authentication is required.
  allow?: Role[];
  // Where to redirect a user who fails the check. Defaults to "/".
  redirectTo?: string;
}

interface UseRoleGuardResult {
  isReady: boolean;
  isAllowed: boolean;
  roles: Set<Role>;
}

/**
 * Page-level role guard. Call from the top of any page that should be visible
 * to a subset of roles. Redirects unauthenticated users to /login and
 * unauthorized authenticated users to `redirectTo` (default "/").
 *
 * The store is hydrated from a persisted snapshot, so on the first render
 * `user` may be null even for a logged-in user. We wait one tick before
 * making redirect decisions to avoid bouncing the user mid-hydration.
 */
export function useRoleGuard(
  opts: UseRoleGuardOptions = {},
): UseRoleGuardResult {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Collect every role the user holds. Treating product_role and
  // platform_role uniformly lets a single `allow=["data_owner"]` work
  // regardless of which side the role lives on.
  const roles = new Set<Role>();
  if (user?.product_role) roles.add(user.product_role as Role);
  if (user?.platform_role) roles.add(user.platform_role as Role);
  // Platform admins can see everything in dev.
  if (user?.platform_role === "platform_admin") {
    (
      ["org_admin", "dpo", "data_owner", "requester"] as Role[]
    ).forEach((r) => roles.add(r));
  }

  const isAllowed =
    isAuthenticated &&
    (!opts.allow || opts.allow.some((r) => roles.has(r)));

  useEffect(() => {
    // Wait for the store to hydrate before making any redirect decision.
    if (typeof window === "undefined") return;

    if (!isAuthenticated) {
      // Cookie/localStorage might still be hydrating — give it one tick.
      const t = setTimeout(() => {
        if (!useAuthStore.getState().isAuthenticated) {
          router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
        }
      }, 50);
      return () => clearTimeout(t);
    }
    if (!isAllowed) {
      router.replace(opts.redirectTo ?? "/");
    }
  }, [isAuthenticated, isAllowed, opts.redirectTo, router]);

  return {
    isReady: isAuthenticated && isAllowed,
    isAllowed,
    roles,
  };
}
