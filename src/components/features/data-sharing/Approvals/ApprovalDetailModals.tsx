"use client";

import { useState } from "react";
import { CircleX, Flag, MessageSquare, TriangleAlert, X } from "lucide-react";

interface ModalProps {
  onClose: () => void;
  onConfirm: (value: string) => Promise<void>;
  pending: boolean;
}

function ModalShell({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "#00000080" }}>
      <div className="flex flex-col gap-5 rounded-xl bg-white p-6" style={{ width: 500, boxShadow: "0 8px 32px #00000025" }}>
        {children}
      </div>
    </div>
  );
}

const REJECT_REASONS = ["Insufficient justification", "PDPL basis unclear"];

export function RequestChangesModal({ onClose, onConfirm, pending }: ModalProps) {
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    if (!comment.trim()) { setErr("Comment is required."); return; }
    try { await onConfirm(comment.trim()); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); }
  };
  return (
    <ModalShell onClose={onClose}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-[18px] w-[18px]" style={{ color: "#D76736" }} />
          <h2 className="text-base font-bold" style={{ color: "#111827" }}>Request Changes</h2>
        </div>
        <button type="button" onClick={onClose}><X className="h-4 w-4" style={{ color: "#9CA3AF" }} /></button>
      </div>
      <p className="text-[13px]" style={{ color: "#6B7280", lineHeight: 1.5 }}>
        The requester will be notified and sent back to edit and resubmit their request. Address your specific concern in the comment — they must resolve it before resubmitting.
      </p>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[13px] font-semibold" style={{ color: "#374151" }}>Your comment</span>
          <span className="rounded px-1.5 py-0.5 text-[11px] font-medium" style={{ backgroundColor: "#FEF2F2", color: "#DC2626" }}>Required</span>
        </div>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Explain what needs to be changed or clarified…"
          className="h-20 w-full resize-none rounded-md p-3 text-[13px] outline-none"
          style={{ backgroundColor: "#F9FAFB", border: "1px solid #E5E7EB", color: "#374151" }}
        />
      </div>
      <div className="flex items-start gap-2 rounded-md p-3 text-[12px]" style={{ backgroundColor: "#FFFBEB", border: "1px solid #FDE68A", color: "#92400E" }}>
        <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#D97706" }} />
        <span>If the requester changes classification, legal basis, personal data flag, or data selection, DPO review will re-trigger automatically.</span>
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <div className="flex items-center justify-end gap-2">
        <button type="button" onClick={onClose} className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium" style={{ borderColor: "#E5E7EB", color: "#374151" }}>Cancel</button>
        <button
          type="button"
          onClick={submit}
          disabled={pending}
          className="flex h-9 items-center rounded-md px-4 text-[13px] font-semibold disabled:cursor-not-allowed"
          style={comment.trim() ? { backgroundColor: "#D76736", color: "#FFFFFF" } : { backgroundColor: "#E5E7EB", color: "#9CA3AF" }}
        >
          {pending ? "Sending…" : "Send back to Requester"}
        </button>
      </div>
    </ModalShell>
  );
}

export function RejectModal({ onClose, onConfirm, pending }: ModalProps) {
  const [comment, setComment] = useState("");
  const [chips, setChips] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const toggle = (r: string) => setChips((c) => c.includes(r) ? c.filter((x) => x !== r) : [...c, r]);
  const submit = async () => {
    const body = [...chips, ...(comment.trim() ? [comment.trim()] : [])].join(" — ");
    if (!body) { setErr("A rejection reason is required."); return; }
    try { await onConfirm(body); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); }
  };
  return (
    <ModalShell onClose={onClose}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CircleX className="h-[18px] w-[18px]" style={{ color: "#DC2626" }} />
          <h2 className="text-base font-bold" style={{ color: "#111827" }}>Reject Request</h2>
        </div>
        <button type="button" onClick={onClose}><X className="h-4 w-4" style={{ color: "#9CA3AF" }} /></button>
      </div>
      <div className="flex items-start gap-2 rounded-md p-3 text-[12px]" style={{ backgroundColor: "#FEF2F2", border: "1px solid #FECACA", color: "#991B1B" }}>
        <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#DC2626" }} />
        <span>Rejection permanently closes this request and notifies the requester. This action cannot be undone.</span>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[13px] font-semibold" style={{ color: "#374151" }}>Rejection reason</span>
          <span className="rounded px-1.5 py-0.5 text-[11px] font-medium" style={{ backgroundColor: "#FEF2F2", color: "#DC2626" }}>Required</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {REJECT_REASONS.map((r) => (
            <button key={r} type="button" onClick={() => toggle(r)} className="rounded-full px-2.5 py-1 text-[11px]"
              style={chips.includes(r) ? { backgroundColor: "#FEF2F2", color: "#DC2626", border: "1px solid #FECACA" } : { backgroundColor: "#F3F4F6", color: "#374151", border: "1px solid #E5E7EB" }}>
              {r}
            </button>
          ))}
        </div>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="State the reason for rejection clearly — this will be sent to the requester…"
          className="h-20 w-full resize-none rounded-md p-3 text-[13px] outline-none"
          style={{ backgroundColor: "#F9FAFB", border: "1px solid #E5E7EB", color: "#374151" }}
        />
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <div className="flex items-center justify-end gap-2">
        <button type="button" onClick={onClose} className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium" style={{ borderColor: "#E5E7EB", color: "#374151" }}>Cancel</button>
        <button type="button" onClick={submit} disabled={pending} className="flex h-9 items-center rounded-md px-4 text-[13px] font-semibold"
          style={{ backgroundColor: "#FCA5A5", color: "#7F1D1D" }}>
          {pending ? "Rejecting…" : "Reject request"}
        </button>
      </div>
    </ModalShell>
  );
}

export function ApproveModal({ onClose, onConfirm, pending }: ModalProps) {
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    try { await onConfirm(comment.trim()); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); }
  };
  return (
    <ModalShell onClose={onClose}>
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold" style={{ color: "#111827" }}>Approve Request</h2>
        <button type="button" onClick={onClose}><X className="h-4 w-4" style={{ color: "#9CA3AF" }} /></button>
      </div>
      <p className="text-[13px]" style={{ color: "#6B7280", lineHeight: 1.5 }}>
        The request will advance to the next workflow step. Add an optional note for the audit trail.
      </p>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Optional note for the audit trail…"
        className="h-20 w-full resize-none rounded-md p-3 text-[13px] outline-none"
        style={{ backgroundColor: "#F9FAFB", border: "1px solid #E5E7EB", color: "#374151" }}
      />
      {err && <p className="text-xs text-red-600">{err}</p>}
      <div className="flex items-center justify-end gap-2">
        <button type="button" onClick={onClose} className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium" style={{ borderColor: "#E5E7EB", color: "#374151" }}>Cancel</button>
        <button type="button" onClick={submit} disabled={pending} className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
          style={{ backgroundColor: "#D76736" }}>
          {pending ? "Approving…" : "Approve"}
        </button>
      </div>
    </ModalShell>
  );
}

// Flag for Technical Review — frame 09. Confirms a reviewer + reason. The
// caller wraps the request-changes endpoint and prefixes "[FLAG: <reviewer>]"
// to the comment so the timeline/banner can identify it as a flag.
export interface FlagPayload {
  contact: string;
  comment: string;
}

interface FlagModalProps {
  onClose: () => void;
  onConfirm: (payload: FlagPayload) => Promise<void>;
  pending: boolean;
}

export function FlagModal({ onClose, onConfirm, pending }: FlagModalProps) {
  const [contact, setContact] = useState("");
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    if (!contact.trim()) { setErr("Please specify who should review."); return; }
    if (!comment.trim()) { setErr("Please describe what needs technical review."); return; }
    try {
      await onConfirm({ contact: contact.trim(), comment: comment.trim() });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  };
  return (
    <ModalShell onClose={onClose}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Flag className="h-[18px] w-[18px]" style={{ color: "#2563EB" }} />
          <h2 className="text-base font-bold" style={{ color: "#111827" }}>Flag for Technical Review</h2>
        </div>
        <button type="button" onClick={onClose}><X className="h-4 w-4" style={{ color: "#9CA3AF" }} /></button>
      </div>
      <p className="text-[13px]" style={{ color: "#6B7280", lineHeight: 1.5 }}>
        Routes this request to a technical reviewer for input. You can still
        approve, reject, or request changes at any time after their response.
      </p>
      <div className="flex flex-col gap-1.5">
        <label className="text-[12px] font-semibold" style={{ color: "#374151" }}>
          Who should review? <span style={{ color: "#D76736" }}>*</span>
        </label>
        <input
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          placeholder="Name or team (e.g. IT Security)"
          className="h-10 rounded-md border px-3 text-[13px] outline-none"
          style={{ borderColor: "#E5E7EB" }}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] font-semibold" style={{ color: "#374151" }}>Comment</span>
          <span className="rounded px-1.5 py-0.5 text-[11px] font-medium" style={{ backgroundColor: "#FEF2F2", color: "#DC2626" }}>Required</span>
        </div>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="What technical aspect needs review? (e.g. SQL safety, schema sensitivity)"
          className="h-20 w-full resize-none rounded-md p-3 text-[13px] outline-none"
          style={{ backgroundColor: "#F9FAFB", border: "1px solid #E5E7EB", color: "#374151" }}
        />
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <div className="flex items-center justify-end gap-2">
        <button type="button" onClick={onClose} className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium" style={{ borderColor: "#E5E7EB", color: "#374151" }}>Cancel</button>
        <button
          type="button"
          onClick={submit}
          disabled={pending || !contact.trim() || !comment.trim()}
          className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-50"
          style={{ backgroundColor: "#1D4ED8" }}
        >
          {pending ? "Flagging…" : "Flag for review"}
        </button>
      </div>
    </ModalShell>
  );
}
