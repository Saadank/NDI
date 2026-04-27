"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileSpreadsheet,
  FileText,
  FileType2,
  Flag,
  Lock,
  MessageCircleWarning,
  ShieldAlert,
  TriangleAlert,
  X,
  XCircle,
  Zap,
} from "lucide-react";

import { useGroups } from "@/lib/hooks/platform/useGroups";
import {
  useApprovalSteps,
  useActOnStep,
} from "@/lib/hooks/data-sharing/useApprovalSteps";
import { useRequestDetail } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useRequestFiles } from "@/lib/hooks/data-sharing/useFiles";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";
import { formatDateTime, formatRelativeTime } from "@/lib/utils/formatters";
import type { StepStatus, WorkflowStep } from "@/lib/types/data-sharing/step.types";

// ───────────────────────────────────────────────────────────────
// Small primitives
// ───────────────────────────────────────────────────────────────

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      className="flex items-center py-2.5"
      style={{ borderBottom: "1px solid #F5F5F5" }}
    >
      <span
        className="w-[170px] shrink-0 text-[12px]"
        style={{ color: "#9E9E9E" }}
      >
        {label}
      </span>
      <span
        className="flex-1 text-[13px]"
        style={{ color: "#1A1A1A" }}
      >
        {value || <span style={{ color: "#BABABA" }}>—</span>}
      </span>
    </div>
  );
}

function ClassificationLabel({ value }: { value: string }) {
  const v = value.toLowerCase();
  const Icon = v === "confidential" || v === "sensitive"
    ? Lock
    : v === "restricted"
      ? ShieldAlert
      : null;
  const color =
    v === "confidential" || v === "sensitive"
      ? "#D76736"
      : v === "restricted"
        ? "#7C3AED"
        : "#449235";
  return (
    <span className="inline-flex items-center gap-1.5">
      {Icon ? (
        <Icon className="h-3.5 w-3.5" style={{ color }} />
      ) : (
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: color }}
        />
      )}
      <span style={{ color: "#1A1A1A", textTransform: "capitalize" }}>
        {value}
      </span>
    </span>
  );
}

function fileIcon(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "csv") return FileSpreadsheet;
  if (ext === "xlsx" || ext === "xls") return FileSpreadsheet;
  if (ext === "json") return FileType2;
  return FileText;
}

function PriorityChip({ urgent }: { urgent: boolean }) {
  if (urgent) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium"
        style={{ backgroundColor: "#FFF0EB", color: "#D76736" }}
      >
        <Clock className="h-3 w-3" />
        SLA tight
      </span>
    );
  }
  return null;
}

function AwaitingChip() {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-semibold"
      style={{ backgroundColor: "#FFF7E6", color: "#92400E" }}
    >
      <Zap className="h-3 w-3" />
      Awaiting Your Approval
    </span>
  );
}

// ───────────────────────────────────────────────────────────────
// Workflow card (right column, top)
// ───────────────────────────────────────────────────────────────

function WorkflowStepRow({
  step,
  i,
  total,
}: {
  step: WorkflowStep;
  i: number;
  total: number;
}) {
  const palette = (() => {
    if (step.status === "approved" || step.status === "skipped") {
      return { bg: "#449235", color: "#FFFFFF", icon: <Check className="h-3 w-3" /> };
    }
    if (step.status === "rejected") {
      return { bg: "#D32F2F", color: "#FFFFFF", icon: <X className="h-3 w-3" /> };
    }
    if (step.status === "changes_requested") {
      return { bg: "#B45309", color: "#FFFFFF", icon: <MessageCircleWarning className="h-3 w-3" /> };
    }
    if (step.can_act) {
      return { bg: "#D76736", color: "#FFFFFF", icon: <span className="text-[10px] font-bold">{i + 1}</span> };
    }
    return { bg: "#EEEEEE", color: "#9E9E9E", icon: <span className="text-[10px] font-bold">{i + 1}</span> };
  })();

  return (
    <div
      className="flex items-start gap-3 px-4 py-3"
      style={{
        backgroundColor: step.can_act ? "#FFF8F4" : "transparent",
        borderRadius: 8,
      }}
    >
      <span
        className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
        style={{ backgroundColor: palette.bg, color: palette.color }}
      >
        {palette.icon}
      </span>
      <div className="flex flex-1 flex-col gap-0.5">
        <span className="text-[13px] font-semibold text-auth-text">
          {step.name ?? step.assignee_role ?? `Step ${i + 1}`}
        </span>
        <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
          {step.status === "pending" && step.can_act
            ? "You — awaiting your decision"
            : step.assignee_name ??
              (step.assignee_user_id ? `User #${step.assignee_user_id}` : "—")}
          {step.status !== "pending" && step.completed_at
            ? ` · ${formatRelativeTime(step.completed_at)}`
            : ""}
        </span>
      </div>
      {i < total - 1 && step.status !== "pending" && (
        <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
          done
        </span>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Activity timeline — derived from workflow step transitions
// ───────────────────────────────────────────────────────────────

interface TimelineItem {
  id: string;
  kind: "approved" | "rejected" | "changes" | "raised" | "flagged";
  title: string;
  when: string;
  body?: string | null;
}

function buildTimeline(
  steps: WorkflowStep[],
  raisedAt: string,
  raisedByName: string,
): TimelineItem[] {
  const items: TimelineItem[] = [];
  for (const s of steps) {
    if (!s.completed_at) continue;
    if (s.status === "approved")
      items.push({
        id: s.id,
        kind: "approved",
        title: `${s.name ?? s.assignee_role ?? "Step"} Approved`,
        when: s.completed_at,
        body: s.comment,
      });
    if (s.status === "rejected")
      items.push({
        id: s.id,
        kind: "rejected",
        title: `${s.name ?? s.assignee_role ?? "Step"} Rejected`,
        when: s.completed_at,
        body: s.comment,
      });
    if (s.status === "changes_requested")
      items.push({
        id: s.id,
        kind: "changes",
        title: "Changes requested",
        when: s.completed_at,
        body: s.comment,
      });
  }
  items.push({
    id: "raised",
    kind: "raised",
    title: "Request Raised",
    when: raisedAt,
    body: `${raisedByName} submitted the request.`,
  });
  return items.sort(
    (a, b) => new Date(b.when).getTime() - new Date(a.when).getTime(),
  );
}

function TimelineRow({ item }: { item: TimelineItem }) {
  const palette =
    item.kind === "approved"
      ? { bg: "#F0FAF0", border: "#C6E8C4", dot: "#449235", title: "#2D6B21" }
      : item.kind === "rejected"
        ? { bg: "#FEF2F2", border: "#FCA5A5", dot: "#D32F2F", title: "#991B1B" }
        : item.kind === "changes"
          ? { bg: "#FFFBEB", border: "#FCD34D", dot: "#B45309", title: "#92400E" }
          : { bg: "#F5F5F5", border: "#EEEEEE", dot: "#9E9E9E", title: "#515157" };
  return (
    <div
      className="rounded-md p-3"
      style={{ backgroundColor: palette.bg, border: `1px solid ${palette.border}` }}
    >
      <div className="flex items-center justify-between">
        <span
          className="text-[12px] font-semibold"
          style={{ color: palette.title }}
        >
          {item.title}
        </span>
        <span className="text-[10px]" style={{ color: "#9E9E9E" }}>
          {formatDateTime(item.when)}
        </span>
      </div>
      {item.body && (
        <p
          className="mt-1.5 text-[11px]"
          style={{ color: "#515157", lineHeight: 1.5 }}
        >
          {item.body}
        </p>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Modals
// ───────────────────────────────────────────────────────────────

function ModalShell({
  title,
  onClose,
  children,
  width = 520,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  width?: number;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "#00000066" }}
    >
      <div
        className="flex flex-col gap-4 rounded-2xl bg-white p-6"
        style={{ width, boxShadow: "0 24px 64px #00000026" }}
      >
        <div className="flex items-start justify-between">
          <h2 className="text-base font-bold text-auth-text">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-auth-text-subtle hover:text-auth-text"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function RequestChangesModal({
  onClose,
  onConfirm,
  pending,
}: {
  onClose: () => void;
  onConfirm: (comment: string) => Promise<void>;
  pending: boolean;
}) {
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    if (!comment.trim()) {
      setError("Comment is required.");
      return;
    }
    try {
      await onConfirm(comment.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  };
  return (
    <ModalShell title="Request Changes" onClose={onClose}>
      <p className="text-xs" style={{ color: "#515157", lineHeight: 1.6 }}>
        The requester will be notified and sent back to edit and resubmit their
        request. Address your specific concern in the comment — they must
        respond before resubmitting.
      </p>
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-2 text-xs font-medium" style={{ color: "#616161" }}>
          Your comment{" "}
          <span
            className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold"
            style={{ backgroundColor: "#FFF0EB", color: "#D76736" }}
          >
            Required
          </span>
        </label>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Explain what needs to be changed or clarified…"
          className="h-28 w-full resize-none rounded-md border p-3 text-[13px] outline-none"
          style={{ borderColor: "#EEEEEE" }}
        />
      </div>
      <div
        className="flex items-start gap-2 rounded-md p-3 text-[11px]"
        style={{ backgroundColor: "#FFFBEB", border: "1px solid #FCD34D", color: "#92400E" }}
      >
        <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          If the requester changes classification, legal basis, personal data
          flag, or data selection, DPO review will re-trigger automatically.
        </span>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex justify-end gap-2">
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
          onClick={submit}
          disabled={pending || !comment.trim()}
          className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          style={{ backgroundColor: "#D76736" }}
        >
          {pending ? "Sending…" : "Send back to Requester"}
        </button>
      </div>
    </ModalShell>
  );
}

const REJECT_QUICK_REASONS = [
  "Insufficient justification",
  "PDPL basis unclear",
];

function RejectModal({
  onClose,
  onConfirm,
  pending,
}: {
  onClose: () => void;
  onConfirm: (comment: string) => Promise<void>;
  pending: boolean;
}) {
  const [comment, setComment] = useState("");
  const [active, setActive] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const toggle = (label: string) => {
    setActive((prev) =>
      prev.includes(label) ? prev.filter((p) => p !== label) : [...prev, label],
    );
  };

  const submit = async () => {
    const compiled = [
      ...active,
      ...(comment.trim() ? [comment.trim()] : []),
    ].join(" — ");
    if (!compiled) {
      setError("A reason is required to reject.");
      return;
    }
    try {
      await onConfirm(compiled);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  };

  return (
    <ModalShell title="Reject Request" onClose={onClose}>
      <div
        className="flex items-start gap-2 rounded-md p-3 text-[12px]"
        style={{ backgroundColor: "#FEF2F2", border: "1px solid #FCA5A5", color: "#991B1B" }}
      >
        <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          Rejection permanently closes this request and notifies the requester.
          This action cannot be undone.
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-2 text-xs font-medium" style={{ color: "#616161" }}>
          Rejection reason{" "}
          <span
            className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold"
            style={{ backgroundColor: "#FEF2F2", color: "#B91C1C" }}
          >
            Required
          </span>
        </label>
        <div className="flex flex-wrap items-center gap-2">
          {REJECT_QUICK_REASONS.map((r) => {
            const on = active.includes(r);
            return (
              <button
                key={r}
                type="button"
                onClick={() => toggle(r)}
                className="flex h-7 items-center rounded-full px-3 text-xs"
                style={
                  on
                    ? { backgroundColor: "#FEF2F2", color: "#B91C1C", border: "1px solid #FCA5A5" }
                    : { backgroundColor: "#FFFFFF", color: "#515157", border: "1px solid #EEEEEE" }
                }
              >
                {r}
              </button>
            );
          })}
        </div>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="State the reason for rejection clearly — this will be sent to the requester."
          className="h-24 w-full resize-none rounded-md border p-3 text-[13px] outline-none"
          style={{ borderColor: "#EEEEEE" }}
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex justify-end gap-2">
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
          onClick={submit}
          disabled={pending}
          className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white"
          style={{ backgroundColor: pending ? "#FCA5A5" : "#B91C1C" }}
        >
          {pending ? "Rejecting…" : "Reject request"}
        </button>
      </div>
    </ModalShell>
  );
}

function ApproveModal({
  requestNumber,
  onClose,
  onConfirm,
  pending,
}: {
  requestNumber: string;
  onClose: () => void;
  onConfirm: (comment: string) => Promise<void>;
  pending: boolean;
}) {
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    try {
      await onConfirm(comment.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  };
  return (
    <ModalShell title={`Approve ${requestNumber}`} onClose={onClose}>
      <p className="text-xs" style={{ color: "#515157", lineHeight: 1.6 }}>
        The request advances to the next workflow step. The audit trail will
        record your decision and any optional note you add.
      </p>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Optional note for the audit trail…"
        className="h-24 w-full resize-none rounded-md border p-3 text-[13px] outline-none"
        style={{ borderColor: "#EEEEEE" }}
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex justify-end gap-2">
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
          onClick={submit}
          disabled={pending}
          className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          {pending ? "Approving…" : "Approve"}
        </button>
      </div>
    </ModalShell>
  );
}

// ───────────────────────────────────────────────────────────────
// Main page
// ───────────────────────────────────────────────────────────────

type ModalKey = null | "approve" | "reject" | "changes";

export function ApprovalDetail({ id }: { id: string }) {
  const { isReady } = useRoleGuard({
    allow: ["data_owner", "platform_admin"],
  });
  const router = useRouter();

  const reqQuery = useRequestDetail(id);
  const stepsQuery = useApprovalSteps(id);
  const filesQuery = useRequestFiles(id);
  const groupsQuery = useGroups();
  const act = useActOnStep(id);

  const myProductRole = useAuthStore((s) => s.user?.product_role ?? null);
  const myGroupId = useAuthStore((s) => s.user?.group_id ?? null);
  const myGroupName = (() => {
    if (!myGroupId) return "";
    return groupsQuery.data?.find((g) => g.id === myGroupId)?.name ?? "";
  })();

  const [modal, setModal] = useState<ModalKey>(null);

  if (!isReady) return null;

  if (reqQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-auth-text-subtle">Loading…</p>
      </div>
    );
  }
  if (reqQuery.isError || !reqQuery.data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-red-600">Failed to load request.</p>
      </div>
    );
  }

  const r = reqQuery.data;
  const steps = stepsQuery.data ?? [];
  const myStep = steps.find((s) => s.can_act);

  const senderGroupName =
    groupsQuery.data?.find((g) => g.id === (r.requester_group_id ?? -1))?.name ??
    "—";
  const receiverGroupName =
    groupsQuery.data?.find((g) => g.id === (r.receiver_group_id ?? -1))?.name ??
    "—";

  const hoursLeft = r.expiry_at
    ? (new Date(r.expiry_at).getTime() - Date.now()) / (1000 * 60 * 60)
    : null;
  const slaText = hoursLeft === null
    ? "No SLA set"
    : hoursLeft < 0
      ? "SLA overdue"
      : hoursLeft < 24
        ? `${Math.round(hoursLeft)}h remaining`
        : `${Math.floor(hoursLeft / 24)}d ${Math.round(hoursLeft % 24)}h remaining`;
  const urgent = hoursLeft !== null && hoursLeft > 0 && hoursLeft < 24;

  const timeline = buildTimeline(
    steps,
    r.created_at,
    `User #${r.requester_id}`,
  );

  const handleApprove = async (comment: string) => {
    if (!myStep) return;
    await act.mutateAsync({
      stepId: myStep.id,
      status: "approved",
      comment: comment || undefined,
    });
    setModal(null);
    router.push("/approvals");
  };
  const handleReject = async (comment: string) => {
    if (!myStep) return;
    await act.mutateAsync({
      stepId: myStep.id,
      status: "rejected",
      comment,
    });
    setModal(null);
    router.push("/approvals");
  };
  const handleChanges = async (comment: string) => {
    if (!myStep) return;
    await act.mutateAsync({
      stepId: myStep.id,
      status: "changes_requested",
      comment,
    });
    setModal(null);
    router.push("/approvals");
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Top bar */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Request Detail</h1>
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
            style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
          >
            v{r.version}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/approvals"
            className="flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Inbox
          </Link>
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
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 pb-24 pt-6">
        {/* Sub-header card */}
        <div
          className="flex flex-col gap-3 rounded-lg px-6 py-5"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div className="flex items-center gap-1 text-[11px]" style={{ color: "#9E9E9E" }}>
            <Link href="/approvals" className="hover:text-brand">
              Approvals Inbox
            </Link>
            <ChevronRight className="h-3 w-3" />
            <span>{r.title}</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-bold text-auth-text">{r.title}</h2>
            {myStep ? <AwaitingChip /> : null}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[12px]" style={{ color: "#515157" }}>
            <span className="inline-flex items-center gap-1.5">
              <span
                className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                style={{ backgroundColor: "#D7673626", color: "#D76736" }}
              >
                {(r.requester_id ?? 0).toString().slice(-2)}
              </span>
              User #{r.requester_id}
            </span>
            <span style={{ color: "#BABABA" }}>·</span>
            <span>
              {senderGroupName}{" "}
              <ArrowRight className="inline h-3 w-3" /> {receiverGroupName}
            </span>
            <span style={{ color: "#BABABA" }}>·</span>
            <span
              className="inline-flex items-center gap-1"
              style={{ color: urgent ? "#D76736" : "#515157" }}
            >
              <Clock className="h-3 w-3" />
              {slaText}
            </span>
            <PriorityChip urgent={urgent} />
          </div>
        </div>

        <div className="flex flex-1 gap-4">
          {/* Left column — Metadata + (optional Mode B) + Files */}
          <div className="flex flex-1 flex-col gap-4">
            {/* Request Metadata */}
            <section
              className="flex flex-col rounded-lg overflow-hidden"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div
                className="flex h-11 items-center px-5"
                style={{ borderBottom: "1px solid #EEEEEE" }}
              >
                <span className="text-[13px] font-semibold text-auth-text">
                  Request Metadata
                </span>
              </div>
              <div className="flex flex-col px-5 py-2">
                <MetaRow label="Legal Basis" value={r.legal_basis || "—"} />
                <MetaRow
                  label="Personal Data"
                  value={
                    r.personal_data_involved ? (
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                          style={{ backgroundColor: "#FFF0EB", color: "#D76736" }}
                        >
                          Yes
                        </span>
                        <span style={{ color: "#9E9E9E" }}>
                          {r.data_subject_categories &&
                          r.data_subject_categories.length > 0
                            ? `· ${r.data_subject_categories.join(", ")}`
                            : ""}
                        </span>
                      </span>
                    ) : (
                      "No"
                    )
                  }
                />
                <MetaRow
                  label="Classification"
                  value={<ClassificationLabel value={r.data_classification} />}
                />
                <MetaRow
                  label="Approved Format"
                  value={
                    r.data_type === "structured"
                      ? "Structured query / tabular"
                      : "File upload"
                  }
                />
                <MetaRow label="Purpose" value={r.purpose} />
              </div>
            </section>

            {/* Query Preview — only for structured / SQL mode */}
            {r.data_type === "structured" && r.selection_mode === "query" && r.custom_sql && (
              <section
                className="flex flex-col rounded-lg overflow-hidden"
                style={{
                  backgroundColor: "#FFFFFF",
                  border: "1px solid #EEEEEE",
                }}
              >
                <div
                  className="flex h-11 items-center justify-between px-5"
                  style={{ borderBottom: "1px solid #EEEEEE" }}
                >
                  <span className="text-[13px] font-semibold text-auth-text">
                    Query Preview
                  </span>
                  <div className="flex items-center gap-2">
                    {r.connection_id && (
                      <span
                        className="rounded px-2 py-0.5 text-[10px] font-medium"
                        style={{ backgroundColor: "#EEF2FF", color: "#3B4FD6" }}
                      >
                        {String(r.connection_id).slice(0, 8)}
                      </span>
                    )}
                    {r.legal_basis && (
                      <span
                        className="rounded px-2 py-0.5 text-[10px] font-medium"
                        style={{ backgroundColor: "#F5F0FF", color: "#7C3AED" }}
                      >
                        {r.legal_basis}
                      </span>
                    )}
                  </div>
                </div>
                <pre
                  className="m-4 overflow-x-auto rounded-md p-4 font-mono text-xs"
                  style={{
                    backgroundColor: "#1E1E2E",
                    color: "#D4D4D4",
                  }}
                >
                  {r.custom_sql}
                </pre>
                <div
                  className="px-5 pb-4 text-[11px]"
                  style={{ color: "#9E9E9E" }}
                >
                  Live preview rows are not available; the steward will execute
                  this query during &quot;Prepare &amp; Upload&quot;.
                </div>
              </section>
            )}

            {/* Selected tables (Mode B / tables) */}
            {r.data_type === "structured" &&
              r.selection_mode === "tables" &&
              (r.selected_items ?? []).length > 0 && (
                <section
                  className="flex flex-col rounded-lg overflow-hidden"
                  style={{
                    backgroundColor: "#FFFFFF",
                    border: "1px solid #EEEEEE",
                  }}
                >
                  <div
                    className="flex h-11 items-center px-5"
                    style={{ borderBottom: "1px solid #EEEEEE" }}
                  >
                    <span className="text-[13px] font-semibold text-auth-text">
                      Selected Tables
                    </span>
                  </div>
                  <ul className="flex flex-col px-5 py-2">
                    {(r.selected_items ?? []).map((it, idx) => (
                      <li
                        key={`${it.schema}.${it.table}.${idx}`}
                        className="flex h-9 items-center text-xs"
                        style={{ borderBottom: "1px solid #F5F5F5" }}
                      >
                        {[it.schema, it.table].filter(Boolean).join(".")}
                        {it.columns?.length
                          ? ` (${it.columns.join(", ")})`
                          : ""}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

            {/* Attached Files — Mode A */}
            {r.data_type === "file" && (
              <section
                className="flex flex-col rounded-lg overflow-hidden"
                style={{
                  backgroundColor: "#FFFFFF",
                  border: "1px solid #EEEEEE",
                }}
              >
                <div
                  className="flex h-11 items-center justify-between px-5"
                  style={{ borderBottom: "1px solid #EEEEEE" }}
                >
                  <span className="text-[13px] font-semibold text-auth-text">
                    Attached Files
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                    style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
                  >
                    {filesQuery.data?.length ?? 0} files
                  </span>
                </div>
                <div className="flex flex-col">
                  {filesQuery.isLoading && (
                    <p className="px-5 py-4 text-xs text-auth-text-subtle">
                      Loading…
                    </p>
                  )}
                  {(filesQuery.data ?? []).map((f, i, arr) => {
                    const Icon = fileIcon(f.original_filename);
                    return (
                      <div
                        key={f.id}
                        className="flex h-12 items-center gap-3 px-5"
                        style={{
                          borderBottom:
                            i < arr.length - 1 ? "1px solid #F5F5F5" : undefined,
                        }}
                      >
                        <Icon
                          className="h-4 w-4"
                          style={{ color: "#9E9E9E" }}
                        />
                        <div className="flex flex-1 flex-col">
                          <span className="text-[13px]" style={{ color: "#1A1A1A" }}>
                            {f.original_filename}
                          </span>
                          <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                            {f.mime_type} · {f.status}
                          </span>
                        </div>
                        <span className="text-xs" style={{ color: "#515157" }}>
                          {(f.file_size_bytes / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    );
                  })}
                  {filesQuery.data && filesQuery.data.length === 0 && (
                    <p className="px-5 py-6 text-xs text-auth-text-placeholder">
                      No files attached yet — the requester will upload after
                      approval.
                    </p>
                  )}
                </div>
              </section>
            )}
          </div>

          {/* Right column — Workflow + Activity */}
          <div className="flex w-[340px] shrink-0 flex-col gap-4">
            <section
              className="flex flex-col rounded-lg overflow-hidden"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div
                className="flex h-11 items-center px-5"
                style={{ borderBottom: "1px solid #EEEEEE" }}
              >
                <span className="text-[13px] font-semibold text-auth-text">
                  Workflow
                </span>
              </div>
              <div className="flex flex-col gap-1 p-3">
                {steps.map((s, i) => (
                  <WorkflowStepRow
                    key={s.id}
                    step={s}
                    i={i}
                    total={steps.length}
                  />
                ))}
                {steps.length === 0 && (
                  <p className="px-2 py-2 text-xs text-auth-text-placeholder">
                    No workflow steps yet.
                  </p>
                )}
              </div>
            </section>

            <section
              className="flex flex-col rounded-lg overflow-hidden"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div
                className="flex h-11 items-center px-5"
                style={{ borderBottom: "1px solid #EEEEEE" }}
              >
                <span className="text-[13px] font-semibold text-auth-text">
                  Activity Timeline
                </span>
              </div>
              <div className="flex flex-col gap-2 p-4">
                {timeline.map((t) => (
                  <TimelineRow key={t.id} item={t} />
                ))}
              </div>
            </section>
          </div>
        </div>
      </div>

      {/* Sticky footer action bar — only when this user can act */}
      {myStep && (
        <div
          className="sticky bottom-0 flex h-16 items-center justify-between px-8"
          style={{
            backgroundColor: "#FFFFFF",
            borderTop: "1px solid #EEEEEE",
          }}
        >
          <button
            type="button"
            disabled
            title="Coming soon"
            className="flex h-9 items-center gap-1.5 text-[13px] font-medium"
            style={{ color: "#9E9E9E" }}
          >
            <Flag className="h-3.5 w-3.5" />
            Flag for Technical Review
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setModal("reject")}
              className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium"
              style={{ borderColor: "#FCA5A5", color: "#B91C1C" }}
            >
              <XCircle className="h-3.5 w-3.5" />
              Reject
            </button>
            <button
              type="button"
              onClick={() => setModal("changes")}
              className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium"
              style={{ borderColor: "#FCD34D", color: "#92400E" }}
            >
              <MessageCircleWarning className="h-3.5 w-3.5" />
              Request Changes
            </button>
            <button
              type="button"
              onClick={() => setModal("approve")}
              className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white"
              style={{ backgroundColor: "#D76736" }}
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Approve
            </button>
          </div>
        </div>
      )}

      {modal === "approve" && (
        <ApproveModal
          requestNumber={r.request_number}
          onClose={() => setModal(null)}
          onConfirm={handleApprove}
          pending={act.isPending}
        />
      )}
      {modal === "reject" && (
        <RejectModal
          onClose={() => setModal(null)}
          onConfirm={handleReject}
          pending={act.isPending}
        />
      )}
      {modal === "changes" && (
        <RequestChangesModal
          onClose={() => setModal(null)}
          onConfirm={handleChanges}
          pending={act.isPending}
        />
      )}
    </div>
  );
}
