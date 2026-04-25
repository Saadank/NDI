export type SharingType = "internal" | "external";
export type DataType = "file" | "structured";
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
}

// Body for POST /api/v1/products/data-sharing/requests/.
export interface CreateShareRequestBody {
  title: string;
  purpose: string;
  legal_basis?: string;
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
}
