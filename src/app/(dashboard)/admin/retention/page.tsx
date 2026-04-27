"use client";

import { Timer } from "lucide-react";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { get, put } from "@/lib/api/client";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { RoleBadge } from "@/components/shared/RoleBadge";

interface RetentionPolicy {
  id?: string;
  default_days: number;
  max_days: number;
  auto_delete_enabled: boolean;
  reminder_days_before: number;
}

const BASE = "/api/v1/products/data-sharing/admin/retention-policy";

export default function AdminRetentionPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin"] });
  const qc = useQueryClient();
  const [saved, setSaved] = useState(false);

  const policyQuery = useQuery({
    queryKey: ["admin", "retention-policy"],
    queryFn: () => get<RetentionPolicy>(BASE),
    enabled: isReady,
  });

  const [form, setForm] = useState<RetentionPolicy>({
    default_days: 90,
    max_days: 365,
    auto_delete_enabled: false,
    reminder_days_before: 7,
  });

  // Sync fetched data to form on first load
  const loaded = policyQuery.data;
  if (loaded && form.default_days === 90 && form.max_days === 365) {
    setForm(loaded);
  }

  const saveMutation = useMutation({
    mutationFn: () => put<RetentionPolicy>(BASE, form),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin", "retention-policy"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  if (!isReady) return null;

  const retentionOptions = [30, 60, 90, 180, 365];

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Retention Policy</h1>
          <RoleBadge label="Org Admin" />
        </div>
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="h-9 rounded-md px-4 text-[13px] font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: "#D76736" }}
        >
          {saved ? "Saved!" : "Save Changes"}
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
        <div
          className="flex flex-col gap-6 rounded-lg p-6"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE", maxWidth: 600 }}
        >
          <div className="flex flex-col gap-2">
            <label className="text-[13px] font-semibold text-auth-text">Default Retention Period</label>
            <p className="text-xs" style={{ color: "#9E9E9E" }}>
              Files will be deleted after this many days if the requester does not specify otherwise.
            </p>
            <div className="flex gap-3 flex-wrap">
              {retentionOptions.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, default_days: d }))}
                  className="flex items-center gap-2"
                >
                  <span
                    className="flex h-4 w-4 items-center justify-center rounded-full border-2 transition-colors"
                    style={{ borderColor: form.default_days === d ? "#D76736" : "#CCCCCC" }}
                  >
                    {form.default_days === d && (
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "#D76736" }} />
                    )}
                  </span>
                  <span className="text-[13px]" style={{ color: form.default_days === d ? "#070709" : "#515157", fontWeight: form.default_days === d ? "600" : "400" }}>
                    {d} days
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[13px] font-semibold text-auth-text">Maximum Allowed Period (days)</label>
            <p className="text-xs" style={{ color: "#9E9E9E" }}>
              Requesters cannot request retention beyond this limit.
            </p>
            <input
              type="number"
              min={1}
              value={form.max_days}
              onChange={(e) => setForm((f) => ({ ...f, max_days: Number(e.target.value) }))}
              className="h-9 w-32 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[13px] font-semibold text-auth-text">Reminder Before Expiry (days)</label>
            <p className="text-xs" style={{ color: "#9E9E9E" }}>
              Send a notification this many days before data is auto-deleted.
            </p>
            <input
              type="number"
              min={1}
              value={form.reminder_days_before}
              onChange={(e) => setForm((f) => ({ ...f, reminder_days_before: Number(e.target.value) }))}
              className="h-9 w-32 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="flex items-center gap-3 cursor-pointer">
              <span
                role="checkbox"
                aria-checked={form.auto_delete_enabled}
                onClick={() => setForm((f) => ({ ...f, auto_delete_enabled: !f.auto_delete_enabled }))}
                className="relative flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer"
                style={{ backgroundColor: form.auto_delete_enabled ? "#D76736" : "#DDDDDD" }}
              >
                <span
                  className="absolute h-3.5 w-3.5 rounded-full bg-white shadow transition-transform"
                  style={{ transform: form.auto_delete_enabled ? "translateX(18px)" : "translateX(2px)" }}
                />
              </span>
              <span className="text-[13px] font-semibold text-auth-text">Auto-delete expired data</span>
            </label>
            <p className="text-xs ml-12" style={{ color: "#9E9E9E" }}>
              When enabled, files are permanently deleted after the retention period. This action is irreversible.
            </p>
          </div>
        </div>

        <div
          className="flex items-start gap-3 rounded-lg px-4 py-3"
          style={{ backgroundColor: "#FFFBF0", border: "1px solid #FDE68A", maxWidth: 600 }}
        >
          <Timer className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#D97706" }} />
          <p className="text-[13px]" style={{ color: "#92400E" }}>
            Changes to the retention policy apply to new requests only. Existing data retains the policy
            that was in effect at the time of upload.
          </p>
        </div>
      </div>
    </div>
  );
}
