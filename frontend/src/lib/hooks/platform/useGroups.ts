"use client";

import { useQuery } from "@tanstack/react-query";

import { getGroups } from "@/lib/api/platform/groups.api";

export function useGroups() {
  return useQuery({
    queryKey: ["platform", "groups"],
    queryFn: getGroups,
    staleTime: 60_000,
  });
}
