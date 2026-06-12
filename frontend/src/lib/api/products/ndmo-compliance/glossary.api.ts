/**
 * NDMO Compliance — Business Glossary API wrappers.
 *
 * Routes hit the FastAPI routers mounted at
 * /api/v1/products/ndmo-compliance/glossary, gated by the
 * require_ndmo_compliance backend dependency (403 if the tenant lacks the
 * NDMO product entitlement).  Per-action authorization is domain-scoped and
 * enforced server-side.
 */
import { apiClient, get, post, put, del } from "@/lib/api/client";
import type {
  AcceptCandidateResult,
  AssistAdviseBody,
  AssistDraftBody,
  AssistRephraseBody,
  AssistResponse,
  CreateDomainBody,
  DraftStatus,
  ExtractionConnection,
  GlossaryCandidate,
  ImportSummary,
  ScanResult,
  CreateSubdomainBody,
  CreateTermBody,
  DeprecateBody,
  DuplicateCheckResult,
  GlossaryDomain,
  GlossaryRole,
  GlossaryTerm,
  GlossaryTermDetail,
  GlossaryTermVersion,
  GlossaryUser,
  ReviewBody,
  UpdateTermBody,
} from "@/lib/types/ndmo-compliance/glossary";

const BASE = "/api/v1/products/ndmo-compliance/glossary";

// ---- role / scope -------------------------------------------------------

export function getMyGlossaryRole() {
  return get<GlossaryRole>(`${BASE}/me`);
}

export function listGlossaryUsers(search?: string) {
  return get<GlossaryUser[]>(`${BASE}/users`, { params: search ? { search } : {} });
}

// ---- domains ------------------------------------------------------------

export function listDomains(params: { include_archived?: boolean } = {}) {
  return get<GlossaryDomain[]>(`${BASE}/domains`, { params });
}

export function getDomain(domainId: string) {
  return get<GlossaryDomain>(`${BASE}/domains/${domainId}`);
}

export function createDomain(body: CreateDomainBody) {
  return post<GlossaryDomain, CreateDomainBody>(`${BASE}/domains`, body);
}

export function createSubdomain(parentId: string, body: CreateSubdomainBody) {
  return post<GlossaryDomain, CreateSubdomainBody>(
    `${BASE}/domains/${parentId}/subdomains`,
    body,
  );
}

export function updateDomain(domainId: string, body: Partial<CreateDomainBody>) {
  return put<GlossaryDomain, Partial<CreateDomainBody>>(
    `${BASE}/domains/${domainId}`,
    body,
  );
}

export function archiveDomain(domainId: string) {
  return del<void>(`${BASE}/domains/${domainId}`);
}

export function addSteward(domainId: string, userId: number) {
  return post<void, { user_id: number }>(
    `${BASE}/domains/${domainId}/stewards`,
    { user_id: userId },
  );
}

export function removeSteward(domainId: string, userId: number) {
  return del<void>(`${BASE}/domains/${domainId}/stewards/${userId}`);
}

// ---- terms --------------------------------------------------------------

export interface ListTermsParams {
  domain_id?: string;
  status?: string;
  term_type?: string;
  search?: string;
  scope?: "all" | "my";
  include_deprecated?: boolean;
}

export function listTerms(params: ListTermsParams = {}) {
  return get<GlossaryTerm[]>(`${BASE}/terms`, { params });
}

export function getTerm(termId: string) {
  return get<GlossaryTermDetail>(`${BASE}/terms/${termId}`);
}

export function createTerm(body: CreateTermBody) {
  return post<GlossaryTerm, CreateTermBody>(`${BASE}/terms`, body);
}

export function updateTerm(termId: string, body: UpdateTermBody) {
  return put<GlossaryTerm, UpdateTermBody>(`${BASE}/terms/${termId}`, body);
}

export function deleteTerm(termId: string) {
  return del<void>(`${BASE}/terms/${termId}`);
}

export function submitTerm(termId: string) {
  return post<GlossaryTerm, undefined>(`${BASE}/terms/${termId}/submit`, undefined);
}

export function cancelReview(termId: string) {
  return post<GlossaryTerm, undefined>(`${BASE}/terms/${termId}/cancel-review`, undefined);
}

export function reviewTerm(termId: string, body: ReviewBody) {
  return post<GlossaryTerm, ReviewBody>(`${BASE}/terms/${termId}/review`, body);
}

export function deprecateTerm(termId: string, body: DeprecateBody) {
  return post<GlossaryTerm, DeprecateBody>(`${BASE}/terms/${termId}/deprecate`, body);
}

export function reinstateTerm(termId: string) {
  return post<GlossaryTerm, undefined>(`${BASE}/terms/${termId}/reinstate`, undefined);
}

export function getTermVersions(termId: string) {
  return get<GlossaryTermVersion[]>(`${BASE}/terms/${termId}/versions`);
}

export function checkDuplicate(params: { name_en: string; domain_id?: string }) {
  return post<DuplicateCheckResult, undefined>(
    `${BASE}/terms/check-duplicate`,
    undefined,
    { params },
  );
}

export function listReviewQueue() {
  return get<GlossaryTerm[]>(`${BASE}/terms/review-queue`);
}

// ---- AI Assist ----------------------------------------------------------

export function assistDraft(body: AssistDraftBody) {
  return post<AssistResponse, AssistDraftBody>(`${BASE}/assist/draft`, body);
}

export function assistRephrase(body: AssistRephraseBody) {
  return post<AssistResponse, AssistRephraseBody>(`${BASE}/assist/rephrase`, body);
}

export function assistAdvise(body: AssistAdviseBody) {
  return post<AssistResponse, AssistAdviseBody>(`${BASE}/assist/advise`, body);
}

// ---- DB Extraction ------------------------------------------------------

export function listExtractionConnections() {
  return get<ExtractionConnection[]>(`${BASE}/extraction/connections`);
}

export function runScan(body: { connection_id: string; ai_draft: boolean }) {
  return post<ScanResult, typeof body>(`${BASE}/extraction/scan`, body);
}

export function listCandidates(params: {
  status?: string;
  schema?: string;
  table?: string;
  domain_id?: string;
} = {}) {
  return get<GlossaryCandidate[]>(`${BASE}/extraction/candidates`, { params });
}

export function acceptCandidate(id: string, body: { domain_id?: string; force?: boolean }) {
  return post<AcceptCandidateResult, typeof body>(`${BASE}/extraction/candidates/${id}/accept`, body);
}

export function assignCandidate(id: string, body: { domain_id?: string; user_id?: number }) {
  return put<GlossaryCandidate, typeof body>(`${BASE}/extraction/candidates/${id}/assign`, body);
}

export function dismissCandidate(id: string, reason?: string) {
  return post<void, { reason?: string }>(`${BASE}/extraction/candidates/${id}/dismiss`, { reason });
}

export function clearCandidates(table?: string) {
  return post<{ cleared: number }, { table?: string }>(`${BASE}/extraction/candidates/clear`, { table });
}

export function getDraftStatus() {
  return get<DraftStatus>(`${BASE}/extraction/draft/status`);
}

export function startDrafting() {
  return post<DraftStatus, undefined>(`${BASE}/extraction/draft`, undefined);
}

// ---- Import / Export ----------------------------------------------------

export function getExportCount(scope: "all" | "my") {
  return get<{ count: number }>(`${BASE}/export/count`, { params: { scope } });
}

/** Download approved-glossary Excel and trigger a browser save. */
export async function exportGlossary(scope: "all" | "my") {
  const res = await apiClient.get(`${BASE}/export`, { params: { scope }, responseType: "blob" });
  triggerDownload(res.data as Blob, "business-glossary.xlsx");
}

export async function downloadImportTemplate() {
  const res = await apiClient.get(`${BASE}/import/template`, { responseType: "blob" });
  triggerDownload(res.data as Blob, "glossary-import-template.xlsx");
}

export async function importGlossary(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await apiClient.post(`${BASE}/import`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data as ImportSummary;
}

export function rollbackImport(batchId: string) {
  return post<{ deleted: number }, undefined>(`${BASE}/import/${batchId}/rollback`, undefined);
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
