"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  Building2,
  CalendarOff,
  ClipboardList,
  Database,
  FileSpreadsheet,
  FileText,
  GitBranch,
  Inbox,
  LayoutGrid,
  ListChecks,
  Plus,
  Timer,
  UploadCloud,
  User as UserIcon,
  UserCog,
  Users as UsersIcon,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Logo } from "@/components/shared/Logo";
import { useAuthStore } from "@/lib/store/auth.store";
import { useNotifications } from "@/lib/hooks/platform/useNotifications";
import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { cn } from "@/lib/utils";

// ───────────────────────────────────────────────────────────────
// Types
// ───────────────────────────────────────────────────────────────

type Matcher = (pathname: string) => boolean;

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  match?: Matcher;
  badgeKey?: "requests" | "approvals";
}

interface NavSection {
  title?: string;
  items: NavItem[];
}

type EffectiveRole =
  | "requester"
  | "data_owner"
  | "dpo"
  | "org_admin"
  | "platform_admin";

// ───────────────────────────────────────────────────────────────
// Nav item definitions
// ───────────────────────────────────────────────────────────────

const ITEM = {
  // DS
  myRequests: {
    label: "My Requests",
    href: "/data-sharing",
    icon: FileSpreadsheet,
    badgeKey: "requests",
    match: (p: string) =>
      p === "/data-sharing" ||
      (p.startsWith("/data-sharing/") && !p.startsWith("/data-sharing/new")),
  } as NavItem,
  raise: { label: "Raise New Request", href: "/data-sharing/new", icon: Plus } as NavItem,
  prepare: { label: "Prepare & Upload", href: "/prepare", icon: UploadCloud } as NavItem,

  // DO
  approvalsInbox: {
    label: "Approvals Inbox",
    href: "/approvals",
    icon: Inbox,
    badgeKey: "approvals",
    match: (p: string) => p === "/approvals" || p.startsWith("/approvals/"),
  } as NavItem,
  myDepartment: { label: "My Department", href: "/my-department", icon: UsersIcon } as NavItem,

  // DPO + Admin shared governance
  orgRequestList: {
    label: "Organisation Request List",
    href: "/dpo",
    icon: ListChecks,
    match: (p: string) => p === "/dpo",
  } as NavItem,
  requestDetailPdpl: {
    label: "Request Detail + PDPL Review",
    href: "/dpo",
    icon: FileText,
    match: (p: string) => p.startsWith("/dpo/") && !p.startsWith("/dpo/workflows") && !p.startsWith("/dpo/recipients") && !p.startsWith("/dpo/audit"),
  } as NavItem,
  workflowEditor: {
    label: "Workflow Editor",
    href: "/dpo/workflows",
    icon: GitBranch,
    match: (p: string) => p === "/dpo/workflows",
  } as NavItem,
  workflowTemplates: {
    label: "Workflow Templates",
    href: "/dpo/templates",
    icon: ClipboardList,
    match: (p: string) => p === "/dpo/templates",
  } as NavItem,
  externalRecipients: {
    label: "External Recipients Directory",
    href: "/dpo/recipients",
    icon: ClipboardList,
  } as NavItem,
  auditTrail: { label: "Audit Trail", href: "/dpo/audit", icon: ListChecks } as NavItem,

  // Org Admin administration
  adminDepartments: { label: "Departments", href: "/admin/departments", icon: Building2 } as NavItem,
  adminUsers: { label: "Users", href: "/admin/users", icon: UsersIcon } as NavItem,
  adminConnections: { label: "Database Connections", href: "/admin/connections", icon: Database } as NavItem,
  adminHolidays: { label: "Business Holidays", href: "/admin/holidays", icon: CalendarOff } as NavItem,
  adminRetention: { label: "Retention Policy", href: "/admin/retention", icon: Timer } as NavItem,

  // Platform Admin
  organisations: { label: "Organisations", href: "/platform/organisations", icon: Building2 } as NavItem,
  onboardCompany: { label: "Onboard Company", href: "/platform/onboard", icon: Plus } as NavItem,

  // Footer (shared)
  productPortal: { label: "All Products", href: "/", icon: LayoutGrid } as NavItem,
  notifications: { label: "Notifications", href: "/notifications", icon: Bell } as NavItem,
  profile: { label: "Profile", href: "/profile", icon: UserIcon } as NavItem,
  delegation: { label: "Delegation", href: "/delegation", icon: UserCog } as NavItem,
};

const PRIMARY_NAV: Record<EffectiveRole, NavSection[]> = {
  requester: [
    { items: [ITEM.myRequests, ITEM.raise, ITEM.prepare] },
  ],
  data_owner: [
    { items: [ITEM.approvalsInbox, ITEM.myDepartment] },
  ],
  dpo: [
    {
      items: [
        ITEM.orgRequestList,
        ITEM.requestDetailPdpl,
        ITEM.workflowEditor,
        ITEM.workflowTemplates,
        ITEM.externalRecipients,
        ITEM.auditTrail,
      ],
    },
  ],
  org_admin: [
    {
      items: [
        ITEM.adminDepartments,
        ITEM.adminUsers,
        ITEM.adminConnections,
        ITEM.adminHolidays,
        ITEM.adminRetention,
      ],
    },
  ],
  platform_admin: [
    { items: [ITEM.organisations, ITEM.onboardCompany] },
  ],
};

const FOOTER_NAV: Record<EffectiveRole, NavItem[]> = {
  requester: [ITEM.productPortal, ITEM.notifications, ITEM.profile],
  data_owner: [ITEM.productPortal, ITEM.notifications, ITEM.profile, ITEM.delegation],
  dpo: [ITEM.productPortal, ITEM.notifications, ITEM.profile, ITEM.delegation],
  org_admin: [ITEM.productPortal, ITEM.notifications, ITEM.profile],
  platform_admin: [ITEM.productPortal, ITEM.notifications, ITEM.profile],
};

// ───────────────────────────────────────────────────────────────
// Role resolution
// ───────────────────────────────────────────────────────────────

function resolveEffectiveRole(
  productRole: string | null,
  platformRole: string | null,
): EffectiveRole {
  if (platformRole === "platform_admin") return "platform_admin";
  if (platformRole === "org_admin") return "org_admin";
  if (productRole === "data_owner") return "data_owner";
  if (productRole === "dpo") return "dpo";
  return "requester";
}

// ───────────────────────────────────────────────────────────────
// Rendering
// ───────────────────────────────────────────────────────────────

function defaultMatch(href: string): Matcher {
  return (p) => p === href || p.startsWith(href + "/");
}

function NavLink({
  item,
  active,
  badge,
}: {
  item: NavItem;
  active: boolean;
  badge?: number;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-9 items-center gap-2.5 rounded-md px-3 text-[13px] transition-colors",
        active
          ? "bg-[#FFF5F0] font-semibold text-brand"
          : "font-medium text-[#515157] hover:bg-[#F4F4F4] hover:text-[#070709]",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate">{item.label}</span>
      {badge !== undefined && badge > 0 && (
        <span
          className="flex h-5 min-w-[20px] items-center justify-center rounded-full px-1.5 text-[11px] font-semibold text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </Link>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-1 mt-3 px-3 text-[10px] font-semibold uppercase tracking-[0.6px] text-[#9E9E9E]">
      {children}
    </p>
  );
}

export function Sidebar() {
  const pathname = usePathname() ?? "";
  const productRole = useAuthStore((s) => s.user?.product_role ?? null);
  const platformRole = useAuthStore((s) => s.user?.platform_role ?? null);

  const role = resolveEffectiveRole(productRole, platformRole);
  const primary = PRIMARY_NAV[role];
  const footer = FOOTER_NAV[role];

  // M-9: count badges — only fetch what's relevant for the role
  const requestsQuery = useRequests({ page: 1, limit: 1 });
  const notifQuery = useNotifications({ unread_only: true });

  const requestCount =
    role === "requester"
      ? (requestsQuery.data?.pagination?.total_pages !== undefined
          ? undefined // total isn't directly available, use pagination
          : undefined)
      : undefined;

  // For simplicity, show notification badge count as proxy for "my requests" count
  // The actual total comes from the pagination object
  const totalRequests =
    role === "requester"
      ? (requestsQuery.data?.pagination
          ? requestsQuery.data.pagination.page *
              (requestsQuery.data.data?.length ?? 0) || undefined
          : undefined)
      : undefined;

  // We get the total from the pagination next_page / total_pages heuristic.
  // The backend doesn't expose a direct count on the list endpoint so we fall
  // back to showing the badge only when data has loaded.
  const myRequestsBadge =
    role === "requester" && requestsQuery.isSuccess
      ? requestsQuery.data?.data?.length ?? 0
      : undefined;

  const approvalsBadge =
    role === "data_owner" && requestsQuery.isSuccess
      ? requestsQuery.data?.data?.length ?? 0
      : undefined;

  void requestCount;
  void totalRequests;

  const isActive = (item: NavItem) => {
    const matcher = item.match ?? defaultMatch(item.href);
    if (item.href === "/") return pathname === "/";
    return matcher(pathname);
  };

  const getBadge = (item: NavItem) => {
    if (item.badgeKey === "requests") return myRequestsBadge;
    if (item.badgeKey === "approvals") return approvalsBadge;
    return undefined;
  };

  void notifQuery;

  return (
    <aside className="sticky top-0 flex h-screen w-[240px] shrink-0 flex-col border-r border-auth-border bg-white px-3 py-5">
      <Link
        href="/"
        aria-label="Datarix home"
        className="mb-4 flex items-center gap-2 px-3"
      >
        <Logo height={22} />
      </Link>

      <nav className="flex flex-col gap-0.5">
        {primary.map((section, sIdx) => (
          <div key={`section-${sIdx}`} className="flex flex-col gap-0.5">
            {section.title && <SectionTitle>{section.title}</SectionTitle>}
            {section.items.map((item, i) => (
              <NavLink
                key={`${item.label}-${i}`}
                item={item}
                active={isActive(item)}
                badge={getBadge(item)}
              />
            ))}
          </div>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-0.5">
        <div className="my-3 h-px bg-auth-border" />
        {footer.map((item, i) => (
          <NavLink
            key={`footer-${item.label}-${i}`}
            item={item}
            active={isActive(item)}
          />
        ))}
      </div>
    </aside>
  );
}
