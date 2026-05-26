// Lifecycle states the backend stamps on a t_files row.
export type FileStatus =
  | "pending_upload"
  | "uploaded"
  | "scanning"
  | "clean"
  | "infected"
  | "failed"
  | "deleted";

export interface RequestFile {
  id: string; // UUID
  request_id: string; // UUID
  tenant_id: number;
  original_filename: string;
  storage_key: string;
  file_size_bytes: number;
  mime_type: string;
  sha256_hash: string;
  status: FileStatus;
  uploaded_by: number | null;
  uploaded_at: string | null;
  expires_at: string | null;
  deleted_at: string | null;
  deletion_reason: string | null;
  created_at: string;
}

// POST /api/v1/products/data-sharing/files/initiate body shape (matches
// backend `InitiateUploadBody`).
export interface InitiateUploadBody {
  request_id: string;
  filename: string;
  size: number;
  mime_type: string;
  sha256_hash: string;
}
