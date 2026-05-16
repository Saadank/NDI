import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CurrentUser } from "@/lib/types/platform/auth.types";

interface AuthState {
  user: CurrentUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: CurrentUser) => void;
  logout: () => void;
  initialize: () => void;
}

// The Next.js middleware (`src/middleware.ts`) gates protected routes by
// reading a cookie named `datarix-auth` and looking for `state.accessToken`.
// Zustand's `persist` writes to localStorage by default, which the
// server-side middleware cannot see — so without this cookie sync, every
// post-login navigation to a protected route redirects back to /login.
//
// We keep the full state in localStorage (richer client-side hydration)
// and mirror just an `accessToken` marker into a cookie so middleware can
// detect "logged in" without ever exposing the real JWT in the cookie.
const AUTH_COOKIE = "datarix-auth";
const AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 days

// Normalize the user payload returned by /auth/login + /users/me. The
// backend's AuthUser Pydantic model serializes its primary key as
// `user_id`, but the rest of the frontend reads `user.id`. Mapping
// once at the store boundary keeps every consumer (the inbox filter,
// /prepare, the approval detail, …) free of `?? user_id` fallbacks.
function normalizeUser<T extends Partial<CurrentUser> & { user_id?: number }>(
  user: T,
): CurrentUser {
  const id = user.id ?? user.user_id;
  if (id === undefined) {
    // Should never happen in production — log and let downstream
    // null-checks short-circuit instead of crashing.
    console.warn("[auth] login response missing both `id` and `user_id`:", user);
  }
  return { ...(user as CurrentUser), id: id as number };
}

function writeAuthCookie(hasToken: boolean) {
  if (typeof document === "undefined") return;
  if (hasToken) {
    const value = encodeURIComponent(
      JSON.stringify({ state: { accessToken: "1" } }),
    );
    document.cookie = `${AUTH_COOKIE}=${value}; Path=/; Max-Age=${AUTH_COOKIE_MAX_AGE}; SameSite=Lax`;
  } else {
    document.cookie = `${AUTH_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      setTokens: (accessToken, refreshToken) => {
        writeAuthCookie(Boolean(accessToken));
        set({ accessToken, refreshToken, isAuthenticated: true });
      },

      setUser: (user) => set({ user: normalizeUser(user) }),

      logout: () => {
        writeAuthCookie(false);
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },

      initialize: () =>
        set((state) => {
          writeAuthCookie(Boolean(state.accessToken));
          return { isAuthenticated: Boolean(state.accessToken) };
        }),
    }),
    {
      name: "datarix-auth",
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
      onRehydrateStorage: () => (state) => {
        // After Zustand restores from localStorage on a fresh tab/load,
        // re-mirror the marker cookie so middleware lets the user through.
        if (state) {
          writeAuthCookie(Boolean(state.accessToken));
          state.isAuthenticated = Boolean(state.accessToken);
          // Normalize previously-persisted user blobs that may have
          // `user_id` but no `id` (sessions created before the
          // normalization landed). One-time fix-up.
          if (state.user && (state.user as Partial<CurrentUser>).id === undefined) {
            state.user = normalizeUser(state.user);
          }
        }
      },
    },
  ),
);
