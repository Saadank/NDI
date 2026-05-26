"use client";

import { useQuery } from "@tanstack/react-query";

import { getRequest } from "@/lib/api/products/data-sharing/requests.api";

export function useRequestDetail(id: string) {
  return useQuery({
    queryKey: ["data-sharing", "request", id],
    queryFn: () => getRequest(id),
    enabled: Boolean(id),
  });
}
