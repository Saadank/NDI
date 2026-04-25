import { get } from "@/lib/api/client";
import type { Connection } from "@/lib/types/data-sharing/connection.types";

const BASE = "/api/v1/products/data-sharing/connections";

export function getConnections(): Promise<Connection[]> {
  return get<Connection[]>(`${BASE}/browse`);
}

export function getConnection(id: string): Promise<Connection> {
  return get<Connection>(`${BASE}/${id}/browse`);
}
