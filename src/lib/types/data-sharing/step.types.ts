export type StepStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "changes_requested";

export interface WorkflowStep {
  id: string;
  request_id: string;
  order: number;
  assignee_id: string;
  assignee_name: string;
  status: StepStatus;
  comment?: string;
  can_act: boolean;
  acted_at?: string;
}
