import { get, post } from "@/lib/api/client";
import type { WorkflowStep } from "@/lib/types/data-sharing/step.types";

const BASE = "/api/v1/products/data-sharing/workflows";

export function getRequestSteps(requestId: string): Promise<WorkflowStep[]> {
  return get<WorkflowStep[]>(`${BASE}/requests/${requestId}/steps`);
}

export function approveStep(
  stepId: string,
  comment?: string,
): Promise<WorkflowStep> {
  return post<WorkflowStep, { comment?: string }>(
    `${BASE}/steps/${stepId}/approve`,
    { comment },
  );
}

export function rejectStep(
  stepId: string,
  comment?: string,
): Promise<WorkflowStep> {
  return post<WorkflowStep, { comment?: string }>(
    `${BASE}/steps/${stepId}/reject`,
    { comment },
  );
}

export function requestChangesOnStep(
  stepId: string,
  comment?: string,
): Promise<WorkflowStep> {
  return post<WorkflowStep, { comment?: string }>(
    `${BASE}/steps/${stepId}/request-changes`,
    { comment },
  );
}
