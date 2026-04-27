"use client";

import { CalendarOff, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { get, post, del } from "@/lib/api/client";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { RoleBadge } from "@/components/shared/RoleBadge";

interface Holiday {
  id: string;
  date: string;
  name: string;
  is_recurring: boolean;
}

const BASE = "/api/v1/products/data-sharing/admin/holidays";

export default function AdminHolidaysPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin"] });
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [newDate, setNewDate] = useState("");
  const [newName, setNewName] = useState("");
  const [isRecurring, setIsRecurring] = useState(false);

  const holidaysQuery = useQuery({
    queryKey: ["admin", "holidays"],
    queryFn: () => get<Holiday[]>(BASE),
    enabled: isReady,
  });

  const addMutation = useMutation({
    mutationFn: () => post<Holiday>(BASE, { date: newDate, name: newName, is_recurring: isRecurring }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin", "holidays"] });
      setNewDate("");
      setNewName("");
      setIsRecurring(false);
      setShowAdd(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => del(`${BASE}/${id}`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin", "holidays"] }),
  });

  if (!isReady) return null;

  const holidays = (holidaysQuery.data ?? []).slice().sort((a, b) => a.date.localeCompare(b.date));

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Business Holidays</h1>
          <RoleBadge label="Org Admin" />
        </div>
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          Add Holiday
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {showAdd && (
          <div
            className="flex flex-col gap-3 rounded-lg p-5"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <h2 className="text-[13px] font-semibold text-auth-text">Add Holiday</h2>
            <div className="flex items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>Date</label>
                <input
                  type="date"
                  value={newDate}
                  onChange={(e) => setNewDate(e.target.value)}
                  className="h-9 rounded-md border px-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. National Day"
                  className="h-9 w-full rounded-md border px-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>
              <label className="flex items-center gap-2 text-[13px]" style={{ color: "#515157" }}>
                <input type="checkbox" checked={isRecurring} onChange={(e) => setIsRecurring(e.target.checked)} />
                Recurring annually
              </label>
              <div className="flex gap-2">
                <button type="button" onClick={() => setShowAdd(false)}
                  className="h-9 rounded-md border px-4 text-[13px]"
                  style={{ borderColor: "#EEEEEE", color: "#515157" }}>
                  Cancel
                </button>
                <button type="button" onClick={() => addMutation.mutate()}
                  disabled={!newDate || !newName || addMutation.isPending}
                  className="h-9 rounded-md px-4 text-[13px] font-medium text-white disabled:opacity-50"
                  style={{ backgroundColor: "#D76736" }}>
                  Save
                </button>
              </div>
            </div>
          </div>
        )}

        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>DATE</span>
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>NAME</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>RECURRING</span>
            <span className="w-[60px]" />
          </div>

          {holidaysQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : holidays.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-20">
              <CalendarOff className="h-10 w-10" style={{ color: "#EEEEEE" }} />
              <p className="text-sm font-medium text-auth-text">No holidays configured</p>
              <p className="text-xs" style={{ color: "#9E9E9E" }}>Holidays are excluded from SLA calculations.</p>
            </div>
          ) : (
            holidays.map((h, i) => (
              <div
                key={h.id}
                className="flex h-12 items-center px-5"
                style={{ borderBottom: i < holidays.length - 1 ? "1px solid #F5F5F5" : undefined }}
              >
                <span className="w-[140px] text-[13px] font-medium text-auth-text">{h.date}</span>
                <span className="flex-1 text-[13px]" style={{ color: "#515157" }}>{h.name}</span>
                <span className="w-[120px] text-xs" style={{ color: h.is_recurring ? "#D76736" : "#9E9E9E" }}>
                  {h.is_recurring ? "Yes" : "No"}
                </span>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(h.id)}
                  className="flex w-[60px] justify-center rounded p-1.5 transition-colors hover:bg-red-50"
                  style={{ color: "#CCCCCC" }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
