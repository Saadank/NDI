import { get, post, put } from "@/lib/api/client";
import type { PaginatedResponse } from "@/lib/types/common.types";
import type { CurrentUser } from "@/lib/types/platform/auth.types";
import type { UserListItem } from "@/lib/types/platform/user.types";

const BASE = "/api/v1/platform/users";

export function getCurrentUser(): Promise<CurrentUser> {
  return get<CurrentUser>(`${BASE}/me`);
}

export function getUsers(params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedResponse<UserListItem>> {
  return get<PaginatedResponse<UserListItem>>(BASE, { params });
}

// Backend route: PUT /api/v1/platform/users/{user_id}/group
// Body: { group_id: number | null }  (pass null to remove from any dept)
export function assignUserGroup(userId: number | string, groupId: number | null) {
  return put(`${BASE}/${userId}/group`, { group_id: groupId });
}

// Backend route: POST /api/v1/platform/users/{user_id}/deactivate
// Optional body: { transfer_to_user_id?: number } — when provided, the
// backend reassigns the user's open responsibilities before deactivating.
export function deactivateUser(
  userId: number | string,
  transferToUserId?: number | null,
) {
  return post(`${BASE}/${userId}/deactivate`, {
    transfer_to_user_id: transferToUserId ?? null,
  });
}
