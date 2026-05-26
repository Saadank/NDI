/**
 * NDMO Compliance — type definitions mirroring the backend DTOs.
 *
 * Fields use snake_case to match the FastAPI responses exactly (consistent
 * with the data-sharing types convention).
 */

// ───────────────────────────────────────────────────────────────
// Catalog (global — same for every tenant)
// ───────────────────────────────────────────────────────────────

export interface NdmoDomain {
  id: number;
  code: string;
  name_ar: string;
  name_en: string | null;
  sort_order: number;
}

export interface NdmoControl {
  id: number;
  domain_id: number;
  code: string;
  name_ar: string;
  sort_order: number;
}

export interface NdmoSpecification {
  id: number;
  control_id: number;
  code: string;
  name_ar: string;
  description_ar: string | null;
  priority: 1 | 2 | 3;
  nca_conditional: boolean;
  maturity_levels: Record<string, MaturityLevelDescriptor>;
  required_elements: Record<string, unknown>;
  acceptance_criteria: string | null;
  search_query: string | null;
  related_specs: string[];
  control_code?: string;
  control_name_ar?: string;
  domain_code?: string;
  domain_name_ar?: string;
}

export interface MaturityLevelDescriptor {
  name_ar?: string;
  description_ar?: string;
  evidence_codes?: Array<{ code: string; name_ar?: string; description_ar?: string }>;
}

// ───────────────────────────────────────────────────────────────
// Cycles
// ───────────────────────────────────────────────────────────────

export type CycleStatus = "planning" | "active" | "completed" | "archived";

export interface NdmoCycle {
  id: number;
  tenant_id: number;
  year: number;
  quarter: number | null;
  active_priorities: number[];
  status: CycleStatus;
}

// ───────────────────────────────────────────────────────────────
// Documents
// ───────────────────────────────────────────────────────────────

export type DocumentStatus =
  | "uploaded"
  | "scanning"
  | "infected"
  | "clean"
  | "extracting"
  | "embedding"
  | "ready"
  | "failed";

export interface NdmoDocument {
  id: string;
  file_name: string;
  mime_type: string | null;
  size_bytes: number | null;
  status: DocumentStatus;
  page_count: number | null;
  cycle_id: number | null;
  uploaded_at: string;
  processed_at: string | null;
}

export interface InitiateUploadBody {
  file_name: string;
  mime_type: string;
  size_bytes: number;
  cycle_id?: number;
}

export interface InitiateUploadResponse {
  document_id: string;
  minio_key: string;
  presigned_put_url: string;
  expires_seconds: number;
}

// Tree-shaped Restate status (as exposed by GET /documents/{id}/status)
export interface PipelineStatusNode {
  name: string;
  status: "pending" | "in_progress" | "succeeded" | "failed";
  children: PipelineStatusNode[];
}

// ───────────────────────────────────────────────────────────────
// Assessments
// ───────────────────────────────────────────────────────────────

export type AssessmentStatus =
  | "pending"
  | "in_progress"
  | "under_review"
  | "approved"
  | "rejected";

export type ReviewDecision = "approved" | "changes_requested" | "rejected";

export interface AssessmentListItem {
  id: string;
  specification_id: number;
  maturity_level: 0 | 1 | 2 | 3 | 4 | 5;
  status: AssessmentStatus;
  confidence: number | null;
  updated_at: string;
  spec_code: string;
  name_ar: string;
  priority: 1 | 2 | 3;
  control_code: string;
  domain_code: string;
}

export interface AssessmentCitation {
  chunk_id: string;
  citation_text: string;
  source_file: string;
  page_number: number;
  confidence: number | null;
}

export interface AssessmentDetail {
  id: string;
  specification_id: number;
  cycle_id: number;
  maturity_level: 0 | 1 | 2 | 3 | 4 | 5;
  status: AssessmentStatus;
  confidence: number | null;
  ai_result: {
    rationale_ar?: string;
    gaps_ar?: string;
    needs_review?: boolean;
    raw_citations?: Array<{
      chunk_id: string;
      page_number: number;
      source_file: string;
      quoted_text_ar: string;
      supports_level?: number;
    }>;
    prompt?: Record<string, unknown>;
  };
  review_decision: ReviewDecision | null;
  review_note: string | null;
  reviewed_by: number | null;
  updated_at: string;
  spec_code: string;
  spec_name_ar: string;
  priority: 1 | 2 | 3;
  nca_conditional: boolean;
  control_code: string;
  control_name_ar: string;
  domain_code: string;
  domain_name_ar: string;
  citations: AssessmentCitation[];
}

export interface RunAssessmentBody {
  cycle_id?: number;
  dry_run?: boolean;
  spec_limit?: number;
}

export interface RunAssessmentResponse {
  cycle_id: number;
  total_specs: number;
  dry_run: boolean;
}

export interface SubmitReviewBody {
  decision: ReviewDecision;
  note?: string;
  override_maturity_level?: 0 | 1 | 2 | 3 | 4 | 5;
}

// ───────────────────────────────────────────────────────────────
// Maturity-level Arabic labels (mirrors backend MaturityLevel enum)
// ───────────────────────────────────────────────────────────────

export const MATURITY_AR: Record<0 | 1 | 2 | 3 | 4 | 5, string> = {
  0: "غياب القدرات",
  1: "البناء",
  2: "مُعرَّف",
  3: "مُفعَّل",
  4: "مُمكَّن",
  5: "ريادي",
};

export const ASSESSMENT_STATUS_AR: Record<AssessmentStatus, string> = {
  pending: "قيد الانتظار",
  in_progress: "قيد المعالجة",
  under_review: "بانتظار المراجعة",
  approved: "مُعتمَد",
  rejected: "مرفوض",
};

export const DOCUMENT_STATUS_AR: Record<DocumentStatus, string> = {
  uploaded: "تم الرفع",
  scanning: "فحص الفيروسات",
  infected: "مرفوض - فحص الفيروسات",
  clean: "نظيف",
  extracting: "استخراج المحتوى",
  embedding: "بناء الفهرس",
  ready: "جاهز",
  failed: "فشل",
};
