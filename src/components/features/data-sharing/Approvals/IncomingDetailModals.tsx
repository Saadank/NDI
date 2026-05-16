"use client";

import { useState } from "react";
import { CircleX, MessageSquare, PackageCheck, X } from "lucide-react";

interface BaseProps {
  pending: boolean;
  onClose: () => void;
  onConfirm: (value: string) => Promise<void>;
}

function ModalShell({
  onClose: _onClose,
  children,
}: {
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "#00000080" }}
    >
      <div
        className="flex flex-col gap-5 rounded-xl bg-white p-6"
        style={{ width: 500, boxShadow: "0 8px 32px #00000025" }}
      >
        {children}
      </div>
    </div>
  );
}

// ─── Confirm Receipt ─────────────────────────────────────────────────────────

export function ConfirmReceiptModal({
  deptName,
  pending,
  onClose,
  onConfirm,
}: BaseProps & { deptName: string }) {
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    try {
      await onConfirm(comment.trim());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  };
  return (
    <ModalShell onClose={onClose}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <PackageCheck
            className="h-[18px] w-[18px]"
            style={{ color: "#D76736" }}
          />
          <h2 className="text-base font-bold" style={{ color: "#111827" }}>
            Confirm receipt
          </h2>
        </div>
        <button type="button" onClick={onClose}>
          <X className="h-4 w-4" style={{ color: "#9CA3AF" }} />
        </button>
      </div>
      <p
        className="text-[13px]"
        style={{ color: "#6B7280", lineHeight: 1.5 }}
      >
        By confirming, you accept this data on behalf of{" "}
        <strong>{deptName || "your department"}</strong>. The sender is
        notified and the workflow advances.
      </p>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Optional note for the audit trail…"
        className="h-20 w-full resize-none rounded-md p-3 text-[13px] outline-none"
        style={{
          backgroundColor: "#F9FAFB",
          border: "1px solid #E5E7EB",
          color: "#374151",
        }}
      />
      {err && <p className="text-xs text-red-600">{err}</p>}
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#E5E7EB", color: "#374151" }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={pending}
          className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
          style={{ backgroundColor: "#D76736" }}
        >
          {pending ? "Confirming…" : "Confirm receipt"}
        </button>
      </div>
    </ModalShell>
  );
}

// ─── Decline Receipt ─────────────────────────────────────────────────────────

export function DeclineReceiptModal({
  pending,
  onClose,
  onConfirm,
}: BaseProps) {
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    if (!reason.trim()) {
      setErr("A reason is required.");
      return;
    }
    try {
      await onConfirm(reason.trim());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  };
  return (
    <ModalShell onClose={onClose}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CircleX
            className="h-[18px] w-[18px]"
            style={{ color: "#DC2626" }}
          />
          <h2 className="text-base font-bold" style={{ color: "#111827" }}>
            Decline receipt
          </h2>
        </div>
        <button type="button" onClick={onClose}>
          <X className="h-4 w-4" style={{ color: "#9CA3AF" }} />
        </button>
      </div>
      <p
        className="text-[13px]"
        style={{ color: "#6B7280", lineHeight: 1.5 }}
      >
        The sender will be notified the data was not accepted. A reason is
        required and is added to the audit trail.
      </p>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5">
          <span
            className="text-[13px] font-semibold"
            style={{ color: "#374151" }}
          >
            Reason
          </span>
          <span
            className="rounded px-1.5 py-0.5 text-[11px] font-medium"
            style={{ backgroundColor: "#FEF2F2", color: "#DC2626" }}
          >
            Required
          </span>
        </div>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="State the reason — this will be sent to the sender…"
          className="h-20 w-full resize-none rounded-md p-3 text-[13px] outline-none"
          style={{
            backgroundColor: "#F9FAFB",
            border: "1px solid #E5E7EB",
            color: "#374151",
          }}
        />
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#E5E7EB", color: "#374151" }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={pending}
          className="flex h-9 items-center rounded-md px-4 text-[13px] font-semibold disabled:opacity-60"
          style={{ backgroundColor: "#FCA5A5", color: "#7F1D1D" }}
        >
          {pending ? "Declining…" : "Decline"}
        </button>
      </div>
    </ModalShell>
  );
}

// ─── Request More Details ────────────────────────────────────────────────────

export function RequestMoreDetailsModal({
  pending,
  onClose,
  onConfirm,
}: BaseProps) {
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    if (!comment.trim()) {
      setErr("Comment is required.");
      return;
    }
    try {
      await onConfirm(comment.trim());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  };
  return (
    <ModalShell onClose={onClose}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare
            className="h-[18px] w-[18px]"
            style={{ color: "#D76736" }}
          />
          <h2 className="text-base font-bold" style={{ color: "#111827" }}>
            Request more details
          </h2>
        </div>
        <button type="button" onClick={onClose}>
          <X className="h-4 w-4" style={{ color: "#9CA3AF" }} />
        </button>
      </div>
      <p
        className="text-[13px]"
        style={{ color: "#6B7280", lineHeight: 1.5 }}
      >
        Send a question back to the sender — they&rsquo;ll resolve it before
        you confirm receipt.
      </p>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5">
          <span
            className="text-[13px] font-semibold"
            style={{ color: "#374151" }}
          >
            Your comment
          </span>
          <span
            className="rounded px-1.5 py-0.5 text-[11px] font-medium"
            style={{ backgroundColor: "#FEF2F2", color: "#DC2626" }}
          >
            Required
          </span>
        </div>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="What do you need clarified before confirming receipt?"
          className="h-20 w-full resize-none rounded-md p-3 text-[13px] outline-none"
          style={{
            backgroundColor: "#F9FAFB",
            border: "1px solid #E5E7EB",
            color: "#374151",
          }}
        />
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#E5E7EB", color: "#374151" }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={pending}
          className="flex h-9 items-center rounded-md px-4 text-[13px] font-semibold text-white disabled:opacity-60"
          style={{ backgroundColor: "#D76736" }}
        >
          {pending ? "Sending…" : "Send"}
        </button>
      </div>
    </ModalShell>
  );
}
