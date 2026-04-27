"use client";

import Link from "next/link";
import { Search, Download } from "lucide-react";
import { useState } from "react";

import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { REQUEST_STATUS_LABELS } from "@/lib/utils/constants";
import { formatDate } from "@/lib/utils/formatters";
import type { RequestStatus } from "@/lib/types/data-sharing/request.types";

const STATUS_OPTIONS: { value: RequestStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "submitted", label: "Submitted" },
  { value: "in_review", label: "Under Review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "completed", label: "Completed" },
];

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  draft: { bg: "#EEEEEE", color: "#616161" },
  submitted: { bg: "#EEF2FF", color: "#3B4FD6" },
  in_review: { bg: "#FFF7E6", color: "#B45309" },
  approved: { bg: "#F0FAF0", color: "#449235" },
  rejected: { bg: "#FFF0F0", color: "#D32F2F" },
  cancelled: { bg: "#F5F5F5", color: "#9E9E9E" },
  completed: { bg: "#F0FAF0", color: "#449235" },
  expired: { bg: "#F5F5F5", color: "#9E9E9E" },
};

export default function DpoOrgRequestListPage() {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin"] });
  const [statusFilter, setStatusFilter] = useState<RequestStatus | "">("");
  const [classification, setClassification] = useState<string>("");
  const [query, setQuery] = useState("");

  const requestsQuery = useRequests({
    page: 1,
    limit: 100,
    status: statusFilter || undefined,
  });
  const groupsQuery = useGroups();
  const groupNameById = new Map<number, string>();
  for (const g of groupsQuery.data ?? []) groupNameById.set(g.id, g.name);

  if (!isReady) return null;

  const all = requestsQuery.data?.data ?? [];
  const filtered = all.filter((r) => {
    if (classification && r.data_classification !== classification) return false;
    if (
      query &&
      !`${r.title} ${r.request_number}`.toLowerCase().includes(query.toLowerCase())
    )
      return false;
    return true;
  });

  // Lets DPO export the current filtered view as CSV. Generated client-side
  // because the backend doesn't have a CSV export endpoint yet.
  const exportCsv = () => {
    const headers = [
      "request_number",
      "title",
      "sharing_type",
      "data_classification",
      "status",
      "personal_data_involved",
      "receiver_group",
      "created_at",
    ];
    const rows = filtered.map((r) => [
      r.request_number,
      r.title.replaceAll('"', '""'),
      r.sharing_type,
      r.data_classification,
      r.status,
      String(r.personal_data_involved),
      groupNameById.get(r.receiver_group_id ?? 0) ?? "",
      r.created_at,
    ]);
    const csv = [
      headers.join(","),
      ...rows.map((r) => r.map((v) => `"${v}"`).join(",")),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `datarix-requests-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">
            Organisation Requests
          </h1>
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
        <div className="flex items-center gap-3">
          <div
            className="flex h-9 flex-1 items-center gap-2 rounded-md px-3"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search requests…"
              className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as RequestStatus | "")
            }
            className="h-9 rounded-md border bg-white px-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE", color: "#070709" }}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <select
            value={classification}
            onChange={(e) => setClassification(e.target.value)}
            className="h-9 rounded-md border bg-white px-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE", color: "#070709" }}
          >
            <option value="">All classifications</option>
            <option value="public">Public</option>
            <option value="internal">Internal</option>
            <option value="confidential">Confidential</option>
            <option value="sensitive">Sensitive</option>
          </select>
        </div>

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
            <span
              className="flex-1 text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              REQUEST
            </span>
            <span
              className="w-40 text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              RECEIVER
            </span>
            <span
              className="w-[130px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              CLASSIFICATION
            </span>
            <span
              className="w-[90px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              PII
            </span>
            <span
              className="w-[150px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              STATUS
            </span>
            <span
              className="w-[100px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              CREATED
            </span>
          </div>

          {requestsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              Loading…
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              No requests match the current filters.
            </div>
          ) : (
            filtered.map((r, i) => {
              const style = STATUS_STYLE[r.status] ?? STATUS_STYLE.draft;
              return (
                <Link
                  key={r.id}
                  href={`/dpo/${r.id}`}
                  className="flex h-16 items-center px-5 hover:bg-[#FFFBF9]"
                  style={{
                    borderBottom:
                      i < filtered.length - 1 ? "1px solid #EEEEEE" : undefined,
                  }}
                >
                  <div className="flex flex-1 flex-col gap-1">
                    <span className="text-[13px] font-semibold text-auth-text">
                      {r.title}
                    </span>
                    <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      {r.request_number} · {r.sharing_type}
                    </span>
                  </div>
                  <span className="w-40 text-[13px]" style={{ color: "#515157" }}>
                    {groupNameById.get(r.receiver_group_id ?? 0) ?? "—"}
                  </span>
                  <span className="w-[130px] text-xs" style={{ color: "#9E9E9E" }}>
                    {r.data_classification.charAt(0).toUpperCase() +
                      r.data_classification.slice(1)}
                  </span>
                  <span className="w-[90px] text-xs" style={{ color: "#9E9E9E" }}>
                    {r.personal_data_involved ? "Yes" : "—"}
                  </span>
                  <div className="w-[150px]">
                    <span
                      className="inline-flex items-center rounded px-2.5 py-1 text-xs font-medium"
                      style={{ backgroundColor: style.bg, color: style.color }}
                    >
                      {REQUEST_STATUS_LABELS[r.status] ?? r.status}
                    </span>
                  </div>
                  <span className="w-[100px] text-xs" style={{ color: "#9E9E9E" }}>
                    {formatDate(r.created_at)}
                  </span>
                </Link>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
