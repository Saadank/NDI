"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, ChevronDown, LogOut, User as UserIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Logo } from "@/components/shared/Logo";
import { useAuthStore } from "@/lib/store/auth.store";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useNotifications } from "@/lib/hooks/platform/useNotifications";
import { useLogout } from "@/lib/hooks/platform/useAuth";
import { cn } from "@/lib/utils";

// ─── Role label helpers ────────────────────────────────────────────

// We render whichever role is most descriptive: product role > platform role.
// This mirrors what users see in the sidebar's role-specific nav.
function roleLabel(productRole: string | null | undefined, platformRole: string | undefined): string {
  if (platformRole === "platform_admin") return "Platform Admin";
  if (platformRole === "org_admin") return "Org Admin";
  if (productRole === "data_owner") return "Data Owner";
  if (productRole === "dpo") return "DPO";
  if (productRole === "data_steward" || productRole === "requester") return "Data Steward";
  return "Member";
}

export function Topbar() {
  const pathname = usePathname() ?? "";
  const bellActive = pathname.startsWith("/notifications");
  const profileActive = pathname.startsWith("/profile");

  const user = useAuthStore((s) => s.user);
  const groupsQuery = useGroups();
  const groupName = user?.group_id
    ? (groupsQuery.data ?? []).find((g) => g.id === user.group_id)?.name
    : null;

  const fullName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim() ||
    user?.email ||
    "Guest";
  const initials =
    `${user?.first_name?.[0] ?? ""}${user?.last_name?.[0] ?? ""}`.toUpperCase() ||
    user?.email?.[0]?.toUpperCase() ||
    "?";
  const role = roleLabel(user?.product_role, user?.platform_role);

  const notifQuery = useNotifications({ unread_only: true });
  const hasUnread = (notifQuery.data ?? []).length > 0;

  // Click-outside-to-close popover for the avatar dropdown.
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menuOpen) return;
    function handle(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [menuOpen]);

  const logoutMutation = useLogout();
  function handleLogout() {
    setMenuOpen(false);
    logoutMutation.mutate();
  }

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

        {/* Identity widget — name + role + dept (right side) */}
        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className={cn(
              "flex h-10 items-center gap-2.5 rounded-lg px-2 transition-colors",
              menuOpen || profileActive ? "bg-[#FFF5F0]" : "hover:bg-auth-bg",
            )}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label="User menu"
          >
            <div className="flex flex-col items-end leading-tight">
              <span
                className="max-w-[140px] truncate text-[12px] font-semibold"
                style={{ color: "#1A1A1A" }}
              >
                {fullName}
              </span>
              <span
                className="max-w-[140px] truncate text-[10px] font-medium uppercase tracking-[0.4px]"
                style={{ color: "#9E9E9E" }}
              >
                {role}
                {groupName ? ` · ${groupName}` : ""}
              </span>
            </div>
            <div
              className="flex h-9 w-9 items-center justify-center rounded-full text-[13px] font-semibold text-brand"
              style={{ backgroundColor: "rgba(215, 103, 54, 0.15)" }}
            >
              {initials}
            </div>
            <ChevronDown
              className={cn(
                "h-3 w-3 transition-transform",
                menuOpen && "rotate-180",
              )}
              style={{ color: "#9E9E9E" }}
            />
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-12 z-50 flex w-56 flex-col overflow-hidden rounded-lg border border-auth-border bg-white py-1"
              style={{ boxShadow: "0 12px 32px rgba(0,0,0,0.12)" }}
            >
              <div className="border-b border-auth-border px-3 py-2.5">
                <p
                  className="truncate text-[12px] font-semibold"
                  style={{ color: "#1A1A1A" }}
                >
                  {fullName}
                </p>
                <p
                  className="truncate text-[11px]"
                  style={{ color: "#9E9E9E" }}
                >
                  {user?.email ?? ""}
                </p>
              </div>
              <Link
                href="/profile"
                role="menuitem"
                onClick={() => setMenuOpen(false)}
                className="flex h-9 items-center gap-2.5 px-3 text-[13px] text-auth-text hover:bg-auth-bg"
              >
                <UserIcon className="h-3.5 w-3.5" style={{ color: "#9E9E9E" }} />
                Profile
              </Link>
              <button
                type="button"
                role="menuitem"
                onClick={handleLogout}
                disabled={logoutMutation.isPending}
                className="flex h-9 items-center gap-2.5 px-3 text-left text-[13px] text-auth-text hover:bg-auth-bg disabled:opacity-60"
              >
                <LogOut className="h-3.5 w-3.5" style={{ color: "#D76736" }} />
                {logoutMutation.isPending ? "Signing out…" : "Log out"}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
