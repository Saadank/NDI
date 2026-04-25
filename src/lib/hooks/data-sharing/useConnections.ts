"use client";

import { useQuery } from "@tanstack/react-query";

import {
  getConnection,
  getConnections,
} from "@/lib/api/products/data-sharing/connections.api";

export function useConnections() {
  return useQuery({
    queryKey: ["data-sharing", "connections"],
    queryFn: getConnections,
  });
}

export function useConnection(id: string) {
  return useQuery({
    queryKey: ["data-sharing", "connections", id],
    queryFn: () => getConnection(id),
    enabled: Boolean(id),
  });
}
