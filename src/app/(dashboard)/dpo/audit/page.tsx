"use client";

import { ChevronDown, Download, Info, X } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import apiClient from "@/lib/api/client";
import { getAuditEvents } from "@/lib/api/platform/audit.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDateTime } from "@/lib/utils/formatters";

const PAGE_SIZE = 10;

const ACTION_STYLES: Record<string, { label: string; bg: string; color: string }> = {
  login:           { label: "login",         bg: "#F5F5F5", color: "#616161" },
  create:          { label: "create",        bg: "#F0FAF0", color: "#449235" },
  submit:          { label: "submit",        bg: "#EFF6FF", color: "#2563EB" },
  approve:         { label: "approve",       bg: "#F0FAF0", color: "#449235" },
  reject:          { label: "reject",        bg: "#FEF2F2", color: "#D32F2F" },
  cancel:          { label: "cancel",        bg: "#FEF2F2", color: "#D32F2F" },
  delete:          { label: "delete",        bg: "#FEF2F2", color: "#D32F2F" },
  upload:          { label: "upload",        bg: "#EFF6FF", color: "#2563EB" },
  download:        { label: "download",      bg: "#F5F0FF", color: "#7C3AED" },
  delegate:        { label: "delegate",      bg: "#FFF5F0", color: "#D76736" },
  "workflow-edit": { label: "workflow-edit", bg: "#F5F5F5", color: "#515157" },
  update:          { label: "update",        bg: "#FFF5F0", color: "#D76736" },
};

function actionStyleFromType(t: string) {
  if (ACTION_STYLES[t]) return ACTION_STYLES[t];
  const verb = t.split(".").pop() ?? t;
  const normalized = verb.replace(/ed$/, "e").replace(/ing$/, "");
  return ACTION_STYLES[normalized] ?? { label: verb, bg: "#F5F5F5", color: "#515157" };
}

function ActionBadge({ actionType }: { actionType: string }) {
  const s = actionStyleFromType(actionType);
  return (
    <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: s.bg, color: s.color }}>
      {s.label}
    </span>
  );
}

// ─── Filter chip ──────────────────────────────────────────────────

function TextChip({ placeholder, value, onChange }: { placeholder: string; value: string; onChange: (v: string) => void }) {
  const active = !!value;
  return (
    <div
      className="flex h-8 items-center rounded-full border bg-white"
      style={{ borderColor: active ? "#D76736" : "#EEEEEE" }}
    >
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-transparent pl-3 text-[12px] outline-none"
        style={{ color: active ? "#D76736" : "#515157", width: active ? 110 : 80 }}
      />
      {active ? (
        <button type="button" onClick={() => onChange("")} className="pr-2.5">
          <X className="h-3 w-3" style={{ color: "#D76736" }} />
        </button>
      ) : (
        <ChevronDown className="mr-2.5 h-3 w-3 shrink-0" style={{ color: "#9E9E9E" }} />
      )}
    </div>
  );
}

function SelectChip({
  placeholder,
  value,
  onChange,
  options,
}: {
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  const active = !!value;
  return (
    <div
      className="flex h-8 items-center rounded-full border bg-white pr-2.5"
      style={{ borderColor: active ? "#D76736" : "#EEEEEE" }}
    >
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none bg-transparent pl-3 text-[12px] outline-none"
        style={{ color: active ? "#D76736" : "#515157", minWidth: active ? 110 : 90 }}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {active ? (
        <button type="button" onClick={() => onChange("")}>
          <X className="h-3 w-3" style={{ color: "#D76736" }} />
        </button>
      ) : (
        <ChevronDown className="h-3 w-3 shrink-0" style={{ color: "#9E9E9E" }} />
      )}
    </div>
  );
}

function DateRangeChip({
  from, to, onFromChange, onToChange,
}: {
  from: string; to: string;
  onFromChange: (v: string) => void;
  onToChange: (v: string) => void;
}) {
  const active = !!(from || to);
  return (
    <div
      className="flex h-8 items-center gap-1 rounded-full border bg-white px-3"
      style={{ borderColor: active ? "#D76736" : "#EEEEEE" }}
    >
      {!active && <span className="text-[12px]" style={{ color: "#515157" }}>Date range</span>}
      <input
        type="date"
        value={from}
        onChange={(e) => onFromChange(e.target.value)}
        className="bg-transparent text-[12px] outline-none"
        style={{ color: from ? "#D76736" : "#9E9E9E", width: from ? 120 : (active ? 120 : 0), overflow: "hidden" }}
      />
      {active && <span className="text-[11px]" style={{ color: "#9E9E9E" }}>–</span>}
      <input
        type="date"
        value={to}
        onChange={(e) => onToChange(e.target.value)}
        className="bg-transparent text-[12px] outline-none"
        style={{ color: to ? "#D76736" : "#9E9E9E", width: to ? 120 : (active ? 120 : 0), overflow: "hidden" }}
      />
      {active && (
        <button type="button" onClick={() => { onFromChange(""); onToChange(""); }}>
          <X className="h-3 w-3" style={{ color: "#D76736" }} />
        </button>
      )}
      {!active && <ChevronDown className="h-3 w-3 shrink-0" style={{ color: "#9E9E9E" }} />}
    </div>
  );
}

// ─── Export modal ─────────────────────────────────────────────────

interface ExportModalProps {
  onClose: () => void;
  eventCount: number;
  activeFilters: { label: string }[];
  onExport: (format: "pdf" | "csv", fileName: string) => Promise<void>;
}

function ExportModal({ onClose, eventCount, activeFilters, onExport }: ExportModalProps) {
  const [format, setFormat] = useState<"pdf" | "csv">("pdf");
  const [fileName, setFileName] = useState(`audit-log-${new Date().toISOString().slice(0, 10)}.pdf`);
  const [exporting, setExporting] = useState(false);

  function handleFormatChange(f: "pdf" | "csv") {
    setFormat(f);
    setFileName((prev) => prev.replace(/\.(pdf|csv)$/, `.${f}`));
  }

  async function handleExport() {
    setExporting(true);
    try {
      await onExport(format, fileName);
      onClose();
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "#07070966" }}>
      <div className="flex w-[480px] flex-col gap-5 rounded-xl p-6" style={{ backgroundColor: "#FFFFFF", boxShadow: "0 24px 64px #00000026" }}>
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-auth-text">Export Audit Log</h2>
          <button type="button" onClick={onClose}><X className="h-4 w-4" style={{ color: "#9E9E9E" }} /></button>
        </div>

        <p className="text-[13px]" style={{ color: "#616161" }}>
          Exporting the currently filtered view. Review the scope below before downloading.
        </p>

        {/* Active filters summary */}
        <div className="flex flex-col gap-2 rounded-md px-4 py-3" style={{ backgroundColor: "#FFF5F0", border: "1px solid #FFCDB8" }}>
          <p className="text-[12px] font-semibold" style={{ color: "#D76736" }}>
            Action filters — {eventCount} event{eventCount !== 1 ? "s" : ""} will be exported
          </p>
          <div className="flex flex-wrap gap-1.5">
            {activeFilters.map((f, i) => (
              <span key={i} className="rounded-full px-2.5 py-0.5 text-[11px] font-medium" style={{ backgroundColor: "#FFFFFF", color: "#D76736", border: "1px solid #FFCDB8" }}>
                {f.label}
              </span>
            ))}
          </div>
        </div>

        {/* Format */}
        <div className="flex flex-col gap-2">
          <span className="text-[12px] font-semibold text-auth-text">Export format</span>
          <div className="flex gap-3">
            {(["pdf", "csv"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => handleFormatChange(f)}
                className="flex h-9 items-center gap-2 rounded-md border px-4 text-[13px] font-medium"
                style={{
                  borderColor: format === f ? "#D76736" : "#EEEEEE",
                  color: format === f ? "#D76736" : "#616161",
                  backgroundColor: format === f ? "#FFF5F0" : "#FFFFFF",
                }}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* File name */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-semibold text-auth-text">File name (optional)</label>
          <input
            value={fileName}
            onChange={(e) => setFileName(e.target.value)}
            className="h-9 rounded-md border px-3 text-[12px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          />
        </div>

        <div className="flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} className="flex h-9 items-center rounded-md border px-4 text-[13px]" style={{ borderColor: "#EEEEEE", color: "#515157" }}>
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
            {exporting ? "Exporting…" : "Export"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────

const ACTION_OPTIONS = [
  { value: "login", label: "Login" },
  { value: "create", label: "Create" },
  { value: "submit", label: "Submit" },
  { value: "approve", label: "Approve" },
  { value: "reject", label: "Reject" },
  { value: "cancel", label: "Cancel" },
  { value: "delete", label: "Delete" },
  { value: "upload", label: "Upload" },
  { value: "download", label: "Download" },
  { value: "delegate", label: "Delegate" },
  { value: "workflow-edit", label: "Workflow edit" },
];

export default function AuditTrailPage() {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin", "org_admin"] });

  const [page, setPage] = useState(1);
  const [requestFilter, setRequestFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [actionType, setActionType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [showExportModal, setShowExportModal] = useState(false);

  const hasFilters = !!(requestFilter || actorFilter || actionType || dateFrom || dateTo);

  const eventsQuery = useQuery({
    queryKey: ["platform", "audit", { page, requestFilter, actorFilter, actionType, dateFrom, dateTo }],
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
  const total = pagination?.total ?? events.length;
  const totalPages = pagination?.total_pages ?? 1;

  const filtered = events.filter((e) => {
    if (requestFilter && !`${e.target_type ?? ""} ${e.target_id ?? ""}`.toLowerCase().includes(requestFilter.toLowerCase())) return false;
    if (actorFilter && !(e.actor_email ?? "").toLowerCase().includes(actorFilter.toLowerCase())) return false;
    return true;
  });

  const clearFilters = () => {
    setRequestFilter(""); setActorFilter(""); setActionType(""); setDateFrom(""); setDateTo(""); setPage(1);
  };

  const activeFilterLabels = [
    requestFilter && { label: `Request: ${requestFilter}` },
    actorFilter && { label: `Actor: ${actorFilter}` },
    actionType && { label: `Action type: ${actionType}` },
    (dateFrom || dateTo) && { label: `Date: ${dateFrom || "…"} – ${dateTo || "…"}` },
  ].filter(Boolean) as { label: string }[];

  const exportAuditLog = async (format: "pdf" | "csv", fileName: string) => {
    const res = await apiClient.get("/api/v1/platform/audit/export", {
      params: { format, action_type: actionType || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined },
      responseType: "blob",
    });
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Pagination numbers
  const pageNumbers: (number | "...")[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pageNumbers.push(i);
  } else {
    pageNumbers.push(1, 2, 3);
    if (page > 4) pageNumbers.push("...");
    if (page > 3 && page < totalPages - 2) pageNumbers.push(page);
    if (page < totalPages - 3) pageNumbers.push("...");
    pageNumbers.push(totalPages);
  }

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div className="flex h-16 shrink-0 items-center justify-between px-8" style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Audit Trail</h1>
          <span className="rounded px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}>DPO</span>
          <span className="rounded px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: "#F5F5F5", color: "#515157" }}>Data Sharing</span>
        </div>
        <div className="flex items-center gap-3">
          {total > 0 && <span className="text-[13px]" style={{ color: "#9E9E9E" }}>{total} events</span>}
          {hasFilters && (
            <button type="button" onClick={clearFilters} className="text-[13px]" style={{ color: "#9E9E9E" }}>
              Clear filters
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowExportModal(true)}
            className="flex h-9 items-center gap-2 rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            <Download className="h-3.5 w-3.5" />
            Export
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* Filter chips */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-medium" style={{ color: "#515157" }}>Filter</span>
          <TextChip placeholder="Request" value={requestFilter} onChange={(v) => { setRequestFilter(v); setPage(1); }} />
          <TextChip placeholder="Actor" value={actorFilter} onChange={(v) => { setActorFilter(v); setPage(1); }} />
          <SelectChip
            placeholder="Action type"
            value={actionType}
            onChange={(v) => { setActionType(v); setPage(1); }}
            options={ACTION_OPTIONS}
          />
          <DateRangeChip
            from={dateFrom} to={dateTo}
            onFromChange={(v) => { setDateFrom(v); setPage(1); }}
            onToChange={(v) => { setDateTo(v); setPage(1); }}
          />
        </div>

        {/* Append-only banner */}
        <div className="flex items-center gap-2 rounded-md px-4 py-2" style={{ backgroundColor: "#F5F5F5", border: "1px solid #E8E8E8" }}>
          <Info className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
          <p className="text-[12px]" style={{ color: "#616161" }}>
            Append-only · regulatory log — entries cannot be added or deleted
          </p>
        </div>

        {/* Table */}
        <div className="flex flex-col overflow-hidden rounded-lg" style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}>
          <div className="flex h-10 shrink-0 items-center px-5" style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}>
            <span className="w-[160px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>TIMESTAMP</span>
            <span className="w-[180px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ACTOR</span>
            <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ACTION</span>
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>TARGET OBJECT/DETAILS</span>
          </div>

          {eventsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : eventsQuery.isError ? (
            <div className="py-20 text-center text-sm text-red-600">Failed to load audit events.</div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">No events match the current filters.</div>
          ) : (
            filtered.map((e, i) => (
              <div
                key={e.id}
                className="flex min-h-[52px] items-start px-5 py-3"
                style={{ borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined }}
              >
                <span className="w-[160px] shrink-0 text-[12px]" style={{ color: "#9E9E9E" }}>{formatDateTime(e.created_at)}</span>
                <span className="w-[180px] shrink-0 text-[12px]" style={{ color: "#1A1A1A" }}>{e.actor_email ?? "system"}</span>
                <div className="w-[140px] shrink-0"><ActionBadge actionType={e.action_type} /></div>
                <div className="flex-1">
                  <span className="text-[12px]" style={{ color: "#515157" }}>
                    {e.target_type && e.target_id ? `${e.target_type} ${e.target_id}` : e.target_type ?? e.target_id ?? "—"}
                  </span>
                  {(e as { details?: string }).details && (
                    <p className="mt-0.5 text-[11px]" style={{ color: "#9E9E9E" }}>{(e as { details?: string }).details}</p>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Footer */}
          {!eventsQuery.isLoading && !eventsQuery.isError && (
            <div className="flex h-10 items-center justify-between px-5" style={{ borderTop: "1px solid #F5F5F5" }}>
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>Showing {filtered.length} of {total} events</span>
              {totalPages > 1 && (
                <div className="flex items-center gap-1">
                  <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="px-2 text-[12px] disabled:opacity-40" style={{ color: "#515157" }}>← Prev</button>
                  {pageNumbers.map((n, idx) =>
                    n === "..." ? (
                      <span key={`e-${idx}`} className="px-1 text-[12px]" style={{ color: "#9E9E9E" }}>…</span>
                    ) : (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setPage(n as number)}
                        className="flex h-7 w-7 items-center justify-center rounded text-[12px]"
                        style={{ backgroundColor: page === n ? "#D76736" : "transparent", color: page === n ? "#FFFFFF" : "#515157" }}
                      >
                        {n}
                      </button>
                    )
                  )}
                  <button type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="px-2 text-[12px] disabled:opacity-40" style={{ color: "#515157" }}>Next →</button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {showExportModal && (
        <ExportModal
          onClose={() => setShowExportModal(false)}
          eventCount={filtered.length || total}
          activeFilters={activeFilterLabels}
          onExport={exportAuditLog}
        />
      )}
    </div>
  );
}
