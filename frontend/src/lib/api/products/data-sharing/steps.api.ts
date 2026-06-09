import { get, post } from "@/lib/api/client";
import type { WorkflowStep } from "@/lib/types/data-sharing/step.types";
import type { RequiredDocument } from "@/lib/types/data-sharing/request.types";

// Steps live under TWO different prefixes on the backend:
//   GET  …/workflows/requests/{request_id}/steps      → list steps for a request
//   POST …/requests/{request_id}/steps/{step_id}/…    → act on a step (approve / reject / request-changes)

const WF_BASE = "/api/v1/products/data-sharing/workflows";
const REQ_BASE = "/api/v1/products/data-sharing/requests";

export function getRequestSteps(requestId: string): Promise<WorkflowStep[]> {
  return get<WorkflowStep[]>(`${WF_BASE}/requests/${requestId}/steps`);
}

export function approveStep(
  requestId: string,
  stepId: string,
  comment?: string,
): Promise<WorkflowStep> {
  return post<WorkflowStep, { comment?: string }>(
    `${REQ_BASE}/${requestId}/steps/${stepId}/approve`,
    { comment },
  );
}

export function rejectStep(
  requestId: string,
  stepId: string,
  comment: string,
): Promise<WorkflowStep> {
  return post<WorkflowStep, { comment: string }>(
    `${REQ_BASE}/${requestId}/steps/${stepId}/reject`,
    { comment },
  );
}

export function requestChangesOnStep(
  requestId: string,
  stepId: string,
  comment: string,
  requiredDocuments?: RequiredDocument[],
): Promise<WorkflowStep> {
  return post<
    WorkflowStep,
    { comment: string; required_documents?: RequiredDocument[] }
  >(`${REQ_BASE}/${requestId}/steps/${stepId}/request-changes`, {
    comment,
    ...(requiredDocuments ? { required_documents: requiredDocuments } : {}),
  });
}
