import { del, get, post } from "@/lib/api/client";

// Mirrors the backend's `DelegationBody` Pydantic model and the response
// shape from `users.set_my_delegation`.
export interface DelegationBody {
  delegate_to_user_id: number | null;
  delegation_start?: string | null;
  delegation_end?: string | null;
  reason?: string | null;
}

export interface UserWithDelegation {
  id: number;
  email: string;
  first_name: string | null;
  last_name: string | null;
  delegation_to_user_id: number | null;
  delegation_start: string | null;
  delegation_end: string | null;
  delegation_reason: string | null;
  [k: string]: unknown;
}

const BASE = "/api/v1/platform/users/me/delegation";

export function setMyDelegation(
  body: DelegationBody,
): Promise<UserWithDelegation> {
  return post<UserWithDelegation, DelegationBody>(BASE, body);
}

export function clearMyDelegation(): Promise<{
  delegation_to_user_id: number | null;
}> {
  return del<{ delegation_to_user_id: number | null }>(BASE);
}

export interface DelegationHistoryItem {
  id: string;
  delegate_to_user_id: number;
  delegate_name: string | null;
  delegation_start: string;
  delegation_end: string;
  summary: string | null;
}

export function getMyDelegationHistory(): Promise<DelegationHistoryItem[]> {
  return get<DelegationHistoryItem[]>(`${BASE}/history`);
}
