"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import * as authApi from "@/lib/api/platform/auth.api";
import { clearAllQueries } from "@/lib/api/queryClient";
import { getCurrentUser } from "@/lib/api/platform/users.api";
import { useAuthStore } from "@/lib/store/auth.store";
import type { LoginRequest } from "@/lib/types/platform/auth.types";

export function useLogin() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  return useMutation({
    mutationFn: (body: LoginRequest) => authApi.login(body),
    onSuccess: (data) => {
      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);
    },
  });
}

export function useLogout() {
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const logout = useAuthStore((s) => s.logout);

  return useMutation({
    // Always resolve — we want logout to succeed even if the network call
    // for /auth/logout fails (the local session must still be killed).
    mutationFn: () =>
      refreshToken
        ? authApi.logout(refreshToken).catch(() => ({ success: true }))
        : Promise.resolve({ success: true }),
    onSettled: () => {
      // 1. Clear React Query cache so no stale user data leaks into the
      //    next session that logs in on this tab.
      clearAllQueries();
      // 2. Clear zustand auth state + the marker cookie used by middleware.
      logout();
      // 3. Hard-redirect so any in-flight queries are torn down and the
      //    middleware re-evaluates protected routes with no token.
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    },
  });
}

export function useCurrentUser() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  return useQuery({
    queryKey: ["currentUser"],
    queryFn: getCurrentUser,
    enabled: isAuthenticated,
  });
}
