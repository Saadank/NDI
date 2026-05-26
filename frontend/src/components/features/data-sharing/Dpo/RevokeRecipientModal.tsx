"use client";

import { useState } from "react";
import { TriangleAlert, X } from "lucide-react";

import type { ExternalRecipient } from "@/lib/api/products/data-sharing/recipients.api";

// Pencil frame 18 — "Revoke access for <NAME>?". Shows three info rows
// (request title / file count / contact email) plus an OPTIONAL reason
// textarea ("for the audit trail"). Cancel + red Revoke button.
//
// The current backend doesn't return a per-recipient active-request
// summary, so the info rows are filled from the recipient record where
// possible and dashed otherwise — same trade-off as the list page.

export interface RevokeRecipientModalProps {
  recipient: ExternalRecipient;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}

export function RevokeRecipientModal({
  recipient,
  pending,
  error,
  onClose,
  onConfirm,
}: RevokeRecipientModalProps) {
  const [reason, setReason] = useState("");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "#00000080" }}
    >
      <div
        className="flex w-[500px] flex-col gap-5 rounded-xl bg-white p-6"
        style={{ boxShadow: "0 24px 64px #00000026" }}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold" style={{ color: "#111827" }}>
            Revoke access for {recipient.name}?
          </h2>
          <button type="button" onClick={onClose}>
            <X className="h-4 w-4" style={{ color: "#9CA3AF" }} />
          </button>
        </div>

        <p className="text-[13px]" style={{ color: "#6B7280", lineHeight: 1.5 }}>
          Revoking the token immediately stops the magic link from working. The
          contact will see an &ldquo;access has ended&rdquo; page if they try to
          download. Already-downloaded files are not affected.
        </p>

        {/* Info rows */}
        <div
          className="flex flex-col gap-1 rounded-md p-3 text-[12px]"
          style={{ backgroundColor: "#F9FAFB", border: "1px solid #E5E7EB" }}
        >
          <div className="flex items-start justify-between gap-3">
            <span style={{ color: "#9CA3AF" }}>Request</span>
            <span className="text-right" style={{ color: "#374151" }}>
              {recipient.files_count
                ? `${recipient.files_count} file${recipient.files_count === 1 ? "" : "s"} shared`
                : recipient.organisation}
            </span>
          </div>
          <div className="flex items-start justify-between gap-3">
            <span style={{ color: "#9CA3AF" }}>Files</span>
            <span style={{ color: "#374151" }}>
              {recipient.files_count ?? "—"}
            </span>
          </div>
          <div className="flex items-start justify-between gap-3">
            <span style={{ color: "#9CA3AF" }}>Contact email</span>
            <span style={{ color: "#374151" }}>{recipient.email}</span>
          </div>
        </div>

        {/* Optional reason */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-semibold" style={{ color: "#374151" }}>
            Reason for revocation (optional)
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Add a note for the audit trail…"
            className="h-20 w-full resize-none rounded-md p-3 text-[13px] outline-none"
            style={{ backgroundColor: "#F9FAFB", border: "1px solid #E5E7EB", color: "#374151" }}
          />
        </div>

        {/* Warning */}
        <div
          className="flex items-start gap-2 rounded-md p-3 text-[12px]"
          style={{ backgroundColor: "#FEF2F2", border: "1px solid #FECACA", color: "#991B1B" }}
        >
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            This action immediately revokes all active tokens for this
            recipient and is recorded in the audit log.
          </span>
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

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
            onClick={() => onConfirm(reason.trim())}
            disabled={pending}
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
            style={{ backgroundColor: "#B91C1C" }}
          >
            {pending ? "Revoking…" : "Revoke access"}
          </button>
        </div>
      </div>
    </div>
  );
}
