import { post, get } from "@/lib/api/client";

const BASE = "/api/v1/platform/invitations/";

// Backend route: POST /api/v1/platform/invitations/
// Body shape (CreateInvitationRequest in backend):
//   - email (required)
//   - role (required)               — platform role: "user" | "org_admin"
//   - product_slug (optional)       — e.g. "data-sharing"
//   - product_role (optional)       — e.g. "data_steward" | "data_owner" | "dpo"
//   - tenant_id (optional)          — only used by platform_admin
//
// The backend's invite flow emails the user a token; first_name/last_name/dept
// are collected on the accept screen, NOT on invite. The Pencil form still
// shows those inputs for context (so the inviter can plan the assignment),
// but they aren't part of the API call.
export interface CreateInvitationBody {
  email: string;
  role: string;
  product_slug?: string;
  product_role?: string;
  tenant_id?: number;
}

export interface InvitationRecord {
  id: number;
  email: string;
  role: string;
  product_slug: string | null;
  product_role: string | null;
  status: string;
  created_at: string;
  expires_at: string;
}

export function createInvitation(body: CreateInvitationBody): Promise<InvitationRecord> {
  return post<InvitationRecord, CreateInvitationBody>(BASE, body);
}

export function listInvitations(): Promise<InvitationRecord[]> {
  return get<InvitationRecord[]>(BASE);
}
