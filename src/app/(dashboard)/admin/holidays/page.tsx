"use client";

import { AlertCircle, CheckCircle2, ChevronLeft, Plus } from "lucide-react";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createHoliday,
  listHolidays,
  type HolidayRecord,
} from "@/lib/api/platform/holidays.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";

// Local view-model. The backend currently doesn't store is_recurring; the
// Pencil toggle is kept in the UI but the value is not persisted yet.
interface Holiday {
  id: number;
  date: string;
  name: string;
  name_ar?: string | null;
  is_recurring: boolean;
}

function adaptHoliday(row: HolidayRecord): Holiday {
  return {
    id: row.id,
    date: row.holiday_date,
    name: row.name,
    name_ar: row.name_ar,
    is_recurring: false, // backend does not yet store this
  };
}

function formatHolidayDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

type View = "list" | "add";

export default function AdminHolidaysPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin", "platform_admin"] });
  const qc = useQueryClient();
  const [view, setView] = useState<View>("list");

  const holidaysQuery = useQuery({
    queryKey: ["admin", "holidays"],
    queryFn: async () => (await listHolidays()).map(adaptHoliday),
    enabled: isReady,
  });

  if (!isReady) return null;

  const holidays = (holidaysQuery.data ?? []).slice().sort((a, b) => a.date.localeCompare(b.date));

  if (view === "add") {
    return (
      <AddHolidayPage
        onBack={() => setView("list")}
        onSaved={() => {
          void qc.invalidateQueries({ queryKey: ["admin", "holidays"] });
          setView("list");
        }}
      />
    );
  }

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Business Holidays</h1>
          {holidays.length > 0 && (
            <span
              className="rounded px-2 py-0.5 text-xs font-medium"
              style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
            >
              {holidays.length} holidays
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setView("add")}
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-semibold text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          Add holiday
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-auto px-8 py-6">
        <div
          className="flex items-center gap-2 rounded-md px-4 py-2.5"
          style={{ backgroundColor: "#FFF5F0", border: "1px solid #FFCDB8" }}
        >
          <AlertCircle className="h-3.5 w-3.5 shrink-0" style={{ color: "#D76736" }} />
          <p className="text-xs" style={{ color: "#D76736" }}>
            Weekends (Fri–Sat) are automatically excluded from business day calculations.
          </p>
        </div>

        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="w-[130px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>DATE</span>
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>HOLIDAY NAME (EN)</span>
            <span className="w-[200px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>HOLIDAY NAME (AR)</span>
            <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>RECURS ANNUALLY</span>
          </div>

          {holidaysQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : holidays.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-20">
              <p className="text-sm font-medium text-auth-text">No holidays configured</p>
              <p className="text-xs" style={{ color: "#9E9E9E" }}>Holidays are excluded from SLA calculations.</p>
            </div>
          ) : (
            <>
              {holidays.map((h, i) => (
                <div
                  key={h.id}
                  className="flex h-12 items-center px-5"
                  style={{ borderBottom: i < holidays.length - 1 ? "1px solid #F5F5F5" : undefined }}
                >
                  <span className="w-[130px] text-[13px] font-medium text-auth-text">
                    {formatHolidayDate(h.date)}
                  </span>
                  <span className="flex-1 text-[13px]" style={{ color: "#515157" }}>{h.name}</span>
                  <span className="w-[200px] text-[13px]" style={{ color: "#9E9E9E", direction: "rtl" }}>
                    {h.name_ar ?? "—"}
                  </span>
                  <span className="w-[140px]">
                    {h.is_recurring ? (
                      <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "#449235" }}>
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Annual
                      </span>
                    ) : (
                      <span className="text-xs" style={{ color: "#9E9E9E" }}>One-time</span>
                    )}
                  </span>
                </div>
              ))}
              <div
                className="flex h-10 items-center justify-between px-5"
                style={{ borderTop: "1px solid #F5F5F5" }}
              >
                <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                  Showing {holidays.length} of {holidays.length} holidays
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

// ─── Add Holiday full page ─────────────────────────────────────────

function AddHolidayPage({
  onBack,
  onSaved,
}: {
  onBack: () => void;
  onSaved: () => void;
}) {
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [isRecurring, setIsRecurring] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: () =>
      createHoliday({
        holiday_date: date,
        name: name.trim(),
        name_ar: nameAr.trim() || undefined,
      }),
    onSuccess: onSaved,
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <h1 className="text-lg font-bold text-auth-text">Add Holiday</h1>
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-[13px] font-medium"
          style={{ color: "#616161" }}
        >
          <ChevronLeft className="h-4 w-4" />
          Back to list
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6" style={{ maxWidth: 600 }}>
        <div
          className="flex flex-col gap-5 rounded-lg p-6"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <h2 className="text-[14px] font-semibold text-auth-text">Holiday details</h2>

          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Date <span style={{ color: "#D76736" }}>*</span>
            </label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="h-10 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Holiday Name (English) <span style={{ color: "#D76736" }}>*</span>
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. National Day"
              className="h-10 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">Holiday Name (Arabic)</label>
            <input
              value={nameAr}
              onChange={(e) => setNameAr(e.target.value)}
              dir="rtl"
              placeholder="مثال: اليوم الوطني"
              className="h-10 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-0.5">
              <span className="text-[13px] font-medium text-auth-text">Recurs annually</span>
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                This holiday recurs on the same date each year.
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIsRecurring((v) => !v)}
              className="relative h-6 w-11 rounded-full transition-colors"
              style={{ backgroundColor: isRecurring ? "#D76736" : "#BABABA" }}
              aria-checked={isRecurring}
              role="switch"
            >
              <span
                className="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform"
                style={{ left: isRecurring ? "calc(100% - 22px)" : "2px" }}
              />
            </button>
          </div>

          {error && (
            <p className="text-xs" style={{ color: "#D32F2F" }}>{error}</p>
          )}
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onBack}
            className="flex h-9 items-center rounded-md border px-5 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => add.mutate()}
            disabled={!date || !name.trim() || add.isPending}
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
            style={{ backgroundColor: "#D76736" }}
          >
            {add.isPending ? "Saving…" : "Save holiday"}
          </button>
        </div>
      </div>
    </div>
  );
}
