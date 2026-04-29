"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import { getMyDelegationHistory } from "@/lib/api/platform/delegation.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate } from "@/lib/utils/formatters";

export default function DelegationExpiredPage() {
  const { isReady } = useRoleGuard({ allow: ["data_owner", "dpo"] });

  const historyQuery = useQuery({
    queryKey: ["platform", "delegation", "history"],
    queryFn: getMyDelegationHistory,
    enabled: isReady,
  });

  if (!isReady) return null;

  const history = historyQuery.data ?? [];
  const last = history[0] ?? null;

  const initials = last?.delegate_name
    ? last.delegate_name
        .split(" ")
        .slice(0, 2)
        .map((p: string) => p[0]?.toUpperCase() ?? "")
        .join("")
    : "??";

  const durationDays = last?.delegation_start && last?.delegation_end
    ? Math.round(
        (new Date(last.delegation_end).getTime() - new Date(last.delegation_start).getTime()) /
          (1000 * 60 * 60 * 24),
      )
    : null;

  return (
    <main className="flex flex-1 flex-col gap-6 px-60 py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Profile", href: "/profile" },
          { label: "Delegation Settings" },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>

      <div
        className="flex flex-col gap-5 rounded-lg p-6"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center justify-between">
          <span className="text-[15px] font-semibold text-auth-text">Last delegation</span>
          <span
            className="rounded-full px-3 py-0.5 text-[11px] font-semibold"
            style={{ backgroundColor: "#F5F5F5", color: "#9E9E9E" }}
          >
            Expired
          </span>
        </div>

        {historyQuery.isLoading ? (
          <p className="text-[13px]" style={{ color: "#9E9E9E" }}>Loading…</p>
        ) : !last ? (
          <p className="text-[13px]" style={{ color: "#9E9E9E" }}>
            No past delegations found.
          </p>
        ) : (
          <>
            <p className="text-[13px]" style={{ color: "#9E9E9E" }}>
              A summary of your most recently completed delegation window.
            </p>

            <div
              className="flex flex-col divide-y rounded-lg overflow-hidden"
              style={{ border: "1px solid #EEEEEE" }}
            >
              {/* Backup */}
              <div className="flex items-center gap-4 px-4 py-3">
                <span className="w-[140px] text-[12px] font-medium" style={{ color: "#9E9E9E" }}>Backup</span>
                <div className="flex items-center gap-2">
                  <div
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                    style={{ backgroundColor: "#D7673626", color: "#D76736" }}
                  >
                    {initials}
                  </div>
                  <span className="text-[13px] font-medium text-auth-text">{last.delegate_name ?? `User #${String(last.delegate_to_user_id)}`}</span>
                </div>
              </div>

              {/* Period */}
              <div className="flex items-center gap-4 px-4 py-3">
                <span className="w-[140px] text-[12px] font-medium" style={{ color: "#9E9E9E" }}>Period</span>
                <span className="text-[13px] text-auth-text">
                  {formatDate(last.delegation_start)} → {formatDate(last.delegation_end)}
                  {durationDays !== null && ` (${durationDays} days)`}
                </span>
              </div>

              {/* Approvals handled */}
              {last.summary && (
                <div className="flex items-center gap-4 px-4 py-3">
                  <span className="w-[140px] text-[12px] font-medium" style={{ color: "#9E9E9E" }}>Approvals handled</span>
                  <span className="text-[13px] text-auth-text">{last.summary}</span>
                </div>
              )}
            </div>

            <Link
              href="/dpo/audit"
              className="text-[13px] font-medium"
              style={{ color: "#D76736" }}
            >
              View audit-trail entries from this window →
            </Link>
          </>
        )}

        <div className="flex justify-end">
          <Link
            href="/delegation"
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            Set up new delegation
          </Link>
        </div>
      </div>
    </main>
  );
}
