import { get } from "@/lib/api/client";
import type { PaginatedResponse } from "@/lib/types/common.types";

// Mirrors a row from the platform audit log returned by GET /platform/audit/.
// Fields are intentionally permissive — `metadata` shape varies per
// `action_type`.
export interface AuditEvent {
  id: number;
  tenant_id: number;
  actor_id: number | null;
  actor_email: string | null;
  action_type: string;
  request_id: string | null;
  target_type: string | null;
  target_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

const BASE = "/api/v1/platform/audit";

export function getAuditEvents(params?: {
  page?: number;
  limit?: number;
  request_id?: string;
  actor_id?: number;
  action_type?: string;
  date_from?: string;
  date_to?: string;
}): Promise<PaginatedResponse<AuditEvent>> {
  return get<PaginatedResponse<AuditEvent>>(`${BASE}/`, { params });
}

// Triggers a CSV download. We use the apiClient base instance so the Bearer
// token is auto-attached.
export function getAuditExportUrl(params?: {
  request_id?: string;
  actor_id?: number;
  action_type?: string;
  from_date?: string;
  to_date?: string;
}): { url: string; query: Record<string, string> } {
  const url = `${BASE}/export`;
  const query: Record<string, string> = {};
  if (params?.request_id) query.request_id = params.request_id;
  if (params?.actor_id) query.actor_id = String(params.actor_id);
  if (params?.action_type) query.action_type = params.action_type;
  if (params?.from_date) query.from_date = params.from_date;
  if (params?.to_date) query.to_date = params.to_date;
  return { url, query };
}
