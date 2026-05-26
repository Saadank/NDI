"use client";

import Link from "next/link";
import { Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listRecipients,
  revokeRecipient,
  type ExternalRecipient,
  type RecipientTokenStatus,
} from "@/lib/api/products/data-sharing/recipients.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate } from "@/lib/utils/formatters";

import { RevokeRecipientModal } from "@/components/features/data-sharing/Dpo/RevokeRecipientModal";

// ─── Status pill ─────────────────────────────────────────────────────────────

type Filter = "all" | RecipientTokenStatus;

function TokenStatusPill({ status }: { status: RecipientTokenStatus }) {
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

// ─── Status counter chip (top of page) ───────────────────────────────────────

function CounterChip({
  count,
  label,
  bg,
  fg,
}: {
  count: number;
  label: string;
  bg: string;
  fg: string;
}) {
  return (
    <span
      className="flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium"
      style={{ backgroundColor: bg, color: fg }}
    >
      <span className="font-semibold">{count}</span>
      {label}
    </span>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ExternalRecipientsPage() {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin"] });
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [revokeFor, setRevokeFor] = useState<ExternalRecipient | null>(null);

  const recipientsQuery = useQuery({
    queryKey: ["dpo", "external-recipients"],
    queryFn: listRecipients,
    enabled: isReady,
  });

  const revokeMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      revokeRecipient(id, { reason: reason || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dpo", "external-recipients"] });
      setRevokeFor(null);
    },
  });

  const recipients = recipientsQuery.data ?? [];

  // Per Pencil frame 17 the header above the table shows three count chips
  // (active / expired / revoked tokens). When the backend doesn't return
  // token-level data we fall back to is_active for the active vs revoked
  // split and show 0 for expired.
  const counts = useMemo(() => {
    let active = 0;
    let expired = 0;
    let revoked = 0;
    for (const r of recipients) {
      const ts: RecipientTokenStatus =
        r.token_status ?? (r.is_active ? "active" : "revoked");
      if (ts === "active") active += 1;
      else if (ts === "expired") expired += 1;
      else if (ts === "revoked") revoked += 1;
    }
    return { active, expired, revoked };
  }, [recipients]);

  if (!isReady) return null;

  const filtered = recipients.filter((r) => {
    const ts: RecipientTokenStatus =
      r.token_status ?? (r.is_active ? "active" : "revoked");
    if (filter !== "all" && ts !== filter) return false;
    if (!search) return true;
    const text = `${r.organisation} ${r.name} ${r.email} ${r.country ?? ""}`.toLowerCase();
    return text.includes(search.toLowerCase());
  });

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Top bar */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <h1 className="text-lg font-bold text-auth-text">External Recipients Directory</h1>
        <span
          className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
          style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#D76736" }} />
          DPO · Data Sharing
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* Counter chips + search */}
        <div className="flex items-center gap-3">
          <CounterChip count={counts.active} label="active tokens" bg="#ECFDF5" fg="#047857" />
          <CounterChip count={counts.expired} label="expired" bg="#F3F4F6" fg="#6B7280" />
          <CounterChip count={counts.revoked} label="revoked" bg="#FEF2F2" fg="#B91C1C" />
          <div className="ml-auto flex h-9 w-72 items-center gap-2 rounded-md px-3"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}>
            <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search organisations…"
              className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
            />
          </div>
        </div>

        {/* Filter chips row */}
        <div className="flex items-center gap-2 text-[12px]">
          <span style={{ color: "#9E9E9E" }}>Filter:</span>
          {([
            { id: "all", label: "All Status" },
            { id: "active", label: "Active" },
            { id: "expired", label: "Expired" },
            { id: "revoked", label: "Revoked" },
          ] as { id: Filter; label: string }[]).map((f) => {
            const active = filter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                className="flex h-7 items-center rounded-full px-3 text-[12px] font-medium"
                style={
                  active
                    ? { backgroundColor: "#FFF5F0", color: "#D76736", border: "1px solid #FDDCCC" }
                    : { backgroundColor: "#FFFFFF", color: "#515157", border: "1px solid #EEEEEE" }
                }
              >
                {f.label}
                {active && filter !== "all" && <X className="ml-1 h-3 w-3" />}
              </button>
            );
          })}
        </div>

        {/* Table — columns per Pencil frame 17 */}
        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}>
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ORGANISATION</span>
            <span className="w-[200px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>CONTACT</span>
            <span className="w-[80px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>FILES</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>TOKEN STATUS</span>
            <span className="w-[160px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>LAST ACCESSED</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ACTIONS</span>
          </div>

          {recipientsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : recipientsQuery.isError ? (
            <div className="py-20 text-center text-sm text-red-600">Failed to load recipients.</div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-sm text-auth-text-subtle">
              No recipients match the current filters.
            </div>
          ) : (
            filtered.map((r, i) => {
              const ts: RecipientTokenStatus =
                r.token_status ?? (r.is_active ? "active" : "revoked");
              return (
                <div
                  key={r.id}
                  className="flex h-14 items-center px-5 hover:bg-[#FFFBF9]"
                  style={{ borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined }}
                >
                  <div className="flex flex-1 flex-col gap-0.5 min-w-0">
                    <span className="truncate pr-4 text-[13px] font-medium text-auth-text">
                      {r.organisation}
                    </span>
                    {r.country && (
                      <span className="truncate pr-4 text-[11px]" style={{ color: "#9E9E9E" }}>
                        {r.country}
                      </span>
                    )}
                  </div>
                  <div className="w-[200px] flex flex-col">
                    <span className="text-[12px] truncate" style={{ color: "#1A1A1A" }}>{r.name}</span>
                    <span className="text-[11px] truncate" style={{ color: "#9E9E9E" }}>{r.email}</span>
                  </div>
                  <span className="w-[80px] text-[12px]" style={{ color: "#515157" }}>
                    {r.files_count ?? "—"}
                  </span>
                  <span className="w-[120px]"><TokenStatusPill status={ts} /></span>
                  <span className="w-[160px] text-[12px]" style={{ color: "#9E9E9E" }}>
                    {r.last_accessed_at ? formatDate(r.last_accessed_at) : "—"}
                  </span>
                  <div className="flex w-[120px] items-center gap-3 text-[12px]">
                    <Link
                      href={`/dpo/recipients/${r.id}`}
                      className="font-medium hover:underline"
                      style={{ color: "#1D4ED8" }}
                    >
                      View
                    </Link>
                    {ts === "active" && (
                      <button
                        type="button"
                        onClick={() => setRevokeFor(r)}
                        className="font-medium hover:underline"
                        style={{ color: "#B91C1C" }}
                      >
                        Revoke
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {revokeFor && (
        <RevokeRecipientModal
          recipient={revokeFor}
          pending={revokeMutation.isPending}
          error={
            revokeMutation.error instanceof Error
              ? revokeMutation.error.message
              : null
          }
          onClose={() => setRevokeFor(null)}
          onConfirm={(reason) =>
            revokeMutation.mutate({ id: revokeFor.id, reason })
          }
        />
      )}
    </div>
  );
}
