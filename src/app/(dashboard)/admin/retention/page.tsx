"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { get, put } from "@/lib/api/client";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { RoleBadge } from "@/components/shared/RoleBadge";

interface RetentionPolicy {
  id?: string;
  default_days: number;
}

const BASE = "/api/v1/products/data-sharing/admin/retention-policy";
const RETENTION_OPTIONS = [30, 60, 90, 180] as const;

export default function AdminRetentionPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin", "platform_admin"] });
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number>(90);
  const [saved, setSaved] = useState(false);

  const policyQuery = useQuery({
    queryKey: ["admin", "retention-policy"],
    queryFn: () => get<RetentionPolicy>(BASE),
    enabled: isReady,
  });

  useEffect(() => {
    if (policyQuery.data?.default_days) {
      setSelected(policyQuery.data.default_days);
    }
  }, [policyQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => put<RetentionPolicy>(BASE, { default_days: selected }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin", "retention-policy"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  if (!isReady) return null;

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
          {saved ? "Saved!" : "Save changes"}
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
        <div
          className="flex flex-col gap-5 rounded-lg p-6"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE", maxWidth: 560 }}
        >
          <div className="flex flex-col gap-1.5">
            <h2 className="text-[15px] font-semibold text-auth-text">Default Retention Period</h2>
            <p className="text-xs" style={{ color: "#9E9E9E" }}>
              Sets the org-wide cap for all data sharing requests. Individual requests may
              select shorter windows but cannot exceed this value.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[12px] font-semibold text-auth-text">Retention cap</label>
            <div
              className="flex overflow-hidden rounded-lg"
              style={{ border: "1px solid #EEEEEE" }}
            >
              {RETENTION_OPTIONS.map((days) => {
                const active = selected === days;
                return (
                  <button
                    key={days}
                    type="button"
                    onClick={() => setSelected(days)}
                    className="flex flex-1 items-center justify-center py-2.5 text-[13px] transition-colors"
                    style={{
                      backgroundColor: active ? "#D76736" : "#FFFFFF",
                      color: active ? "#FFFFFF" : "#515157",
                      fontWeight: active ? 600 : 400,
                      borderRight: days !== 180 ? "1px solid #EEEEEE" : undefined,
                    }}
                  >
                    {days} days
                  </button>
                );
              })}
            </div>
            <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
              ⚠ Request a custom cap (requires platform admin approval)
            </p>
          </div>

          <div
            className="flex items-start gap-2.5 rounded-md p-3"
            style={{ backgroundColor: "#FFF5F0", border: "1px solid #FFCDB8" }}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#D76736" }} />
            <p className="text-xs" style={{ color: "#D76736" }}>
              Files are permanently deleted after the retention window closes and cannot be
              recovered.
            </p>
          </div>

          <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
            This cap applies to all new sharing requests. Existing approved windows are not
            retroactively affected.
          </p>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
              className="h-9 rounded-md px-6 text-[13px] font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: "#D76736" }}
            >
              {saved ? "Saved!" : "Save changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
