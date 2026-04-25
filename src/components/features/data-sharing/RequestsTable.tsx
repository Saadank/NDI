"use client";

import Link from "next/link";
import { Inbox, Plus } from "lucide-react";

import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { REQUEST_STATUS_LABELS } from "@/lib/utils/constants";
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

function formatClassification(c: string): string {
  return c.charAt(0).toUpperCase() + c.slice(1);
}

function formatRow(r: ShareRequest) {
  return {
    id: r.id,
    title: r.title,
    sub: `${r.request_number} · ${r.sharing_type}`,
    classification: formatClassification(r.data_classification),
    status: r.status,
    sla: r.expiry_at ? new Date(r.expiry_at).toLocaleDateString() : "—",
  };
}

export interface RequestsTableProps {
  status?: RequestStatus;
}

export function RequestsTable({ status }: RequestsTableProps) {
  const requestsQuery = useRequests({ page: 1, limit: 50, status });

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

  const rows = (requestsQuery.data?.data ?? []).map(formatRow);

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24">
        <div
          className="flex h-14 w-14 items-center justify-center rounded-full"
          style={{ backgroundColor: "#FFF5F0" }}
        >
          <Inbox className="h-7 w-7" style={{ color: "#D76736" }} />
        </div>
        <div className="flex flex-col items-center gap-1 text-center">
          <p className="text-sm font-semibold text-auth-text">
            No requests yet
          </p>
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
      {rows.map((row, i) => (
        <Link
          key={row.id}
          href={`/data-sharing/${row.id}`}
          className="flex h-16 shrink-0 items-center px-5 transition-colors hover:bg-[#FFFBF9]"
          style={{
            borderBottom:
              i < rows.length - 1 ? "1px solid #EEEEEE" : undefined,
          }}
        >
          <div className="flex flex-1 flex-col gap-1">
            <span className="text-[13px] font-semibold text-auth-text">
              {row.title}
            </span>
            <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
              {row.sub}
            </span>
          </div>
          <span
            className="w-[130px] text-xs"
            style={{ color: "#9E9E9E" }}
          >
            {row.classification}
          </span>
          <div className="w-[150px]">
            <StatusBadge status={row.status} />
          </div>
          <span
            className="w-[100px] text-xs"
            style={{ color: "#9E9E9E" }}
          >
            {row.sla}
          </span>
        </Link>
      ))}
    </>
  );
}
