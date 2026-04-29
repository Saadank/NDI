"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Calendar, ChevronLeft, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, post } from "@/lib/api/client";
import { getUsers } from "@/lib/api/platform/users.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";

interface UserDetail {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  ds_role?: string | null;
  group_name?: string | null;
  is_active: boolean;
}

export default function SetDelegationOnBehalfPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin", "platform_admin"] });
  const params = useParams<{ userId: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const userId = params.userId;

  const [backupSearch, setBackupSearch] = useState("");
  const [backupId, setBackupId] = useState<string | null>(null);
  const [backupLabel, setBackupLabel] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const userQuery = useQuery({
    queryKey: ["platform", "users", userId],
    queryFn: () => get<UserDetail>(`/api/v1/platform/users/${userId}`),
    enabled: isReady && !!userId,
  });

  const allUsersQuery = useQuery({
    queryKey: ["platform", "users"],
    queryFn: () => getUsers({ page: 1, limit: 100 }),
    enabled: isReady,
    staleTime: 60_000,
  });

  const activateMutation = useMutation({
    mutationFn: () =>
      post(`/api/v1/platform/users/${userId}/delegation`, {
        delegate_to_user_id: backupId ? Number(backupId) : null,
        delegation_start: start ? new Date(start).toISOString() : null,
        delegation_end: end ? new Date(end).toISOString() : null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["platform", "users"] });
      router.push("/admin/users");
    },
  });

  if (!isReady) return null;

  const user = userQuery.data;
  const allUsers = allUsersQuery.data?.data ?? [];
  const filteredUsers = backupSearch
    ? allUsers.filter(
        (u) =>
          u.id !== userId &&
          `${u.first_name ?? ""} ${u.last_name ?? ""} ${u.email}`
            .toLowerCase()
            .includes(backupSearch.toLowerCase()),
      )
    : allUsers.filter((u) => u.id !== userId);

  const absentInitials = user
    ? `${(user.first_name?.[0] ?? "").toUpperCase()}${(user.last_name?.[0] ?? "").toUpperCase()}`
    : "??";

  const absentName = user
    ? `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || user.email
    : "Loading…";

  const canActivate = !!backupId && !!start;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Set Delegation</h1>
          <span className="rounded px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: "#F5F5F5", color: "#515157" }}>
            On behalf of
          </span>
        </div>
        <Link
          href="/admin/users"
          className="flex items-center gap-1.5 text-[13px] font-medium"
          style={{ color: "#616161" }}
        >
          <ChevronLeft className="h-4 w-4" />
          Back to Users
        </Link>
      </div>

      <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6" style={{ maxWidth: 720 }}>
        {/* Absent user banner */}
        {user && (
          <div
            className="flex items-center justify-between rounded-lg px-4 py-3"
            style={{ backgroundColor: "#FFF5F0", border: "1px solid #FDDCCC" }}
          >
            <p className="text-[13px]" style={{ color: "#D76736" }}>
              Setting delegation on behalf of{" "}
              <span className="font-semibold">{absentName}</span>
            </p>
            <span className="rounded px-2 py-0.5 text-[11px] font-semibold" style={{ backgroundColor: "#FFF5F0", border: "1px solid #FDDCCC", color: "#D76736" }}>
              Currently absent
            </span>
          </div>
        )}

        {/* Absent user card */}
        {user && (
          <div
            className="flex flex-col gap-3 rounded-lg p-5"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <span className="text-[11px] font-semibold uppercase tracking-[0.5px]" style={{ color: "#9E9E9E" }}>
              Absent User
            </span>
            <div className="flex items-center gap-3">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[13px] font-bold"
                style={{ backgroundColor: "#D7673626", color: "#D76736" }}
              >
                {absentInitials}
              </div>
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-[14px] font-semibold text-auth-text">{absentName}</span>
                  {user.ds_role && (
                    <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}>
                      {user.ds_role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                  )}
                  {user.group_name && (
                    <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: "#F5F5F5", color: "#616161" }}>
                      {user.group_name}
                    </span>
                  )}
                </div>
                <span className="text-[12px]" style={{ color: "#9E9E9E" }}>{user.email}</span>
              </div>
            </div>
          </div>
        )}

        {/* Backup delegate */}
        <div
          className="flex flex-col gap-4 rounded-lg p-5"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Backup delegate <span style={{ color: "#D76736" }}>*</span>
            </label>

            {backupId ? (
              <div
                className="flex h-10 items-center justify-between rounded-md border px-3"
                style={{ borderColor: "#D76736", backgroundColor: "#FFF5F0" }}
              >
                <span className="text-[13px] font-medium" style={{ color: "#D76736" }}>{backupLabel}</span>
                <button type="button" onClick={() => { setBackupId(null); setBackupLabel(""); setBackupSearch(""); }}>
                  <X className="h-4 w-4" style={{ color: "#D76736" }} />
                </button>
              </div>
            ) : (
              <div className="relative">
                <input
                  value={backupSearch}
                  onChange={(e) => setBackupSearch(e.target.value)}
                  placeholder="Search by name or email…"
                  className="h-10 w-full rounded-md border px-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
                {backupSearch && filteredUsers.length > 0 && (
                  <div
                    className="absolute left-0 top-full z-10 mt-1 w-full overflow-hidden rounded-md shadow-md"
                    style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
                  >
                    {filteredUsers.slice(0, 6).map((u) => (
                      <button
                        key={u.id}
                        type="button"
                        onClick={() => {
                          setBackupId(u.id);
                          const name = `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim() || u.email;
                          setBackupLabel(name);
                          setBackupSearch("");
                        }}
                        className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-[#FAFAFA]"
                      >
                        <div
                          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                          style={{ backgroundColor: "#D7673626", color: "#D76736" }}
                        >
                          {(u.first_name?.[0] ?? "").toUpperCase()}{(u.last_name?.[0] ?? "").toUpperCase()}
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[13px] font-medium text-auth-text">{u.first_name} {u.last_name}</span>
                          <span className="text-[11px]" style={{ color: "#9E9E9E" }}>{u.email}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
              Must have Data Owner role in at least one department
            </p>
          </div>

          {/* Date range */}
          <div className="flex gap-4">
            <div className="flex flex-1 flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-auth-text">
                Delegation starts <span style={{ color: "#D76736" }}>*</span>
              </label>
              <div
                className="flex h-10 items-center gap-2 rounded-md border px-3"
                style={{ borderColor: "#EEEEEE" }}
              >
                <Calendar className="h-4 w-4 shrink-0" style={{ color: "#BABABA" }} />
                <input
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  className="flex-1 bg-transparent text-[13px] outline-none"
                />
              </div>
            </div>
            <div className="flex flex-1 flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-auth-text">
                Delegation ends
              </label>
              <div
                className="flex h-10 items-center gap-2 rounded-md border px-3"
                style={{ borderColor: "#EEEEEE" }}
              >
                <Calendar className="h-4 w-4 shrink-0" style={{ color: "#BABABA" }} />
                <input
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  className="flex-1 bg-transparent text-[13px] outline-none"
                  placeholder="Select end date (optional)"
                />
              </div>
            </div>
          </div>

          {/* Audit log note */}
          <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
            Logged as: set by you (Org Admin) on behalf of {absentName} · {new Date().toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3">
          <Link
            href="/admin/users"
            className="flex h-9 items-center rounded-md border px-5 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            Cancel
          </Link>
          <button
            type="button"
            onClick={() => activateMutation.mutate()}
            disabled={!canActivate || activateMutation.isPending}
            className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: "#D76736" }}
          >
            {activateMutation.isPending ? "Activating…" : "Activate delegation"}
          </button>
        </div>
      </div>
    </div>
  );
}
