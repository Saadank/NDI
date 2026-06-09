"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, ChevronRight, Clock, Flag, Info, ShieldCheck } from "lucide-react";

import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useApprovalSteps, useActOnStep } from "@/lib/hooks/data-sharing/useApprovalSteps";
import { useRequestDetail } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useRequestFiles } from "@/lib/hooks/data-sharing/useFiles";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";
import { MetaCard, FilesCard, QueryCard, TablesCard } from "./ApprovalDetailMeta";
import { WorkflowCard, TimelineCard, buildTimeline } from "./ApprovalDetailRight";
import { RequestChangesModal, RejectModal, ApproveModal, FlagModal } from "./ApprovalDetailModals";
import { explainNoAction } from "./noActionReason";
import type { RequiredDocument } from "@/lib/types/data-sharing/request.types";

type ModalKey = null | "approve" | "reject" | "changes" | "flag";

export function ApprovalDetail({ id }: { id: string }) {
  const { isReady } = useRoleGuard({ allow: ["data_owner", "platform_admin"] });
  const router = useRouter();

  const reqQuery = useRequestDetail(id);
  const stepsQuery = useApprovalSteps(id);
  const filesQuery = useRequestFiles(id);
  const groupsQuery = useGroups();
  const act = useActOnStep(id);

  const myGroupId = useAuthStore((s) => s.user?.group_id ?? null);
  const myProductRole = useAuthStore((s) => s.user?.product_role ?? null);
  const myUserId = useAuthStore((s) => s.user?.id ?? null);
  const myGroupName = myGroupId
    ? (groupsQuery.data?.find((g) => g.id === myGroupId)?.name ?? "")
    : "";

  const [modal, setModal] = useState<ModalKey>(null);
  const [flaggedBy, setFlaggedBy] = useState<string | null>(null);

  if (!isReady) return null;
  if (reqQuery.isLoading) {
    return <div className="flex flex-1 items-center justify-center"><p className="text-sm" style={{ color: "#9CA3AF" }}>Loading…</p></div>;
  }
  if (reqQuery.isError || !reqQuery.data) {
    return <div className="flex flex-1 items-center justify-center"><p className="text-sm text-red-600">Failed to load request.</p></div>;
  }

  const r = reqQuery.data;
  const steps = stepsQuery.data ?? [];
  const myStep = steps.find((s) => s.can_act);
  // Computed lazily: only when the footer can't render do we explain
  // why. This is the single source of truth for the diagnostic panel.
  const noActionReason = !myStep
    ? explainNoAction(r, steps, myProductRole, myUserId)
    : null;
  // Either an explicit "flagged" step (future), or the most recent
  // changes_requested step whose comment starts with our [FLAG: ...] marker.
  const flaggedStep =
    steps.find((s) => s.status === "flagged") ??
    [...steps]
      .reverse()
      .find(
        (s) =>
          s.status === "changes_requested" &&
          typeof s.comment === "string" &&
          /^\[FLAG:\s*[^\]]+\]/i.test(s.comment),
      );
  const extractFlaggedContact = (comment: string | null | undefined) => {
    if (!comment) return null;
    const m = comment.match(/^\[FLAG:\s*([^\]]+)\]/i);
    if (m) return m[1].trim();
    // Legacy format kept for steps written before the new prefix.
    const legacy = comment.match(/^Flagged for technical review — awaiting:\s*(.+)$/i);
    return legacy ? legacy[1].trim() : null;
  };
  const flaggedContact = flaggedBy ?? extractFlaggedContact(flaggedStep?.comment);

  const senderGroup = groupsQuery.data?.find((g) => g.id === (r.requester_group_id ?? -1))?.name ?? "—";
  const receiverGroup = groupsQuery.data?.find((g) => g.id === (r.receiver_group_id ?? -1))?.name ?? "—";
  const hoursLeft = r.expiry_at ? (new Date(r.expiry_at).getTime() - Date.now()) / 3_600_000 : null;
  const slaText = hoursLeft === null ? "No SLA set"
    : hoursLeft < 0 ? "SLA overdue"
    : hoursLeft < 24 ? `${Math.round(hoursLeft)}h remaining`
    : `${Math.floor(hoursLeft / 24)}d remaining`;

  const timeline = buildTimeline(steps, r.created_at, `User #${r.requester_id}`);

  const actAndRedirect = async (
    status: "approved" | "rejected" | "changes_requested",
    comment: string,
    requiredDocuments?: RequiredDocument[],
  ) => {
    if (!myStep) return;
    await act.mutateAsync({ stepId: myStep.id, status, comment: comment || undefined, requiredDocuments });
    setModal(null);
    router.push("/approvals");
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#F9FAFB" }}>
      {/* Top bar */}
      <div className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}>
        <div className="flex items-center gap-2.5">
          <span className="text-lg font-bold" style={{ color: "#111827" }}>Request Detail</span>
          <span className="rounded px-2 py-0.5 text-[11px] font-semibold" style={{ backgroundColor: "#F3F4F6", color: "#6B7280" }}>v{r.version}</span>
        </div>
        <div className="flex items-center gap-2.5">
          <Link href="/approvals" className="flex h-8 items-center gap-1.5 rounded-md border px-3.5 text-[13px] font-medium"
            style={{ borderColor: "#E5E7EB", color: "#616161", backgroundColor: "#FFFFFF" }}>
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Inbox
          </Link>
          <span className="flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}>
            <ShieldCheck className="h-3.5 w-3.5" />
            Data Owner{myGroupName ? ` · ${myGroupName}` : ""}
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col gap-4 overflow-auto px-6 pb-24 pt-5">
        {/* Flagged banner (DO-09) */}
        {flaggedContact && (
          <div className="flex items-center gap-3 rounded-lg px-4 py-3"
            style={{ backgroundColor: "#EFF6FF", border: "1px solid #BFDBFE" }}>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full" style={{ backgroundColor: "#DBEAFE" }}>
              <Flag className="h-4 w-4" style={{ color: "#2563EB" }} />
            </div>
            <div className="flex flex-col gap-0.5">
              <p className="text-[13px] font-semibold" style={{ color: "#1D4ED8" }}>
                Flagged for Technical Review · Waiting on response before deciding
              </p>
              <p className="text-[12px]" style={{ color: "#3B82F6" }}>
                Sent to {flaggedContact} — comment received, shown in timeline below
              </p>
            </div>
          </div>
        )}

        {/* Request header card */}
        <div className="flex flex-col gap-2 rounded-lg px-5 py-3.5"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}>
          <div className="flex items-center gap-1 text-[12px]" style={{ color: "#6B7280" }}>
            <Link href="/approvals" className="hover:underline">Approvals Inbox</Link>
            <ChevronRight className="h-3 w-3" />
            <span style={{ color: "#374151", fontWeight: 500 }}>{r.title}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-bold" style={{ color: "#111827" }}>{r.title}</h2>
            {myStep && (
              <span className="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium"
                style={{ backgroundColor: "#FEF3C7", color: "#92400E" }}>
                Awaiting Your Approval
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 text-[12px]" style={{ color: "#6B7280" }}>
            <span>{senderGroup} → {receiverGroup}</span>
            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{slaText}</span>
          </div>
        </div>

        {/* Two-column content */}
        <div className="flex flex-1 gap-3">
          <div className="flex flex-1 flex-col gap-3">
            <MetaCard r={r} />
            {r.data_type === "file" && <FilesCard files={filesQuery.data ?? []} />}
            {r.data_type === "structured" && r.selection_mode === "query" && <QueryCard r={r} />}
            {r.data_type === "structured" && r.selection_mode === "tables" && <TablesCard r={r} />}
          </div>
          <div className="flex w-[284px] shrink-0 flex-col gap-3">
            <WorkflowCard steps={steps} />
            <TimelineCard items={timeline} />
          </div>
        </div>
      </div>

      {/* Sticky action bar — only when can_act */}
      {myStep && (
        <div className="sticky bottom-0 flex h-16 items-center justify-between px-5"
          style={{ backgroundColor: "#FFFFFF", borderTop: "1px solid #E5E7EB" }}>
          {flaggedContact ? (
            <span className="flex items-center gap-2 rounded-md px-3.5 py-2 text-[13px] font-medium"
              style={{ backgroundColor: "#EFF6FF", border: "1px solid #BFDBFE", color: "#1D4ED8" }}>
              <span className="h-2 w-2 rounded" style={{ backgroundColor: "#2563EB" }} />
              Flagged · Waiting on {flaggedContact}
            </span>
          ) : (
            <button type="button" onClick={() => setModal("flag")}
              className="flex h-9 items-center gap-1.5 rounded-md border px-3.5 text-[13px] font-medium"
              style={{ borderColor: "#E5E7EB", color: "#374151" }}>
              <Flag className="h-3.5 w-3.5" style={{ color: "#6B7280" }} />
              Flag for Technical Review
            </button>
          )}
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setModal("reject")}
              className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
              style={{ borderColor: "#DC2626", color: "#DC2626" }}>Reject</button>
            <button type="button" onClick={() => setModal("changes")}
              className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
              style={{ borderColor: "#E5E7EB", color: "#374151" }}>Request Changes</button>
            <button type="button" onClick={() => setModal("approve")}
              className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white"
              style={{ backgroundColor: "#D76736" }}>Approve →</button>
          </div>
        </div>
      )}

      {/* "Why no buttons?" panel — replaces silent footer omission so the
          page never just shows the request without telling the user
          whose turn it is or what is blocking action. */}
      {!myStep && noActionReason && (
        <div
          className="sticky bottom-0 flex items-start gap-3 px-6 py-4"
          style={{
            backgroundColor:
              noActionReason.kind === "closed"
                ? "#F9FAFB"
                : noActionReason.kind === "no_workflow" || noActionReason.kind === "wrong_role"
                  ? "#FFFBEB"
                  : "#EFF6FF",
            borderTop: `1px solid ${
              noActionReason.kind === "closed"
                ? "#E5E7EB"
                : noActionReason.kind === "no_workflow" || noActionReason.kind === "wrong_role"
                  ? "#FCD34D"
                  : "#BFDBFE"
            }`,
          }}
        >
          <Info
            className="mt-0.5 h-4 w-4 shrink-0"
            style={{
              color:
                noActionReason.kind === "closed"
                  ? "#6B7280"
                  : noActionReason.kind === "no_workflow" || noActionReason.kind === "wrong_role"
                    ? "#92400E"
                    : "#1D4ED8",
            }}
          />
          <div className="flex flex-col gap-0.5">
            <span
              className="text-[13px] font-semibold"
              style={{
                color:
                  noActionReason.kind === "closed"
                    ? "#374151"
                    : noActionReason.kind === "no_workflow" || noActionReason.kind === "wrong_role"
                      ? "#92400E"
                      : "#1D4ED8",
              }}
            >
              {noActionReason.title}
            </span>
            {noActionReason.detail && (
              <span
                className="text-[12px]"
                style={{
                  color:
                    noActionReason.kind === "closed"
                      ? "#6B7280"
                      : noActionReason.kind === "no_workflow" || noActionReason.kind === "wrong_role"
                        ? "#92400E"
                        : "#3B82F6",
                  lineHeight: 1.5,
                }}
              >
                {noActionReason.detail}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Modals */}
      {modal === "changes" && (
        <RequestChangesModal onClose={() => setModal(null)} pending={act.isPending}
          onConfirm={(c, docs) => actAndRedirect("changes_requested", c, docs)} />
      )}
      {modal === "reject" && (
        <RejectModal onClose={() => setModal(null)} pending={act.isPending}
          onConfirm={(c) => actAndRedirect("rejected", c)} />
      )}
      {modal === "approve" && (
        <ApproveModal onClose={() => setModal(null)} pending={act.isPending}
          onConfirm={(c) => actAndRedirect("approved", c)} />
      )}
      {modal === "flag" && (
        <FlagModal onClose={() => setModal(null)} pending={act.isPending}
          onConfirm={async ({ contact, comment }) => {
            if (!myStep) return;
            // Prefix the comment with [FLAG: <reviewer>] so the timeline /
            // banner can identify this entry as a technical-review flag and
            // surface "Waiting on <reviewer>" without a separate endpoint.
            await act.mutateAsync({
              stepId: myStep.id,
              status: "changes_requested",
              comment: `[FLAG: ${contact}] ${comment}`,
            });
            setFlaggedBy(contact);
            setModal(null);
          }} />
      )}
    </div>
  );
}
