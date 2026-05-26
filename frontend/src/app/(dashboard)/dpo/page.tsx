"use client";

import Link from "next/link";
import { Download, Filter, Lock, ShieldAlert, X } from "lucide-react";
import { useMemo, useState } from "react";

import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate } from "@/lib/utils/formatters";
import type { RequestStatus, ShareRequest } from "@/lib/types/data-sharing/request.types";

// ─── constants ───────────────────────────────────────────────────

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  draft:             { bg: "#EEEEEE",  color: "#616161",  label: "Draft" },
  submitted:         { bg: "#EEF2FF",  color: "#3B4FD6",  label: "Submitted" },
  in_review:         { bg: "#FFF7E6",  color: "#B45309",  label: "In Review" },
  approved:          { bg: "#F0FAF0",  color: "#449235",  label: "Approved" },
  rejected:          { bg: "#FFF0F0",  color: "#D32F2F",  label: "Rejected" },
  changes_requested: { bg: "#FFFBEB",  color: "#B45309",  label: "Changes Requested" },
  cancelled:         { bg: "#F5F5F5",  color: "#9E9E9E",  label: "Cancelled" },
  completed:         { bg: "#F0FAF0",  color: "#449235",  label: "Complete" },
  expired:           { bg: "#F5F5F5",  color: "#9E9E9E",  label: "Expired" },
};

interface SavedPreset {
  id: string;
  label: string;
  status: RequestStatus | "";
  type: string;
  classification: string;
}

const DEFAULT_PRESETS: SavedPreset[] = [
  { id: "1", label: "Awaiting DPO Review", status: "in_review", type: "", classification: "" },
  { id: "2", label: "Sensitive data requests", status: "", type: "", classification: "sensitive" },
  { id: "3", label: "External requests", status: "", type: "external", classification: "" },
];

function businessDaysLeft(r: ShareRequest): string | null {
  if (!r.expiry_at) return null;
  const ms = new Date(r.expiry_at).getTime() - Date.now();
  if (ms <= 0) return "Overdue";
  const bd = Math.round((ms / (1000 * 60 * 60 * 8)) * 10) / 10;
  return `${bd} business day${bd === 1 ? "" : "s"}`;
}

function ClassificationBadge({ value }: { value: string }) {
  const v = value.toLowerCase();
  const Icon = v === "confidential" || v === "sensitive" ? Lock : v === "restricted" ? ShieldAlert : null;
  const color = v === "confidential" || v === "sensitive" ? "#D76736" : v === "restricted" ? "#7C3AED" : "#449235";
  const bg = v === "confidential" || v === "sensitive" ? "#FFF5F0" : v === "restricted" ? "#F5F0FF" : "#F0FAF0";
  return (
    <span
      className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold capitalize"
      style={{ backgroundColor: bg, color }}
    >
      {Icon && <Icon className="h-2.5 w-2.5" />}
      {value}
    </span>
  );
}

// ─── Export modal ────────────────────────────────────────────────

interface ExportModalProps {
  onClose: () => void;
  filtered: ShareRequest[];
  activeFilterLabels: string[];
}

function ExportModal({ onClose, filtered, activeFilterLabels }: ExportModalProps) {
  const [format, setFormat] = useState<"pdf" | "csv">("pdf");
  const [exporting, setExporting] = useState(false);

  const handleExport = () => {
    setExporting(true);
    if (format === "csv") {
      const headers = ["request_number", "title", "sharing_type", "data_classification", "status", "created_at"];
      const csvRows = filtered.map((r) => [
        r.request_number, `"${r.title.replaceAll('"', '""')}"`, r.sharing_type,
        r.data_classification, r.status, r.created_at,
      ]);
      const csv = [headers.join(","), ...csvRows.map((r) => r.join(","))].join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `datarix-dpo-requests-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
    setExporting(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.35)" }}>
      <div
        className="flex w-[440px] flex-col gap-5 rounded-xl p-6"
        style={{ backgroundColor: "#FFFFFF", boxShadow: "0 20px 60px rgba(0,0,0,0.12)" }}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-auth-text">Export Filtered View</h2>
          <button type="button" onClick={onClose}>
            <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
          </button>
        </div>

        {/* Active filters */}
        {activeFilterLabels.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.5px]" style={{ color: "#9E9E9E" }}>
              Active filters
            </span>
            <div className="flex flex-wrap gap-1.5">
              {activeFilterLabels.map((label) => (
                <span
                  key={label}
                  className="rounded-full px-2.5 py-1 text-[11px] font-medium"
                  style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
                >
                  {label}
                </span>
              ))}
            </div>
            <p className="text-[12px]" style={{ color: "#9E9E9E" }}>
              {filtered.length} matching request{filtered.length === 1 ? "" : "s"} will be included in the export.
            </p>
          </div>
        )}

        {/* Format */}
        <div className="flex flex-col gap-2">
          <span className="text-[12px] font-semibold text-auth-text">Export format</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setFormat("pdf")}
              className="flex flex-1 flex-col gap-0.5 rounded-lg border p-3 text-left"
              style={{
                borderColor: format === "pdf" ? "#D76736" : "#EEEEEE",
                backgroundColor: format === "pdf" ? "#FFF5F0" : "#FFFFFF",
              }}
            >
              <span className="text-[13px] font-semibold" style={{ color: format === "pdf" ? "#D76736" : "#1A1A1A" }}>
                PDF Report
              </span>
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>Formatted, shareable</span>
            </button>
            <button
              type="button"
              onClick={() => setFormat("csv")}
              className="flex flex-1 flex-col gap-0.5 rounded-lg border p-3 text-left"
              style={{
                borderColor: format === "csv" ? "#D76736" : "#EEEEEE",
                backgroundColor: format === "csv" ? "#FFF5F0" : "#FFFFFF",
              }}
            >
              <span className="text-[13px] font-semibold" style={{ color: format === "csv" ? "#D76736" : "#1A1A1A" }}>
                CSV Data
              </span>
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>Raw data, importable</span>
            </button>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: "#D76736" }}
          >
            <Download className="h-3.5 w-3.5" />
            {exporting ? "Exporting…" : `Export ${filtered.length} request${filtered.length === 1 ? "" : "s"}`}
          </button>
        </div>
      </div>
    </div>
  );
}


// ─── Main page ────────────────────────────────────────────────────

export default function DpoOrgRequestListPage() {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin"] });
  const [statusFilter, setStatusFilter] = useState<RequestStatus | "">("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [classification, setClassification] = useState<string>("");
  const [deptFilter, setDeptFilter] = useState<string>("");
  const [showPresetsRow, setShowPresetsRow] = useState(false);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [showExport, setShowExport] = useState(false);

  const requestsQuery = useRequests({ page: 1, limit: 100, status: statusFilter || undefined });
  const groupsQuery = useGroups();

  const groupNameById = useMemo(() => {
    const m = new Map<number, string>();
    for (const g of groupsQuery.data ?? []) m.set(g.id, g.name);
    return m;
  }, [groupsQuery.data]);

  if (!isReady) return null;

  const all = requestsQuery.data?.data ?? [];

  const filtered = all.filter((r) => {
    if (typeFilter && r.sharing_type !== typeFilter) return false;
    if (classification && r.data_classification !== classification) return false;
    if (deptFilter && String(r.requester_group_id) !== deptFilter && String(r.receiver_group_id) !== deptFilter) return false;
    return true;
  });

  const awaitingDpo = filtered.filter((r) => r.status === "in_review").length;
  const inProgress = filtered.filter((r) => ["submitted", "in_review", "approved"].includes(r.status)).length;

  const activeFilterLabels: string[] = [];
  if (statusFilter) activeFilterLabels.push(`Status: ${STATUS_STYLE[statusFilter]?.label ?? statusFilter}`);
  if (typeFilter) activeFilterLabels.push(`Type: ${typeFilter}`);
  if (classification) activeFilterLabels.push(`Classification: ${classification.charAt(0).toUpperCase() + classification.slice(1)}`);
  if (deptFilter) activeFilterLabels.push(`Dept: ${groupNameById.get(Number(deptFilter)) ?? deptFilter}`);

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <h1 className="text-lg font-bold text-auth-text">Organisation Request List</h1>
        <span
          className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
          style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#D76736" }} />
          DPO · Data Sharing
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-auto px-8 py-6">
        {/* Presets row — visible when presets panel is open */}
        {showPresetsRow && (
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-semibold text-auth-text">Presets</span>
            <div className="flex flex-1 flex-wrap items-center gap-1.5">
              {DEFAULT_PRESETS.map((p) => {
                const active = activePresetId === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      if (active) {
                        setActivePresetId(null);
                        setStatusFilter("");
                        setTypeFilter("");
                        setClassification("");
                      } else {
                        setActivePresetId(p.id);
                        setStatusFilter(p.status);
                        setTypeFilter(p.type);
                        setClassification(p.classification);
                      }
                    }}
                    className="flex h-7 items-center gap-1 rounded-full px-3 text-[12px] font-medium"
                    style={
                      active
                        ? { backgroundColor: "#FFF5F0", color: "#D76736", border: "1px solid #FDDCCC" }
                        : { backgroundColor: "#F5F5F5", color: "#515157", border: "1px solid #EEEEEE" }
                    }
                  >
                    {p.label}
                    {active && <X className="ml-1 h-3 w-3" />}
                  </button>
                );
              })}
            </div>
            <button type="button" className="text-[12px]" style={{ color: "#9E9E9E" }}>
              Save current
            </button>
            <button type="button" className="text-[12px] font-medium" style={{ color: "#D76736" }}>
              Manage presets
            </button>
          </div>
        )}

        {/* Filter bar */}
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-medium" style={{ color: "#9E9E9E" }}>Filter:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as RequestStatus | "")}
            className="flex h-8 items-center rounded-full border px-3 text-[12px] outline-none"
            style={{ borderColor: "#EEEEEE", color: statusFilter ? "#1A1A1A" : "#515157" }}
          >
            <option value="">All Status</option>
            <option value="submitted">Submitted</option>
            <option value="in_review">In Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="completed">Completed</option>
          </select>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="flex h-8 items-center rounded-full border px-3 text-[12px] outline-none"
            style={{ borderColor: "#EEEEEE", color: typeFilter ? "#1A1A1A" : "#515157" }}
          >
            <option value="">All Types</option>
            <option value="internal">Internal</option>
            <option value="external">External</option>
          </select>
          <select
            value={classification}
            onChange={(e) => setClassification(e.target.value)}
            className="flex h-8 items-center rounded-full border px-3 text-[12px] outline-none"
            style={{ borderColor: "#EEEEEE", color: classification ? "#1A1A1A" : "#515157" }}
          >
            <option value="">All Classifications</option>
            <option value="public">Public</option>
            <option value="internal">Internal</option>
            <option value="confidential">Confidential</option>
            <option value="sensitive">Sensitive</option>
            <option value="restricted">Restricted</option>
          </select>
          <select
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
            className="flex h-8 items-center rounded-full border px-3 text-[12px] outline-none"
            style={{ borderColor: "#EEEEEE", color: deptFilter ? "#1A1A1A" : "#515157" }}
          >
            <option value="">All Departments</option>
            {(groupsQuery.data ?? []).map((g) => (
              <option key={g.id} value={String(g.id)}>{g.name}</option>
            ))}
          </select>
          <div className="flex-1" />
          {!showPresetsRow && (
            <button
              type="button"
              onClick={() => setShowPresetsRow(true)}
              className="flex h-8 items-center gap-1.5 rounded-full border px-3 text-[12px] font-medium"
              style={{ borderColor: "#EEEEEE", color: "#515157" }}
            >
              <Filter className="h-3 w-3" />
              Presets
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowExport(true)}
            className="flex h-8 items-center gap-1.5 rounded-full border px-3 text-[12px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#515157" }}
          >
            <Download className="h-3 w-3" />
            Export
          </button>
          <span className="text-[12px]" style={{ color: "#9E9E9E" }}>{filtered.length} requests</span>
        </div>

        {/* Summary bar */}
        {filtered.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium" style={{ color: "#515157" }}>{filtered.length} total</span>
            <span style={{ color: "#EEEEEE" }}>·</span>
            {awaitingDpo > 0 && (
              <span className="text-xs font-medium" style={{ color: "#D76736" }}>
                {awaitingDpo} awaiting DPO review
              </span>
            )}
            {inProgress > 0 && (
              <>
                <span style={{ color: "#EEEEEE" }}>·</span>
                <span className="text-xs" style={{ color: "#9E9E9E" }}>{inProgress} in progress</span>
              </>
            )}
          </div>
        )}

        {/* Table */}
        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>REQUEST</span>
            <span className="w-[130px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>CLASSIFICATION</span>
            <span className="w-[130px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STATUS</span>
            <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>SLA</span>
            <span className="w-[130px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>CURRENT STEP</span>
            <span className="w-[80px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>DPO</span>
          </div>

          {requestsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">No requests match the current filters.</div>
          ) : (
            filtered.map((r, i) => {
              const style = STATUS_STYLE[r.status] ?? STATUS_STYLE.draft;
              const slaText = businessDaysLeft(r);
              const senderName = groupNameById.get(r.requester_group_id ?? 0) ?? "—";
              const isDpoAwaiting = r.status === "in_review";
              return (
                <Link
                  key={r.id}
                  href={`/dpo/${r.id}`}
                  className="flex h-[72px] items-center px-5 hover:bg-[#FFFBF9]"
                  style={{ borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined }}
                >
                  <div className="flex flex-1 flex-col gap-0.5">
                    <span className="truncate pr-4 text-[13px] font-semibold text-auth-text">{r.title}</span>
                    <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      {senderName} · {formatDate(r.created_at)}
                    </span>
                  </div>
                  <div className="w-[130px]">
                    <ClassificationBadge value={r.data_classification} />
                  </div>
                  <div className="w-[130px]">
                    <span
                      className="inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold"
                      style={{ backgroundColor: style.bg, color: style.color }}
                    >
                      {style.label}
                    </span>
                  </div>
                  <div className="w-[140px]">
                    {slaText ? (
                      <span
                        className="text-xs"
                        style={{ color: slaText === "Overdue" ? "#D32F2F" : "#515157" }}
                      >
                        {slaText}
                      </span>
                    ) : (
                      <span className="text-xs" style={{ color: "#BABABA" }}>—</span>
                    )}
                  </div>
                  <span className="w-[130px] truncate text-xs" style={{ color: "#515157" }}>
                    {isDpoAwaiting ? "DPO Review" : r.status === "approved" ? "Complete" : "Data Owner"}
                  </span>
                  <span className="w-[80px] text-xs" style={{ color: isDpoAwaiting ? "#D76736" : "#BABABA" }}>
                    {isDpoAwaiting ? "Pending" : "—"}
                  </span>
                </Link>
              );
            })
          )}
        </div>
      </div>

      {showExport && <ExportModal onClose={() => setShowExport(false)} filtered={filtered} activeFilterLabels={activeFilterLabels} />}
    </div>
  );
}
