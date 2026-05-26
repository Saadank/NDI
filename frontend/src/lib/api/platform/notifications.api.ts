import { get, post } from "@/lib/api/client";

// Mirrors the t_notifications row returned by the backend's
// `notification_service.list_notifications` (plain list, not paginated).
export interface Notification {
  id: string;
  user_id: number;
  tenant_id: number;
  type: string;
  title: string;
  body: string | null;
  request_id: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

const BASE = "/api/v1/products/data-sharing/notifications";

export function getNotifications(params?: {
  unread_only?: boolean;
}): Promise<Notification[]> {
  return get<Notification[]>(`${BASE}/`, { params });
}

export function markNotificationRead(
  id: string,
): Promise<Notification | { success: boolean }> {
  return post<Notification | { success: boolean }>(`${BASE}/${id}/read`);
}
