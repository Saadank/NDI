import { del, get, post } from "@/lib/api/client";

// Mirrors `t_workflow_templates` rows from the backend.
export interface WorkflowTemplate {
  id: string;
  tenant_id: number;
  name: string;
  sharing_type: string | null;
  data_classification: string | null;
  is_active: boolean;
  version: number;
  created_at: string;
  created_by: number;
  step_count?: number;
}

export interface WorkflowTemplateStep {
  id: string;
  template_id: string;
  step_order: number;
  step_type: string;
  name: string;
  assignee_role: string | null;
  execution_mode: string;
  sla_days: number;
  condition_expr: string | null;
  created_at: string;
}

export interface WorkflowTemplateWithSteps extends WorkflowTemplate {
  steps: WorkflowTemplateStep[];
}

const BASE = "/api/v1/products/data-sharing/workflows";

export function getWorkflowTemplates(): Promise<WorkflowTemplate[]> {
  return get<WorkflowTemplate[]>(`${BASE}/templates`);
}

export function getWorkflowTemplate(
  id: string,
): Promise<WorkflowTemplateWithSteps> {
  return get<WorkflowTemplateWithSteps>(`${BASE}/templates/${id}`);
}

export interface DeleteTemplateResponse {
  deleted: boolean;
  detached_requests: number;
}

export function deleteWorkflowTemplate(
  id: string,
): Promise<DeleteTemplateResponse> {
  return del<DeleteTemplateResponse>(`${BASE}/templates/${id}`);
}

export interface BackfillResponse {
  backfilled: number;
  skipped: { request_id: string; reason: string }[];
}

export function backfillWorkflows(body: {
  request_id?: string;
  all_stuck?: boolean;
}): Promise<BackfillResponse> {
  return post<BackfillResponse, { request_id?: string; all_stuck?: boolean }>(
    `${BASE}/backfill`,
    body,
  );
}
