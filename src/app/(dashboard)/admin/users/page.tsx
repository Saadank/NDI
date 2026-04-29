"use client";

import { AlertTriangle, Pencil, Search, Send, UserMinus, UserPlus, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { post } from "@/lib/api/client";
import { getUsers } from "@/lib/api/platform/users.api";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatRelativeTime } from "@/lib/utils/formatters";

// ─── Role badge helpers ───────────────────────────────────────────

function OrgRoleBadge({ role }: { role: string }) {
  if (role === "org_admin" || role === "platform_admin") {
    return (
      <span
        className="inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold"
        style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
      >
        Org Admin
      </span>
    );
  }
  return <span className="text-xs" style={{ color: "#9E9E9E" }}>User</span>;
}

function DsRoleBadge({ role }: { role: string | null }) {
  if (!role) return <span className="text-xs" style={{ color: "#BABABA" }}>—</span>;
  if (role === "data_owner") {
    return (
      <span
        className="inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold"
        style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
      >
        Data Owner
      </span>
    );
  }
  if (role === "dpo") {
    return (
      <span
        className="inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold"
        style={{ backgroundColor: "#F5F0FF", color: "#7C3AED" }}
      >
        DPO
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold"
      style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
    >
      {role === "data_steward" ? "Data Steward" : role.replace(/_/g, " ")}
    </span>
  );
}

// ─── Main page ────────────────────────────────────────────────────

type ModalState =
  | { kind: "none" }
  | { kind: "invite" }
  | { kind: "deactivate"; userId: string; name: string };

export default function AdminUsersPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin", "platform_admin"] });
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [deptFilter, setDeptFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [modal, setModal] = useState<ModalState>({ kind: "none" });

  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => getUsers({ page: 1, limit: 100 }),
    enabled: isReady,
  });
  const groupsQuery = useGroups();

  const groupNameById = useMemo(() => {
    const m = new Map<number, string>();
    for (const g of groupsQuery.data ?? []) m.set(g.id, g.name);
    return m;
  }, [groupsQuery.data]);

  if (!isReady) return null;

  const allUsers = usersQuery.data?.data ?? [];

  const filtered = allUsers.filter((u) => {
    if (search) {
      const hay = `${u.first_name} ${u.last_name} ${u.email}`.toLowerCase();
      if (!hay.includes(search.toLowerCase())) return false;
    }
    if (statusFilter === "active" && !u.is_active) return false;
    if (statusFilter === "inactive" && u.is_active) return false;
    return true;
  });

  const totalMembers = allUsers.length;

  return (
    <>
      <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
        <div
          className="flex h-16 shrink-0 items-center justify-between px-8"
          style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
        >
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-auth-text">Users</h1>
            {totalMembers > 0 && (
              <span
                className="rounded px-2 py-0.5 text-xs font-medium"
                style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
              >
                {totalMembers} members
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setModal({ kind: "invite" })}
            className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            <UserPlus className="h-3.5 w-3.5" />
            Invite user
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
          {/* Toolbar */}
          <div className="flex items-center gap-2">
            <div
              className="flex h-9 flex-1 max-w-xs items-center gap-2 rounded-md px-3"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name or email…"
                className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
              />
            </div>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE", color: roleFilter ? "#1A1A1A" : "#9E9E9E" }}
            >
              <option value="">All roles</option>
              <option value="org_admin">Org Admin</option>
              <option value="user">User</option>
            </select>
            <select
              value={deptFilter}
              onChange={(e) => setDeptFilter(e.target.value)}
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE", color: deptFilter ? "#1A1A1A" : "#9E9E9E" }}
            >
              <option value="">All departments</option>
              {(groupsQuery.data ?? []).map((g) => (
                <option key={g.id} value={String(g.id)}>{g.name}</option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE", color: statusFilter ? "#1A1A1A" : "#9E9E9E" }}
            >
              <option value="">Status: All</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>

          <div
            className="flex flex-col overflow-hidden rounded-lg"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            {/* Column headers */}
            <div
              className="flex h-10 shrink-0 items-center px-5"
              style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
            >
              <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>USER</span>
              <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ORG ROLE</span>
              <span className="w-[130px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>DS ROLE</span>
              <span className="w-[150px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>DEPARTMENT</span>
              <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STATUS</span>
              <span className="w-[110px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>LAST ACTIVE</span>
              <span className="w-[72px]" />
            </div>

            {usersQuery.isLoading ? (
              <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
            ) : usersQuery.isError ? (
              <div className="py-20 text-center text-sm text-red-600">Failed to load users.</div>
            ) : filtered.length === 0 ? (
              <div className="py-20 text-center text-sm text-auth-text-subtle">No users found.</div>
            ) : (
              <>
                {filtered.map((u, i) => {
                  const fullName = `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim();
                  const orgRole = u.roles?.[0] ?? "user";
                  const dsRole = (u as unknown as { product_role?: string | null }).product_role ?? null;
                  const groupId = (u as unknown as { group_id?: number | null }).group_id ?? null;
                  const deptName = groupId ? (groupNameById.get(groupId) ?? "—") : "—";
                  const lastActive = (u as unknown as { last_active_at?: string | null }).last_active_at;
                  const isDelegating = (u as unknown as { is_delegating?: boolean }).is_delegating;

                  return (
                    <div
                      key={u.id}
                      className="flex h-[60px] items-center px-5"
                      style={{ borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined }}
                    >
                      <div className="flex flex-1 flex-col gap-0.5">
                        <span className="text-[13px] font-medium text-auth-text">{fullName || "—"}</span>
                        <span className="text-[11px]" style={{ color: "#9E9E9E" }}>{u.email}</span>
                      </div>
                      <span className="w-[120px]">
                        <OrgRoleBadge role={orgRole} />
                      </span>
                      <span className="w-[130px]">
                        <DsRoleBadge role={dsRole} />
                      </span>
                      <span className="w-[150px] text-xs truncate" style={{ color: "#515157" }}>
                        {deptName}
                      </span>
                      <span className="w-[140px]">
                        {u.is_active ? (
                          <span className="flex items-center gap-1.5">
                            <span className="text-xs font-medium" style={{ color: "#449235" }}>Active</span>
                            {isDelegating && (
                              <span className="text-[10px]" style={{ color: "#9E9E9E" }}>· Delegating</span>
                            )}
                          </span>
                        ) : (
                          <span className="text-xs" style={{ color: "#D76736" }}>Invited · Pending</span>
                        )}
                      </span>
                      <span className="w-[110px] text-xs" style={{ color: "#9E9E9E" }}>
                        {lastActive ? formatRelativeTime(lastActive) : u.is_active ? "—" : "—"}
                      </span>
                      <div className="flex w-[72px] items-center gap-1">
                        <button
                          type="button"
                          title="Edit"
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#F5F5F5]"
                          style={{ color: "#9E9E9E" }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        {u.is_active && (
                          <button
                            type="button"
                            onClick={() =>
                              setModal({
                                kind: "deactivate",
                                userId: u.id,
                                name: fullName || u.email,
                              })
                            }
                            title="Deactivate"
                            className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#FFF0F0]"
                            style={{ color: "#9E9E9E" }}
                          >
                            <UserMinus className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div
                  className="flex h-10 items-center justify-between px-5"
                  style={{ borderTop: "1px solid #F5F5F5" }}
                >
                  <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                    Showing {filtered.length} of {totalMembers} users
                  </span>
                  <span className="text-[11px]" style={{ color: "#9E9E9E" }}>← Page 1 of 1 →</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {modal.kind === "invite" && (
        <InviteUserModal
          groups={groupsQuery.data ?? []}
          onClose={() => setModal({ kind: "none" })}
        />
      )}
      {modal.kind === "deactivate" && (
        <DeactivateModal
          userId={modal.userId}
          name={modal.name}
          onClose={() => setModal({ kind: "none" })}
        />
      )}
    </>
  );
}

// ─── Invite modal ─────────────────────────────────────────────────

function InviteUserModal({
  groups,
  onClose,
}: {
  groups: { id: number; name: string }[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [nameEn, setNameEn] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [email, setEmail] = useState("");
  const [orgRole, setOrgRole] = useState<"user" | "org_admin">("user");
  const [dsRole, setDsRole] = useState("data_steward");
  const [groupId, setGroupId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const invite = useMutation({
    mutationFn: () =>
      post("/api/v1/platform/users/invite", {
        email: email.trim(),
        first_name: nameEn.trim().split(" ")[0] ?? "",
        last_name: nameEn.trim().split(" ").slice(1).join(" ") || "",
        name_ar: nameAr.trim() || undefined,
        platform_role: orgRole,
        product_role: dsRole || undefined,
        group_id: groupId ? Number(groupId) : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      onClose();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed to send invite"),
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "#00000066" }}
    >
      <div
        className="flex w-[560px] flex-col gap-5 rounded-2xl bg-white p-6"
        style={{ boxShadow: "0 24px 64px #00000026" }}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-auth-text">Invite user</h2>
          <button type="button" onClick={onClose}>
            <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
          </button>
        </div>

        <div className="flex gap-4">
          <div className="flex flex-1 flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Full name (English) <span style={{ color: "#D76736" }}>*</span>
            </label>
            <input
              value={nameEn}
              onChange={(e) => setNameEn(e.target.value)}
              placeholder="Layla Al-Harbi"
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>
          <div className="flex flex-1 flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Full name (Arabic)
            </label>
            <input
              value={nameAr}
              onChange={(e) => setNameAr(e.target.value)}
              dir="rtl"
              placeholder="ليلى الحربي"
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-semibold text-auth-text">
            Email address <span style={{ color: "#D76736" }}>*</span>
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="layla.newshire@sts.sa"
            className="h-9 rounded-md border px-3 text-[13px] outline-none focus:border-[#D76736]"
            style={{ borderColor: "#EEEEEE" }}
          />
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-[12px] font-semibold text-auth-text">Role assignment</label>
          <div className="flex gap-2">
            {(["org_admin", "user"] as const).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setOrgRole(r)}
                className="flex h-8 items-center rounded-md px-4 text-[13px] font-medium"
                style={
                  orgRole === r
                    ? { backgroundColor: "#D76736", color: "#FFFFFF" }
                    : { backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE", color: "#515157" }
                }
              >
                {r === "org_admin" ? "Org Admin" : "User"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-semibold text-auth-text">Data Sharing role</label>
          <select
            value={dsRole}
            onChange={(e) => setDsRole(e.target.value)}
            className="h-9 rounded-md border px-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          >
            <option value="data_steward">Data Steward</option>
            <option value="data_owner">Data Owner</option>
            <option value="dpo">DPO</option>
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-semibold text-auth-text">
            Department <span style={{ color: "#D76736" }}>*</span>
          </label>
          <select
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            className="h-9 rounded-md border px-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          >
            <option value="">Select a department…</option>
            {groups.map((g) => (
              <option key={g.id} value={String(g.id)}>{g.name}</option>
            ))}
          </select>
          <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
            The Data Owner for this dept can also assign stewards directly.
          </p>
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => invite.mutate()}
            disabled={!email.trim() || !nameEn.trim() || invite.isPending}
            className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
            style={{ backgroundColor: "#D76736" }}
          >
            <Send className="h-3.5 w-3.5" />
            {invite.isPending ? "Sending…" : "Send invite"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Deactivate modal ─────────────────────────────────────────────

function DeactivateModal({
  userId,
  name,
  onClose,
}: {
  userId: string;
  name: string;
  onClose: () => void;
}) {
  const [transferTo, setTransferTo] = useState("");

  const requestsQuery = useQuery({
    queryKey: ["data-sharing", "requests", "user", userId],
    queryFn: async () => {
      const { get } = await import("@/lib/api/client");
      return get<{ data: Array<{ id: string; title: string; status: string; request_number: string }> }>(
        `/api/v1/products/data-sharing/requests?requester_id=${userId}&status=submitted,in_review&limit=10`,
      );
    },
  });

  const activeRequests = requestsQuery.data?.data ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "#00000066" }}
    >
      <div
        className="flex w-[520px] flex-col gap-4 rounded-2xl bg-white p-6"
        style={{ boxShadow: "0 24px 64px #00000026" }}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full" style={{ backgroundColor: "#FFF5F0" }}>
              <AlertTriangle className="h-4 w-4" style={{ color: "#D76736" }} />
            </div>
            <div className="flex flex-col gap-0.5">
              <h2 className="text-base font-bold text-auth-text">Deactivate {name}?</h2>
              <p className="text-[12px]" style={{ color: "#9E9E9E" }}>
                {name} has active responsibilities that must be transferred before deactivation.
              </p>
            </div>
          </div>
          <button type="button" onClick={onClose}>
            <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
          </button>
        </div>

        <div className="flex flex-col overflow-hidden rounded-lg" style={{ border: "1px solid #EEEEEE" }}>
          {requestsQuery.isLoading ? (
            <div className="px-4 py-3 text-[12px]" style={{ color: "#9E9E9E" }}>Loading…</div>
          ) : activeRequests.length === 0 ? (
            <div className="px-4 py-3 text-[12px]" style={{ color: "#9E9E9E" }}>No active requests — safe to deactivate.</div>
          ) : (
            activeRequests.slice(0, 5).map((item, i, arr) => (
              <div
                key={item.id}
                className="flex items-center justify-between px-4 py-2.5"
                style={{ borderBottom: i < arr.length - 1 ? "1px solid #F5F5F5" : undefined }}
              >
                <span className="text-[12px]" style={{ color: "#515157" }}>
                  <span className="font-medium">{item.request_number}</span>
                  {item.title ? ` · ${item.title}` : ""}
                </span>
                <span
                  className="rounded px-2 py-0.5 text-[10px] font-semibold"
                  style={{ backgroundColor: "#FFF7E6", color: "#B45309" }}
                >
                  {item.status.replace(/_/g, " ")}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-semibold text-auth-text">Transfer responsibilities to:</label>
          <div
            className="flex h-9 items-center gap-2 rounded-md px-3"
            style={{ border: "1px solid #EEEEEE" }}
          >
            <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
            <input
              value={transferTo}
              onChange={(e) => setTransferTo(e.target.value)}
              placeholder="Search for a user with Data Owner access…"
              className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
            />
          </div>
          <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
            All pending requests and approvals will be reassigned to the selected user.
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!transferTo.trim()}
            className="flex h-9 items-center rounded-md px-4 text-[13px] font-semibold text-white disabled:opacity-60"
            style={{ backgroundColor: "#D76736" }}
          >
            Transfer &amp; deactivate
          </button>
        </div>
      </div>
    </div>
  );
}
