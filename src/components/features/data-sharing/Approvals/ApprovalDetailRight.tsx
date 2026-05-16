"use client";

import { Circle, CircleCheck, GitBranch, List } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { formatDateTime } from "@/lib/utils/formatters";
import type { WorkflowStep } from "@/lib/types/data-sharing/step.types";

// ─── Timeline types + builder ─────────────────────────────────────────────────

export interface TimelineItem {
  id: string;
  kind: "approved" | "rejected" | "changes" | "raised" | "flagged";
  title: string;
  when: string;
  body?: string | null;
}

export function buildTimeline(
  steps: WorkflowStep[],
  raisedAt: string,
  raisedByName: string,
): TimelineItem[] {
  const items: TimelineItem[] = [];
  for (const s of steps) {
    if (!s.completed_at) continue;
    const n = s.name ?? s.assignee_role ?? "Step";
    if (s.status === "approved") items.push({ id: s.id, kind: "approved", title: `${n} Approved`, when: s.completed_at, body: s.comment });
    if (s.status === "rejected") items.push({ id: s.id, kind: "rejected", title: `${n} Rejected`, when: s.completed_at, body: s.comment });
    if (s.status === "changes_requested") items.push({ id: s.id, kind: "changes", title: "Changes requested", when: s.completed_at, body: s.comment });
    if (s.status === "flagged") items.push({ id: s.id, kind: "flagged", title: "Flagged for Technical Review", when: s.completed_at, body: s.comment });
  }
  items.push({ id: "raised", kind: "raised", title: "Request Raised", when: raisedAt, body: `${raisedByName} submitted the request.` });
  return items.sort((a, b) => new Date(b.when).getTime() - new Date(a.when).getTime());
}

// ─── Shared card header ───────────────────────────────────────────────────────

function CardHeader({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex h-10 items-center gap-2 px-4 rounded-t-lg"
      style={{ backgroundColor: "#F8FAFC", borderBottom: "1px solid #E5E7EB" }}>
      <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: "#6B7280" }} />
      <span className="text-[13px] font-semibold" style={{ color: "#374151" }}>{title}</span>
    </div>
  );
}

// ─── Workflow step row ────────────────────────────────────────────────────────

function WorkflowStepRow({ step, isLast }: { step: WorkflowStep; isLast: boolean }) {
  const done = step.status === "approved" || step.status === "skipped";
  const active = step.can_act && step.status === "pending";
  const iconColor = done ? "#16A34A" : step.status === "rejected" ? "#DC2626" : active ? "#D76736" : "#D1D5DB";
  const Icon = done || step.status === "rejected" ? CircleCheck : Circle;

  return (
    <>
      <div
        className="flex items-center gap-2 rounded-md px-2 py-1.5"
        style={active ? { backgroundColor: "#FFF5F0" } : undefined}
      >
        <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: iconColor }} />
        <div className="flex flex-col gap-0.5">
          <span className="text-[12px] font-semibold" style={{ color: active ? "#D76736" : "#374151" }}>
            {step.name ?? step.assignee_role ?? "Step"}
          </span>
          <span className="text-[11px]" style={{ color: active ? "#D76736" : "#9CA3AF" }}>
            {active
              ? "You — awaiting your decision"
              : (step.assignee_name ?? (step.completed_at ? formatDateTime(step.completed_at) : "Pending"))}
          </span>
        </div>
      </div>
      {!isLast && (
        <div className="relative h-4 w-[14px]">
          <div className="absolute left-[6px] top-0 h-full w-px" style={{ backgroundColor: "#D1D5DB" }} />
        </div>
      )}
    </>
  );
}

// ─── Timeline row ─────────────────────────────────────────────────────────────

function TimelineRow({ item }: { item: TimelineItem }) {
  const pal =
    item.kind === "approved" ? { bg: "#F0FDF4", border: "#BBF7D0", title: "#166534" }
    : item.kind === "rejected" ? { bg: "#FEF2F2", border: "#FECACA", title: "#991B1B" }
    : item.kind === "changes" ? { bg: "#FFFBEB", border: "#FDE68A", title: "#92400E" }
    : item.kind === "flagged" ? { bg: "#EFF6FF", border: "#BFDBFE", title: "#1D4ED8" }
    : { bg: "#F8FAFC", border: "#E5E7EB", title: "#374151" };
  return (
    <div className="flex flex-col gap-1 rounded-md p-3" style={{ backgroundColor: pal.bg, border: `1px solid ${pal.border}` }}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-semibold" style={{ color: pal.title }}>{item.title}</span>
        <span className="shrink-0 text-[11px]" style={{ color: "#6B7280" }}>{formatDateTime(item.when)}</span>
      </div>
      {item.body && (
        <p className="text-[11px]" style={{ color: "#374151", lineHeight: 1.5 }}>{item.body}</p>
      )}
    </div>
  );
}

// ─── Exported cards ───────────────────────────────────────────────────────────

export function WorkflowCard({ steps }: { steps: WorkflowStep[] }) {
  return (
    <section className="flex flex-col overflow-hidden rounded-lg" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}>
      <CardHeader icon={GitBranch} title="Workflow" />
      <div className="flex flex-col p-4">
        {steps.map((s, i) => (
          <WorkflowStepRow key={s.id} step={s} isLast={i === steps.length - 1} />
        ))}
        {steps.length === 0 && (
          <p className="text-[13px]" style={{ color: "#9CA3AF" }}>No workflow steps yet.</p>
        )}
      </div>
    </section>
  );
}

export function TimelineCard({ items }: { items: TimelineItem[] }) {
  return (
    <section className="flex flex-col overflow-hidden rounded-lg" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}>
      <CardHeader icon={List} title="Activity Timeline" />
      <div className="flex flex-col gap-3 p-4">
        {items.map((it) => (
          <TimelineRow key={it.id} item={it} />
        ))}
      </div>
    </section>
  );
}
