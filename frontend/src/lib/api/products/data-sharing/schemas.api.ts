import { get } from "@/lib/api/client";
import type { ConnectionSchemaResponse } from "@/lib/types/data-sharing/connection.types";

const BASE = "/api/v1/products/data-sharing/schemas";

// GET /schemas/{connection_id}/browse → introspected schema for a connection.
export function getConnectionSchemas(
  connectionId: string,
): Promise<ConnectionSchemaResponse> {
  return get<ConnectionSchemaResponse>(`${BASE}/${connectionId}/browse`);
}
