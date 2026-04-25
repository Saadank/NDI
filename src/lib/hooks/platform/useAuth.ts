"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import * as authApi from "@/lib/api/platform/auth.api";
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
    mutationFn: () =>
      refreshToken
        ? authApi.logout(refreshToken)
        : Promise.resolve({ success: true }),
    onSettled: () => logout(),
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
