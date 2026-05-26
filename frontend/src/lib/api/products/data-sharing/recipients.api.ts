import { del, get, post } from "@/lib/api/client";

// External Recipients (per Pencil frames 17–19). The backend table only
// stores the registry-side fields today (name, organisation, email,
// country, safeguard, is_active, created_at). The token-level fields
// (file counts, token status, last accessed, granted/expired/revoked
// counters) are surfaced in Pencil but the backend doesn't currently
// expose them. We model them here as optional so the UI can render
// placeholders ("—") wherever the API hasn't filled them in yet.
export type RecipientTokenStatus = "active" | "expired" | "revoked";

export interface ExternalRecipient {
  id: string;
  name: string;
  organisation: string;
  email: string;
  phone?: string | null;
  country: string | null;
  safeguard: string | null;
  is_active: boolean;
  created_at: string;
  // Optional aggregates rendered on the list/detail when the backend has
  // them. Default to undefined and the UI shows "—".
  files_count?: number;
  token_status?: RecipientTokenStatus;
  last_accessed_at?: string | null;
  first_granted_at?: string | null;
  tokens_delivered?: number;
  active_tokens?: number;
  expired_tokens?: number;
  revoked_tokens?: number;
}

export interface CreateRecipientBody {
  name: string;
  organisation: string;
  email: string;
  country?: string;
  safeguard?: string;
}

export interface RevokeRecipientBody {
  reason?: string;
}

const BASE = "/api/v1/products/data-sharing/dpo/external-recipients";

export function listRecipients(): Promise<ExternalRecipient[]> {
  return get<ExternalRecipient[]>(BASE);
}

export function getRecipient(id: string): Promise<ExternalRecipient> {
  return get<ExternalRecipient>(`${BASE}/${id}`);
}

export function createRecipient(
  body: CreateRecipientBody,
): Promise<ExternalRecipient> {
  return post<ExternalRecipient, CreateRecipientBody>(BASE, body);
}

// Pencil frame 18 calls this "Revoke access" — it deactivates all active
// tokens. Today's backend exposes a delete; we keep the same call but
// rename it semantically and accept an audit-trail reason string. If the
// backend later adds a soft-deactivate endpoint, swap the implementation
// without changing the call sites.
export function revokeRecipient(id: string, body: RevokeRecipientBody): Promise<void> {
  return del<void>(`${BASE}/${id}`, { params: body });
}
