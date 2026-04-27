"use client";

import { Building2, Plus, Search } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { get } from "@/lib/api/client";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { RoleBadge } from "@/components/shared/RoleBadge";

interface Organisation {
  id: string;
  name: string;
  slug: string;
  plan: string | null;
  is_active: boolean;
  user_count: number | null;
  created_at: string;
}

const BASE = "/api/v1/platform/tenants";

export default function PlatformOrganisationsPage() {
  const { isReady } = useRoleGuard({ allow: ["platform_admin"] });
  const [search, setSearch] = useState("");

  const orgsQuery = useQuery({
    queryKey: ["platform", "organisations"],
    queryFn: () => get<Organisation[]>(BASE),
    enabled: isReady,
  });

  if (!isReady) return null;

  const orgs = orgsQuery.data ?? [];
  const filtered = search
    ? orgs.filter((o) => o.name.toLowerCase().includes(search.toLowerCase()) || o.slug.toLowerCase().includes(search.toLowerCase()))
    : orgs;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Organisations</h1>
          <RoleBadge label="Platform Admin" />
        </div>
        <a
          href="/platform/onboard"
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          Onboard Company
        </a>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
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

        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ORGANISATION</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>SLUG</span>
            <span className="w-[100px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>PLAN</span>
            <span className="w-[80px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>USERS</span>
            <span className="w-[80px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STATUS</span>
          </div>

          {orgsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : orgsQuery.isError ? (
            <div className="py-20 text-center text-sm text-red-600">Failed to load organisations.</div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-20">
              <Building2 className="h-10 w-10" style={{ color: "#EEEEEE" }} />
              <p className="text-sm font-medium text-auth-text">No organisations found</p>
            </div>
          ) : (
            filtered.map((org, i) => (
              <div
                key={org.id}
                className="flex h-14 items-center px-5 hover:bg-[#FFFBF9]"
                style={{ borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined }}
              >
                <div className="flex flex-1 items-center gap-3">
                  <div
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[13px] font-bold text-white"
                    style={{ backgroundColor: "#D76736" }}
                  >
                    {org.name[0]?.toUpperCase() ?? "?"}
                  </div>
                  <span className="text-[13px] font-medium text-auth-text">{org.name}</span>
                </div>
                <span className="w-[120px] text-xs" style={{ color: "#9E9E9E" }}>{org.slug}</span>
                <span className="w-[100px] text-xs" style={{ color: "#515157" }}>{org.plan ?? "—"}</span>
                <span className="w-[80px] text-xs" style={{ color: "#515157" }}>{org.user_count ?? "—"}</span>
                <span
                  className="w-[80px] text-xs font-medium"
                  style={{ color: org.is_active ? "#449235" : "#9E9E9E" }}
                >
                  {org.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
