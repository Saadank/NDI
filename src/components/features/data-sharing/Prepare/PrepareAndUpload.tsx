"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Database,
  FileText,
  Loader2,
  Lock,
  MessageSquare,
  RotateCcw,
  UploadCloud,
  X,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { del, get, post } from "@/lib/api/client";
import { uploadFileForRequest } from "@/lib/api/products/data-sharing/files.api";
import { useDeleteFile, useRequestFiles } from "@/lib/hooks/data-sharing/useFiles";
import { useRequestDetail } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useConnection } from "@/lib/hooks/data-sharing/useConnections";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate } from "@/lib/utils/formatters";
import type { FileStatus, RequestFile } from "@/lib/types/data-sharing/file.types";
import type { ShareRequest } from "@/lib/types/data-sharing/request.types";

// ─── Export types ─────────────────────────────────────────────────────────────

type ExportPhase = "idle" | "running" | "preview" | "scope_warning";

interface ExportJob {
  job_id: string;
  status: "running" | "done" | "error";
  row_count?: number;
  file_size_mb?: number;
  exported_at?: string;
  preview_columns?: string[];
  preview_rows?: Record<string, string | number>[];
  approved_row_estimate?: number;
  scope_ratio?: number;
  error?: string;
}

// ─── Scan status chip ─────────────────────────────────────────────────────────

function ScanChip({ status }: { status: FileStatus }) {
  if (status === "scanning") {
    return (
      <span className="flex items-center gap-1 text-[11px] font-medium" style={{ color: "#B45309" }}>
        <Loader2 className="h-3 w-3 animate-spin" />
        Scanning for viruses
      </span>
    );
  }
  if (status === "clean") {
    return (
      <span className="flex items-center gap-1 text-[11px] font-medium" style={{ color: "#449235" }}>
        <CheckCircle2 className="h-3 w-3" />
        Scanned clean
      </span>
    );
  }
  return (
    <span className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>
      Queued
    </span>
  );
}

// ─── File row ─────────────────────────────────────────────────────────────────

function formatSize(bytes: number): string {
  if (bytes === 0) return "";
  const mb = bytes / (1024 * 1024);
  return mb >= 0.1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}

function FileRow({
  f,
  onDelete,
  onReplace,
}: {
  f: RequestFile;
  onDelete: () => void;
  onReplace: () => void;
}) {
  const isInfected = f.status === "infected" || f.status === "failed";

  if (isInfected) {
    return (
      <div
        className="flex items-start gap-3 px-5 py-3"
        style={{ backgroundColor: "#FFF0F0", borderBottom: "1px solid #F5F5F5" }}
      >
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#D32F2F" }} />
        <div className="flex flex-1 flex-col gap-2">
          <div className="flex items-center justify-between gap-4">
            <span className="text-[13px] font-medium" style={{ color: "#D32F2F" }}>
              {f.original_filename}
            </span>
            <span
              className="shrink-0 rounded px-2 py-0.5 text-[11px] font-semibold"
              style={{ backgroundColor: "#FEE2E2", color: "#D32F2F" }}
            >
              Scan Failed
            </span>
          </div>
          <p className="text-[12px]" style={{ color: "#991B1B" }}>
            Virus detected — this file cannot be shared with the requester. Remove it or replace with
            a clean copy.
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onDelete}
              className="flex h-7 items-center rounded-md px-3 text-[12px] font-semibold text-white"
              style={{ backgroundColor: "#D32F2F" }}
            >
              Remove file
            </button>
            <button
              type="button"
              onClick={onReplace}
              className="flex h-7 items-center rounded-md border px-3 text-[12px] font-medium"
              style={{ borderColor: "#D32F2F", color: "#D32F2F" }}
            >
              Replace
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-3 px-5 py-3"
      style={{ borderBottom: "1px solid #F5F5F5" }}
    >
      <FileText className="h-4 w-4 shrink-0" style={{ color: "#9E9E9E" }} />
      <span className="flex-1 text-[13px] font-medium" style={{ color: "#1A1A1A" }}>
        {f.original_filename}
      </span>
      <div className="flex items-center gap-3">
        <ScanChip status={f.status} />
        {f.file_size_bytes > 0 && (
          <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
            {formatSize(f.file_size_bytes)}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={onDelete}
        className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#F5F5F5]"
        aria-label="Remove file"
      >
        <X className="h-3.5 w-3.5" style={{ color: "#9E9E9E" }} />
      </button>
    </div>
  );
}

// ─── InfoRow helper ───────────────────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>{label}</span>
      <span className="text-[13px]" style={{ color: "#515157" }}>{value || "—"}</span>
    </div>
  );
}

// ─── Structured export panel ──────────────────────────────────────────────────

function formatElapsed(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function StructuredExportPanel({
  id,
  r,
  qc,
}: {
  id: string;
  r: ShareRequest;
  qc: ReturnType<typeof useQueryClient>;
}) {
  const [phase, setPhase] = useState<ExportPhase>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<ExportJob | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const connectionQuery = useConnection(r.connection_id ?? "");
  const conn = connectionQuery.data;
  const connLabel = conn
    ? `${conn.db_type.charAt(0).toUpperCase() + conn.db_type.slice(1)} — ${conn.description ?? conn.database ?? conn.host}`
    : r.connection_id ?? "—";

  useEffect(() => {
    if (phase !== "running") { setElapsed(0); return; }
    const t = setInterval(() => setElapsed((p) => p + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  const statusQuery = useQuery({
    queryKey: ["export-status", id, jobId],
    queryFn: () => get<ExportJob>(`/api/v1/products/data-sharing/requests/${id}/export/${jobId}`),
    enabled: phase === "running" && jobId !== null,
    refetchInterval: 3000,
  });

  useEffect(() => {
    if (statusQuery.data?.status === "done") {
      const job = statusQuery.data;
      const estimate = job.approved_row_estimate ?? 0;
      const count = job.row_count ?? 0;
      const overScope = estimate > 0 && count > estimate * 1.5;
      setResult(job);
      setPhase(overScope ? "scope_warning" : "preview");
    }
  }, [statusQuery.data]);

  const runMutation = useMutation({
    mutationFn: () =>
      post<{ job_id: string }>(`/api/v1/products/data-sharing/requests/${id}/export`),
    onSuccess: (data) => {
      setJobId(data.job_id);
      setPhase("running");
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () =>
      del(`/api/v1/products/data-sharing/requests/${id}/export/${jobId}`),
    onSuccess: () => {
      setPhase("idle");
      setJobId(null);
    },
  });

  const submitMutation = useMutation({
    mutationFn: () => post(`/api/v1/products/data-sharing/requests/${id}/deliver`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["data-sharing", "request", id] });
    },
  });

  const previewColumns = result?.preview_columns ?? [];
  const previewRows = result?.preview_rows ?? [];
  const rowCount = result?.row_count ?? 0;
  const fileSizeMb = result?.file_size_mb ?? 0;
  const exportedAt = result?.exported_at ?? "";
  const scopeRatio = result?.scope_ratio ?? 1;
  const approvedEstimate = result?.approved_row_estimate ?? 0;

  return (
    <div className="flex flex-col gap-4 overflow-auto px-8 py-6">
      {/* Approved Selection — read-only */}
      <div
        className="flex flex-col overflow-hidden rounded-lg"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div
          className="flex h-11 items-center gap-2 px-5"
          style={{ borderBottom: "1px solid #EEEEEE", backgroundColor: "#FAFAFA" }}
        >
          <Lock className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
          <span className="text-[13px] font-semibold text-auth-text">
            Approved Selection — read-only, you may not modify this
          </span>
        </div>
        <div className="flex flex-col gap-4 p-5">
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>Connection</span>
            <span className="text-[13px] font-medium" style={{ color: "#515157" }}>{connLabel}</span>
          </div>
          {r.selection_mode === "query" && r.custom_sql ? (
            <pre
              className="overflow-x-auto rounded-md p-4 font-mono text-[12px] leading-relaxed"
              style={{ backgroundColor: "#1E1E2E", color: "#D4D4D4" }}
            >
              {r.custom_sql}
            </pre>
          ) : r.selection_mode === "tables" && r.selected_items ? (
            <div className="flex flex-wrap gap-2">
              {r.selected_items.map((it, i) => (
                <span
                  key={i}
                  className="rounded px-2.5 py-1 font-mono text-[12px]"
                  style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
                >
                  {[it.schema, it.table].filter(Boolean).join(".")}
                </span>
              ))}
            </div>
          ) : null}
          <div className="flex gap-8">
            {(r.estimated_data_subjects ?? 0) > 0 && (
              <InfoRow
                label="Row estimate"
                value={`~${(r.estimated_data_subjects ?? 0).toLocaleString()} rows (approved estimate)`}
              />
            )}
            {r.legal_basis && (
              <InfoRow
                label="Legal basis"
                value={r.legal_basis.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              />
            )}
          </div>
        </div>
      </div>

      {/* Run Export / Export Preview card */}
      <div
        className="flex flex-col overflow-hidden rounded-lg"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div
          className="flex h-11 items-center px-5"
          style={{
            borderBottom: "1px solid #EEEEEE",
            backgroundColor: phase === "scope_warning" ? "#FFFBEB" : "#FAFAFA",
          }}
        >
          <span className="text-[13px] font-semibold text-auth-text">
            {phase === "idle" || phase === "running"
              ? "Run Export"
              : phase === "scope_warning"
                ? "Export Preview — Scope Warning"
                : "Export Preview"}
          </span>
        </div>
        <div className="flex flex-col gap-4 p-5">
          {phase === "idle" && (
            <>
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 shrink-0" style={{ color: "#449235" }} />
                <span className="text-[13px] font-medium" style={{ color: "#515157" }}>
                  Connected to {connLabel}
                </span>
              </div>
              <p className="text-[13px]" style={{ color: "#9E9E9E" }}>
                Running the approved query will export approximately{" "}
                {approvedEstimate > 0
                  ? `${approvedEstimate.toLocaleString()} rows`
                  : "the selected data"}
                . Actual row count may vary slightly from the estimate.
              </p>
              {runMutation.isError && (
                <p className="text-xs" style={{ color: "#D32F2F" }}>
                  {runMutation.error instanceof Error ? runMutation.error.message : "Failed to start export."}
                </p>
              )}
              <div>
                <button
                  type="button"
                  onClick={() => runMutation.mutate()}
                  disabled={runMutation.isPending}
                  className="flex h-9 items-center gap-2 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-50"
                  style={{ backgroundColor: "#D76736" }}
                >
                  {runMutation.isPending ? (
                    <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Starting…</>
                  ) : (
                    "Run export"
                  )}
                </button>
              </div>
            </>
          )}
          {phase === "running" && (
            <>
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin shrink-0" style={{ color: "#D76736" }} />
                <span className="text-[13px] font-semibold text-auth-text">
                  Exporting data from {connLabel}…
                </span>
              </div>
              <p className="text-[12px]" style={{ color: "#9E9E9E" }}>
                Running approved query · Elapsed: {formatElapsed(elapsed)} · Estimated: 2–5 min
              </p>
              <div>
                <button
                  type="button"
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                  className="flex h-8 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium disabled:opacity-50"
                  style={{ borderColor: "#EEEEEE", color: "#616161" }}
                >
                  <X className="h-3.5 w-3.5" />
                  {cancelMutation.isPending ? "Cancelling…" : "Cancel export"}
                </button>
              </div>
            </>
          )}
          {(phase === "preview" || phase === "scope_warning") && result && (
            <>
              <div
                className="flex items-center gap-3 rounded-lg px-4 py-3"
                style={{
                  backgroundColor: phase === "scope_warning" ? "#FFFBEB" : "#F0FAF0",
                  border: `1px solid ${phase === "scope_warning" ? "#FDE68A" : "#BBF7D0"}`,
                }}
              >
                {phase === "preview" ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: "#449235" }} />
                ) : (
                  <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: "#D97706" }} />
                )}
                <p className="flex-1 text-[13px]" style={{ color: phase === "scope_warning" ? "#92400E" : "#14532D" }}>
                  <strong>{rowCount.toLocaleString()} rows returned</strong>
                  {fileSizeMb > 0 && ` · ${fileSizeMb.toFixed(1)} MB`}
                  {exportedAt && ` · Exported ${new Date(exportedAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`}
                  {phase === "preview" && " · First 100 rows shown below"}
                  {phase === "scope_warning" && (
                    <span className="ml-2 font-semibold">↑ {Math.round(scopeRatio)}× over approved scope</span>
                  )}
                </p>
              </div>
              {phase === "scope_warning" && (
                <div
                  className="flex items-start gap-3 rounded-lg px-4 py-3"
                  style={{ backgroundColor: "#FFFBEB", border: "1px solid #FDE68A" }}
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#D97706" }} />
                  <div className="flex flex-col gap-0.5">
                    <p className="text-[13px] font-semibold" style={{ color: "#92400E" }}>
                      Scope mismatch — {Math.round(scopeRatio)}× more rows than approved!
                    </p>
                    <p className="text-[12px]" style={{ color: "#78350F" }}>
                      The approved estimate was ~{approvedEstimate.toLocaleString()} rows but{" "}
                      {rowCount.toLocaleString()} rows were returned. Submitting without raising an
                      issue may violate the data sharing agreement.
                    </p>
                  </div>
                </div>
              )}
              {previewColumns.length > 0 && (
                <div className="overflow-hidden rounded-lg" style={{ border: "1px solid #EEEEEE" }}>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[12px]">
                      <thead>
                        <tr style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}>
                          {previewColumns.map((col) => (
                            <th key={col} className="px-4 py-2.5 font-semibold tracking-[0.4px] uppercase text-[11px]" style={{ color: "#9E9E9E" }}>
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewRows.map((row, i) => (
                          <tr key={i} style={{ borderBottom: i < previewRows.length - 1 ? "1px solid #F5F5F5" : undefined }}>
                            {previewColumns.map((col) => (
                              <td key={col} className="px-4 py-2.5" style={{ color: "#515157" }}>
                                {String(row[col] ?? "")}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {rowCount > previewRows.length && (
                    <div className="flex items-center px-4 py-2.5" style={{ borderTop: "1px solid #EEEEEE", backgroundColor: "#FAFAFA" }}>
                      <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                        ↕ {(rowCount - previewRows.length).toLocaleString()} more rows not shown
                      </span>
                    </div>
                  )}
                </div>
              )}
              <div className="flex items-center justify-between pt-1">
                <button
                  type="button"
                  onClick={() => { setPhase("idle"); setResult(null); setJobId(null); }}
                  className="flex items-center gap-1.5 text-[13px] font-medium"
                  style={{ color: "#616161" }}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Re-run export
                </button>
                <button
                  type="button"
                  onClick={() => submitMutation.mutate()}
                  disabled={submitMutation.isPending}
                  className="flex h-9 items-center gap-2 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-50"
                  style={{ backgroundColor: "#D76736" }}
                >
                  {submitMutation.isPending ? "Submitting…" : phase === "scope_warning" ? (
                    <><AlertTriangle className="h-3.5 w-3.5" /> Submit anyway</>
                  ) : "Submit to Requester →"}
                </button>
              </div>
              {submitMutation.isError && (
                <p className="text-xs" style={{ color: "#D32F2F" }}>
                  {submitMutation.error instanceof Error ? submitMutation.error.message : "Submit failed."}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function PrepareAndUpload({ id }: { id: string }) {
  const { isReady } = useRoleGuard({ allow: ["requester", "data_owner"] });
  const reqQuery = useRequestDetail(id);
  const filesQuery = useRequestFiles(id);
  const groupsQuery = useGroups();
  const qc = useQueryClient();
  const deleteFile = useDeleteFile(id);
  const inputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const submitMutation = useMutation({
    mutationFn: () => post(`/api/v1/products/data-sharing/requests/${id}/deliver`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["data-sharing", "request", id] });
    },
  });

  if (!isReady) return null;

  if (reqQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm" style={{ color: "#9E9E9E" }}>Loading…</p>
      </div>
    );
  }
  if (reqQuery.isError || !reqQuery.data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm" style={{ color: "#EF4444" }}>Failed to load request.</p>
      </div>
    );
  }

  const r = reqQuery.data;
  const files = filesQuery.data ?? [];
  const cleanFiles = files.filter((f) => f.status === "clean");
  const pendingFiles = files.filter(
    (f) => f.status === "scanning" || f.status === "uploaded" || f.status === "pending_upload",
  );
  const blockerFiles = files.filter((f) => f.status === "infected" || f.status === "failed");
  const canSubmit =
    files.length > 0 && cleanFiles.length > 0 && pendingFiles.length === 0 && blockerFiles.length === 0;

  const groupNameById = new Map<number, string>();
  for (const g of groupsQuery.data ?? []) groupNameById.set(g.id, g.name);
  const receiverGroupName = r.receiver_group_id ? groupNameById.get(r.receiver_group_id) : null;

  const handlePicked = async (fileList: FileList | null) => {
    if (!fileList) return;
    setUploadError(null);
    setUploading(true);
    try {
      for (const f of Array.from(fileList)) {
        await uploadFileForRequest(id, f);
      }
      await filesQuery.refetch();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const legalBasisLabel = r.legal_basis
    ? r.legal_basis.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : null;

  const deliveryLabel = r.delivery_channel
    ? r.delivery_channel.charAt(0).toUpperCase() + r.delivery_channel.slice(1)
    : null;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <h1 className="text-lg font-bold text-auth-text">Prepare &amp; Upload</h1>
        <Link
          href="/prepare"
          className="flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs font-medium"
          style={{ borderColor: "#EEEEEE", color: "#616161" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to list
        </Link>
      </div>

      {/* Orange info banner */}
      <div
        className="flex shrink-0 items-start gap-2 px-8 py-3"
        style={{ backgroundColor: "#FFF5F0", borderBottom: "1px solid #FFCDB8" }}
      >
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#D76736" }} />
        <p className="text-[13px]" style={{ color: "#D76736" }}>
          <strong>You have been asked to provide data for this request!</strong>{" "}
          Review the approved selection below,{" "}
          {r.data_type === "structured"
            ? "run the export query,"
            : "upload the required files,"}{" "}
          then submit to the requester.
        </p>
      </div>

      {/* Structured mode */}
      {r.data_type === "structured" ? (
        <>
          <StructuredExportPanel id={id} r={r} qc={qc} />
          <div
            className="flex shrink-0 items-center justify-center px-8 py-4"
            style={{ borderTop: "1px solid #EEEEEE" }}
          >
            <button
              type="button"
              className="flex items-center gap-1.5 text-[13px]"
              style={{ color: "#9E9E9E" }}
            >
              <MessageSquare className="h-3.5 w-3.5" />
              Raise an issue
            </button>
          </div>
        </>
      ) : (
        /* ── File upload mode — single column ─────────────────────────── */
        <>
          <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
            {/* Request info card */}
            <div
              className="flex flex-col gap-2 rounded-lg p-4"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                {r.request_number}
                {receiverGroupName ? ` · ${receiverGroupName} workstream` : ""}
              </span>
              <div className="flex items-start justify-between gap-4">
                <h2 className="text-[15px] font-bold text-auth-text">{r.title}</h2>
                <span
                  className="shrink-0 rounded-full px-3 py-1 text-[11px] font-semibold"
                  style={{ backgroundColor: "#F0FAF0", color: "#449235" }}
                >
                  Approved · Awaiting Upload
                </span>
              </div>
              <span className="text-[12px]" style={{ color: "#9E9E9E" }}>
                Raised {formatDate(r.created_at)}
              </span>
            </div>

            {/* Approved Selection card */}
            <div
              className="flex flex-col overflow-hidden rounded-lg"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div
                className="flex h-11 items-center gap-2 px-5"
                style={{ borderBottom: "1px solid #EEEEEE", backgroundColor: "#FAFAFA" }}
              >
                <Lock className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
                <span className="text-[13px] font-semibold text-auth-text">
                  Approved Selection — read-only, you may not modify this
                </span>
              </div>
              <div className="flex flex-col gap-4 p-5">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>Click scope</span>
                  <span className="text-[13px]" style={{ color: "#515157" }}>{r.purpose || "—"}</span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {legalBasisLabel && (
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>Legal basis</span>
                      <span className="text-[13px]" style={{ color: "#515157" }}>{legalBasisLabel}</span>
                    </div>
                  )}
                  {deliveryLabel && (
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>Delivery format</span>
                      <span className="text-[13px]" style={{ color: "#515157" }}>{deliveryLabel}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Upload Files section */}
            <div
              className="flex flex-col overflow-hidden rounded-lg"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div
                className="flex h-11 shrink-0 items-center px-5"
                style={{ borderBottom: "1px solid #EEEEEE" }}
              >
                <span className="text-[13px] font-semibold text-auth-text">Upload Files</span>
              </div>

              {/* Hidden file input (always rendered once) */}
              <input
                ref={inputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => void handlePicked(e.target.files)}
              />

              {/* Dropzone (shown when no files) */}
              {files.length === 0 && (
                <div
                  className="flex flex-col items-center gap-3 py-12 cursor-pointer"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => { e.preventDefault(); void handlePicked(e.dataTransfer.files); }}
                  onClick={() => inputRef.current?.click()}
                >
                  <UploadCloud className="h-8 w-8" style={{ color: "#BABABA" }} />
                  <div className="flex flex-col items-center gap-1 text-center">
                    <span className="text-[13px] font-medium" style={{ color: "#515157" }}>
                      Drag files here or click to browse
                    </span>
                    <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      Supports CSV, XLSX, JSON, PDF — Max 5 MB per file
                    </span>
                  </div>
                </div>
              )}

              {/* File list */}
              {files.map((f) => (
                <FileRow
                  key={f.id}
                  f={f}
                  onDelete={() => deleteFile.mutate(f.id)}
                  onReplace={() => inputRef.current?.click()}
                />
              ))}

              {/* Add more files (once files exist) */}
              {files.length > 0 && (
                <div className="px-5 py-3" style={{ borderTop: "1px solid #F5F5F5" }}>
                  <button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    disabled={uploading}
                    className="text-[12px] font-medium disabled:opacity-50"
                    style={{ color: "#D76736" }}
                  >
                    {uploading ? "Uploading…" : "+ Add more files"}
                  </button>
                </div>
              )}

              <div className="px-5 py-2" style={{ borderTop: "1px solid #F5F5F5" }}>
                <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
                  Files are virus-scanned before being shared with the requester.
                </p>
              </div>
            </div>

            {uploadError && (
              <div
                className="rounded-md px-4 py-3 text-xs"
                style={{ backgroundColor: "#FEF2F2", border: "1px solid #FCA5A5", color: "#991B1B" }}
              >
                {uploadError}
              </div>
            )}

            {/* All clean banner */}
            {canSubmit && (
              <div
                className="flex items-center gap-3 rounded-lg px-4 py-3"
                style={{ backgroundColor: "#F0FAF0", border: "1px solid #BBF7D0" }}
              >
                <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: "#449235" }} />
                <p className="text-[13px]" style={{ color: "#14532D" }}>
                  All files uploaded and scanned cleanly. Submitting will mark this request as
                  Completed and notify the requester.
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div
            className="flex shrink-0 items-center justify-between px-8 py-4"
            style={{ borderTop: "1px solid #EEEEEE", backgroundColor: "#FFFFFF" }}
          >
            <button
              type="button"
              className="flex items-center gap-1.5 text-[13px]"
              style={{ color: "#9E9E9E" }}
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              Raise an issue
            </button>
            <button
              type="button"
              onClick={() => submitMutation.mutate()}
              disabled={!canSubmit || submitMutation.isPending}
              className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-40"
              style={{ backgroundColor: "#D76736" }}
            >
              {submitMutation.isPending ? "Submitting…" : "Submit to Requester →"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
