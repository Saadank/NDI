import { get, post } from "@/lib/api/client";
import type { PaginatedResponse } from "@/lib/types/common.types";

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
}

const BASE = "/api/v1/products/data-sharing/notifications";

export function getNotifications(params?: {
  page?: number;
  limit?: number;
  unread_only?: boolean;
}): Promise<PaginatedResponse<Notification>> {
  return get<PaginatedResponse<Notification>>(BASE, { params });
}

export function markNotificationRead(
  id: string,
): Promise<{ success: boolean }> {
  return post<{ success: boolean }>(`${BASE}/${id}/read`);
}
