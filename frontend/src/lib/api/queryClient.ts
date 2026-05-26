// Module-level reference to the app's QueryClient so non-React code (auth
// store, axios interceptors, logout handler) can clear the cache on sign-out
// without having to thread the client through every call site.
//
// Providers.tsx calls `setQueryClient(client)` once when the React tree
// mounts; consumers call `getQueryClient()` and gracefully no-op if the
// reference isn't ready yet (e.g. during SSR).

import type { QueryClient } from "@tanstack/react-query";

let _queryClient: QueryClient | null = null;

export function setQueryClient(client: QueryClient): void {
  _queryClient = client;
}

export function getQueryClient(): QueryClient | null {
  return _queryClient;
}

export function clearAllQueries(): void {
  _queryClient?.clear();
}
