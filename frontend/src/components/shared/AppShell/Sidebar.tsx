"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  Building2,
  CalendarOff,
  Database,
  FileSpreadsheet,
  FileText,
  GitBranch,
  Inbox,
  LayoutDashboard,
  LayoutGrid,
  ListChecks,
  LogOut,
  Plus,
  ShieldCheck,
  Sparkles,
  Timer,
  UploadCloud,
  User as UserIcon,
  UserCog,
  Users as UsersIcon,
} from "lucide-react";
// DO + DPO sidebars no longer include duplicate "Request Detail + …"
// items — those pages are reached by clicking rows in the list/inbox.
// FileText and ClipboardList icons are no longer needed here.
import type { LucideIcon } from "lucide-react";
import { useAuthStore } from "@/lib/store/auth.store";
import { useNotifications } from "@/lib/hooks/platform/useNotifications";
import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useLogout } from "@/lib/hooks/platform/useAuth";
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
  tooltip?: string;
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
    // Highlights for the inbox AND for any nested approval detail page
    // (/approvals/[id] outgoing OR /approvals/incoming/[id]).
    match: (p: string) => p === "/approvals" || p.startsWith("/approvals/"),
  } as NavItem,
  myDepartment: { label: "My Department", href: "/my-department", icon: UsersIcon } as NavItem,

  // Governance (shared DPO / Org Admin)
  orgRequestList: {
    label: "Organisation Request List",
    href: "/dpo",
    icon: ListChecks,
    // Highlights for the list AND for the request-detail/PDPL Review page
    // (/dpo/[id]) — same pattern as Data Owner inbox.
    match: (p: string) =>
      p === "/dpo" ||
      (p.startsWith("/dpo/") &&
        !p.startsWith("/dpo/workflows") &&
        !p.startsWith("/dpo/recipients") &&
        !p.startsWith("/dpo/audit")),
  } as NavItem,
  workflowEditor: {
    label: "Workflow Editor",
    href: "/dpo/workflows",
    icon: GitBranch,
    match: (p: string) => p.startsWith("/dpo/workflows"),
  } as NavItem,
  externalRecipients: {
    label: "External Recipients Directory",
    href: "/dpo/recipients",
    icon: Building2,
    match: (p: string) => p.startsWith("/dpo/recipients"),
  } as NavItem,
  auditTrail: {
    label: "Audit Trail",
    href: "/dpo/audit",
    icon: ListChecks,
    match: (p: string) => p.startsWith("/dpo/audit"),
  } as NavItem,

  // Org Admin administration
  adminDepartments: { label: "Departments", href: "/admin/departments", icon: Building2 } as NavItem,
  adminUsers: { label: "Users", href: "/admin/users", icon: UsersIcon } as NavItem,
  adminConnections: { label: "Database Connections", href: "/admin/connections", icon: Database } as NavItem,
  adminHolidays: { label: "Business Holidays", href: "/admin/holidays", icon: CalendarOff } as NavItem,
  adminRetention: { label: "Retention Policy", href: "/admin/retention", icon: Timer } as NavItem,

  // Platform Admin
  organisations: { label: "Organisations", href: "/platform/organisations", icon: Building2 } as NavItem,
  onboardCompany: { label: "Onboard Company", href: "/platform/onboard", icon: Plus } as NavItem,

  // NDMO Compliance (product-scoped sidebar; appears for org_admin + platform_admin)
  ndmoDashboard: {
    label: "لوحة NDMO",
    href: "/ndmo-compliance",
    icon: LayoutDashboard,
    match: (p: string) => p === "/ndmo-compliance",
  } as NavItem,
  ndmoDocuments: {
    label: "الوثائق",
    href: "/ndmo-compliance/documents",
    icon: UploadCloud,
    match: (p: string) => p.startsWith("/ndmo-compliance/documents"),
  } as NavItem,
  ndmoSpecs: {
    label: "المواصفات",
    href: "/ndmo-compliance/specs",
    icon: ListChecks,
    match: (p: string) => p.startsWith("/ndmo-compliance/specs"),
  } as NavItem,
  ndmoGapReport: {
    label: "تقرير الفجوة",
    href: "/ndmo-compliance/gap-report",
    icon: FileText,
    match: (p: string) => p.startsWith("/ndmo-compliance/gap-report"),
  } as NavItem,
  ndmoSettings: {
    label: "الإعدادات",
    href: "/ndmo-compliance/settings",
    icon: ShieldCheck,
    match: (p: string) => p.startsWith("/ndmo-compliance/settings"),
  } as NavItem,

  // Footer
  allProducts: { label: "All Products", href: "/", icon: LayoutGrid } as NavItem,
  productPortal: { label: "Product Portal", href: "/", icon: LayoutGrid } as NavItem,
  notifications: { label: "Notifications", href: "/notifications", icon: Bell } as NavItem,
  profile: { label: "Profile", href: "/profile", icon: UserIcon } as NavItem,
  delegation: { label: "Delegation", href: "/delegation", icon: UserCog } as NavItem,
};

// Org Admin still uses the legacy 5-item Governance list; the DPO sidebar
// per the latest Pencil is a trimmed 4-item list (no "Request Detail +
// PDPL Review" duplicate, no "Request Templates", + External Recipients
// Directory promoted in).
const GOVERNANCE_SECTION: NavSection = {
  title: "GOVERNANCE",
  items: [
    ITEM.orgRequestList,
    ITEM.workflowEditor,
    ITEM.auditTrail,
  ],
};

// NDMO Compliance is its OWN product (reached via the Product Portal card),
// not a section of the Data Sharing / Governance / Admin sidebar.  It is
// therefore intentionally absent from the role-based PRIMARY_NAV entries and
// is shown ONLY when the route is /ndmo-compliance/* — at which point it is
// the sole section (see the isNdmoRoute override in the Sidebar component).
const NDMO_SECTION: NavSection = {
  title: "NDMO COMPLIANCE",
  items: [
    ITEM.ndmoDashboard,
    ITEM.ndmoDocuments,
    ITEM.ndmoSpecs,
    ITEM.ndmoGapReport,
    ITEM.ndmoSettings,
  ],
};

const PRIMARY_NAV: Record<EffectiveRole, NavSection[]> = {
  requester: [{ items: [ITEM.myRequests, ITEM.raise, ITEM.prepare] }],
  data_owner: [{ items: [ITEM.approvalsInbox, ITEM.myDepartment] }],
  dpo: [{ items: [ITEM.orgRequestList, ITEM.workflowEditor, ITEM.externalRecipients, ITEM.auditTrail] }],
  org_admin: [
    GOVERNANCE_SECTION,
    {
      title: "ADMINISTRATION",
      items: [ITEM.adminDepartments, ITEM.adminUsers, ITEM.adminConnections, ITEM.adminHolidays, ITEM.adminRetention],
    },
  ],
  platform_admin: [{ items: [ITEM.organisations, ITEM.onboardCompany] }],
};

// When the user is anywhere under /ndmo-compliance, swap to a focused
// NDMO-only sidebar regardless of their role.  This keeps the product
// experience clean (no governance/admin items while doing assessment work).
const NDMO_PRIMARY_NAV: NavSection[] = [NDMO_SECTION];

const FOOTER_NAV: Record<EffectiveRole, NavItem[]> = {
  requester: [ITEM.allProducts, ITEM.notifications, ITEM.profile],
  data_owner: [ITEM.productPortal, ITEM.notifications, ITEM.profile, ITEM.delegation],
  dpo: [ITEM.productPortal, ITEM.notifications, ITEM.profile, ITEM.delegation],
  org_admin: [ITEM.productPortal, ITEM.notifications, ITEM.profile, ITEM.delegation],
  platform_admin: [],
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
// Sub-components
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
  const cls = cn(
    "flex h-9 cursor-pointer items-center gap-2.5 rounded-md px-3 text-[13px] transition-colors",
    active
      ? "bg-[#FFF5F0] font-semibold text-brand"
      : "font-medium text-[#515157] hover:bg-[#F4F4F4] hover:text-[#070709]",
  );
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cls}
      title={item.tooltip}
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
    <p className="mb-1 mt-4 px-3 text-[10px] font-semibold uppercase tracking-[0.6px] text-[#9E9E9E]">
      {children}
    </p>
  );
}

// ───────────────────────────────────────────────────────────────
// Sidebar
// ───────────────────────────────────────────────────────────────

export function Sidebar() {
  const pathname = usePathname() ?? "";
  const user = useAuthStore((s) => s.user);
  const productRole = user?.product_role ?? null;
  const platformRole = user?.platform_role ?? null;

  const role = resolveEffectiveRole(productRole, platformRole);
  // When the user is anywhere under /ndmo-compliance, show the NDMO-only
  // sidebar regardless of their role.  Footer (Product Portal, Profile, …)
  // is still role-based so they can navigate back to other products.
  const isNdmoRoute = pathname.startsWith("/ndmo-compliance");
  const primary = isNdmoRoute ? NDMO_PRIMARY_NAV : PRIMARY_NAV[role];
  const footer = FOOTER_NAV[role];

  const logoutMutation = useLogout();

  const requestsQuery = useRequests({ page: 1, limit: 1 });
  const notifQuery = useNotifications({ unread_only: true });
  void notifQuery;

  const myRequestsBadge =
    role === "requester" && requestsQuery.isSuccess
      ? (requestsQuery.data?.data?.length ?? 0)
      : undefined;

  const approvalsBadge =
    role === "data_owner" && requestsQuery.isSuccess
      ? (requestsQuery.data?.data?.length ?? 0)
      : undefined;

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

  const isPlatformAdmin = role === "platform_admin";
  const vendorName =
    user
      ? `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || user.email
      : "Platform Admin";
  const vendorInitials = user
    ? `${(user.first_name?.[0] ?? "").toUpperCase()}${(user.last_name?.[0] ?? "").toUpperCase()}`
    : "PA";

  return (
    <aside className="sticky top-0 z-20 flex h-screen w-[240px] shrink-0 flex-col border-r border-auth-border bg-white px-3 py-5">
      {/* Header — the global Topbar already shows the brand mark, so the
          sidebar only carries the Platform Admin badge (no duplicate logo). */}
      {isPlatformAdmin && (
        <div className="mb-4 flex items-center gap-2 px-3">
          <div className="flex flex-1 flex-col gap-0.5">
            <span className="text-[11px] font-bold uppercase tracking-[0.8px] text-[#515157]">
              Platform Admin
            </span>
          </div>
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-bold"
            style={{ backgroundColor: "#D76736", color: "#FFFFFF" }}
          >
            ADMIN
          </span>
        </div>
      )}

      {/* Primary nav */}
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

      {/* Footer */}
      <div className="mt-auto flex flex-col gap-0.5">
        <div className="my-3 h-px bg-auth-border" />
        {isPlatformAdmin ? (
          <div className="flex items-center gap-2.5 px-3 py-2">
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
              style={{ backgroundColor: "#D7673626", color: "#D76736" }}
            >
              {vendorInitials}
            </div>
            <span className="truncate text-[13px] font-medium text-[#515157]">{vendorName}</span>
          </div>
        ) : (
          footer.map((item, i) => (
            <NavLink
              key={`footer-${item.label}-${i}`}
              item={item}
              active={isActive(item)}
            />
          ))
        )}
        <button
          type="button"
          onClick={() => logoutMutation.mutate()}
          disabled={logoutMutation.isPending}
          className="flex h-9 w-full cursor-pointer items-center gap-2.5 rounded-md px-3 text-[13px] font-medium text-[#515157] transition-colors hover:bg-[#FFF5F0] hover:text-brand disabled:opacity-60"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          <span>{logoutMutation.isPending ? "Signing out…" : "Log out"}</span>
        </button>
      </div>
    </aside>
  );
}
