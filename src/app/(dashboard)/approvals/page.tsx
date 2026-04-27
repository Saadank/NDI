"use client";

import Link from "next/link";
import { ArrowRight, Clock, Inbox, Lock, ShieldAlert, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";
import type { ShareRequest } from "@/lib/types/data-sharing/request.types";

// ───────────────────────────────────────────────────────────────
// Helpers — priority + SLA derivation
// ───────────────────────────────────────────────────────────────

const URGENT_THRESHOLD_HOURS = 24;

function hoursUntil(iso: string | null): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return ms / (1000 * 60 * 60);
}

function isUrgent(r: ShareRequest): boolean {
  const h = hoursUntil(r.expiry_at);
  return h !== null && h > 0 && h < URGENT_THRESHOLD_HOURS;
}

function formatSlaRemaining(r: ShareRequest): string {
  const h = hoursUntil(r.expiry_at);
  if (h === null) return "—";
  if (h <= 0) return "Overdue";
  if (h < 48) return `${Math.round(h)}h left`;
  const days = Math.floor(h / 24);
  const remHours = Math.round(h % 24);
  return remHours > 0 ? `${days}d ${remHours}h left` : `${days}d left`;
}

function avgDaysRemaining(rows: ShareRequest[]): number {
  const days = rows
    .map((r) => hoursUntil(r.expiry_at))
    .filter((h): h is number => h !== null && h > 0)
    .map((h) => h / 24);
  if (days.length === 0) return 0;
  return Math.round(days.reduce((a, b) => a + b, 0) / days.length);
}

// ───────────────────────────────────────────────────────────────
// Sub-components
// ───────────────────────────────────────────────────────────────

function ClassificationCell({ value }: { value: string }) {
  const v = value.toLowerCase();
  const Icon =
    v === "confidential" || v === "sensitive" ? Lock :
    v === "restricted" ? ShieldAlert :
    null;
  const color =
    v === "confidential" || v === "sensitive" ? "#D76736" :
    v === "restricted" ? "#7C3AED" :
    "#9E9E9E";
  return (
    <span className="flex items-center gap-1.5 text-xs" style={{ color }}>
      {Icon ? <Icon className="h-3 w-3" /> : <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />}
      <span style={{ color: "#515157", textTransform: "capitalize" }}>{value}</span>
    </span>
  );
}

function PriorityCell({ urgent }: { urgent: boolean }) {
  if (urgent) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: "#FFF0EB", color: "#D76736" }}
      >
        <TriangleAlert className="h-3 w-3" />
        Urgent
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ backgroundColor: "#F5F5F5", color: "#616161" }}
    >
      Normal
    </span>
  );
}

function SlaCell({ value, urgent }: { value: string; urgent: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs"
      style={{ color: urgent ? "#D76736" : "#515157" }}
    >
      <Clock className="h-3 w-3" />
      {value}
    </span>
  );
}

function ActionButton({
  label,
  primary,
  href,
}: {
  label: string;
  primary: boolean;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium"
      style={
        primary
          ? { backgroundColor: "#D76736", color: "#FFFFFF" }
          : label === "Confirm"
            ? { backgroundColor: "#1D4ED8", color: "#FFFFFF" }
            : { borderWidth: 1, borderColor: "#EEEEEE", color: "#515157" }
      }
    >
      {label}
      <ArrowRight className="h-3 w-3" />
    </Link>
  );
}

// ───────────────────────────────────────────────────────────────
// Main page
// ───────────────────────────────────────────────────────────────

type Tab = "outgoing" | "incoming";

export default function ApprovalsInboxPage() {
  const { isReady } = useRoleGuard({
    allow: ["data_owner", "platform_admin"],
  });
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

  const myGroupName = myGroupId ? groupNameById.get(myGroupId) ?? "" : "";

  // Split the dataset into outgoing (my dept sent it) vs incoming (sent to
  // my dept). Backend's list endpoint already filters by what this role
  // can see; we just bucket.
  const { outgoing, incoming } = useMemo(() => {
    const all = requestsQuery.data?.data ?? [];
    return {
      outgoing: all.filter(
        (r) =>
          (r.requester_group_id !== null &&
            r.requester_group_id === myGroupId) ||
          r.requester_id !== null /* my own raised requests */,
      ).filter((r) => r.requester_group_id === myGroupId),
      incoming: all.filter((r) => r.receiver_group_id === myGroupId),
    };
  }, [requestsQuery.data?.data, myGroupId]);

  if (!isReady) return null;

  const visibleRows = tab === "outgoing" ? outgoing : incoming;
  const urgentCount = visibleRows.filter(isUrgent).length;
  const bothEmpty = outgoing.length === 0 && incoming.length === 0;

  // Sort: urgent rows first (DO-03 "pinned" semantics), then by expiry ASC.
  const sorted = [...visibleRows].sort((a, b) => {
    const ua = isUrgent(a) ? 0 : 1;
    const ub = isUrgent(b) ? 0 : 1;
    if (ua !== ub) return ua - ub;
    const ea = a.expiry_at ? new Date(a.expiry_at).getTime() : Infinity;
    const eb = b.expiry_at ? new Date(b.expiry_at).getTime() : Infinity;
    return ea - eb;
  });

  const showUrgentBanner = tab === "outgoing" && urgentCount > 0;
  // The "Normal priority" divider marks the visual split between urgent
  // and non-urgent rows on DO-03.
  const firstNormalIdx = sorted.findIndex((r) => !isUrgent(r));

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #EEEEEE",
        }}
      >
        <h1 className="text-lg font-bold text-auth-text">Approvals Inbox</h1>
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
            {myGroupName ? ` · ${myGroupName}` : ""}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-auto px-8 py-6">
        {/* Tabs */}
        <div className="flex items-center gap-2">
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
              className="flex h-8 items-center gap-2 rounded-full px-3 text-xs"
              style={
                tab === t.id
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
              <span>× {t.label}</span>
              <span
                className="flex h-5 min-w-[20px] items-center justify-center rounded-full px-1 text-[11px] font-bold"
                style={
                  tab === t.id
                    ? { backgroundColor: "#D76736", color: "#FFFFFF" }
                    : { backgroundColor: "#F5F5F5", color: "#9E9E9E" }
                }
              >
                {t.count}
              </span>
            </button>
          ))}
        </div>

        {/* Stats line */}
        {!bothEmpty && (
          <div className="flex items-center gap-4 text-xs">
            <span style={{ color: "#515157" }}>
              {visibleRows.length} pending
            </span>
            {urgentCount > 0 && (
              <span
                className="inline-flex items-center gap-1"
                style={{ color: "#D76736" }}
              >
                <TriangleAlert className="h-3 w-3" />
                {urgentCount} Urgent
              </span>
            )}
            <span style={{ color: "#9E9E9E" }}>
              Avg SLA remaining: {avgDaysRemaining(visibleRows)} days
            </span>
          </div>
        )}

        {/* Empty state covers DO-04 — both tabs at zero */}
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
              <p className="text-sm font-semibold text-auth-text">
                You&rsquo;re all caught up
              </p>
              <p className="text-xs" style={{ color: "#9E9E9E", maxWidth: 360 }}>
                No approvals pending in either queue. All requests have been
                actioned.
              </p>
            </div>
            <div className="flex items-center gap-2 pt-2">
              <Link
                href="/dpo/audit"
                className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium"
                style={{ borderColor: "#EEEEEE", color: "#616161" }}
              >
                <Clock className="h-3.5 w-3.5" />
                View recent department activity
              </Link>
              <Link
                href="/"
                className="flex h-9 items-center gap-1.5 rounded-md px-4 text-[13px] font-semibold text-white"
                style={{ backgroundColor: "#D76736" }}
              >
                <ArrowRight className="h-3.5 w-3.5" />
                Return to Product Portal
              </Link>
            </div>
          </div>
        ) : (
          <>
            {/* DO-03 amber urgent banner (only on outgoing when urgent rows exist) */}
            {showUrgentBanner && (
              <div
                className="flex items-center gap-2 rounded-md p-3"
                style={{
                  backgroundColor: "#FFFBEB",
                  border: "1px solid #FCD34D",
                }}
              >
                <TriangleAlert
                  className="h-4 w-4 shrink-0"
                  style={{ color: "#B45309" }}
                />
                <p className="text-xs" style={{ color: "#92400E" }}>
                  <strong>Urgent</strong> — Action required within 1 business
                  day · Compressed SLA
                </p>
              </div>
            )}

            {/* Table */}
            <div
              className="flex flex-col overflow-hidden rounded-lg"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              {/* Header row */}
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
                  Request
                </span>
                <span
                  className="w-[120px] text-[11px] font-semibold tracking-[0.6px]"
                  style={{ color: "#9E9E9E" }}
                >
                  {tab === "incoming" ? "From Dept" : "Dept"}
                </span>
                <span
                  className="w-[140px] text-[11px] font-semibold tracking-[0.6px]"
                  style={{ color: "#9E9E9E" }}
                >
                  Classification
                </span>
                <span
                  className="w-[100px] text-[11px] font-semibold tracking-[0.6px]"
                  style={{ color: "#9E9E9E" }}
                >
                  Priority
                </span>
                <span
                  className="w-[140px] text-[11px] font-semibold tracking-[0.6px]"
                  style={{ color: "#9E9E9E" }}
                >
                  SLA Remaining
                </span>
                <span
                  className="w-[110px] text-[11px] font-semibold tracking-[0.6px]"
                  style={{ color: "#9E9E9E" }}
                >
                  Action
                </span>
              </div>

              {/* Loading */}
              {requestsQuery.isLoading && (
                <div className="py-12 text-center text-sm text-auth-text-subtle">
                  Loading approvals…
                </div>
              )}

              {/* Error */}
              {requestsQuery.isError && (
                <div className="py-12 text-center text-sm text-red-600">
                  Failed to load approvals.
                </div>
              )}

              {/* Rows */}
              {!requestsQuery.isLoading &&
                !requestsQuery.isError &&
                sorted.map((r, i) => {
                  const urgent = isUrgent(r);
                  const isFirstNormal =
                    showUrgentBanner && i === firstNormalIdx && firstNormalIdx > 0;
                  return (
                    <div key={r.id}>
                      {isFirstNormal && (
                        <div
                          className="flex h-9 items-center px-5 text-[11px] uppercase tracking-[0.6px]"
                          style={{
                            backgroundColor: "#FAFAFA",
                            color: "#9E9E9E",
                            borderTop: "1px solid #EEEEEE",
                            borderBottom: "1px solid #EEEEEE",
                          }}
                        >
                          Normal priority — standard 3-day SLA
                        </div>
                      )}
                      <div
                        className="flex h-[68px] items-center px-5"
                        style={{
                          backgroundColor: urgent ? "#FFF8F4" : undefined,
                          borderBottom:
                            i < sorted.length - 1
                              ? "1px solid #F5F5F5"
                              : undefined,
                        }}
                      >
                        <div className="flex flex-1 flex-col gap-1">
                          <span className="text-[13px] font-semibold text-auth-text">
                            {r.title}
                          </span>
                          <span
                            className="text-[11px]"
                            style={{ color: "#9E9E9E" }}
                          >
                            {tab === "incoming" ? "From " : "Raised by "}
                            {groupNameById.get(
                              tab === "incoming"
                                ? r.requester_group_id ?? 0
                                : r.receiver_group_id ?? 0,
                            ) ?? "—"}{" "}
                            · {r.request_number}
                          </span>
                        </div>
                        <span
                          className="w-[120px] text-xs"
                          style={{ color: "#515157" }}
                        >
                          {groupNameById.get(
                            tab === "incoming"
                              ? r.requester_group_id ?? 0
                              : r.receiver_group_id ?? 0,
                          ) ?? "—"}
                        </span>
                        <div className="w-[140px]">
                          <ClassificationCell value={r.data_classification} />
                        </div>
                        <div className="w-[100px]">
                          <PriorityCell urgent={urgent} />
                        </div>
                        <div className="w-[140px]">
                          <SlaCell
                            value={formatSlaRemaining(r)}
                            urgent={urgent}
                          />
                        </div>
                        <div className="w-[110px]">
                          <ActionButton
                            label={tab === "incoming" ? "Confirm" : "Review"}
                            primary={urgent}
                            href={`/approvals/${r.id}`}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
