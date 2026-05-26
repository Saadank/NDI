import type { WorkflowStep } from "@/lib/types/data-sharing/step.types";
import type { ShareRequest } from "@/lib/types/data-sharing/request.types";

// Single source of truth for the "Why no buttons?" panel on both
// /approvals/[id] (Outgoing detail) and /approvals/incoming/[id]
// (Incoming detail). The detail pages render the result of
// `explainNoAction` whenever they would otherwise hide the action footer
// silently, so the user always sees a sentence explaining who is
// blocking the request.

export interface NoActionReason {
  kind:
    | "closed"
    | "draft"
    | "no_workflow"
    | "waiting_on_prior_step"
    | "different_assignee"
    | "wrong_role";
  title: string;
  detail?: string;
}

export function roleLabel(role: string | null | undefined): string {
  if (!role) return "another reviewer";
  return role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function explainNoAction(
  request: ShareRequest,
  steps: WorkflowStep[],
  myProductRole: string | null,
  myUserId: number | null = null,
): NoActionReason | null {
  // Closed states first — once closed there is nothing to do regardless
  // of role.
  if (
    request.status === "completed" ||
    request.status === "rejected" ||
    request.status === "cancelled"
  ) {
    return {
      kind: "closed",
      title: "This request is closed.",
      detail: "No further actions available.",
    };
  }
  if (request.status === "draft") {
    return {
      kind: "draft",
      title: "This request is still a draft.",
      detail: "It hasn't been submitted yet.",
    };
  }
  // Submitted-or-later but no workflow attached.
  if (steps.length === 0) {
    return {
      kind: "no_workflow",
      title: "This request has no active workflow step.",
      detail:
        "Ask your Org Admin to run \"Apply to in-flight requests\" from the Workflow Editor, or to create an active workflow that matches this request's scope.",
    };
  }
  // Find the currently pending step.
  const pending = steps.find((s) => s.status === "pending");
  if (!pending) {
    return {
      kind: "waiting_on_prior_step",
      title: "Waiting on the next workflow step to activate.",
      detail:
        "All currently visible steps are either complete or queued. No action is required from you.",
    };
  }

  // Assignee-aware reasoning (mirrors the backend's can_approve_step
  // rule). When the step has a specific assignee, role doesn't matter
  // — only user_id does. When it has no specific assignee, we fall
  // back to role matching.
  const assigneeUserId = pending.assignee_user_id ?? null;
  if (assigneeUserId !== null && myUserId !== null) {
    if (assigneeUserId === myUserId) {
      // This is YOUR step — the caller should be rendering buttons.
      // Returning null tells the page "no reason to hide the footer".
      return null;
    }
    // Assigned to someone else.
    return {
      kind: "different_assignee",
      title: pending.assignee_name
        ? `Assigned to ${pending.assignee_name}.`
        : `Assigned to another user.`,
      detail: pending.assignee_name
        ? `Waiting on ${pending.assignee_name} (${roleLabel(pending.assignee_role)}) to act first.`
        : `Waiting on the specific ${roleLabel(pending.assignee_role)} this step is assigned to.`,
    };
  }

  // Null-assignee step — role-based gating.
  const stepRole = (pending.assignee_role ?? "").toLowerCase();
  if (myProductRole && myProductRole === stepRole) {
    // Caller's role matches the role-based step — buttons should
    // render. The caller's can_act bool should also be true.
    return null;
  }
  return {
    kind: "different_assignee",
    title: `Waiting on ${roleLabel(pending.assignee_role)} to act first.`,
    detail: pending.assignee_name
      ? `Currently with ${pending.assignee_name}.`
      : `This step is open to any ${roleLabel(pending.assignee_role)} in your organisation.`,
  };
}
