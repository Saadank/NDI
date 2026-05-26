"use client";

import { useQuery } from "@tanstack/react-query";

import { getConnectionSchemas } from "@/lib/api/products/data-sharing/schemas.api";

export function useSchemas(connectionId: string) {
  return useQuery({
    queryKey: ["data-sharing", "schemas", connectionId],
    queryFn: () => getConnectionSchemas(connectionId),
    enabled: Boolean(connectionId),
  });
}
