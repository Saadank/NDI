"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell } from "lucide-react";

import { Logo } from "@/components/shared/Logo";
import { useAuthStore } from "@/lib/store/auth.store";
import { useNotifications } from "@/lib/hooks/platform/useNotifications";
import { cn } from "@/lib/utils";

export function Topbar() {
  const pathname = usePathname() ?? "";
  const bellActive = pathname.startsWith("/notifications");
  const avatarActive = pathname.startsWith("/profile");

  const user = useAuthStore((s) => s.user);
  const initials = user
    ? `${user.first_name?.[0] ?? ""}${user.last_name?.[0] ?? ""}`.toUpperCase() ||
      user.email?.[0]?.toUpperCase() ||
      "?"
    : "?";

  // M-4: derive bell dot from real unread count
  const notifQuery = useNotifications({ unread_only: true });
  const hasUnread = (notifQuery.data ?? []).length > 0;

  return (
    <header className="h-16 shrink-0 border-b border-auth-border bg-white px-8 flex items-center justify-between">
      <Link href="/" aria-label="Datarix home" className="flex items-center">
        <Logo height={20} />
      </Link>

      <div className="flex items-center gap-3">
        <Link
          href="/notifications"
          aria-label="Notifications"
          className={cn(
            "relative h-9 w-9 flex items-center justify-center rounded-lg transition-colors",
            bellActive ? "bg-[#FFF5F0]" : "hover:bg-auth-bg",
          )}
        >
          <Bell
            className="h-5 w-5"
            style={{ color: bellActive ? "#D76736" : "#515157" }}
          />
          {hasUnread && !bellActive && (
            <span className="absolute right-[6px] top-[4px] h-2 w-2 rounded-[2px] bg-brand" />
          )}
        </Link>

        <Link
          href="/profile"
          className={cn(
            "h-9 w-9 rounded-full flex items-center justify-center text-[13px] font-semibold text-brand transition-colors",
            avatarActive ? "ring-2 ring-brand/40" : "",
          )}
          style={{ backgroundColor: "rgba(215, 103, 54, 0.15)" }}
          aria-label="User menu"
        >
          {initials}
        </Link>
      </div>
    </header>
  );
}
