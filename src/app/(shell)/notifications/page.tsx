"use client";

import { useState } from "react";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import { NotificationsEmpty } from "@/components/features/notifications/NotificationsEmpty";
import { NotificationRow } from "@/components/features/notifications/NotificationRow";
import {
  useMarkNotificationRead,
  useNotifications,
} from "@/lib/hooks/platform/useNotifications";
import { formatRelativeTime } from "@/lib/utils/formatters";

export default function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const notifQuery = useNotifications({ unread_only: unreadOnly });
  const markRead = useMarkNotificationRead();

  const items = notifQuery.data ?? [];

  const handleMarkAllRead = async () => {
    const unread = items.filter((n) => !n.is_read);
    await Promise.all(unread.map((n) => markRead.mutateAsync(n.id)));
  };

  return (
    <main className="flex-1 flex flex-col gap-5 px-12 py-8">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Notifications" },
        ]}
      />

      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-auth-text">Notifications</h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setUnreadOnly((v) => !v)}
            className="text-[13px] font-medium text-auth-text-muted hover:text-auth-text"
          >
            {unreadOnly ? "Show all" : "Unread only"}
          </button>
          <button
            type="button"
            disabled={
              markRead.isPending || items.every((n) => n.is_read)
            }
            onClick={handleMarkAllRead}
            className="text-[13px] font-normal text-brand hover:underline disabled:cursor-not-allowed disabled:opacity-50"
          >
            Mark all read
          </button>
        </div>
      </div>

      <div className="flex-1 rounded-lg border border-auth-border bg-white overflow-hidden">
        {notifQuery.isLoading ? (
          <div className="flex items-center justify-center py-24 text-sm text-auth-text-subtle">
            Loading notifications…
          </div>
        ) : notifQuery.isError ? (
          <div className="flex items-center justify-center py-24 text-sm text-red-600">
            Failed to load notifications.
          </div>
        ) : items.length === 0 ? (
          <NotificationsEmpty />
        ) : (
          items.map((n, i) => (
            <button
              key={n.id}
              type="button"
              onClick={() => !n.is_read && markRead.mutate(n.id)}
              className="block w-full text-left"
            >
              <NotificationRow
                last={i === items.length - 1}
                item={{
                  id: n.id,
                  title: n.title,
                  subtitle: n.body ?? n.type,
                  time: formatRelativeTime(n.created_at),
                  unread: !n.is_read,
                }}
              />
            </button>
          ))
        )}
      </div>
    </main>
  );
}
