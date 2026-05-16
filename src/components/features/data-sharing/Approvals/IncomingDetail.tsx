"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, ChevronRight, Info, ShieldCheck } from "lucide-react";

import { useGroups } from "@/lib/hooks/platform/useGroups";
import {
  useApprovalSteps,
  useActOnStep,
} from "@/lib/hooks/data-sharing/useApprovalSteps";
import { useRequestDetail } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useRequestFiles } from "@/lib/hooks/data-sharing/useFiles";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";

import {
  WorkflowCard,
  TimelineCard,
  buildTimeline,
} from "./ApprovalDetailRight";
import {
  IncomingSummaryCard,
  IncomingFilesCard,
  IncomingSchemaCard,
} from "./IncomingDetailCards";
import {
  ConfirmReceiptModal,
  DeclineReceiptModal,
  RequestMoreDetailsModal,
} from "./IncomingDetailModals";
import { explainNoAction } from "./noActionReason";

// Three modal kinds the Incoming page surfaces. The page is deliberately
// simpler than the Outgoing detail — no SQL inspection, no PDPL section.
type ModalKey = null | "confirm" | "decline" | "details";

export function IncomingDetail({ id }: { id: string }) {
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

  if (!isReady) return null;
  if (reqQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm" style={{ color: "#9CA3AF" }}>Loading…</p>
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
  // When myStep is falsy we render a diagnostic panel in place of the
  // sticky footer so the user always knows whose turn it is.
  const noActionReason = !myStep
    ? explainNoAction(r, steps, myProductRole, myUserId)
    : null;
  // Sender = the dept where the data comes from. For Incoming requests we
  // (the requester) asked them; their group sits in receiver_group_id.
  const senderGroup =
    groupsQuery.data?.find((g) => g.id === (r.receiver_group_id ?? -1))?.name ??
    "—";
  const timeline = buildTimeline(steps, r.created_at, `User #${r.requester_id}`);
  const files = filesQuery.data ?? [];

  // Wraps every step action with a redirect back to /approvals on success.
  const actAndRedirect = async (
    status: "approved" | "rejected" | "changes_requested",
    comment: string,
  ) => {
    if (!myStep) return;
    await act.mutateAsync({
      stepId: myStep.id,
      status,
      comment: comment || undefined,
    });
    setModal(null);
    router.push("/approvals");
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#F9FAFB" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-2.5">
          <span className="text-lg font-bold" style={{ color: "#111827" }}>
            Receipt Confirmation
          </span>
          <span
            className="rounded px-2 py-0.5 text-[11px] font-semibold"
            style={{ backgroundColor: "#F3F4F6", color: "#6B7280" }}
          >
            v{r.version}
          </span>
        </div>
        <div className="flex items-center gap-2.5">
          <Link
            href="/approvals"
            className="flex h-8 items-center gap-1.5 rounded-md border px-3.5 text-[13px] font-medium"
            style={{ borderColor: "#E5E7EB", color: "#616161", backgroundColor: "#FFFFFF" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Inbox
          </Link>
          <span
            className="flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Data Owner{myGroupName ? ` · ${myGroupName}` : ""}
          </span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-6 pb-24 pt-5">
        {/* Header card */}
        <div
          className="flex flex-col gap-2 rounded-lg px-5 py-3.5"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}
        >
          <div className="flex items-center gap-1 text-[12px]" style={{ color: "#6B7280" }}>
            <Link href="/approvals" className="hover:underline">Approvals Inbox</Link>
            <ChevronRight className="h-3 w-3" />
            <span style={{ color: "#374151", fontWeight: 500 }}>{r.title}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-bold" style={{ color: "#111827" }}>{r.title}</h2>
            {myStep && (
              <span
                className="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium"
                style={{ backgroundColor: "#DBEAFE", color: "#1D4ED8" }}
              >
                Pending Receipt Confirmation
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 text-[12px]" style={{ color: "#6B7280" }}>
            <span>From {senderGroup}</span>
            <span style={{ textTransform: "capitalize" }}>· {r.data_classification}</span>
          </div>
        </div>

        {/* Two-column body */}
        <div className="flex flex-1 gap-3">
          <div className="flex flex-1 flex-col gap-3">
            <IncomingSummaryCard r={r} senderGroup={senderGroup} fileCount={files.length} />
            {r.data_type === "file" ? <IncomingFilesCard files={files} /> : <IncomingSchemaCard r={r} />}
          </div>
          <div className="flex w-[284px] shrink-0 flex-col gap-3">
            <WorkflowCard steps={steps} />
            <TimelineCard items={timeline} />
          </div>
        </div>
      </div>

      {/* Sticky footer — only when our step can act */}
      {myStep && (
        <div
          className="sticky bottom-0 flex h-16 items-center justify-between px-5"
          style={{ backgroundColor: "#FFFFFF", borderTop: "1px solid #E5E7EB" }}
        >
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setModal("decline")}
              className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
              style={{ borderColor: "#DC2626", color: "#DC2626" }}
            >
              Decline
            </button>
            <button
              type="button"
              onClick={() => setModal("details")}
              className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
              style={{ borderColor: "#E5E7EB", color: "#374151" }}
            >
              Request more details
            </button>
          </div>
          <button
            type="button"
            onClick={() => setModal("confirm")}
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            Confirm receipt →
          </button>
        </div>
      )}

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

      {modal === "confirm" && (
        <ConfirmReceiptModal
          deptName={myGroupName}
          pending={act.isPending}
          onClose={() => setModal(null)}
          onConfirm={(c) => actAndRedirect("approved", c)}
        />
      )}
      {modal === "decline" && (
        <DeclineReceiptModal
          pending={act.isPending}
          onClose={() => setModal(null)}
          onConfirm={(c) => actAndRedirect("rejected", c)}
        />
      )}
      {modal === "details" && (
        <RequestMoreDetailsModal
          pending={act.isPending}
          onClose={() => setModal(null)}
          onConfirm={(c) => actAndRedirect("changes_requested", c)}
        />
      )}
    </div>
  );
}
