"use client";

import Link from "next/link";
import { ArrowLeft, ChevronRight, Download } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getRecipient,
  revokeRecipient,
  type ExternalRecipient,
  type RecipientTokenStatus,
} from "@/lib/api/products/data-sharing/recipients.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate, formatDateTime } from "@/lib/utils/formatters";

import { RevokeRecipientModal } from "./RevokeRecipientModal";

// Pencil frame 19 — Recipient Detail (NEW). Single page, no tabs.
// Sections: Overview · Recipient Overview counters · Share Requests
// Delivered table · Download Activity Log table.

function StatusPill({ status }: { status: RecipientTokenStatus }) {
  const map: Record<RecipientTokenStatus, { bg: string; fg: string; label: string }> = {
    active: { bg: "#ECFDF5", fg: "#047857", label: "Active" },
    expired: { bg: "#F3F4F6", fg: "#6B7280", label: "Expired" },
    revoked: { bg: "#FEF2F2", fg: "#B91C1C", label: "Revoked" },
  };
  const s = map[status];
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium"
      style={{ backgroundColor: s.bg, color: s.fg }}
    >
      {s.label}
    </span>
  );
}

function StatBlock({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "active" | "expired" | "revoked" | "neutral";
}) {
  const colorMap: Record<string, string> = {
    active: "#047857",
    expired: "#6B7280",
    revoked: "#B91C1C",
    neutral: "#111827",
  };
  return (
    <div
      className="flex flex-1 flex-col gap-1 rounded-lg p-3"
      style={{ backgroundColor: "#F9FAFB", border: "1px solid #E5E7EB" }}
    >
      <span className="text-[10px] font-semibold uppercase tracking-[0.5px]" style={{ color: "#9CA3AF" }}>
        {label}
      </span>
      <span className="text-[15px] font-bold" style={{ color: colorMap[tone ?? "neutral"] }}>
        {value}
      </span>
    </div>
  );
}

export function RecipientDetail({ id }: { id: string }) {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin"] });
  const qc = useQueryClient();
  const [showRevoke, setShowRevoke] = useState(false);

  const recipientQuery = useQuery({
    queryKey: ["dpo", "external-recipients", id],
    queryFn: () => getRecipient(id),
    enabled: isReady,
  });

  const revokeMutation = useMutation({
    mutationFn: (reason: string) =>
      revokeRecipient(id, { reason: reason || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dpo", "external-recipients"] });
      qc.invalidateQueries({ queryKey: ["dpo", "external-recipients", id] });
      setShowRevoke(false);
    },
  });

  if (!isReady) return null;
  if (recipientQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm" style={{ color: "#9CA3AF" }}>Loading…</p>
      </div>
    );
  }
  if (recipientQuery.isError || !recipientQuery.data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-red-600">Failed to load recipient.</p>
      </div>
    );
  }

  const r: ExternalRecipient = recipientQuery.data;
  const ts: RecipientTokenStatus =
    r.token_status ?? (r.is_active ? "active" : "revoked");
  const canRevoke = ts === "active";

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#F9FAFB" }}>
      {/* Top bar */}
      <div
        className="flex h-14 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-1.5 text-[12px]" style={{ color: "#6B7280" }}>
          <span style={{ color: "#374151", fontWeight: 600 }}>Data Sharing Platform</span>
          <ChevronRight className="h-3 w-3" />
          <Link href="/dpo/recipients" className="hover:underline">External Recipients</Link>
          <ChevronRight className="h-3 w-3" />
          <span style={{ color: "#111827", fontWeight: 500 }}>{r.organisation}</span>
        </div>
        <span
          className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
          style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#D76736" }} />
          DPO · Data Sharing
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
        <Link
          href="/dpo/recipients"
          className="flex items-center gap-1.5 self-start text-[12px] font-medium"
          style={{ color: "#6B7280" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to External Recipients
        </Link>

        {/* Title row */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <h1 className="text-[22px] font-bold" style={{ color: "#111827" }}>
              {r.organisation}
            </h1>
            <p className="text-[12px]" style={{ color: "#6B7280" }}>
              {r.name} · {r.email}
              {r.phone ? ` · ${r.phone}` : ""}
              {r.country ? ` · ${r.country}` : ""}
            </p>
          </div>
          {canRevoke && (
            <button
              type="button"
              onClick={() => setShowRevoke(true)}
              className="flex h-9 items-center gap-1.5 rounded-md px-4 text-[13px] font-semibold text-white"
              style={{ backgroundColor: "#B91C1C" }}
            >
              Revoke all active tokens
            </button>
          )}
        </div>

        {/* Recipient Overview counters */}
        <section
          className="flex flex-col gap-3 rounded-lg p-4"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}
        >
          <h2 className="text-[12px] font-semibold uppercase tracking-[0.5px]" style={{ color: "#9CA3AF" }}>
            Recipient Overview
          </h2>
          <div className="flex gap-3 flex-wrap">
            <StatBlock
              label="First Granted"
              value={r.first_granted_at ? formatDate(r.first_granted_at) : formatDate(r.created_at)}
              tone="neutral"
            />
            <StatBlock
              label="Last Activity"
              value={r.last_accessed_at ? formatDate(r.last_accessed_at) : "—"}
              tone="neutral"
            />
            <StatBlock
              label="Tokens Delivered"
              value={r.tokens_delivered != null ? `${r.tokens_delivered} total` : "—"}
              tone="neutral"
            />
            <StatBlock
              label="Active Tokens"
              value={r.active_tokens != null ? `${r.active_tokens} active` : (canRevoke ? "Active" : "—")}
              tone="active"
            />
            <StatBlock
              label="Expired Tokens"
              value={r.expired_tokens != null ? `${r.expired_tokens} expired` : "—"}
              tone="expired"
            />
            <StatBlock
              label="Revoked Tokens"
              value={r.revoked_tokens != null ? `${r.revoked_tokens} revoked` : (ts === "revoked" ? "Revoked" : "—")}
              tone="revoked"
            />
          </div>
        </section>

        {/* Share Requests Delivered */}
        <section
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}
        >
          <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: "1px solid #EEEEEE" }}>
            <h2 className="text-[13px] font-semibold" style={{ color: "#374151" }}>
              Share Requests Delivered
            </h2>
            <span className="text-[12px]" style={{ color: "#9CA3AF" }}>
              Per-request token detail comes from a backend endpoint that&rsquo;s not
              wired to this page yet.
            </span>
          </div>
          <div className="flex h-10 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}>
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>REQUEST</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>TOKEN STATUS</span>
            <span className="w-[180px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>EXPIRY · DOWNLOADS</span>
            <span className="w-[100px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ACTION</span>
          </div>
          <div className="py-12 text-center text-[13px]" style={{ color: "#9CA3AF" }}>
            <StatusPill status={ts} />
            <p className="mt-3">No per-request token data available for this recipient yet.</p>
          </div>
        </section>

        {/* Download Activity Log */}
        <section
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}
        >
          <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: "1px solid #EEEEEE" }}>
            <h2 className="text-[13px] font-semibold" style={{ color: "#374151" }}>
              Download Activity Log
            </h2>
            <button
              type="button"
              className="flex h-7 items-center gap-1.5 rounded-md border px-3 text-[12px] font-medium"
              style={{ borderColor: "#E5E7EB", color: "#374151" }}
              onClick={() => {
                // CSV export of whatever is currently visible. Today there's
                // no per-recipient activity endpoint — emit a single stub
                // row so the button is wired and the user can verify the
                // download path works end-to-end.
                const csv = [
                  "timestamp,file,status,ip",
                  `${new Date().toISOString()},${r.organisation},${ts},—`,
                ].join("\n");
                const blob = new Blob([csv], { type: "text/csv" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `recipient-${r.id}-activity.csv`;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              <Download className="h-3 w-3" />
              Export CSV
            </button>
          </div>
          <div className="flex h-10 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}>
            <span className="w-[200px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>TIMESTAMP · FILE</span>
            <span className="flex-1" />
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STATUS</span>
            <span className="w-[160px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>IP/LOCATION</span>
          </div>
          <div className="py-12 text-center text-[13px]" style={{ color: "#9CA3AF" }}>
            Recipient activity log: {r.last_accessed_at ? `Last accessed ${formatDateTime(r.last_accessed_at)}` : "no recorded activity yet"}.
          </div>
        </section>
      </div>

      {showRevoke && (
        <RevokeRecipientModal
          recipient={r}
          pending={revokeMutation.isPending}
          error={
            revokeMutation.error instanceof Error
              ? revokeMutation.error.message
              : null
          }
          onClose={() => setShowRevoke(false)}
          onConfirm={(reason) => revokeMutation.mutate(reason)}
        />
      )}
    </div>
  );
}
