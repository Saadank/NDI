"use client";

import {
  Eye,
  Lock,
  Plus,
  Search,
  TriangleAlert,
  UserMinus,
  UserPlus,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addGroupMember,
  getGroupMembers,
  removeGroupMember,
} from "@/lib/api/platform/groups.api";
import {
  clearMyDelegation,
  getMyDelegationHistory,
  setMyDelegation,
} from "@/lib/api/platform/delegation.api";
import { getUsers } from "@/lib/api/platform/users.api";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";
import { formatDate, formatRelativeTime } from "@/lib/utils/formatters";
import type { Group } from "@/lib/types/platform/group.types";

type Pane = "members" | "delegation";

export default function MyDepartmentPage() {
  const { isReady } = useRoleGuard({
    allow: ["data_owner", "platform_admin"],
  });
  const myProductRole = useAuthStore((s) => s.user?.product_role ?? null);
  const myGroupId = useAuthStore((s) => s.user?.group_id ?? null);
  const groupsQuery = useGroups();

  const myGroup: Group | null = useMemo(() => {
    if (!myGroupId || !groupsQuery.data) return null;
    return groupsQuery.data.find((g) => g.id === myGroupId) ?? null;
  }, [groupsQuery.data, myGroupId]);

  const membersQuery = useQuery({
    queryKey: ["platform", "groups", myGroupId, "members"],
    queryFn: () => getGroupMembers(myGroupId as number),
    enabled: isReady && myGroupId !== null,
  });

  const delegationHistoryQuery = useQuery({
    queryKey: ["platform", "delegation-history"],
    queryFn: () => getMyDelegationHistory(),
    enabled: isReady,
  });

  const activeDelegation = (delegationHistoryQuery.data ?? []).find(
    (d) => new Date(d.delegation_end) > new Date(),
  );

  const [pane, setPane] = useState<Pane>("members");
  const [showAddModal, setShowAddModal] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<{
    id: number;
    name: string;
  } | null>(null);

  if (!isReady) return null;
  if (!myGroupId) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-sm text-auth-text-subtle">
          You aren&rsquo;t assigned to a department yet.
        </p>
      </main>
    );
  }

  const members = membersQuery.data ?? [];
  const stewardsCount = members.length;
  const activeDelegates = members.filter((m) => m.is_acting_data_owner);

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #EEEEEE",
        }}
      >
        <h1 className="text-lg font-bold text-auth-text">My Department</h1>
        {myProductRole && (
          <span
            className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: "#D76736" }}
            />
            {myProductRole === "data_owner" ? "Data Owner" : myProductRole}
            {myGroup ? ` · ${myGroup.name}` : ""}
          </span>
        )}
      </div>

      {/* Delegation active banner — Pencil frame 10 uses a blue info banner */}
      {activeDelegates.length > 0 && (
        <div
          className="mx-8 mt-4 flex items-center justify-between rounded-md px-4 py-2.5"
          style={{ backgroundColor: "#EFF6FF", border: "1px solid #BFDBFE" }}
        >
          <p className="text-[13px]" style={{ color: "#1D4ED8" }}>
            <strong>Delegation active</strong>
            {activeDelegation?.delegation_end
              ? ` until ${new Date(activeDelegation.delegation_end).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`
              : ""}
            {" — "}
            {activeDelegates
              .map((m) => `${m.first_name ?? ""} ${m.last_name ?? ""}`.trim() || m.email)
              .join(", ")}{" "}
            {activeDelegates.length === 1 ? "is" : "are"} acting as Data Owner
          </p>
          <button
            type="button"
            onClick={() => setPane("delegation")}
            className="text-[12px] font-medium hover:underline"
            style={{ color: "#3B82F6" }}
          >
            View details →
          </button>
        </div>
      )}

      <div className="flex flex-1 flex-col gap-3 overflow-auto px-8 py-6">
        {/* Pane switcher */}
        <div className="flex items-center gap-2">
          {(
            [
              { id: "members", label: "Stewards" },
              { id: "delegation", label: "Role Delegation" },
            ] as { id: Pane; label: string }[]
          ).map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPane(p.id)}
              className="flex h-8 items-center rounded-full px-4 text-xs"
              style={
                pane === p.id
                  ? {
                      backgroundColor: "#FFF5F0",
                      color: "#D76736",
                      border: "1px solid #FCD8C5",
                      fontWeight: 600,
                    }
                  : {
                      backgroundColor: "#FFFFFF",
                      color: "#9E9E9E",
                      border: "1px solid #EEEEEE",
                      fontWeight: 500,
                    }
              }
            >
              {p.label}
            </button>
          ))}
        </div>

        {pane === "members" ? (
          <MembersPane
            group={myGroup}
            members={members}
            isLoading={membersQuery.isLoading}
            stewardsCount={stewardsCount}
            onOpenAdd={() => setShowAddModal(true)}
            onRequestRemove={(m) =>
              setConfirmRemove({
                id: m.id,
                name: `${m.first_name ?? ""} ${m.last_name ?? ""}`.trim() || m.email,
              })
            }
          />
        ) : (
          <DelegationPane groupId={myGroupId} groupName={myGroup?.name ?? ""} productRole={myProductRole ?? ""} />
        )}
      </div>

      {showAddModal && (
        <AddStewardModal
          groupId={myGroupId}
          groupName={myGroup?.name ?? ""}
          existingMemberIds={new Set(members.map((m) => m.id))}
          onClose={() => setShowAddModal(false)}
        />
      )}

      {confirmRemove && (
        <RemoveStewardModal
          groupId={myGroupId}
          userId={confirmRemove.id}
          name={confirmRemove.name}
          onClose={() => setConfirmRemove(null)}
        />
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Members pane (DO-10)
// ───────────────────────────────────────────────────────────────

function MembersPane(props: {
  group: Group | null;
  members: import("@/lib/api/platform/groups.api").GroupMember[];
  isLoading: boolean;
  stewardsCount: number;
  onOpenAdd: () => void;
  onRequestRemove: (m: { id: number; first_name: string | null; last_name: string | null; email: string }) => void;
}) {
  const { group, members, isLoading, stewardsCount, onOpenAdd, onRequestRemove } = props;
  const activeDelegationCount = members.filter((m) => m.is_acting_data_owner).length;
  return (
    <>
      <section
        className="flex flex-col rounded-lg overflow-hidden"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        {/* Section header */}
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: "1px solid #EEEEEE" }}
        >
          <div className="flex flex-col gap-1">
            <h2 className="flex items-center gap-1.5 text-[14px] font-semibold text-auth-text">
              <Lock className="h-3.5 w-3.5" style={{ color: "#9E9E9E" }} />
              {group?.name ?? "Department"}
            </h2>
            <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
              Data Owner: {group?.data_owner_name ?? "—"}
              {" · "}
              <strong>{stewardsCount}</strong> Stewards
              {activeDelegationCount > 0 ? (
                <>
                  {" · "}
                  <span style={{ color: "#1D4ED8" }}>
                    {activeDelegationCount} Active Delegation
                    {activeDelegationCount === 1 ? "" : "s"}
                  </span>
                </>
              ) : null}
            </p>
          </div>
          <button
            type="button"
            onClick={onOpenAdd}
            className="flex h-9 items-center gap-1.5 rounded-md px-4 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            <Plus className="h-3.5 w-3.5" />
            Add Steward
          </button>
        </div>

        {/* Table */}
        <div
          className="flex h-10 items-center px-5"
          style={{
            backgroundColor: "#FAFAFA",
            borderBottom: "1px solid #EEEEEE",
          }}
        >
          <span
            className="flex-1 text-[11px] font-semibold tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            Steward
          </span>
          <span
            className="w-[120px] text-[11px] font-semibold tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            Joined
          </span>
          <span
            className="w-[140px] text-[11px] font-semibold tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            Requests / 30d
          </span>
          <span
            className="w-[120px] text-[11px] font-semibold tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            Last Active
          </span>
          <span
            className="w-[80px] text-[11px] font-semibold tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            Actions
          </span>
        </div>

        {isLoading ? (
          <div className="py-12 text-center text-sm text-auth-text-subtle">
            Loading…
          </div>
        ) : members.length === 0 ? (
          <div className="py-12 text-center text-sm text-auth-text-subtle">
            No stewards yet — add the first one above.
          </div>
        ) : (
          members.map((m, i, arr) => {
            const fullName =
              `${m.first_name ?? ""} ${m.last_name ?? ""}`.trim() || m.email;
            return (
              <div
                key={m.id}
                className="flex h-14 items-center px-5"
                style={{
                  borderBottom:
                    i < arr.length - 1 ? "1px solid #F5F5F5" : undefined,
                }}
              >
                <div className="flex flex-1 items-center gap-2">
                  <span className="text-[13px] font-medium text-auth-text">
                    {fullName}
                  </span>
                  {m.is_acting_data_owner && (
                    <span
                      className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                      style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
                    >
                      Acting DO
                    </span>
                  )}
                </div>
                <span className="w-[120px] text-xs" style={{ color: "#9E9E9E" }}>
                  {m.joined_at ? formatDate(m.joined_at) : "—"}
                </span>
                <span className="w-[140px] text-xs" style={{ color: "#515157" }}>
                  {m.request_count_30d !== undefined
                    ? `${m.request_count_30d} requests`
                    : "—"}
                </span>
                <span className="w-[120px] text-xs" style={{ color: "#9E9E9E" }}>
                  {m.last_active_at
                    ? formatRelativeTime(m.last_active_at)
                    : "—"}
                </span>
                <div className="flex w-[80px] items-center gap-1">
                  <button
                    type="button"
                    title="View profile"
                    className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#F5F5F5]"
                    style={{ color: "#9E9E9E" }}
                  >
                    <Eye className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      onRequestRemove({
                        id: m.id,
                        first_name: m.first_name,
                        last_name: m.last_name,
                        email: m.email,
                      })
                    }
                    title="Remove steward"
                    className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#FFF0F0]"
                    style={{ color: "#D76736" }}
                  >
                    <UserMinus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </section>
    </>
  );
}

// ───────────────────────────────────────────────────────────────
// Add Steward modal (DO-11)
// ───────────────────────────────────────────────────────────────

function AddStewardModal({
  groupId,
  groupName,
  existingMemberIds,
  onClose,
}: {
  groupId: number;
  groupName: string;
  existingMemberIds: Set<number>;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch all users in the tenant — backend filters by tenant_id. We then
  // exclude users already in the group client-side.
  const usersQuery = useQuery({
    queryKey: ["platform", "users"],
    queryFn: () => getUsers({ page: 1, limit: 200 }),
    staleTime: 30_000,
  });

  const candidates = (usersQuery.data?.data ?? [])
    .filter((u) => {
      const idNum = (u as unknown as { id: number | string }).id;
      const numeric =
        typeof idNum === "string" ? Number(idNum) : (idNum as number);
      if (Number.isNaN(numeric)) return false;
      if (existingMemberIds.has(numeric)) return false;
      const text = `${u.first_name ?? ""} ${u.last_name ?? ""} ${u.email}`.toLowerCase();
      return query ? text.includes(query.toLowerCase()) : true;
    })
    .map((u) => {
      const idNum = (u as unknown as { id: number | string }).id;
      return {
        id: typeof idNum === "string" ? Number(idNum) : (idNum as number),
        first_name: u.first_name ?? "",
        last_name: u.last_name ?? "",
        email: u.email,
      };
    });

  const add = useMutation({
    mutationFn: (userId: number) => addGroupMember(groupId, userId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["platform", "groups", groupId, "members"],
      });
      onClose();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "#00000066" }}
    >
      <div
        className="flex w-[520px] flex-col gap-4 rounded-2xl bg-white p-6"
        style={{ boxShadow: "0 24px 64px #00000026" }}
      >
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-base font-bold text-auth-text">
            <UserPlus className="h-4 w-4" style={{ color: "#D76736" }} />
            Add Steward
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-auth-text-subtle hover:text-auth-text"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div
          className="flex items-start gap-2 rounded-md p-3 text-[11px]"
          style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
        >
          <span>
            Only {groupName || "department"} members can be added. External users
            must be onboarded first.
          </span>
        </div>

        <div
          className="flex h-9 items-center gap-2 rounded-md px-3"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <Search
            className="h-3.5 w-3.5 shrink-0"
            style={{ color: "#9E9E9E" }}
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Search ${groupName || "tenant"} members…`}
            className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
          />
        </div>

        <div
          className="flex max-h-[260px] flex-col overflow-auto rounded-md"
          style={{ border: "1px solid #EEEEEE" }}
        >
          {usersQuery.isLoading && (
            <div className="py-6 text-center text-xs text-auth-text-subtle">
              Loading…
            </div>
          )}
          {!usersQuery.isLoading && candidates.length === 0 && (
            <div className="py-6 text-center text-xs text-auth-text-subtle">
              No matching users.
            </div>
          )}
          {candidates.map((u) => {
            const selected = picked === u.id;
            return (
              <button
                key={u.id}
                type="button"
                onClick={() => setPicked(u.id)}
                className="flex h-12 items-center gap-3 px-3 text-left"
                style={{
                  backgroundColor: selected ? "#FFF5F0" : "#FFFFFF",
                  borderBottom: "1px solid #F5F5F5",
                }}
              >
                <span
                  className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full"
                  style={
                    selected
                      ? { backgroundColor: "#D76736" }
                      : { border: "2px solid #BABABA", backgroundColor: "#FFFFFF" }
                  }
                >
                  {selected && (
                    <span className="h-[6px] w-[6px] rounded-full bg-white" />
                  )}
                </span>
                <div className="flex flex-1 flex-col">
                  <span
                    className="text-[13px]"
                    style={{
                      color: selected ? "#D76736" : "#1A1A1A",
                      fontWeight: selected ? 600 : 500,
                    }}
                  >
                    {`${u.first_name} ${u.last_name}`.trim() || u.email}
                  </span>
                  <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                    {u.email}
                  </span>
                </div>
              </button>
            );
          })}
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
            onClick={() => picked !== null && add.mutate(picked)}
            disabled={picked === null || add.isPending}
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            style={{ backgroundColor: "#D76736" }}
          >
            {add.isPending ? "Adding…" : "Add as Steward"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Remove Steward modal (DO-12 confirm flow)
// ───────────────────────────────────────────────────────────────

function RemoveStewardModal({
  groupId,
  userId,
  name,
  onClose,
}: {
  groupId: number;
  userId: number;
  name: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: () => removeGroupMember(groupId, userId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["platform", "groups", groupId, "members"],
      });
      onClose();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "#00000066" }}
    >
      <div
        className="flex w-[480px] flex-col gap-4 rounded-2xl bg-white p-6"
        style={{ boxShadow: "0 24px 64px #00000026" }}
      >
        <h2 className="text-base font-bold text-auth-text">
          Remove {name}?
        </h2>
        <div
          className="flex items-start gap-2 rounded-md p-3 text-xs"
          style={{
            backgroundColor: "#FEF2F2",
            border: "1px solid #FCA5A5",
            color: "#991B1B",
          }}
        >
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Removing this steward revokes their access to in-flight requests
            assigned to them. They can be re-added later.
          </span>
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
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#B91C1C" }}
          >
            {remove.isPending ? "Removing…" : "Confirm removal"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Delegation pane (DO-12 main view)
// ───────────────────────────────────────────────────────────────

function DelegationPane({ groupId: _groupId, groupName, productRole }: { groupId: number; groupName: string; productRole: string }) {
  const qc = useQueryClient();
  const usersQuery = useQuery({
    queryKey: ["platform", "users"],
    queryFn: () => getUsers({ page: 1, limit: 200 }),
    staleTime: 30_000,
  });
  const [picked, setPicked] = useState<number | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const activate = useMutation({
    mutationFn: () =>
      setMyDelegation({
        delegate_to_user_id: picked,
        delegation_start: start ? new Date(start).toISOString() : null,
        delegation_end: end ? new Date(end).toISOString() : null,
        reason: null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform", "users", "me"] });
      setPicked(null);
      setStart("");
      setEnd("");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  const cancel = useMutation({
    mutationFn: clearMyDelegation,
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["platform", "users", "me"] }),
  });

  const candidates = (usersQuery.data?.data ?? [])
    .filter((u) => {
      const text = `${u.first_name ?? ""} ${u.last_name ?? ""} ${u.email}`.toLowerCase();
      return query ? text.includes(query.toLowerCase()) : true;
    })
    .map((u) => {
      const idNum = (u as unknown as { id: number | string }).id;
      return {
        id: typeof idNum === "string" ? Number(idNum) : (idNum as number),
        first_name: u.first_name ?? "",
        last_name: u.last_name ?? "",
        email: u.email,
      };
    });

  // Per Pencil frame 12, the Role Delegation card opens with a green
  // success-style header that confirms the role + dept context, then the
  // form lives below it on a white card. We render the header and form as
  // separate panels stacked in the same column.
  const formattedRole = productRole
    ? productRole.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : "";
  return (
    <section className="flex flex-col gap-3">
      <div
        className="flex items-start gap-2 rounded-lg p-4"
        style={{ backgroundColor: "#ECFDF5", border: "1px solid #A7F3D0" }}
      >
        <span
          className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white"
          style={{ backgroundColor: "#10B981" }}
        >
          ✓
        </span>
        <div className="flex flex-col gap-1">
          <p className="text-[13px] font-semibold" style={{ color: "#065F46" }}>
            Role Delegation
            {(formattedRole || groupName) && (
              <span style={{ fontWeight: 500 }}>
                {" "}— {formattedRole ? `${formattedRole} · ` : ""}
                {groupName} Department
              </span>
            )}
          </p>
          <p className="text-[12px]" style={{ color: "#047857" }}>
            Configure a backup to act in your absence. All decisions during
            the active window are logged with both your name and your
            backup&rsquo;s name in the audit trail.
          </p>
        </div>
      </div>
    <section
      className="flex flex-col rounded-lg overflow-hidden"
      style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
    >
      <div className="flex flex-col gap-4 p-5">
        <div className="flex flex-col gap-2">
          <label className="text-[12px] font-semibold text-auth-text">Select Backup</label>
          <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
            Only Data Owners with Finance Dept access are shown.
          </p>
          <div
            className="flex h-9 items-center gap-2 rounded-md px-3"
            style={{ border: "1px solid #EEEEEE" }}
          >
            <Search
              className="h-3.5 w-3.5 shrink-0"
              style={{ color: "#9E9E9E" }}
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for a Data Owner with department access…"
              className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
            />
          </div>
          <div
            className="flex max-h-[180px] flex-col overflow-auto rounded-md"
            style={{ border: "1px solid #EEEEEE" }}
          >
            {usersQuery.isLoading && (
              <div className="py-4 text-center text-xs text-auth-text-subtle">
                Loading…
              </div>
            )}
            {!usersQuery.isLoading && candidates.length === 0 && (
              <div className="py-4 text-center text-xs text-auth-text-subtle">
                No matching users.
              </div>
            )}
            {candidates.map((u) => {
              const selected = picked === u.id;
              return (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => setPicked(u.id)}
                  className="flex h-11 items-center gap-3 px-3 text-left"
                  style={{
                    backgroundColor: selected ? "#FFF5F0" : "#FFFFFF",
                    borderBottom: "1px solid #F5F5F5",
                  }}
                >
                  <span
                    className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full"
                    style={
                      selected
                        ? { backgroundColor: "#D76736" }
                        : {
                            border: "2px solid #BABABA",
                            backgroundColor: "#FFFFFF",
                          }
                    }
                  >
                    {selected && (
                      <span className="h-[6px] w-[6px] rounded-full bg-white" />
                    )}
                  </span>
                  <div className="flex flex-1 flex-col">
                    <span
                      className="text-[13px]"
                      style={{
                        color: selected ? "#D76736" : "#1A1A1A",
                        fontWeight: selected ? 600 : 500,
                      }}
                    >
                      {`${u.first_name} ${u.last_name}`.trim() || u.email}
                    </span>
                    <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      {u.email}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <label className="text-[12px] font-semibold text-auth-text">Delegation Window</label>
        <div className="flex gap-3">
          <div className="flex flex-1 flex-col gap-1.5">
            <label className="text-xs font-medium" style={{ color: "#616161" }}>
              From
            </label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>
          <div className="flex flex-1 flex-col gap-1.5">
            <label className="text-xs font-medium" style={{ color: "#616161" }}>
              Until
            </label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>
        </div>
        </div>

        <div
          className="flex items-start gap-2 rounded-md p-3 text-[11px]"
          style={{
            backgroundColor: "#FFFBEB",
            border: "1px solid #FCD34D",
            color: "#92400E",
          }}
        >
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            During the active window, the selected backup receives all approval
            assignments. Every decision is logged with both names — visible to
            stakeholders in the audit trail.
          </span>
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <div className="flex justify-between">
          <button
            type="button"
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending}
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            {cancel.isPending ? "Clearing…" : "Cancel"}
          </button>
          <button
            type="button"
            onClick={() => activate.mutate()}
            disabled={
              picked === null || !start || !end || activate.isPending
            }
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            style={{ backgroundColor: "#D76736" }}
          >
            {activate.isPending ? "Activating…" : "Activate Delegation"}
          </button>
        </div>
      </div>
    </section>
    </section>
  );
}
