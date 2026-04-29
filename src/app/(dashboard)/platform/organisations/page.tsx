"use client";

import Link from "next/link";
import { AlertTriangle, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { get } from "@/lib/api/client";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate } from "@/lib/utils/formatters";

interface Organisation {
  id: string;
  name: string;
  name_ar?: string | null;
  slug: string;
  tenant_type?: string | null;
  plan?: string | null;
  is_active: boolean;
  status?: string | null;
  user_count?: number | null;
  user_limit?: number | null;
  storage_used_gb?: number | null;
  storage_limit_gb?: number | null;
  products?: string[];
  created_at: string;
}

const BASE = "/api/v1/platform/tenants";

const PRODUCT_LABELS: Record<string, string> = {
  "data_sharing": "DS",
  "data_quality": "DQ",
  "ndi": "NDI",
  "dsr": "DSR",
  "ds": "DS",
  "do": "DO",
};

const TYPE_LABELS: Record<string, string> = {
  government: "Government",
  semi_gov: "Semi-Gov",
  private: "Private",
};

function OrgTypeBadge({ type }: { type: string | null | undefined }) {
  if (!type) return <span className="text-xs" style={{ color: "#BABABA" }}>—</span>;
  const label = TYPE_LABELS[type] ?? type;
  const color = type === "government" ? "#3B4FD6" : type === "semi_gov" ? "#7C3AED" : "#515157";
  const bg = type === "government" ? "#EEF2FF" : type === "semi_gov" ? "#F5F0FF" : "#F5F5F5";
  return (
    <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: bg, color }}>
      {label}
    </span>
  );
}

function StatusBadge({ status, isActive }: { status: string | null | undefined; isActive: boolean }) {
  const s = status ?? (isActive ? "active" : "inactive");
  const map: Record<string, { bg: string; color: string; label: string }> = {
    active:    { bg: "#F0FAF0", color: "#449235", label: "Active" },
    pending:   { bg: "#FFF7E6", color: "#B45309", label: "Pending" },
    suspended: { bg: "#FEF2F2", color: "#D32F2F", label: "Suspended" },
    inactive:  { bg: "#F5F5F5", color: "#9E9E9E", label: "Inactive" },
  };
  const style = map[s] ?? map.inactive;
  return (
    <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: style.bg, color: style.color }}>
      {style.label}
    </span>
  );
}

export default function PlatformOrganisationsPage() {
  const { isReady } = useRoleGuard({ allow: ["platform_admin"] });
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const orgsQuery = useQuery({
    queryKey: ["platform", "organisations"],
    queryFn: () => get<Organisation[]>(BASE),
    enabled: isReady,
  });

  if (!isReady) return null;

  const orgs = orgsQuery.data ?? [];
  const filtered = orgs.filter((o) => {
    if (search && !`${o.name} ${o.slug}`.toLowerCase().includes(search.toLowerCase())) return false;
    if (typeFilter && o.tenant_type !== typeFilter) return false;
    if (statusFilter) {
      const s = o.status ?? (o.is_active ? "active" : "inactive");
      if (s !== statusFilter) return false;
    }
    return true;
  });

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Vendor warning banner */}
      <div
        className="flex items-center gap-2 px-8 py-2"
        style={{ backgroundColor: "#FFFBEB", borderBottom: "1px solid #FCD34D" }}
      >
        <AlertTriangle className="h-3.5 w-3.5 shrink-0" style={{ color: "#B45309" }} />
        <p className="text-[11px]" style={{ color: "#92400E" }}>
          Vendor view — metadata only. No access to organisation request content or uploaded files.
        </p>
      </div>

      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Organisations</h1>
          {orgs.length > 0 && (
            <span className="rounded px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: "#F5F5F5", color: "#515157" }}>
              {orgs.length} orgs
            </span>
          )}
        </div>
        <Link
          href="/platform/onboard"
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-semibold text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          Create organisation
        </Link>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* Toolbar */}
        <div className="flex items-center gap-2">
          <div
            className="flex h-9 w-72 items-center gap-2 rounded-md px-3"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search organisations…"
              className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
            />
          </div>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="h-9 rounded-md border px-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE", color: typeFilter ? "#1A1A1A" : "#9E9E9E" }}
          >
            <option value="">All types</option>
            <option value="government">Government</option>
            <option value="semi_gov">Semi-Gov</option>
            <option value="private">Private</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border px-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE", color: statusFilter ? "#1A1A1A" : "#9E9E9E" }}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="pending">Pending</option>
            <option value="suspended">Suspended</option>
          </select>
          <select
            className="h-9 rounded-md border px-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE", color: "#9E9E9E" }}
          >
            <option value="">Products</option>
          </select>
        </div>

        {/* Table */}
        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ORG NAME</span>
            <span className="w-[110px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>TYPE</span>
            <span className="w-[100px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STATUS</span>
            <span className="w-[180px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>PRODUCTS</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STORAGE</span>
            <span className="w-[100px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>SEATS</span>
            <span className="w-[100px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>CREATED</span>
            <span className="w-[56px]" />
          </div>

          {orgsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : orgsQuery.isError ? (
            <div className="py-20 text-center text-sm text-red-600">Failed to load organisations.</div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">No organisations found.</div>
          ) : (
            <>
              {filtered.map((org, i) => (
                <div
                  key={org.id}
                  className="flex h-[60px] items-center px-5"
                  style={{ borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined }}
                >
                  <div className="flex flex-1 flex-col gap-0.5">
                    <span className="text-[13px] font-semibold text-auth-text">{org.name}</span>
                    {org.name_ar && (
                      <span className="text-[11px]" style={{ color: "#9E9E9E", direction: "rtl", textAlign: "left" }}>
                        {org.name_ar}
                      </span>
                    )}
                  </div>
                  <div className="w-[110px]">
                    <OrgTypeBadge type={org.tenant_type} />
                  </div>
                  <div className="w-[100px]">
                    <StatusBadge status={org.status} isActive={org.is_active} />
                  </div>
                  <div className="flex w-[180px] flex-wrap gap-1">
                    {(org.products ?? []).map((p) => (
                      <span
                        key={p}
                        className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                        style={{ backgroundColor: "#D7673620", color: "#D76736" }}
                      >
                        {PRODUCT_LABELS[p] ?? p.toUpperCase()}
                      </span>
                    ))}
                    {(!org.products || org.products.length === 0) && (
                      <span className="text-[10px]" style={{ color: "#BABABA" }}>—</span>
                    )}
                  </div>
                  <span className="w-[120px] text-xs" style={{ color: "#9E9E9E" }}>
                    {org.storage_used_gb != null && org.storage_limit_gb != null
                      ? `${org.storage_used_gb} / ${org.storage_limit_gb} GB`
                      : "—"}
                  </span>
                  <span className="w-[100px] text-xs" style={{ color: "#9E9E9E" }}>
                    {org.user_count != null && org.user_limit != null
                      ? `${org.user_count} / ${org.user_limit}`
                      : org.user_count ?? "—"}
                  </span>
                  <span className="w-[100px] text-xs" style={{ color: "#9E9E9E" }}>
                    {formatDate(org.created_at)}
                  </span>
                  <div className="flex w-[56px] items-center gap-0.5">
                    <button
                      type="button"
                      title="Edit"
                      className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#F5F5F5]"
                      style={{ color: "#9E9E9E" }}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      title="Delete"
                      className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#FFF0F0]"
                      style={{ color: "#B91C1C" }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
              <div
                className="flex h-10 items-center justify-between px-5"
                style={{ borderTop: "1px solid #F5F5F5" }}
              >
                <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                  Showing {filtered.length} of {orgs.length} organisations
                </span>
                <span className="text-[11px]" style={{ color: "#9E9E9E" }}>← Page 1 of 1 →</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
