export type SharingType = "internal" | "external";
export type DataType = "file" | "structured";
// PULL = requester is asking another dept FOR data they need.
// PUSH = requester has data ready and is SENDING it to another dept.
// Drives source/receiver dept resolution in the workflow engine and
// changes Step 2 of the wizard (PULL = describe, PUSH = upload/query).
export type RequestDirection = "pull" | "push";
export type SelectionMode = "tables" | "query";
export type DeliveryChannel = "portal" | "email" | "api";

export type DataClassification =
  | "public"
  | "internal"
  | "confidential"
  | "sensitive";

export type LegalBasis =
  | ""
  | "consent"
  | "contract"
  | "legal_obligation"
  | "vital_interest"
  | "public_interest"
  | "legitimate_interest";

export type RequestStatus =
  | "draft"
  | "submitted"
  | "in_review"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "cancelled"
  | "completed"
  | "expired";

// Item descriptor for `selected_items` when selection_mode === "tables".
export interface SelectedTableItem {
  schema?: string;
  table: string;
  columns?: string[];
}

export interface ExternalRecipientInline {
  org_name: string;
  contact_email: string;
  contact_name?: string;
  phone?: string;
}

// PUSH/EXTERNAL wizard collects DPA text inline so the steward can
// edit the canned agreement before sending. The backend ignores this
// for now (the recipient's t_external_recipients row owns the DPA);
// kept on the create body for forward-compatibility.
export interface ExternalDsaInline {
  dsa_text: string;
}

// Compact summary of the currently-pending step on a request, surfaced
// inline on list responses so the inbox can bucket by step role
// (Outgoing vs Incoming) without an N+1 fetch. NULL on the wire when
// the workflow is finished, not started, or stalled.
export interface CurrentStepSummary {
  id: string;
  step_order: number;
  name: string | null;
  assignee_role: string | null;
  assignee_user_id: number | null;
  status: string;
}

// Mirrors the t_share_requests row returned by the backend service. Note that
// the backend uses integer surrogate keys for tenants/groups/users.
export interface ShareRequest {
  id: string; // UUID
  tenant_id: number;
  request_number: string;
  version: number;
  title: string;
  purpose: string;
  legal_basis: LegalBasis | string;
  sharing_type: SharingType;
  data_classification: DataClassification;
  personal_data_involved: boolean;
  estimated_data_subjects: number | null;
  data_subject_categories: string[] | null;
  source_description: string | null;
  requester_id: number;
  receiving_tenant_id: number | null;
  requester_group_id: number | null;
  receiver_group_id: number | null;
  workflow_template_id: string | null;
  request_direction: RequestDirection;
  status: RequestStatus;
  expiry_at: string | null;
  conditions: unknown | null;
  dpia_confirmed: boolean;
  created_at: string;
  updated_at: string;
  created_by: number;
  updated_by: number | null;
  data_type: DataType;
  connection_id: string | null;
  selection_mode: SelectionMode | null;
  selected_items: SelectedTableItem[] | null;
  custom_sql: string | null;
  external_recipient_id: number | null;
  external_contact_id: number | null;
  delivery_channel: DeliveryChannel;
  // Annotated by the list endpoint (`find_for_user`); absent on
  // single-request GETs.
  current_step?: CurrentStepSummary | null;
}

// Body for POST /api/v1/products/data-sharing/requests/.
export interface CreateShareRequestBody {
  title: string;
  purpose: string;
  legal_basis?: string;
  request_direction?: RequestDirection;
  sharing_type?: SharingType;
  data_classification?: DataClassification;
  personal_data_involved?: boolean;
  estimated_data_subjects?: number | null;
  data_subject_categories?: string[] | null;
  source_description?: string | null;
  receiving_tenant_id?: number | null;
  receiver_group_id?: number | null;
  dpia_confirmed?: boolean;
  data_type?: DataType;
  connection_id?: string | null;
  selection_mode?: SelectionMode | null;
  selected_items?: SelectedTableItem[] | null;
  custom_sql?: string | null;
  external_recipient?: ExternalRecipientInline | null;
  delivery_channel?: DeliveryChannel;
  // Inline DSA text for push/external (UI only — kept on the create
  // body so the wizard can persist the canned agreement the steward
  // edited; backend currently surfaces the DSA from t_external_recipients).
  external_dsa_text?: string;
}
