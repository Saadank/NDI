import apiClient, { del, get, post } from "@/lib/api/client";
import type {
  InitiateUploadBody,
  RequestFile,
} from "@/lib/types/data-sharing/file.types";

const BASE = "/api/v1/products/data-sharing/files";

// GET /files/by-request/{request_id}
export function getRequestFiles(requestId: string): Promise<RequestFile[]> {
  return get<RequestFile[]>(`${BASE}/by-request/${requestId}`);
}

// POST /files/initiate  → returns the t_files row in `pending_upload`.
export function initiateUpload(
  body: InitiateUploadBody,
): Promise<RequestFile> {
  return post<RequestFile, InitiateUploadBody>(`${BASE}/initiate`, body);
}

// PUT /files/{file_id}/upload  (multipart) → final t_files row in `uploaded`.
export async function completeUpload(
  fileId: string,
  file: File,
  sha256Hash: string,
): Promise<RequestFile> {
  const formData = new FormData();
  formData.append("file", file);
  // The shared `apiClient` ships with a default Content-Type of
  // application/json. Setting Content-Type to undefined here lets the browser
  // set the correct `multipart/form-data; boundary=...` header on its own —
  // without that, FastAPI's UploadFile parser rejects the body.
  const res = await apiClient.put<RequestFile>(
    `${BASE}/${fileId}/upload`,
    formData,
    {
      params: { sha256_hash: sha256Hash },
      headers: { "Content-Type": undefined as unknown as string },
    },
  );
  return res.data;
}

// GET /files/{file_id}/download-url
export function getDownloadUrl(
  fileId: string,
): Promise<{ download_url: string }> {
  return get<{ download_url: string }>(`${BASE}/${fileId}/download-url`);
}

// DELETE /files/{file_id}
export function deleteRequestFile(
  fileId: string,
  reason = "manual",
): Promise<{ detail: string }> {
  return del<{ detail: string }>(
    `${BASE}/${fileId}?reason=${encodeURIComponent(reason)}`,
  );
}

// Browsers occasionally hand us an empty `file.type`. The backend's
// allow-list rejects unknown MIME types, so guess from the extension when
// possible — falling back to `application/octet-stream` only as a last
// resort, which the backend will (correctly) reject loudly.
const EXT_TO_MIME: Record<string, string> = {
  pdf: "application/pdf",
  doc: "application/msword",
  docx:
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xls: "application/vnd.ms-excel",
  xlsx:
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ppt: "application/vnd.ms-powerpoint",
  pptx:
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  txt: "text/plain",
  csv: "text/csv",
  json: "application/json",
  xml: "application/xml",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  gif: "image/gif",
  webp: "image/webp",
  zip: "application/zip",
  "7z": "application/x-7z-compressed",
  tar: "application/x-tar",
  gz: "application/gzip",
};

export function resolveMimeType(file: File): string {
  if (file.type) return file.type;
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXT_TO_MIME[ext] ?? "application/octet-stream";
}

// SHA-256 of a File via the Web Crypto API. Returns a 64-char hex string —
// exactly what the backend's `InitiateUploadBody.sha256_hash` validator wants.
export async function sha256OfFile(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// Convenience: hash → initiate → PUT in one call.
export async function uploadFileForRequest(
  requestId: string,
  file: File,
): Promise<RequestFile> {
  const sha256_hash = await sha256OfFile(file);
  const initiated = await initiateUpload({
    request_id: requestId,
    filename: file.name,
    size: file.size,
    mime_type: resolveMimeType(file),
    sha256_hash,
  });
  return completeUpload(initiated.id, file, sha256_hash);
}
