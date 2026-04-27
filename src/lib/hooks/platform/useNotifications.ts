"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getNotifications,
  markNotificationRead,
} from "@/lib/api/platform/notifications.api";

export function useNotifications(params?: { unread_only?: boolean }) {
  return useQuery({
    queryKey: ["notifications", params],
    queryFn: () => getNotifications(params),
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => markNotificationRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}
