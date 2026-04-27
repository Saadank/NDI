import { del, get, post, put } from "@/lib/api/client";
import type { Group } from "@/lib/types/platform/group.types";

const BASE = "/api/v1/platform/groups";

// GET /api/v1/platform/groups/  → list of groups in the caller's tenant.
export function getGroups(): Promise<Group[]> {
  return get<Group[]>(`${BASE}/`);
}

export interface CreateGroupBody {
  name: string;
  name_ar?: string;
  description?: string;
}

export interface UpdateGroupBody {
  name: string;
  name_ar?: string;
  description?: string;
  is_active?: boolean;
}

export function createGroup(body: CreateGroupBody): Promise<Group> {
  return post<Group, CreateGroupBody>(`${BASE}/`, body);
}

export function updateGroup(id: number, body: UpdateGroupBody): Promise<Group> {
  return put<Group, UpdateGroupBody>(`${BASE}/${id}`, body);
}

export function deleteGroup(id: number): Promise<{ detail: string }> {
  return del<{ detail: string }>(`${BASE}/${id}`);
}

// ── Group members ────────────────────────────────────────────────
// Member rows reuse the platform User shape — first/last name + email +
// optional title. The backend's `find_members` joins t_users so each row
// includes whatever the users table has plus group-specific fields.
export interface GroupMember {
  id: number;
  email: string;
  first_name: string | null;
  last_name: string | null;
  title?: string | null;
  is_active?: boolean;
  joined_at?: string | null;
  request_count_30d?: number;
  last_active_at?: string | null;
  is_acting_data_owner?: boolean;
}

export function getGroupMembers(groupId: number): Promise<GroupMember[]> {
  return get<GroupMember[]>(`${BASE}/${groupId}/members`);
}

export function addGroupMember(
  groupId: number,
  userId: number,
): Promise<GroupMember> {
  return post<GroupMember, { user_id: number }>(
    `${BASE}/${groupId}/members`,
    { user_id: userId },
  );
}

export function removeGroupMember(
  groupId: number,
  userId: number,
): Promise<{ detail: string }> {
  return del<{ detail: string }>(`${BASE}/${groupId}/members/${userId}`);
}

export function setGroupDataOwner(
  groupId: number,
  userId: number,
): Promise<Group> {
  return put<Group, { user_id: number }>(
    `${BASE}/${groupId}/data-owner`,
    { user_id: userId },
  );
}
