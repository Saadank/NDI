import { get } from "@/lib/api/client";

export interface WorkflowTemplate {
  id: number;
  name: string;
  description: string;
  step_count: number;
}

const BASE = "/api/v1/products/data-sharing/workflows";

export function getWorkflowTemplates(): Promise<WorkflowTemplate[]> {
  return get<WorkflowTemplate[]>(BASE);
}
