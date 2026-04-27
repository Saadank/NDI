"use client";

import Link from "next/link";
import { Inbox, Plus } from "lucide-react";

import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useAuthStore } from "@/lib/store/auth.store";
import { REQUEST_STATUS_LABELS } from "@/lib/utils/constants";
import { formatDate } from "@/lib/utils/formatters";
import type {
  RequestStatus,
  ShareRequest,
} from "@/lib/types/data-sharing/request.types";

const STATUS_STYLE: Record<RequestStatus, { bg: string; color: string }> = {
  draft: { bg: "#EEEEEE", color: "#616161" },
  submitted: { bg: "#EEF2FF", color: "#3B4FD6" },
  in_review: { bg: "#FFF7E6", color: "#B45309" },
  approved: { bg: "#F0FAF0", color: "#449235" },
  rejected: { bg: "#FFF0F0", color: "#D32F2F" },
  cancelled: { bg: "#F5F5F5", color: "#9E9E9E" },
  completed: { bg: "#F0FAF0", color: "#449235" },
  expired: { bg: "#F5F5F5", color: "#9E9E9E" },
};

function StatusBadge({ status }: { status: RequestStatus }) {
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.draft;
  return (
    <span
      className="inline-flex items-center rounded px-2.5 py-1 text-xs font-medium"
      style={{ backgroundColor: style.bg, color: style.color }}
    >
      {REQUEST_STATUS_LABELS[status] ?? status}
    </span>
  );
}

function formatClassification(c: string) {
  return c.charAt(0).toUpperCase() + c.slice(1);
}

export interface RequestsTableProps {
  // Filter applied to the API request — consistent with the wireframe tabs.
  // 'mine'  → requests I raised (default)
  // 'incoming' → requests sent TO my department
  // 'all'   → everything I'm allowed to see
  scope?: "mine" | "incoming" | "all";
}

export function RequestsTable({ scope = "mine" }: RequestsTableProps) {
  // Backend's list endpoint already filters by role. For "mine" we just take
  // the unfiltered page (requesters only see their own). For "incoming" we
  // filter client-side by receiver_group_id == my group_id.
  const requestsQuery = useRequests({ page: 1, limit: 50 });
  const groupsQuery = useGroups();
  const myGroupId = useAuthStore((s) => s.user?.group_id ?? null);
  const myUserId = useAuthStore((s) => s.user?.id ?? null);

  const groupNameById = new Map<number, string>();
  for (const g of groupsQuery.data ?? []) groupNameById.set(g.id, g.name);

  const all = requestsQuery.data?.data ?? [];
  const filtered = all.filter((r: ShareRequest) => {
    if (scope === "mine") return r.requester_id === myUserId;
    if (scope === "incoming") return r.receiver_group_id === myGroupId;
    return true;
  });

  if (requestsQuery.isLoading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24">
        <p className="text-sm" style={{ color: "#9E9E9E" }}>
          Loading requests…
        </p>
      </div>
    );
  }

  if (requestsQuery.isError) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24">
        <p className="text-sm" style={{ color: "#EF4444" }}>
          Failed to load requests.{" "}
          {requestsQuery.error instanceof Error
            ? requestsQuery.error.message
            : ""}
        </p>
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24">
        <div
          className="flex h-14 w-14 items-center justify-center rounded-full"
          style={{ backgroundColor: "#FFF5F0" }}
        >
          <Inbox className="h-7 w-7" style={{ color: "#D76736" }} />
        </div>
        <div className="flex flex-col items-center gap-1 text-center">
          <p className="text-sm font-semibold text-auth-text">No requests yet</p>
          <p
            className="text-[13px]"
            style={{ color: "#9E9E9E", maxWidth: 300 }}
          >
            You haven&apos;t raised any data sharing requests yet. Start by
            submitting your first request.
          </p>
        </div>
        <Link
          href="/data-sharing/new"
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          Raise Your First Request
        </Link>
      </div>
    );
  }

  return (
    <>
      {filtered.map((r, i) => {
        const highlight =
          r.status === "rejected" || r.status === "in_review";
        return (
          <Link
            key={r.id}
            href={`/data-sharing/${r.id}`}
            className="flex h-16 shrink-0 items-center px-5 transition-colors hover:bg-[#FFFBF9]"
            style={{
              backgroundColor: highlight ? "#FFFBF9" : undefined,
              borderBottom:
                i < filtered.length - 1 ? "1px solid #EEEEEE" : undefined,
            }}
          >
            <div className="flex flex-1 flex-col gap-1">
              <span className="text-[13px] font-semibold text-auth-text">
                {r.title}
              </span>
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                {scope === "incoming" ? "← " : "→ "}
                {groupNameById.get(r.receiver_group_id ?? 0) ??
                  (r.sharing_type === "external" ? "External" : "—")}{" "}
                · {r.request_number}
              </span>
            </div>
            <span className="w-40 text-[13px]" style={{ color: "#515157" }}>
              {groupNameById.get(r.receiver_group_id ?? 0) ?? "—"}
            </span>
            <span className="w-[130px] text-xs" style={{ color: "#9E9E9E" }}>
              {formatClassification(r.data_classification)}
            </span>
            <div className="w-[150px]">
              <StatusBadge status={r.status} />
            </div>
            <span className="w-[100px] text-xs" style={{ color: "#9E9E9E" }}>
              {r.expiry_at ? formatDate(r.expiry_at) : "—"}
            </span>
          </Link>
        );
      })}
    </>
  );
}

