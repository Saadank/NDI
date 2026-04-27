"use client";

import { Download, Info, Search, X } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import apiClient from "@/lib/api/client";
import { getAuditEvents } from "@/lib/api/platform/audit.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDateTime } from "@/lib/utils/formatters";

const ACTION_OPTIONS = [
  "request.created",
  "request.submitted",
  "request.approved",
  "request.rejected",
  "request.cancelled",
  "file.uploaded",
  "file.deleted",
  "step.approved",
  "step.rejected",
];

const PAGE_SIZE = 25;

export default function AuditTrailPage() {
  const { isReady } = useRoleGuard({
    allow: ["dpo", "platform_admin", "org_admin"],
  });

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [actionType, setActionType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const eventsQuery = useQuery({
    queryKey: ["platform", "audit", { page, actionType, dateFrom, dateTo }],
    queryFn: () =>
      getAuditEvents({
        page,
        limit: PAGE_SIZE,
        action_type: actionType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
    enabled: isReady,
  });

  if (!isReady) return null;

  const events = eventsQuery.data?.data ?? [];
  const pagination = eventsQuery.data?.pagination;
  const totalPages = pagination?.total_pages ?? 1;

  const filtered = search
    ? events.filter((e) => {
        const haystack =
          `${e.actor_email ?? ""} ${e.action_type} ${e.target_type ?? ""} ${e.target_id ?? ""}`.toLowerCase();
        return haystack.includes(search.toLowerCase());
      })
    : events;

  const hasFilters = !!actionType || !!dateFrom || !!dateTo;

  const clearFilters = () => {
    setActionType("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  const exportCsv = async () => {
    const res = await apiClient.get("/api/v1/platform/audit/export", {
      params: {
        action_type: actionType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      },
      responseType: "blob",
    });
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Audit Trail</h1>
          <span
            className="rounded px-2 py-0.5 text-xs font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            DPO
          </span>
        </div>
        <button
          type="button"
          onClick={exportCsv}
          className="flex h-9 items-center gap-2 rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#EEEEEE", color: "#616161" }}
        >
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* Append-only info banner */}
        <div
          className="flex items-start gap-3 rounded-lg px-4 py-3"
          style={{ backgroundColor: "#EFF6FF", border: "1px solid #BFDBFE" }}
        >
          <Info className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#3B82F6" }} />
          <p className="text-[13px]" style={{ color: "#1E40AF" }}>
            <strong>Append-only regulatory log.</strong> Entries cannot be
            modified or deleted. This log meets PDPL Article 30 record-keeping
            obligations.
          </p>
        </div>

        {/* Filters row */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search */}
          <div
            className="flex h-9 w-64 items-center gap-2 rounded-md px-3"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search actor, action, target…"
              className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
            />
          </div>

          {/* Action type chip */}
          <select
            value={actionType}
            onChange={(e) => { setActionType(e.target.value); setPage(1); }}
            className="h-9 rounded-md border bg-white px-3 text-[13px] outline-none"
            style={{ borderColor: actionType ? "#D76736" : "#EEEEEE", color: actionType ? "#D76736" : "#515157" }}
          >
            <option value="">Action type</option>
            {ACTION_OPTIONS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>

          {/* Date from */}
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
            className="h-9 rounded-md border bg-white px-3 text-[13px] outline-none"
            style={{ borderColor: dateFrom ? "#D76736" : "#EEEEEE", color: dateFrom ? "#D76736" : "#515157" }}
            title="From date"
          />

          {/* Date to */}
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
            className="h-9 rounded-md border bg-white px-3 text-[13px] outline-none"
            style={{ borderColor: dateTo ? "#D76736" : "#EEEEEE", color: dateTo ? "#D76736" : "#515157" }}
            title="To date"
          />

          {/* Clear filters */}
          {hasFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="flex h-9 items-center gap-1.5 rounded-md px-3 text-[13px]"
              style={{ color: "#D76736" }}
            >
              <X className="h-3.5 w-3.5" />
              Clear filters
            </button>
          )}
        </div>

        {/* Table */}
        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="w-[180px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              WHEN
            </span>
            <span className="w-[200px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              ACTOR
            </span>
            <span className="w-[200px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              ACTION
            </span>
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              TARGET
            </span>
          </div>

          {eventsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : eventsQuery.isError ? (
            <div className="py-20 text-center text-sm text-red-600">
              Failed to load audit events.
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              No events match the current filters.
            </div>
          ) : (
            filtered.map((e, i) => (
              <div
                key={e.id}
                className="flex h-12 items-center px-5"
                style={{
                  borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined,
                }}
              >
                <span className="w-[180px] text-xs" style={{ color: "#9E9E9E" }}>
                  {formatDateTime(e.created_at)}
                </span>
                <span className="w-[200px] text-xs" style={{ color: "#1A1A1A" }}>
                  {e.actor_email ?? "system"}
                </span>
                <span className="w-[200px] text-xs font-medium" style={{ color: "#070709" }}>
                  {e.action_type}
                </span>
                <span className="flex-1 truncate text-xs" style={{ color: "#515157" }}>
                  {e.target_type ?? "—"}
                  {e.target_id ? ` · ${e.target_id}` : ""}
                </span>
              </div>
            ))
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "#9E9E9E" }}>
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="flex h-8 items-center rounded-md border px-3 text-[13px] disabled:opacity-40"
                style={{ borderColor: "#EEEEEE", color: "#515157" }}
              >
                Previous
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="flex h-8 items-center rounded-md border px-3 text-[13px] disabled:opacity-40"
                style={{ borderColor: "#EEEEEE", color: "#515157" }}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
