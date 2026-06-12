"use client";

import { useQuery } from "@tanstack/react-query";

import {
  getMyGlossaryRole,
  listGlossaryUsers,
} from "@/lib/api/products/ndmo-compliance/glossary.api";

export const GLOSSARY_NS = "ndmo-glossary";

/**
 * The caller's derived glossary role + scope (owned/steward domains, review
 * queue count).  Drives sidebar gating and in-page action visibility.
 */
export function useGlossaryRole(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: [GLOSSARY_NS, "me"],
    queryFn: getMyGlossaryRole,
    staleTime: 60_000,
    enabled: options.enabled ?? true,
    retry: false,
  });
}

/** All assignable users in the tenant (id + display name) for owner/steward
 *  pickers and for resolving user ids to names in the UI. */
export function useGlossaryUsers() {
  return useQuery({
    queryKey: [GLOSSARY_NS, "users"],
    queryFn: () => listGlossaryUsers(),
    staleTime: 300_000,
  });
}
