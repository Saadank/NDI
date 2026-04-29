"use client";

import Link from "next/link";
import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useRequestDetail } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useRequestFiles } from "@/lib/hooks/data-sharing/useFiles";
import { useApprovalSteps } from "@/lib/hooks/data-sharing/useApprovalSteps";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { cancelRequest } from "@/lib/api/products/data-sharing/requests.api";
import { getDownloadUrl } from "@/lib/api/products/data-sharing/files.api";
import { REQUEST_STATUS_LABELS } from "@/lib/utils/constants";
import { formatDate, formatBytes, formatRelativeTime } from "@/lib/utils/formatters";
import type { RequestStatus } from "@/lib/types/data-sharing/request.types";
import type { StepStatus } from "@/lib/types/data-sharing/step.types";

export interface RequestDetailProps {
  id: string;
}

// ─── Status badge ─────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<RequestStatus, { bg: string; color: string }> = {
  draft:             { bg: "#EEEEEE", color: "#616161" },
  submitted:         { bg: "#EEF2FF", color: "#3B4FD6" },
  in_review:         { bg: "#FFF7E6", color: "#B45309" },
  approved:          { bg: "#F0FAF0", color: "#449235" },
  rejected:          { bg: "#FFF0F0", color: "#D32F2F" },
  changes_requested: { bg: "#FFFBEB", color: "#B45309" },
  cancelled:         { bg: "#F5F5F5", color: "#9E9E9E" },
  completed:         { bg: "#F0FAF0", color: "#449235" },
  expired:           { bg: "#F5F5F5", color: "#9E9E9E" },
};

function StatusBadge({ status }: { status: RequestStatus }) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.draft;
  return (
    <span
      className="inline-flex items-center rounded px-2.5 py-0.5 text-xs font-medium"
      style={{ backgroundColor: s.bg, color: s.color }}
    >
      {REQUEST_STATUS_LABELS[status] ?? status}
    </span>
  );
}

// ─── Field row ────────────────────────────────────────────────────────────────

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      className="flex min-h-[34px] items-center gap-2 py-1"
      style={{ borderBottom: "1px solid #F5F5F5" }}
    >
      <span className="w-[180px] shrink-0 text-[11px]" style={{ color: "#9E9E9E" }}>
        {label}
      </span>
      <span className="flex-1 text-xs font-medium" style={{ color: "#1A1A1A" }}>
        {value || <span style={{ color: "#BABABA" }}>—</span>}
      </span>
    </div>
  );
}

// ─── Step bubble ─────────────────────────────────────────────────────────────

const STEP_STATUS_STYLE: Record<StepStatus, { bg: string; color: string }> = {
  pending:           { bg: "#EEEEEE", color: "#9E9E9E" },
  in_progress:       { bg: "#D76736", color: "#FFFFFF" },
  approved:          { bg: "#449235", color: "#FFFFFF" },
  rejected:          { bg: "#D32F2F", color: "#FFFFFF" },
  changes_requested: { bg: "#B45309", color: "#FFFFFF" },
  flagged:           { bg: "#1D4ED8", color: "#FFFFFF" },
  skipped:           { bg: "#EEEEEE", color: "#9E9E9E" },
};

// ─── Download button ──────────────────────────────────────────────────────────

function DownloadButton({ fileId, filename }: { fileId: string; filename: string }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const { download_url } = await getDownloadUrl(fileId);
      window.open(download_url, "_blank");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className="text-[13px] font-medium disabled:opacity-50"
      style={{ color: "#D76736" }}
    >
      {loading ? "…" : "Download"}
    </button>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function RequestDetail({ id }: RequestDetailProps) {
  const { isReady } = useRoleGuard();
  const qc = useQueryClient();
  const reqQuery = useRequestDetail(id);
  const filesQuery = useRequestFiles(id);
  const stepsQuery = useApprovalSteps(id);

  const cancelMutation = useMutation({
    mutationFn: () => cancelRequest(id),
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
  const steps = stepsQuery.data ?? [];
  const files = filesQuery.data ?? [];

  // Find step with changes_requested for the banner
  const changesStep = steps.find((s) => s.status === "changes_requested");

  // Build activity from steps
  const activity: { text: string; sub?: string; ts: string; highlight?: boolean }[] = [
    { text: "You submitted the request", ts: r.created_at },
    ...steps
      .filter((s) => s.completed_at)
      .map((s) => ({
        text:
          s.status === "approved"
            ? `${s.assignee_name ?? "Reviewer"} approved`
            : s.status === "changes_requested"
              ? `${s.assignee_name ?? "Reviewer"} requested changes`
              : s.status === "rejected"
                ? `${s.assignee_name ?? "Reviewer"} rejected the request`
                : `${s.assignee_name ?? "Reviewer"} reviewed`,
        sub: s.comment ?? undefined,
        ts: s.completed_at!,
        highlight: s.status === "changes_requested",
      })),
  ].sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());

  // Action button per status
  let actionButton: React.ReactNode = null;
  if (r.status === "in_review" || r.status === "submitted") {
    actionButton = (
      <button
        type="button"
        onClick={() => cancelMutation.mutate()}
        disabled={cancelMutation.isPending}
        className="flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs font-medium"
        style={{ borderColor: "#EEEEEE", color: "#616161" }}
      >
        ✕ Cancel request
      </button>
    );
  } else if (r.status === "cancelled" || r.status === "expired" || r.status === "rejected") {
    actionButton = (
      <Link
        href="/data-sharing/new"
        className="flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs font-medium"
        style={{ borderColor: "#D76736", color: "#D76736" }}
      >
        Raise a fresh request
      </Link>
    );
  } else if (r.status === "changes_requested") {
    actionButton = (
      <Link
        href={`/data-sharing/${id}/edit`}
        className="flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold text-white"
        style={{ backgroundColor: "#D76736" }}
      >
        Edit &amp; resubmit
      </Link>
    );
  }

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Sticky header */}
      <div
        className="flex h-14 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <span className="text-sm font-semibold text-auth-text">Request Detail</span>
        <Link
          href="/data-sharing"
          className="flex items-center gap-1 text-[13px]"
          style={{ color: "#9E9E9E" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to list
        </Link>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* Title block */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-auth-text">{r.title}</h1>
            <StatusBadge status={r.status} />
            {actionButton}
          </div>
          <p className="text-xs" style={{ color: "#9E9E9E" }}>
            {r.request_number} · Raised {formatDate(r.created_at)}
          </p>
        </div>

        {/* Status banners */}
        {r.status === "changes_requested" && (
          <div
            className="flex items-start gap-3 rounded-lg px-4 py-3"
            style={{ backgroundColor: "#FFFBEB", border: "1px solid #FDE68A" }}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#D97706" }} />
            <div className="flex flex-col gap-1">
              <p className="text-[13px] font-semibold" style={{ color: "#B45309" }}>
                {changesStep?.assignee_name ?? "Reviewer"} sent this back
                {changesStep?.completed_at ? ` · ${formatDate(changesStep.completed_at)}` : ""}
              </p>
              {changesStep?.comment && (
                <p className="text-xs" style={{ color: "#92400E" }}>
                  &ldquo;{changesStep.comment}&rdquo;
                </p>
              )}
              <p className="text-xs" style={{ color: "#92400E" }}>
                Make changes to classification, legal basis, personal-data flag, or data
                selection. All changes re-trigger DPO review.
              </p>
            </div>
          </div>
        )}

        {(r.status === "cancelled" || r.status === "expired") && (
          <div
            className="flex items-start gap-3 rounded-lg px-4 py-3"
            style={{ backgroundColor: "#FFF5F0", border: "1px solid #FFCDB8" }}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#D76736" }} />
            <div className="flex flex-col gap-1">
              <p className="text-[13px] font-semibold" style={{ color: "#D76736" }}>
                Auto-cancelled · Day-7 Escalation
              </p>
              <p className="text-xs" style={{ color: "#515157" }}>
                This request was automatically cancelled after 7 business days without
                approval. The SLA escalation ladder ran its full cycle (Day 3 breach → Day 5
                Org Admin reassignment → Day 7 auto-cancel). No further action is required —
                raise a fresh request if still needed.
              </p>
            </div>
          </div>
        )}

        {r.status === "approved" && (
          <div
            className="flex items-center gap-3 rounded-lg px-4 py-3"
            style={{ backgroundColor: "#F0FAF0", border: "1px solid #BBF7D0" }}
          >
            <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: "#449235" }} />
            <p className="text-[13px]" style={{ color: "#14532D" }}>
              All approvals collected — the source department is preparing your data.
              You&apos;ll be notified when it&apos;s ready.
            </p>
          </div>
        )}

        {/* Two-column layout */}
        <div className="flex gap-4">
          {/* Left column */}
          <div className="flex flex-1 flex-col gap-4">
            {/* Request Details */}
            <div
              className="flex flex-col overflow-hidden rounded-lg"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div
                className="flex h-11 items-center px-5"
                style={{ borderBottom: "1px solid #EEEEEE" }}
              >
                <span className="text-[13px] font-semibold" style={{ color: "#1A1A1A" }}>
                  Request Details
                </span>
              </div>
              <div className="flex flex-col px-5 py-2">
                <Field label="Purpose" value={r.purpose} />
                <Field
                  label="SLA Deadline"
                  value={
                    r.expiry_at ? (
                      <span style={{ color: "#D76736" }}>{formatDate(r.expiry_at)}</span>
                    ) : "—"
                  }
                />
                <Field label="Sharing Type" value={r.sharing_type} />
                <Field label="Classification" value={r.data_classification} />
                <Field label="Legal Basis" value={r.legal_basis || "—"} />
                <Field
                  label="Personal Data"
                  value={r.personal_data_involved ? "Yes — Employees" : "No"}
                />
                <Field label="Receiver Department" value={r.receiver_group_id ?? "—"} />
                <Field label="DPIA Confirmed" value={r.dpia_confirmed ? "Yes" : "No"} />
                <Field label="Retention Period" value="12 months" />
              </div>
            </div>

            {/* Attached Data */}
            {files.length > 0 && (
              <div
                className="flex flex-col overflow-hidden rounded-lg"
                style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
              >
                <div
                  className="flex h-11 items-center px-5"
                  style={{ borderBottom: "1px solid #EEEEEE" }}
                >
                  <span className="text-[13px] font-semibold" style={{ color: "#1A1A1A" }}>
                    Attached Data — File Upload
                  </span>
                </div>
                <div className="flex flex-col gap-0.5 px-5 py-3">
                  {files.map((f, i) => (
                    <div
                      key={f.id}
                      className="flex items-center gap-3 py-2"
                      style={{
                        borderBottom: i < files.length - 1 ? "1px solid #F5F5F5" : undefined,
                      }}
                    >
                      <FileText className="h-4 w-4 shrink-0" style={{ color: "#9E9E9E" }} />
                      <span className="flex-1 text-[13px] text-auth-text">
                        {f.original_filename}
                      </span>
                      <span className="text-xs" style={{ color: "#9E9E9E" }}>
                        {formatBytes(f.file_size_bytes)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Available Downloads (completed only) */}
            {r.status === "completed" && files.length > 0 && (
              <div
                className="flex flex-col overflow-hidden rounded-lg"
                style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
              >
                <div
                  className="flex h-11 items-center px-5"
                  style={{ borderBottom: "1px solid #EEEEEE" }}
                >
                  <span className="text-[13px] font-semibold" style={{ color: "#1A1A1A" }}>
                    Available Downloads
                  </span>
                </div>
                <div className="flex flex-col gap-0.5 px-5 py-3">
                  {files.map((f, i) => (
                    <div
                      key={f.id}
                      className="flex items-center gap-3 py-2"
                      style={{
                        borderBottom: i < files.length - 1 ? "1px solid #F5F5F5" : undefined,
                      }}
                    >
                      <FileText className="h-4 w-4 shrink-0" style={{ color: "#9E9E9E" }} />
                      <span className="flex-1 text-[13px] text-auth-text">
                        {f.original_filename}
                      </span>
                      <DownloadButton fileId={f.id} filename={f.original_filename} />
                    </div>
                  ))}
                </div>
                <div className="px-5 pb-4">
                  <button
                    type="button"
                    className="flex h-9 w-full items-center justify-center gap-2 rounded-md text-[13px] font-medium text-white"
                    style={{ backgroundColor: "#449235" }}
                    onClick={() => {
                      files.forEach((f) => {
                        void getDownloadUrl(f.id).then(({ download_url }) =>
                          window.open(download_url, "_blank"),
                        );
                      });
                    }}
                  >
                    <Download className="h-4 w-4" />
                    Download all files
                  </button>
                  <p className="mt-2 text-center text-[11px]" style={{ color: "#9E9E9E" }}>
                    {files.length} {files.length === 1 ? "file" : "files"} ·
                    You&apos;ll be notified 48h before expiration
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Right column */}
          <div className="flex w-[320px] shrink-0 flex-col gap-4">
            {/* Workflow steps */}
            <div
              className="flex flex-col overflow-hidden rounded-lg"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div
                className="flex h-11 items-center px-5"
                style={{ borderBottom: "1px solid #EEEEEE" }}
              >
                <span className="text-[13px] font-semibold" style={{ color: "#1A1A1A" }}>
                  Approval Workflow
                </span>
              </div>
              <div className="flex flex-col gap-0 px-4 py-3">
                {stepsQuery.isLoading && (
                  <p className="text-xs" style={{ color: "#9E9E9E" }}>Loading…</p>
                )}
                {steps.map((step, i) => {
                  const style = STEP_STATUS_STYLE[step.status] ?? STEP_STATUS_STYLE.pending;
                  return (
                    <div key={step.id} className="flex items-start gap-3 py-2">
                      <span
                        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
                        style={{ backgroundColor: style.bg, color: style.color }}
                      >
                        {i + 1}
                      </span>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[13px] font-medium text-auth-text">
                          {step.name ?? step.assignee_name ?? `Step ${i + 1}`}
                        </span>
                        {step.status !== "pending" && (
                          <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                            {step.status.replace("_", " ")}
                            {step.comment ? ` — ${step.comment}` : ""}
                          </span>
                        )}
                        {step.sla_deadline && step.status === "in_progress" && (
                          <span className="text-[11px]" style={{ color: "#D76736" }}>
                            Due {formatDate(step.sla_deadline)}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
                {steps.length === 0 && !stepsQuery.isLoading && (
                  <p className="text-xs" style={{ color: "#BABABA" }}>No workflow steps yet.</p>
                )}
              </div>
            </div>

            {/* Activity */}
            <div
              className="flex flex-col overflow-hidden rounded-lg"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div
                className="flex h-11 items-center px-5"
                style={{ borderBottom: "1px solid #EEEEEE" }}
              >
                <span className="text-[13px] font-semibold" style={{ color: "#1A1A1A" }}>
                  Activity
                </span>
              </div>
              <div className="flex flex-col px-4 py-3">
                {activity.map((a, i) => (
                  <div key={i} className="flex flex-col gap-0.5 py-2" style={{ borderBottom: i < activity.length - 1 ? "1px solid #F5F5F5" : undefined }}>
                    <div className="flex items-start justify-between gap-2">
                      <span
                        className="text-[13px] font-medium"
                        style={{ color: a.highlight ? "#D76736" : "#1A1A1A" }}
                      >
                        {a.text}
                      </span>
                      <span className="shrink-0 text-[11px]" style={{ color: "#9E9E9E" }}>
                        {formatRelativeTime(a.ts)}
                      </span>
                    </div>
                    {a.sub && (
                      <span className="text-[12px]" style={{ color: "#9E9E9E" }}>
                        {a.sub}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
