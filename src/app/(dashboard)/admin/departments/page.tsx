"use client";

import { AlertTriangle, Info, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createGroup, deleteGroup, updateGroup } from "@/lib/api/platform/groups.api";
import { getUsers as getUsersList } from "@/lib/api/platform/users.api";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate } from "@/lib/utils/formatters";
import type { Group } from "@/lib/types/platform/group.types";

type View = "list" | "edit";

export default function DepartmentsAdminPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin", "platform_admin"] });
  const [view, setView] = useState<View>("list");
  const [editTarget, setEditTarget] = useState<Group | null>(null);
  const [deleteBlocked, setDeleteBlocked] = useState<Group | null>(null);

  if (!isReady) return null;

  if (view === "edit") {
    return (
      <EditDepartmentPage
        group={editTarget}
        onBack={() => {
          setView("list");
          setEditTarget(null);
        }}
      />
    );
  }

  return (
    <>
      <DepartmentListPage
        onEdit={(g) => {
          setEditTarget(g);
          setView("edit");
        }}
        onAdd={() => {
          setEditTarget(null);
          setView("edit");
        }}
        onDeleteBlocked={setDeleteBlocked}
      />
      {deleteBlocked && (
        <DeleteBlockedModal
          group={deleteBlocked}
          onClose={() => setDeleteBlocked(null)}
        />
      )}
    </>
  );
}

// ─── List ─────────────────────────────────────────────────────────

function DepartmentListPage({
  onEdit,
  onAdd,
  onDeleteBlocked,
}: {
  onEdit: (g: Group) => void;
  onAdd: () => void;
  onDeleteBlocked: (g: Group) => void;
}) {
  const groupsQuery = useGroups();
  const qc = useQueryClient();

  const remove = useMutation({
    mutationFn: (id: number) => deleteGroup(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["platform", "groups"] }),
    onError: (_e, _vars, _ctx) => {
      // If backend returns 409 / blocked, show blocked modal
      // We treat any error as "blocked" since group may have members/requests
    },
  });

  const groups = groupsQuery.data ?? [];

  const handleDelete = (g: Group) => {
    if (g.member_count && g.member_count > 0) {
      onDeleteBlocked(g);
      return;
    }
    remove.mutate(g.id);
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Departments</h1>
          {groups.length > 0 && (
            <span
              className="rounded px-2 py-0.5 text-xs font-medium"
              style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
            >
              {groups.length} total
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onAdd}
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-semibold text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          Add department
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          {/* Column headers */}
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              DEPARTMENT
            </span>
            <span className="w-[180px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              DATA OWNER
            </span>
            <span className="w-[100px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              STEWARDS
            </span>
            <span className="w-[130px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              CREATED
            </span>
            <span className="w-[72px]" />
          </div>

          {groupsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : groups.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              No departments yet — create your first one.
            </div>
          ) : (
            <>
              {groups.map((g, i) => (
                <div
                  key={g.id}
                  className="flex h-[60px] items-center px-5"
                  style={{ borderBottom: i < groups.length - 1 ? "1px solid #F5F5F5" : undefined }}
                >
                  <div className="flex flex-1 flex-col gap-0.5">
                    <span className="text-[13px] font-semibold text-auth-text">{g.name}</span>
                    {g.name_ar && (
                      <span className="text-[11px]" style={{ color: "#9E9E9E", direction: "rtl", textAlign: "left" }}>
                        {g.name_ar}
                      </span>
                    )}
                  </div>
                  <span className="w-[180px] text-xs" style={{ color: "#515157" }}>
                    {g.data_owner_name ?? <span style={{ color: "#BABABA" }}>—</span>}
                  </span>
                  <span className="w-[100px] text-xs" style={{ color: "#515157" }}>
                    {g.member_count ?? 0}
                  </span>
                  <span className="w-[130px] text-xs" style={{ color: "#9E9E9E" }}>
                    {formatDate(g.created_at)}
                  </span>
                  <div className="flex w-[72px] items-center gap-1">
                    <button
                      type="button"
                      onClick={() => onEdit(g)}
                      title="Edit"
                      className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#F5F5F5]"
                      style={{ color: "#9E9E9E" }}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(g)}
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
                  Showing {groups.length} of {groups.length} departments
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

// ─── Edit / Add page ──────────────────────────────────────────────

function EditDepartmentPage({
  group,
  onBack,
}: {
  group: Group | null;
  onBack: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(group?.name ?? "");
  const [nameAr, setNameAr] = useState(group?.name_ar ?? "");
  const [description, setDescription] = useState(group?.description ?? "");
  const [dataOwnerId, setDataOwnerId] = useState<number | "">(group?.data_owner_id ?? "");
  const [error, setError] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ["platform", "users", "all"],
    queryFn: () => getUsersList({ page: 1, limit: 200 }),
  });
  const users = usersQuery.data?.data ?? [];

  const create = useMutation({
    mutationFn: () =>
      createGroup({
        name: name.trim(),
        name_ar: nameAr.trim() || undefined,
        description: description.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform", "groups"] });
      onBack();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  const update = useMutation({
    mutationFn: () =>
      updateGroup(group!.id, {
        name: name.trim(),
        name_ar: nameAr.trim() || undefined,
        description: description.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform", "groups"] });
      onBack();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  const isPending = create.isPending || update.isPending;

  const handleSave = () => {
    if (!name.trim()) { setError("Department name is required."); return; }
    if (!nameAr.trim()) { setError("Arabic name is required."); return; }
    setError(null);
    if (group) update.mutate();
    else create.mutate();
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div>
          <h1 className="text-lg font-bold text-auth-text">
            {group ? "Edit department" : "Add department"}
          </h1>
          {group && (
            <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
              {group.name}
              {group.name_ar ? ` · ${group.name_ar}` : ""}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isPending}
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
            style={{ backgroundColor: "#D76736" }}
          >
            {isPending ? "Saving…" : "Save department"}
          </button>
        </div>
      </div>

      {/* Form */}
      <div className="flex flex-1 flex-col overflow-auto px-8 py-6">
        <div
          className="flex flex-col gap-5 rounded-lg p-6"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE", maxWidth: 600 }}
        >
          {group && (
            <div className="flex justify-between text-[11px]" style={{ color: "#9E9E9E" }}>
              <span>Created {formatDate(group.created_at)}</span>
              <span>Last edited {formatDate(group.updated_at)}</span>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Department name (English) <span style={{ color: "#D76736" }}>*</span>
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-10 rounded-md border px-3 text-[13px] outline-none focus:border-[#D76736]"
              style={{ borderColor: "#EEEEEE" }}
              placeholder="e.g. Finance"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label className="text-[12px] font-semibold text-auth-text">
                Department name (Arabic) <span style={{ color: "#D76736" }}>*</span>
              </label>
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>Required · bilingual compliance</span>
            </div>
            <input
              value={nameAr}
              onChange={(e) => setNameAr(e.target.value)}
              dir="rtl"
              className="h-10 rounded-md border px-3 text-[13px] outline-none focus:border-[#D76736]"
              style={{ borderColor: "#EEEEEE" }}
              placeholder="المالية"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Description <span style={{ color: "#9E9E9E" }}>(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="resize-none rounded-md border px-3 py-2.5 text-[13px] outline-none focus:border-[#D76736]"
              style={{ borderColor: "#EEEEEE" }}
              placeholder="Brief description of this department's data handling scope…"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Data Owner <span style={{ color: "#D76736" }}>*</span>
            </label>
            <select
              value={dataOwnerId}
              onChange={(e) => setDataOwnerId(e.target.value ? Number(e.target.value) : "")}
              className="h-10 rounded-md border px-3 text-[13px] outline-none focus:border-[#D76736]"
              style={{ borderColor: "#EEEEEE" }}
            >
              <option value="">Select a Data Owner…</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {`${u.first_name ?? ""} ${u.last_name ?? ""}`.trim() || u.email}
                </option>
              ))}
            </select>
            <button type="button" className="self-start text-[11px]" style={{ color: "#D76736" }}>
              Can&apos;t find the person? Invite by email →
            </button>
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}

          <div className="flex justify-between">
            <button
              type="button"
              onClick={onBack}
              className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
              style={{ borderColor: "#EEEEEE", color: "#616161" }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={isPending}
              className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
              style={{ backgroundColor: "#D76736" }}
            >
              {isPending ? "Saving…" : "Save department"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Delete blocked modal ─────────────────────────────────────────

function DeleteBlockedModal({
  group,
  onClose,
}: {
  group: Group;
  onClose: () => void;
}) {
  const requestsQuery = useQuery({
    queryKey: ["data-sharing", "requests", "dept", group.id],
    queryFn: async () => {
      const { get } = await import("@/lib/api/client");
      return get<{ data: Array<{ id: string; title: string; status: string; request_number: string }> }>(
        `/api/v1/products/data-sharing/requests?group_id=${group.id}&status=submitted,in_review&limit=10`,
      );
    },
  });

  const blockingRequests = requestsQuery.data?.data ?? [];

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
              <AlertTriangle className="h-4.5 w-4.5" style={{ color: "#D76736" }} />
            </div>
            <div className="flex flex-col gap-0.5">
              <h2 className="text-base font-bold text-auth-text">Cannot delete department</h2>
              <p className="text-[12px] leading-relaxed" style={{ color: "#9E9E9E", maxWidth: 380 }}>
                {group.name} has {blockingRequests.length} active request{blockingRequests.length !== 1 ? "s" : ""} in flight.
                This department cannot be deleted until all associated requests are resolved or reassigned to another department.
              </p>
            </div>
          </div>
          <button type="button" onClick={onClose}>
            <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
          </button>
        </div>

        {/* Blocking request list */}
        <div className="flex flex-col overflow-hidden rounded-lg" style={{ border: "1px solid #EEEEEE" }}>
          <div className="flex h-8 items-center px-4" style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}>
            <span className="text-[11px] font-semibold uppercase tracking-[0.5px]" style={{ color: "#9E9E9E" }}>
              Blocking Requests
            </span>
          </div>
          {requestsQuery.isLoading ? (
            <div className="px-4 py-3 text-[12px]" style={{ color: "#9E9E9E" }}>Loading…</div>
          ) : blockingRequests.length === 0 ? (
            <div className="px-4 py-3 text-[12px]" style={{ color: "#9E9E9E" }}>No active requests found.</div>
          ) : (
            blockingRequests.slice(0, 5).map((r, i, arr) => (
              <div
                key={r.id}
                className="flex items-center gap-3 px-4 py-2.5"
                style={{ borderBottom: i < arr.length - 1 ? "1px solid #F5F5F5" : undefined }}
              >
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: "#D76736" }} />
                <span className="text-[12px]" style={{ color: "#515157" }}>
                  <span className="font-medium">{r.request_number}</span>
                  {r.title ? ` · ${r.title}` : ""}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="flex items-start gap-2 rounded-md px-4 py-3" style={{ backgroundColor: "#EFF6FF", border: "1px solid #BFDBFE" }}>
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#2563EB" }} />
          <p className="text-[12px]" style={{ color: "#1D4ED8" }}>
            Reassign or complete these requests before attempting to delete this department.
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            Close
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 items-center rounded-md px-4 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            Reassign requests
          </button>
        </div>
      </div>
    </div>
  );
}
