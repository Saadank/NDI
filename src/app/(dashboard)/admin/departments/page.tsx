"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createGroup,
  deleteGroup,
} from "@/lib/api/platform/groups.api";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";

export default function DepartmentsAdminPage() {
  const { isReady } = useRoleGuard({
    allow: ["org_admin", "platform_admin"],
  });
  const groupsQuery = useGroups();
  const qc = useQueryClient();

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      createGroup({
        name: name.trim(),
        name_ar: nameAr.trim() || undefined,
        description: description.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform", "groups"] });
      setOpen(false);
      setName("");
      setNameAr("");
      setDescription("");
      setError(null);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteGroup(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["platform", "groups"] }),
  });

  if (!isReady) return null;

  const groups = groupsQuery.data ?? [];

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Departments</h1>
          <span
            className="rounded px-2 py-0.5 text-xs font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            Org Admin
          </span>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          New Department
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{
              backgroundColor: "#FAFAFA",
              borderBottom: "1px solid #EEEEEE",
            }}
          >
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              NAME
            </span>
            <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              SLUG
            </span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              MEMBERS
            </span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              STATUS
            </span>
            <span className="w-[80px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}></span>
          </div>

          {groupsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              Loading…
            </div>
          ) : groups.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              No departments yet — create your first one.
            </div>
          ) : (
            groups.map((g, i) => (
              <div
                key={g.id}
                className="flex h-14 items-center px-5"
                style={{
                  borderBottom:
                    i < groups.length - 1 ? "1px solid #F5F5F5" : undefined,
                }}
              >
                <div className="flex flex-1 flex-col">
                  <span className="text-[13px] font-semibold text-auth-text">
                    {g.name}
                  </span>
                  {g.description && (
                    <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      {g.description}
                    </span>
                  )}
                </div>
                <span className="w-[140px] text-xs" style={{ color: "#9E9E9E" }}>
                  {g.slug}
                </span>
                <span className="w-[120px] text-xs" style={{ color: "#9E9E9E" }}>
                  {g.member_count ?? 0}
                </span>
                <span className="w-[120px] text-xs font-medium"
                  style={{ color: g.is_active ? "#449235" : "#9E9E9E" }}
                >
                  {g.is_active ? "Active" : "Inactive"}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`Delete "${g.name}"?`)) remove.mutate(g.id);
                  }}
                  className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-[#FFF0F0]"
                  style={{ color: "#B91C1C" }}
                  aria-label="Delete department"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ backgroundColor: "#00000066" }}
        >
          <div
            className="flex w-[480px] flex-col gap-4 rounded-2xl bg-white p-6"
            style={{ boxShadow: "0 24px 64px #00000026" }}
          >
            <h2 className="text-base font-bold text-auth-text">
              New Department
            </h2>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium" style={{ color: "#616161" }}>
                Name *
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
                placeholder="e.g. Marketing"
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium" style={{ color: "#616161" }}>
                Arabic name
              </label>
              <input
                value={nameAr}
                onChange={(e) => setNameAr(e.target.value)}
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
                placeholder="التسويق"
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium" style={{ color: "#616161" }}>
                Description
              </label>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
              />
            </div>
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="mt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
                style={{ borderColor: "#EEEEEE", color: "#616161" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => create.mutate()}
                disabled={!name.trim() || create.isPending}
                className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white"
                style={{
                  backgroundColor:
                    !name.trim() || create.isPending ? "#D0D0D0" : "#D76736",
                }}
              >
                {create.isPending ? "Creating…" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
