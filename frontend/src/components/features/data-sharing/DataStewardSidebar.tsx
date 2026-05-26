"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Inbox,
  FilePlus,
  Upload,
  LayoutGrid,
  Bell,
  User,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface NavItemProps {
  href: string;
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  badge?: number;
}

function NavItem({ href, icon, label, active, badge }: NavItemProps) {
  return (
    <Link
      href={href}
      className={cn(
        "flex h-9 items-center gap-[10px] rounded-md px-2 text-sm",
        active
          ? "font-semibold"
          : "font-normal",
      )}
      style={
        active
          ? { backgroundColor: "#FFF5F0", color: "#D76736" }
          : { color: "#515157" }
      }
    >
      <span className={cn("shrink-0", active ? "text-brand" : "")}>{icon}</span>
      <span className="flex-1">{label}</span>
      {badge !== undefined && (
        <span
          className="flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[10px] font-bold text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          {badge}
        </span>
      )}
    </Link>
  );
}

export function DataStewardSidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="flex h-full w-60 shrink-0 flex-col"
      style={{ borderRight: "1px solid #EEEEEE", backgroundColor: "#FFFFFF" }}
    >
      {/* Logo */}
      <div
        className="flex h-16 items-center gap-[10px] px-5"
        style={{ borderBottom: "1px solid #EEEEEE" }}
      >
        <Activity className="h-5 w-5 text-brand" />
        <span className="text-[15px] font-bold text-brand">DATARIX</span>
      </div>

      {/* Nav */}
      <div className="flex flex-1 flex-col gap-0.5 p-3">
        <NavItem
          href="/data-sharing"
          icon={<Inbox className="h-4 w-4" />}
          label="My Requests"
          active={pathname === "/data-sharing"}
        />
        <NavItem
          href="/data-sharing/new"
          icon={<FilePlus className="h-4 w-4" />}
          label="Raise New Request"
          active={pathname.startsWith("/data-sharing/new")}
        />
        <NavItem
          href="/data-sharing/upload"
          icon={<Upload className="h-4 w-4" />}
          label="Prepare & Upload"
          active={pathname.startsWith("/data-sharing/upload")}
        />

        {/* Spacer */}
        <div className="flex-1" />

        {/* Divider */}
        <div className="h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />

        <NavItem
          href="/"
          icon={<LayoutGrid className="h-4 w-4" />}
          label="All Products"
          active={false}
        />
        <NavItem
          href="/notifications"
          icon={<Bell className="h-4 w-4" />}
          label="Notifications"
          active={pathname === "/notifications"}
        />
        <NavItem
          href="/profile"
          icon={<User className="h-4 w-4" />}
          label="Profile"
          active={pathname === "/profile"}
        />
      </div>
    </aside>
  );
}
