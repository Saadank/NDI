// Mirrors the t_workflow_steps row, plus the `can_act` annotation that the
// /workflows/requests/{id}/steps endpoint adds per-caller.
export type StepStatus =
  | "pending"
  | "in_progress"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "flagged"
  | "skipped"
  // Future / inactive steps that haven't started yet — the engine
  // writes this for every step after the first when materialising a
  // workflow. Frontend renders these as gray empty circles.
  | "waiting";

export interface WorkflowStep {
  id: string;
  request_id: string;
  template_step_id: string | null;
  step_order: number;
  step_type: string;
  name: string | null;
  assignee_role: string | null;
  assignee_user_id: number | null;
  status: StepStatus;
  sla_deadline: string | null;
  completed_at: string | null;
  completed_by: number | null;
  decision: string | null;
  comment: string | null;
  escalated_at: string | null;
  created_at: string;
  // Annotated server-side per caller.
  can_act: boolean;
  // Optional — some endpoints join the user table and stitch in a name.
  assignee_name?: string;
}
