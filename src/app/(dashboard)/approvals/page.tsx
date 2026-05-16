"use client";

import Link from "next/link";
import { ArrowRight, Inbox, Lock, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";
import { formatDate } from "@/lib/utils/formatters";
import type { ShareRequest } from "@/lib/types/data-sharing/request.types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function businessDaysRemaining(r: ShareRequest): number | null {
  if (!r.expiry_at) return null;
  const ms = new Date(r.expiry_at).getTime() - Date.now();
  if (ms <= 0) return 0;
  // Approximate: 8 working hours per business day
  return Math.max(0, Math.round((ms / (1000 * 60 * 60 * 8)) * 10) / 10);
}

function avgSlaDisplay(rows: ShareRequest[]): string {
  const days = rows
    .map(businessDaysRemaining)
    .filter((d): d is number => d !== null && d > 0);
  if (days.length === 0) return "—";
  const avg = Math.round((days.reduce((a, b) => a + b, 0) / days.length) * 10) / 10;
  return `${avg} business day${avg === 1 ? "" : "s"}`;
}

// ─── Cell helpers ─────────────────────────────────────────────────────────────

function ClassificationCell({ value }: { value: string }) {
  const v = value.toLowerCase();
  const Icon =
    v === "confidential" || v === "sensitive"
      ? Lock
      : v === "restricted"
        ? ShieldAlert
        : null;
  const color =
    v === "confidential" || v === "sensitive"
      ? "#D76736"
      : v === "restricted"
        ? "#7C3AED"
        : "#9E9E9E";
  return (
    <span className="flex items-center gap-1.5 text-xs" style={{ color }}>
      {Icon ? (
        <Icon className="h-3 w-3" />
      ) : (
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: color }}
        />
      )}
      <span style={{ color: "#515157", textTransform: "capitalize" }}>{value}</span>
    </span>
  );
}

function SlaCell({ r }: { r: ShareRequest }) {
  const d = businessDaysRemaining(r);
  if (d === null) return <span className="text-xs" style={{ color: "#BABABA" }}>—</span>;
  if (d === 0) return <span className="text-xs font-medium" style={{ color: "#D32F2F" }}>Overdue</span>;
  const urgent = d <= 1;
  return (
    <span className="flex items-center gap-1 text-xs" style={{ color: urgent ? "#D76736" : "#515157" }}>
      {urgent ? "+" : ""}{d} business day{d === 1 ? "" : "s"}
    </span>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

type Tab = "outgoing" | "incoming";

export default function ApprovalsInboxPage() {
  const { isReady } = useRoleGuard({ allow: ["data_owner", "platform_admin"] });
  const [tab, setTab] = useState<Tab>("outgoing");

  const requestsQuery = useRequests({ page: 1, limit: 100 });
  const groupsQuery = useGroups();
  const myGroupId = useAuthStore((s) => s.user?.group_id ?? null);
  const myProductRole = useAuthStore((s) => s.user?.product_role ?? null);

  const groupNameById = useMemo(() => {
    const m = new Map<number, string>();
    for (const g of groupsQuery.data ?? []) m.set(g.id, g.name);
    return m;
  }, [groupsQuery.data]);

  const myGroupName = myGroupId ? (groupNameById.get(myGroupId) ?? "") : "";

  // Bucket the inbox by the role of the CURRENT pending step (which
  // the backend annotates as `current_step`). Per spec the bucketing
  // is role-driven, not group-driven:
  //
  //   data_owner / source  → Outgoing  (you're on the source side —
  //                                     approving release or uploading)
  //   receiver             → Incoming  (you're on the destination side —
  //                                     confirming receipt)
  //
  // Group-based fallback covers requests the backend returned that
  // don't have a `current_step` annotation (closed / pre-migration
  // rows): they map to Outgoing if the user's group owns the data
  // being released, Incoming otherwise.
  const { outgoing, incoming } = useMemo(() => {
    const all = requestsQuery.data?.data ?? [];
    const out: typeof all = [];
    const inc: typeof all = [];
    for (const r of all) {
      const role = r.current_step?.assignee_role ?? null;
      if (role === "data_owner" || role === "source") {
        out.push(r);
      } else if (role === "receiver") {
        inc.push(r);
      } else {
        // No current_step (workflow finished / not started, or this
        // row predates the annotation) — fall back to the group-based
        // heuristic.
        if (r.receiver_group_id === myGroupId && r.requester_group_id !== myGroupId) {
          out.push(r);
        } else if (r.requester_group_id === myGroupId && r.receiver_group_id !== myGroupId) {
          inc.push(r);
        }
      }
    }
    return { outgoing: out, incoming: inc };
  }, [requestsQuery.data?.data, myGroupId]);

  if (!isReady) return null;

  const visibleRows = tab === "outgoing" ? outgoing : incoming;
  const bothEmpty = outgoing.length === 0 && incoming.length === 0;

  const sorted = [...visibleRows].sort((a, b) => {
    const ea = a.expiry_at ? new Date(a.expiry_at).getTime() : Infinity;
    const eb = b.expiry_at ? new Date(b.expiry_at).getTime() : Infinity;
    return ea - eb;
  });

  const deptColLabel = tab === "incoming" ? "FROM DEPT" : "DEPT";

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <h1 className="text-lg font-bold text-auth-text">Approvals Inbox</h1>
        {myProductRole && (
          <span
            className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#D76736" }} />
            {myProductRole === "data_owner" ? "Data Owner" : myProductRole}
            {myGroupName ? ` · ${myGroupName}` : ""}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-auto px-8 py-6">
        {/* Tabs */}
        <div className="flex" style={{ borderBottom: "1px solid #EEEEEE" }}>
          {(
            [
              { id: "outgoing", label: "Outgoing", count: outgoing.length },
              { id: "incoming", label: "Incoming", count: incoming.length },
            ] as { id: Tab; label: string; count: number }[]
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className="flex items-center gap-2 px-4 py-2.5"
              style={
                tab === t.id
                  ? { borderBottom: "2px solid #D76736", marginBottom: -1 }
                  : undefined
              }
            >
              <span
                className="text-sm"
                style={{
                  color: tab === t.id ? "#D76736" : "#9E9E9E",
                  fontWeight: tab === t.id ? 600 : 400,
                }}
              >
                {t.label}
              </span>
              <span
                className="flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold"
                style={
                  tab === t.id
                    ? { backgroundColor: "#D76736", color: "#FFFFFF" }
                    : { backgroundColor: "#EEEEEE", color: "#9E9E9E" }
                }
              >
                {t.count}
              </span>
            </button>
          ))}
        </div>

        {/* Summary bar */}
        {!bothEmpty && (
          <p className="text-xs" style={{ color: "#515157" }}>
            {visibleRows.length} pending · Avg SLA remaining:{" "}
            <span style={{ color: "#D76736" }}>{avgSlaDisplay(visibleRows)}</span>
          </p>
        )}

        {/* Empty state */}
        {bothEmpty ? (
          <div
            className="mt-6 flex flex-col items-center justify-center gap-4 rounded-lg py-24"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full"
              style={{ backgroundColor: "#F5F5F5" }}
            >
              <Inbox className="h-6 w-6" style={{ color: "#9E9E9E" }} />
            </div>
            <div className="flex flex-col items-center gap-1.5 text-center">
              <p className="text-sm font-semibold text-auth-text">You&rsquo;re all caught up</p>
              <p className="text-xs" style={{ color: "#9E9E9E", maxWidth: 360 }}>
                No approvals pending in either queue. All requests have been actioned.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Link
                href="/my-department"
                className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
                style={{ borderColor: "#EEEEEE", color: "#515157" }}
              >
                View recent department activity
              </Link>
              <Link
                href="/"
                className="flex h-9 items-center rounded-md px-4 text-[13px] font-semibold text-white"
                style={{ backgroundColor: "#D76736" }}
              >
                Return to Product Portal
              </Link>
            </div>
          </div>
        ) : (
          <div
            className="flex flex-col overflow-hidden rounded-lg"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            {/* Column headers */}
            <div
              className="flex h-10 items-center px-5"
              style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
            >
              <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                REQUEST
              </span>
              <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                {deptColLabel}
              </span>
              <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                CLASSIFICATION
              </span>
              <span className="w-[150px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                SLA REMAINING
              </span>
              <span className="w-[110px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                ACTION
              </span>
            </div>

            {requestsQuery.isLoading && (
              <div className="py-12 text-center text-sm" style={{ color: "#9E9E9E" }}>
                Loading approvals…
              </div>
            )}
            {requestsQuery.isError && (
              <div className="py-12 text-center text-sm text-red-600">
                Failed to load approvals.
              </div>
            )}

            {!requestsQuery.isLoading &&
              !requestsQuery.isError &&
              sorted.map((r, i) => {
                // Outgoing: show the EXTERNAL dept that raised the request (requester).
                // Incoming: show the EXTERNAL dept that's the data source (receiver).
                const deptId =
                  tab === "outgoing" ? r.requester_group_id : r.receiver_group_id;
                const deptName = deptId ? (groupNameById.get(deptId) ?? String(deptId)) : "—";
                const subtitle =
                  tab === "outgoing"
                    ? `Raised by: ${r.requester_id} · ${deptName} · ${formatDate(r.created_at)}`
                    : `From ${deptName} · Requested ${formatDate(r.created_at)}`;

                // Outgoing rows → /approvals/[id] (heavy review screen).
                // Incoming rows → /approvals/incoming/[id] (light confirm screen).
                const href =
                  tab === "incoming"
                    ? `/approvals/incoming/${r.id}`
                    : `/approvals/${r.id}`;
                // Per Pencil frame 02: Incoming uses a blue "Confirm" pill,
                // not the brand orange.
                const actionLabel = tab === "incoming" ? "Confirm" : "Review";
                const actionBg = tab === "incoming" ? "#1D4ED8" : "#D76736";

                return (
                  <Link
                    key={r.id}
                    href={href}
                    className="flex h-[68px] cursor-pointer items-center px-5 hover:bg-[#FAFAFA]"
                    style={{
                      borderBottom: i < sorted.length - 1 ? "1px solid #F5F5F5" : undefined,
                    }}
                  >
                    {/* Request */}
                    <div className="flex flex-1 flex-col gap-1">
                      <span className="text-[13px] font-semibold text-auth-text truncate pr-4">
                        {r.title}
                      </span>
                      <span className="text-[11px] truncate pr-4" style={{ color: "#9E9E9E" }}>
                        {subtitle}
                      </span>
                    </div>

                    {/* Dept */}
                    <span className="w-[140px] text-xs truncate" style={{ color: "#515157" }}>
                      {deptName}
                    </span>

                    {/* Classification */}
                    <span className="w-[140px]">
                      <ClassificationCell value={r.data_classification} />
                    </span>

                    {/* SLA */}
                    <span className="w-[150px]">
                      <SlaCell r={r} />
                    </span>

                    {/* Action */}
                    <span className="w-[110px]">
                      <span
                        className="flex h-8 items-center gap-1 rounded-md px-3 text-xs font-medium text-white"
                        style={{ backgroundColor: actionBg }}
                      >
                        {actionLabel}
                        <ArrowRight className="h-3.5 w-3.5" />
                      </span>
                    </span>
                  </Link>
                );
              })}

            {!requestsQuery.isLoading &&
              !requestsQuery.isError &&
              sorted.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-16">
                  <Inbox className="h-8 w-8" style={{ color: "#EEEEEE" }} />
                  <p className="text-sm" style={{ color: "#9E9E9E" }}>
                    No {tab} requests pending
                  </p>
                </div>
              )}
          </div>
        )}
      </div>
    </div>
  );
}
