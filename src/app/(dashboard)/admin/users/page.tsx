"use client";

import { Search, UserPlus } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getUsers } from "@/lib/api/platform/users.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { RoleBadge } from "@/components/shared/RoleBadge";

export default function AdminUsersPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin", "platform_admin"] });
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const usersQuery = useQuery({
    queryKey: ["admin", "users", page],
    queryFn: () => getUsers({ page, limit: 25 }),
    enabled: isReady,
  });

  if (!isReady) return null;

  const users = usersQuery.data?.data ?? [];
  const totalPages = usersQuery.data?.pagination?.total_pages ?? 1;

  const filtered = search
    ? users.filter((u) => {
        const hay = `${u.first_name} ${u.last_name} ${u.email}`.toLowerCase();
        return hay.includes(search.toLowerCase());
      })
    : users;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Users</h1>
          <RoleBadge label="Org Admin" />
        </div>
        <button
          type="button"
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <UserPlus className="h-3.5 w-3.5" />
          Invite User
        </button>
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
            placeholder="Search users…"
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
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>NAME</span>
            <span className="w-[240px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>EMAIL</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ROLE</span>
            <span className="w-[80px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STATUS</span>
          </div>

          {usersQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : usersQuery.isError ? (
            <div className="py-20 text-center text-sm text-red-600">Failed to load users.</div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">No users found.</div>
          ) : (
            filtered.map((u, i) => (
              <div
                key={u.id}
                className="flex h-14 items-center px-5 hover:bg-[#FFFBF9]"
                style={{ borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined }}
              >
                <span className="flex-1 text-[13px] font-medium text-auth-text">
                  {u.first_name} {u.last_name}
                </span>
                <span className="w-[240px] text-xs" style={{ color: "#515157" }}>{u.email}</span>
                <span className="w-[120px] text-xs" style={{ color: "#9E9E9E" }}>
                  {(u.roles?.[0] ?? "—").replace(/_/g, " ")}
                </span>
                <span
                  className="w-[80px] text-xs font-medium"
                  style={{ color: u.is_active ? "#449235" : "#9E9E9E" }}
                >
                  {u.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            ))
          )}
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "#9E9E9E" }}>Page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
                className="h-8 rounded-md border px-3 text-[13px] disabled:opacity-40"
                style={{ borderColor: "#EEEEEE", color: "#515157" }}>
                Previous
              </button>
              <button type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}
                className="h-8 rounded-md border px-3 text-[13px] disabled:opacity-40"
                style={{ borderColor: "#EEEEEE", color: "#515157" }}>
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
