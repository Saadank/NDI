import { get, put } from "@/lib/api/client";

const BASE = "/api/v1/platform/tenants";

export interface TenantRecord {
  id: number;
  name: string;
  slug: string;
  tenant_type: string;
  retention_days: number | null;
  storage_limit_gb: number | null;
  seat_limit: number | null;
}

export function getTenant(tenantId: number): Promise<TenantRecord> {
  return get<TenantRecord>(`${BASE}/${tenantId}`);
}

// Backend route: PUT /api/v1/platform/tenants/{tenant_id}/retention-policy
// Body: { retention_days: 30 | 60 | 90 | 180 }
export function setRetentionPolicy(
  tenantId: number,
  retentionDays: number,
): Promise<TenantRecord> {
  return put<TenantRecord, { retention_days: number }>(
    `${BASE}/${tenantId}/retention-policy`,
    { retention_days: retentionDays },
  );
}
