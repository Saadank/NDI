/**
 * NDMO Compliance — documents API wrappers.
 *
 * Routes hit the FastAPI router mounted at
 * /api/v1/products/ndmo-compliance/documents.  All requests are gated by
 * the require_ndmo_compliance backend dependency (403 if tenant lacks
 * NDMO product entitlement).
 */
import { get, post } from "@/lib/api/client";
import type {
  InitiateUploadBody,
  InitiateUploadResponse,
  NdmoDocument,
  PipelineStatusNode,
} from "@/lib/types/ndmo-compliance";

const BASE = "/api/v1/products/ndmo-compliance/documents";

export function initiateUpload(body: InitiateUploadBody) {
  return post<InitiateUploadResponse, InitiateUploadBody>(`${BASE}/initiate`, body);
}

export function listDocuments(params: {
  cycle_id?: number;
  limit?: number;
  offset?: number;
} = {}) {
  return get<NdmoDocument[]>(BASE, { params });
}

export function getDocument(documentId: string) {
  return get<NdmoDocument>(`${BASE}/${documentId}`);
}

export function getDocumentStatus(documentId: string) {
  return get<PipelineStatusNode | null>(`${BASE}/${documentId}/status`);
}
