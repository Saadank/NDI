import { get } from "@/lib/api/client";
import type { PaginatedResponse } from "@/lib/types/common.types";

export interface AuditEvent {
  id: number;
  actor_id: number;
  actor_name: string;
  action: string;
  target_type: string;
  target_id: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

const BASE = "/api/v1/platform/audit";

export function getAuditEvents(params?: {
  page?: number;
  limit?: number;
  action?: string;
}): Promise<PaginatedResponse<AuditEvent>> {
  return get<PaginatedResponse<AuditEvent>>(BASE, { params });
}
