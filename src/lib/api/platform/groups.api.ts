import { get } from "@/lib/api/client";
import type { Group } from "@/lib/types/platform/group.types";

const BASE = "/api/v1/platform/groups";

// GET /api/v1/platform/groups/  → list of groups in the caller's tenant.
export function getGroups(): Promise<Group[]> {
  return get<Group[]>(`${BASE}/`);
}
