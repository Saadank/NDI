"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Lock,
  MessageCircleWarning,
  Play,
  ShieldAlert,
  X,
  XCircle,
} from "lucide-react";

import { useApprovalSteps, useActOnStep } from "@/lib/hooks/data-sharing/useApprovalSteps";
import { useRequestDetail } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useRequestFiles } from "@/lib/hooks/data-sharing/useFiles";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDateTime, formatRelativeTime } from "@/lib/utils/formatters";
import type { StepStatus, WorkflowStep } from "@/lib/types/data-sharing/step.types";

// ─── Helpers ─────────────────────────────────────────────────────

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center py-2" style={{ borderBottom: "1px solid #F5F5F5" }}>
      <span className="w-[140px] shrink-0 text-[12px]" style={{ color: "#9E9E9E" }}>{label}</span>
      <span className="flex-1 text-[13px]" style={{ color: "#1A1A1A" }}>
        {value ?? <span style={{ color: "#BABABA" }}>—</span>}
      </span>
    </div>
  );
}

function ClassificationBadge({ value }: { value: string }) {
  const v = value.toLowerCase();
  const Icon = v === "confidential" || v === "sensitive" ? Lock : v === "restricted" ? ShieldAlert : null;
  const color = v === "confidential" || v === "sensitive" ? "#D76736" : v === "restricted" ? "#7C3AED" : "#449235";
  const bg = v === "confidential" || v === "sensitive" ? "#FFF5F0" : v === "restricted" ? "#F5F0FF" : "#F0FAF0";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-semibold capitalize"
      style={{ backgroundColor: bg, color }}
    >
      {Icon && <Icon className="h-2.5 w-2.5" />}
      {value}
    </span>
  );
}

// ─── Workflow progress bar ────────────────────────────────────────

function WorkflowProgressBar({ steps }: { steps: WorkflowStep[] }) {
  if (steps.length === 0) return null;
  // The "current" step is the first pending OR in_progress one. If the
  // workflow is finished there is no current step and the bar shows
  // every node as done.
  const currentIdx = steps.findIndex(
    (s) => s.status === "pending" || s.status === "in_progress",
  );

  return (
    <div className="flex flex-col gap-3 px-5 pb-5">
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-semibold text-auth-text">Workflow Progress</span>
        <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
          Step {Math.max(0, currentIdx)} of {steps.length}
        </span>
      </div>
      <div className="relative flex items-center">
        {steps.map((s, i) => {
          // Visual states (must match the right-rail WorkflowStepRow rule):
          //   approved/skipped       → green ✓ (done)
          //   pending/in_progress    → orange filled (current/active)
          //   rejected               → red ✕
          //   waiting/flagged/etc.   → gray empty circle (default)
          const done = s.status === "approved" || s.status === "skipped";
          const active = s.status === "pending" || s.status === "in_progress";
          const rejected = s.status === "rejected";
          const ringColor = rejected
            ? "#DC2626"
            : done
              ? "#16A34A"
              : active
                ? "#D76736"
                : "#EEEEEE";
          const textColor = rejected || done || active ? "#FFFFFF" : "#9E9E9E";
          // Connector colouring: the line BEFORE this node is "done"
          // when this node has been reached (i.e., this node is current
          // or already finished). The line AFTER this node fills only
          // when THIS node itself is done.
          const reached =
            done ||
            active ||
            rejected ||
            (currentIdx !== -1 && i < currentIdx);
          return (
            <div key={s.id} className="flex flex-1 flex-col items-center gap-1.5">
              <div className="relative flex w-full items-center">
                {i > 0 && (
                  <div
                    className="absolute left-0 right-1/2 top-1/2 h-0.5 -translate-y-1/2"
                    style={{ backgroundColor: reached ? "#D76736" : "#EEEEEE" }}
                  />
                )}
                {i < steps.length - 1 && (
                  <div
                    className="absolute left-1/2 right-0 top-1/2 h-0.5 -translate-y-1/2"
                    style={{ backgroundColor: done ? "#D76736" : "#EEEEEE" }}
                  />
                )}
                <div
                  className="relative z-10 mx-auto flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold"
                  style={{ backgroundColor: ringColor, color: textColor }}
                >
                  {done ? (
                    <Check className="h-3 w-3" />
                  ) : rejected ? (
                    <XCircle className="h-3 w-3" />
                  ) : (
                    i + 1
                  )}
                </div>
              </div>
              <span
                className="text-center text-[10px] leading-tight"
                style={{
                  color:
                    done || active
                      ? "#D76736"
                      : rejected
                        ? "#DC2626"
                        : "#9E9E9E",
                  maxWidth: 64,
                }}
              >
                {s.name ?? s.assignee_role ?? `Step ${i + 1}`}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── PDPL Review right panel ──────────────────────────────────────

type ReviewTab = "legal_basis" | "data_min" | "dpia_status" | "all_checks";

function PdplReviewPanel({
  classification,
  legalBasis,
  dpia,
  myStep: _myStep,
  onApprove: _onApprove,
  onChanges: _onChanges,
  onReject: _onReject,
}: {
  classification: string;
  legalBasis: string | null;
  dpia: boolean;
  myStep: WorkflowStep | undefined;
  onApprove: () => void;
  onChanges: () => void;
  onReject: () => void;
}) {
  const [tab, setTab] = useState<ReviewTab>("legal_basis");
  const [override, setOverride] = useState<"accept" | "override" | null>(null);
  const [justification, setJustification] = useState("");
  const [dataMinAssessment, setDataMinAssessment] = useState<"accept_with_note" | "request_changes" | null>(null);
  const [dpiaVerification, setDpiaVerification] = useState<"confirmed" | "request_update" | null>(null);
  const [dpiaAssessment, setDpiaAssessment] = useState<"proceed" | "request_update" | null>(null);

  // Per Pencil frame 07 the right-rail panel gains a 4th tab once all
  // sub-checks are complete: a roll-up summary of Legal Basis +
  // Data Minimisation + DPIA Status with the action consequences below.
  const tabs: { id: ReviewTab; label: string }[] = [
    { id: "legal_basis", label: "Legal Basis" },
    { id: "data_min", label: "Data Minimisation" },
    { id: "dpia_status", label: "DPIA Status" },
    { id: "all_checks", label: "All Checks" },
  ];

  // Each sub-tab's "satisfied?" rule. Used to roll up into the All-Checks
  // summary as ✓/✗ rows and to drive the headline banner.
  const legalBasisSatisfied = override === "accept" || override === "override";
  const dataMinSatisfied = dataMinAssessment === "accept_with_note";
  const dpiaSatisfied = dpiaVerification === "confirmed" && dpiaAssessment === "proceed";
  const checksTotal = 3;
  const checksSatisfied =
    Number(legalBasisSatisfied) + Number(dataMinSatisfied) + Number(dpiaSatisfied);
  const allChecksGreen = checksSatisfied === checksTotal;

  return (
    <div className="flex w-[320px] shrink-0 flex-col gap-3">
      {/* PDPL Review card */}
      <section
        className="flex flex-col overflow-hidden rounded-lg"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div
          className="flex h-11 items-center justify-between px-4"
          style={{ borderBottom: "1px solid #EEEEEE" }}
        >
          <span className="text-[13px] font-semibold text-auth-text">PDPL Review</span>
          <ClassificationBadge value={classification} />
        </div>

        {/* Tabs */}
        <div className="flex" style={{ borderBottom: "1px solid #EEEEEE" }}>
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className="flex-1 px-2 py-2 text-[11px] font-medium"
              style={
                tab === t.id
                  ? { borderBottom: "2px solid #D76736", marginBottom: -1, color: "#D76736" }
                  : { color: "#9E9E9E" }
              }
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-3 p-4">
          {tab === "legal_basis" && (
            <>
              <div
                className="flex items-center gap-2 rounded-md p-2.5 text-[11px] font-semibold"
                style={{ backgroundColor: "#F0FAF0", color: "#2D6B21" }}
              >
                <Check className="h-3.5 w-3.5" />
                AI PDPL checks complete
              </div>

              <div className="flex flex-col gap-1.5">
                <p className="text-[11px] font-semibold" style={{ color: "#515157" }}>Legal Basis</p>
                <span
                  className="inline-flex self-start items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium"
                  style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
                >
                  {legalBasis ?? "Not specified"}
                </span>
                <p className="text-[10px]" style={{ color: "#9E9E9E" }}>System recommendation</p>
                <span
                  className="inline-flex self-start items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
                  style={{ backgroundColor: "#F0FAF0", color: "#449235" }}
                >
                  <Check className="h-3 w-3" />
                  {legalBasis ?? "Legitimate Interest"} — Confirmed
                </span>
              </div>

              <div className="flex flex-col gap-1.5">
                <p className="text-[11px] font-semibold" style={{ color: "#515157" }}>DPO Override</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setOverride("accept")}
                    className="flex h-7 flex-1 items-center justify-center rounded-md text-[12px] font-medium"
                    style={
                      override === "accept"
                        ? { backgroundColor: "#F0FAF0", border: "1px solid #BBF7D0", color: "#449235" }
                        : { border: "1px solid #EEEEEE", color: "#515157" }
                    }
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    onClick={() => setOverride("override")}
                    className="flex h-7 flex-1 items-center justify-center rounded-md text-[12px] font-medium"
                    style={
                      override === "override"
                        ? { backgroundColor: "#FFF5F0", border: "1px solid #FFCDB8", color: "#D76736" }
                        : { border: "1px solid #EEEEEE", color: "#515157" }
                    }
                  >
                    Override
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold" style={{ color: "#515157" }}>DPO Justification</label>
                <textarea
                  value={justification}
                  onChange={(e) => setJustification(e.target.value)}
                  rows={3}
                  className="resize-none rounded-md border p-2 text-[12px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                  placeholder="Record your legal basis assessment…"
                />
              </div>
            </>
          )}

          {tab === "data_min" && (
            <div className="flex flex-col gap-3">
              <p className="text-[11px] font-semibold" style={{ color: "#515157" }}>Data Minimisation Checked</p>
              {([
                { label: "Only necessary fields selected — SSN, salary excluded", type: "pass" },
                { label: "Query limited to active employees only", type: "pass" },
                { label: "Date range restricted to last 60 days", type: "pass" },
                { label: "No sensitive demographic fields included", type: "pass" },
                { label: "Email field included — consider pseudonymisation", type: "warn" },
              ] as const).map((item, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded-md p-2.5 text-[11px]"
                  style={{
                    backgroundColor: item.type === "pass" ? "#F0FAF0" : "#FFF5F0",
                    color: item.type === "pass" ? "#449235" : "#D76736",
                  }}
                >
                  {item.type === "pass"
                    ? <Check className="mt-0.5 h-3 w-3 shrink-0" />
                    : <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />}
                  {item.label}
                </div>
              ))}
              <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
                Review the SQL query preview in left panel to verify field selection
              </p>
              <p className="mt-1 text-[11px] font-semibold" style={{ color: "#515157" }}>DPO Assessment</p>
              {[
                { value: "accept_with_note" as const, label: "Accept with note — email pseudonymisation recommended" },
                { value: "request_changes" as const, label: "Request changes before approval" },
              ].map((opt) => (
                <label key={opt.value} className="flex cursor-pointer items-start gap-2 text-[11px]" style={{ color: "#515157" }}>
                  <input
                    type="radio"
                    name="dataMinAssessment"
                    checked={dataMinAssessment === opt.value}
                    onChange={() => setDataMinAssessment(opt.value)}
                    className="mt-0.5 accent-[#D76736]"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          )}

          {tab === "dpia_status" && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold text-auth-text">DPIA-2026-014</span>
                <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: "#F0FAF0", color: "#449235" }}>On File</span>
              </div>
              <div className="flex flex-col gap-1">
                <p className="text-[11px]" style={{ color: "#9E9E9E" }}>Last reviewed: 12 Jan 2026 · Lead DPO: Layla Hassan</p>
                <p className="text-[11px]" style={{ color: "#515157" }}>Scope: Article 9 (sensitive data) processing for HR compliance reporting</p>
              </div>
              <span className="self-start rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: "#FFFBEB", color: "#B45309" }}>
                Risk level: Medium — additional controls recommended
              </span>
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold" style={{ color: "#515157" }}>DPO Verification</label>
                {([
                  { value: "confirmed" as const, label: "Reviewed DPIA-2026-014 and confirm it covers this processing activity" },
                  { value: "request_update" as const, label: "Request DPIA update before proceeding" },
                ] as const).map((opt) => (
                  <label key={opt.value} className="flex cursor-pointer items-start gap-2 text-[11px]" style={{ color: "#515157" }}>
                    <input
                      type="radio"
                      name="dpiaVerification"
                      checked={dpiaVerification === opt.value}
                      onChange={() => setDpiaVerification(opt.value)}
                      className="mt-0.5 accent-[#D76736]"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
              <p className="text-[11px] font-semibold" style={{ color: "#515157" }}>DPO Assessment</p>
              {[
                { value: "proceed" as const, label: "Proceed — DPIA on file and covers this request" },
                { value: "request_update" as const, label: "Request DPIA update before proceeding" },
              ].map((opt) => (
                <label key={opt.value} className="flex cursor-pointer items-start gap-2 text-[11px]" style={{ color: "#515157" }}>
                  <input
                    type="radio"
                    name="dpiaAssessment"
                    checked={dpiaAssessment === opt.value}
                    onChange={() => setDpiaAssessment(opt.value)}
                    className="mt-0.5 accent-[#D76736]"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          )}

          {tab === "all_checks" && (
            <div className="flex flex-col gap-3">
              {/* Headline banner — green when every sub-check is satisfied,
                  amber otherwise (with a count of remaining issues). */}
              {allChecksGreen ? (
                <div
                  className="flex items-center gap-2 rounded-md p-3 text-[12px] font-semibold"
                  style={{ backgroundColor: "#F0FAF0", color: "#2D6B21", border: "1px solid #BBF7D0" }}
                >
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  All PDPL checks complete
                </div>
              ) : (
                <div
                  className="flex items-center gap-2 rounded-md p-3 text-[12px] font-semibold"
                  style={{ backgroundColor: "#FFFBEB", color: "#92400E", border: "1px solid #FCD34D" }}
                >
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {checksTotal - checksSatisfied} issue{checksTotal - checksSatisfied === 1 ? "" : "s"} blocking approval
                </div>
              )}

              {/* Per-check roll-up rows */}
              {[
                {
                  key: "legal",
                  label: "Legal Basis",
                  satisfied: legalBasisSatisfied,
                  note: legalBasis
                    ? `${legalBasis} — ${override === "override" ? "DPO override applied" : override === "accept" ? "confirmed" : "needs DPO decision"}`
                    : "Not specified",
                },
                {
                  key: "data_min",
                  label: "Data Minimisation",
                  satisfied: dataMinSatisfied,
                  note:
                    dataMinAssessment === "accept_with_note"
                      ? "Accepted — notes captured"
                      : dataMinAssessment === "request_changes"
                        ? "Changes requested"
                        : "DPO assessment pending",
                },
                {
                  key: "dpia",
                  label: "DPIA Status",
                  satisfied: dpiaSatisfied,
                  note: dpia
                    ? dpiaVerification === "confirmed" && dpiaAssessment === "proceed"
                      ? "On file · DPO confirmed"
                      : "Verification pending"
                    : "DPIA flag not set on request",
                },
              ].map((c) => (
                <div
                  key={c.key}
                  className="flex items-start gap-2 rounded-md p-2.5"
                  style={{
                    backgroundColor: c.satisfied ? "#F0FAF0" : "#FFFBEB",
                    border: `1px solid ${c.satisfied ? "#BBF7D0" : "#FCD34D"}`,
                  }}
                >
                  {c.satisfied ? (
                    <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#449235" }} />
                  ) : (
                    <X className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#92400E" }} />
                  )}
                  <div className="flex flex-1 flex-col gap-0.5">
                    <span
                      className="text-[12px] font-semibold"
                      style={{ color: c.satisfied ? "#2D6B21" : "#92400E" }}
                    >
                      {c.label}
                    </span>
                    <span
                      className="text-[11px]"
                      style={{ color: c.satisfied ? "#449235" : "#92400E" }}
                    >
                      {c.note}
                    </span>
                  </div>
                </div>
              ))}

              <p className="text-[11px]" style={{ color: "#9E9E9E", lineHeight: 1.5 }}>
                Switch back to a tab to refine your assessment. The action you
                pick in the footer is recorded in the audit trail with these
                check states attached.
              </p>
            </div>
          )}

        </div>
      </section>

      {/* Decision & Consequences */}
      <section
        className="flex flex-col overflow-hidden rounded-lg"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div className="flex h-10 items-center px-4" style={{ borderBottom: "1px solid #EEEEEE" }}>
          <span className="text-[12px] font-semibold text-auth-text">Decision &amp; Consequences</span>
        </div>
        <div className="flex flex-col gap-2 p-4">
          {[
            {
              label: "Approve",
              desc: "Request granted. Requester notified. Audit log entry created. Data accessible per agreed scope.",
              color: "#449235",
              bg: "#F0FAF0",
              border: "#BBF7D0",
            },
            {
              label: "Request Changes",
              desc: "Request returned to Data Owner with DPO comments. Steward to review requested.",
              color: "#B45309",
              bg: "#FFFBEB",
              border: "#FCD34D",
            },
            {
              label: "Reject",
              desc: "Request declined and closed. Requester notified with reason. No data accessed.",
              color: "#D32F2F",
              bg: "#FEF2F2",
              border: "#FCA5A5",
            },
          ].map((d) => (
            <div
              key={d.label}
              className="rounded-md p-3"
              style={{ backgroundColor: d.bg, border: `1px solid ${d.border}` }}
            >
              <p className="text-[11px] font-semibold" style={{ color: d.color }}>{d.label}</p>
              <p className="mt-1 text-[10px] leading-relaxed" style={{ color: d.color }}>{d.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ─── Modals ───────────────────────────────────────────────────────

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "#00000066" }}>
      <div className="flex w-[520px] flex-col gap-4 rounded-2xl bg-white p-6" style={{ boxShadow: "0 24px 64px #00000026" }}>
        <div className="flex items-start justify-between">
          <h2 className="text-base font-bold text-auth-text">{title}</h2>
          <button type="button" onClick={onClose}><X className="h-4 w-4" style={{ color: "#9E9E9E" }} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────

type ModalKey = null | "approve" | "reject" | "changes";

export function DpoRequestDetail({ id }: { id: string }) {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin"] });
  const router = useRouter();

  const reqQuery = useRequestDetail(id);
  const stepsQuery = useApprovalSteps(id);
  const groupsQuery = useGroups();
  const act = useActOnStep(id);

  const [modal, setModal] = useState<ModalKey>(null);
  const [comment, setComment] = useState("");
  // Track the most recent failure so the modal can surface a real reason
  // instead of silently closing/re-enabling the button. Must live BEFORE
  // any conditional return to keep hook order stable across renders.
  const [actionError, setActionError] = useState<string | null>(null);

  if (!isReady) return null;
  if (reqQuery.isLoading) return <div className="flex flex-1 items-center justify-center"><p className="text-sm text-auth-text-subtle">Loading…</p></div>;
  if (reqQuery.isError || !reqQuery.data) return <div className="flex flex-1 items-center justify-center"><p className="text-sm text-red-600">Failed to load request.</p></div>;

  const r = reqQuery.data;
  const steps = stepsQuery.data ?? [];
  const myStep = steps.find((s) => s.can_act);

  const groupNameById = new Map<number, string>();
  for (const g of groupsQuery.data ?? []) groupNameById.set(g.id, g.name);

  const senderName = groupNameById.get(r.requester_group_id ?? 0) ?? "—";
  const receiverName = groupNameById.get(r.receiver_group_id ?? 0) ?? "—";
  const hoursLeft = r.expiry_at ? (new Date(r.expiry_at).getTime() - Date.now()) / (1000 * 60 * 60) : null;
  const slaText = hoursLeft === null ? null : hoursLeft < 0 ? "SLA overdue" : `${Math.round(hoursLeft / 8)} business days left`;
  const urgent = hoursLeft !== null && hoursLeft > 0 && hoursLeft < 24;

  const timeline = [...steps]
    .filter((s) => s.completed_at)
    .sort((a, b) => new Date(b.completed_at!).getTime() - new Date(a.completed_at!).getTime());

  const handleAct = async (status: "approved" | "rejected" | "changes_requested") => {
    if (!myStep) return;
    try {
      setActionError(null);
      await act.mutateAsync({ stepId: myStep.id, status, comment: comment || undefined });
      setModal(null);
      router.push("/dpo");
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : `Could not ${status.replace("_", " ")} this request`,
      );
    }
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Top bar */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <Link
            href="/dpo"
            className="flex items-center gap-1.5 text-[13px] font-medium"
            style={{ color: "#9E9E9E" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to List
          </Link>
          <span style={{ color: "#EEEEEE" }}>·</span>
          <span className="text-base font-bold text-auth-text">Request Detail + PDPL Review</span>
          <span
            className="rounded px-2 py-0.5 text-[11px] font-semibold"
            style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
          >
            {r.request_number}
          </span>
        </div>
        <span
          className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
          style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#D76736" }} />
          DPO · Data Sharing
        </span>
      </div>

      {/* Main content */}
      <div className="flex flex-1 gap-4 overflow-auto px-8 pb-24 pt-6">
        {/* Left column */}
        <div className="flex flex-1 flex-col gap-4 min-w-0">
          {/* Breadcrumb + title */}
          <div
            className="flex flex-col gap-3 rounded-lg px-5 py-4"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <div className="flex items-center gap-1 text-[11px]" style={{ color: "#9E9E9E" }}>
              <Link href="/dpo" className="hover:underline">Organisation Request List</Link>
              <ChevronRight className="h-3 w-3" />
              <span>{r.title}</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-xl font-bold text-auth-text">{r.title}</h2>
              {myStep && (
                <span
                  className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-semibold"
                  style={{ backgroundColor: "#FFF7E6", color: "#92400E" }}
                >
                  Awaiting DPO Review
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[12px]" style={{ color: "#515157" }}>
              <span>User #{r.requester_id}</span>
              <span style={{ color: "#BABABA" }}>·</span>
              <span>{senderName} <ArrowRight className="inline h-3 w-3" /> {receiverName}</span>
              {r.data_classification && (
                <>
                  <span style={{ color: "#BABABA" }}>·</span>
                  <ClassificationBadge value={r.data_classification} />
                </>
              )}
              {slaText && (
                <>
                  <span style={{ color: "#BABABA" }}>·</span>
                  <span style={{ color: urgent ? "#D76736" : "#515157" }}>
                    <Clock className="inline h-3 w-3 mr-0.5" />{slaText}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Request details */}
          <section
            className="flex flex-col overflow-hidden rounded-lg"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <div className="flex h-10 items-center px-5" style={{ borderBottom: "1px solid #EEEEEE" }}>
              <span className="text-[13px] font-semibold text-auth-text">Request Details</span>
            </div>
            <div className="flex flex-col px-5 py-2">
              <MetaRow label="Classification" value={<ClassificationBadge value={r.data_classification} />} />
              <MetaRow label="Sharing Type" value={r.sharing_type === "external" ? "External" : "Internal"} />
              <MetaRow
                label="Personal Data"
                value={
                  r.personal_data_involved
                    ? <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: "#FFF0EB", color: "#D76736" }}>Yes</span>
                    : "No"
                }
              />
              <MetaRow label="Purpose" value={r.purpose} />
            </div>
          </section>

          {/* Query preview (structured mode) */}
          {r.data_type === "structured" && r.custom_sql && (
            <section
              className="flex flex-col overflow-hidden rounded-lg"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div className="flex h-10 items-center justify-between px-5" style={{ borderBottom: "1px solid #EEEEEE" }}>
                <span className="text-[13px] font-semibold text-auth-text">Query Preview</span>
                <button
                  type="button"
                  className="flex items-center gap-1.5 rounded-md px-3 py-1 text-[12px] font-medium text-white"
                  style={{ backgroundColor: "#D76736" }}
                >
                  <Play className="h-3 w-3" />
                  Run
                </button>
              </div>
              <pre
                className="mx-4 my-3 overflow-x-auto rounded-md p-4 font-mono text-xs"
                style={{ backgroundColor: "#1E1E2E", color: "#D4D4D4" }}
              >
                {r.custom_sql}
              </pre>
            </section>
          )}

          {/* Workflow progress */}
          <section
            className="flex flex-col overflow-hidden rounded-lg"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <div className="flex h-10 items-center px-5" style={{ borderBottom: "1px solid #EEEEEE" }}>
              <span className="text-[13px] font-semibold text-auth-text">Workflow Progress</span>
            </div>
            <WorkflowProgressBar steps={steps} />
          </section>

          {/* Activity */}
          {timeline.length > 0 && (
            <section
              className="flex flex-col overflow-hidden rounded-lg"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              <div className="flex h-10 items-center px-5" style={{ borderBottom: "1px solid #EEEEEE" }}>
                <span className="text-[13px] font-semibold text-auth-text">Activity</span>
              </div>
              <div className="flex flex-col gap-1.5 p-4">
                {timeline.map((s) => (
                  <div key={s.id} className="flex items-center justify-between text-[12px]">
                    <span style={{ color: "#515157" }}>
                      {s.status === "approved" ? "Approved" : s.status === "rejected" ? "Rejected" : "Changes requested"} ·{" "}
                      <span style={{ color: "#9E9E9E" }}>{s.assignee_name ?? `User #${s.assignee_user_id}`}</span>
                    </span>
                    <span style={{ color: "#9E9E9E" }}>{formatRelativeTime(s.completed_at!)}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right column — PDPL Review */}
        <PdplReviewPanel
          classification={r.data_classification}
          legalBasis={r.legal_basis}
          dpia={r.dpia_confirmed}
          myStep={myStep}
          onApprove={() => setModal("approve")}
          onChanges={() => setModal("changes")}
          onReject={() => setModal("reject")}
        />
      </div>

      {/* Sticky footer */}
      {myStep && (
        <div
          className="sticky bottom-0 flex h-16 items-center justify-between px-8"
          style={{ backgroundColor: "#FFFFFF", borderTop: "1px solid #EEEEEE" }}
        >
          <span className="text-[12px]" style={{ color: "#9E9E9E" }}>{r.request_number} · Awaiting DPO decision</span>
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
              Approve Request
            </button>
          </div>
        </div>
      )}

      {/* Modals */}
      {modal === "approve" && (
        <ModalShell title={`Approve ${r.request_number}`} onClose={() => { setModal(null); setActionError(null); }}>
          <p className="text-xs" style={{ color: "#515157", lineHeight: 1.6 }}>
            The request advances to the next workflow step. The audit trail records your decision.
          </p>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional DPO note…"
            className="h-24 w-full resize-none rounded-md border p-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          />
          {actionError && (
            <p className="text-xs" style={{ color: "#D32F2F" }}>{actionError}</p>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => { setModal(null); setActionError(null); }} className="flex h-9 items-center rounded-md border px-4 text-[13px]" style={{ borderColor: "#EEEEEE", color: "#616161" }}>Cancel</button>
            <button type="button" onClick={() => { handleAct("approved"); }} disabled={act.isPending} className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white" style={{ backgroundColor: "#D76736" }}>
              {act.isPending ? "Approving…" : "Approve"}
            </button>
          </div>
        </ModalShell>
      )}
      {modal === "changes" && (
        <ModalShell title="Request Changes" onClose={() => { setModal(null); setActionError(null); }}>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Explain what needs to be changed…"
            className="h-28 w-full resize-none rounded-md border p-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          />
          {actionError && (
            <p className="text-xs" style={{ color: "#D32F2F" }}>{actionError}</p>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => { setModal(null); setActionError(null); }} className="flex h-9 items-center rounded-md border px-4 text-[13px]" style={{ borderColor: "#EEEEEE", color: "#616161" }}>Cancel</button>
            <button type="button" onClick={() => { handleAct("changes_requested"); }} disabled={act.isPending || !comment.trim()} className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60" style={{ backgroundColor: "#D76736" }}>
              {act.isPending ? "Sending…" : "Send back"}
            </button>
          </div>
        </ModalShell>
      )}
      {modal === "reject" && (
        <ModalShell title="Reject Request" onClose={() => { setModal(null); setActionError(null); }}>
          <div className="rounded-md p-3 text-xs" style={{ backgroundColor: "#FEF2F2", border: "1px solid #FCA5A5", color: "#991B1B" }}>
            Rejection permanently closes this request. This action cannot be undone.
          </div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="State the reason for rejection clearly…"
            className="h-24 w-full resize-none rounded-md border p-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          />
          {actionError && (
            <p className="text-xs" style={{ color: "#D32F2F" }}>{actionError}</p>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => { setModal(null); setActionError(null); }} className="flex h-9 items-center rounded-md border px-4 text-[13px]" style={{ borderColor: "#EEEEEE", color: "#616161" }}>Cancel</button>
            <button type="button" onClick={() => { handleAct("rejected"); }} disabled={act.isPending} className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white" style={{ backgroundColor: "#B91C1C" }}>
              {act.isPending ? "Rejecting…" : "Reject request"}
            </button>
          </div>
        </ModalShell>
      )}
    </div>
  );
}
