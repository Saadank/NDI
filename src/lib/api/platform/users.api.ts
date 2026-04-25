import { get } from "@/lib/api/client";
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
