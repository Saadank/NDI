/**
 * Business Glossary (NDMO Compliance) — shared types.
 *
 * Mirrors the FastAPI response shapes under
 * /api/v1/products/ndmo-compliance/glossary.
 */

export type GlossaryTermStatus =
  | "draft"
  | "under_review"
  | "approved"
  | "deprecated"
  | "changes_requested";

export interface GlossaryUser {
  id: number;
  name: string;
  email: string;
}

export type GlossaryTermType = "domain" | "enterprise";

export type GlossaryTermSource = "manual" | "llm_assisted" | "db_extracted";

export type GlossaryReviewDecision = "approve" | "request_changes" | "reject";

export type GlossaryRelationType =
  | "synonym"
  | "related"
  | "parent_of"
  | "calculated_from";

export type GlossaryEffectiveRole =
  | "org_admin"
  | "glossary_data_owner"
  | "glossary_data_steward"
  | "glossary_viewer";

export interface GlossaryRole {
  effective_role: GlossaryEffectiveRole;
  is_org_admin: boolean;
  owned_domain_ids: string[];
  steward_domain_ids: string[];
  review_queue_count: number;
}

export interface GlossaryDomain {
  id: string;
  parent_id: string | null;
  name_en: string;
  name_ar: string | null;
  description_en: string | null;
  description_ar: string | null;
  owner_user_id: number | null;
  steward_ids: number[];
  status: "active" | "archived";
  term_count: number;
}

/** A domain node with its children attached (built client-side from the flat list). */
export interface GlossaryDomainNode extends GlossaryDomain {
  children: GlossaryDomainNode[];
}

export interface GlossaryTerm {
  id: string;
  domain_id: string | null;
  name_en: string;
  name_ar: string | null;
  definition_en: string | null;
  definition_ar: string | null;
  acronym: string | null;
  examples: string | null;
  business_rule: string | null;
  status: GlossaryTermStatus;
  term_type: GlossaryTermType;
  source: GlossaryTermSource;
  owner_user_id: number | null;
  steward_user_id: number | null;
  created_by: number;
  version: number;
  published_version_id: string | null;
  pending_version_id: string | null;
  deprecation_reason: string | null;
  replaced_by_term_id: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  deprecated_at: string | null;
}

export interface GlossaryTermVersion {
  id: string;
  version: number;
  snapshot: Record<string, unknown>;
  changed_by: number;
  changed_at: string;
}

export interface GlossaryTermReview {
  id: string;
  version: number | null;
  reviewer_id: number;
  decision: GlossaryReviewDecision;
  note: string | null;
  reviewed_at: string;
}

export interface GlossaryTermRelation {
  id: string;
  relation_type: GlossaryRelationType;
  source_term_id: string;
  target_term_id: string;
  target_name_en: string;
  target_name_ar: string | null;
}

export interface GlossaryTermDetail extends GlossaryTerm {
  relations: GlossaryTermRelation[];
  versions: GlossaryTermVersion[];
  reviews: GlossaryTermReview[];
  published_snapshot: Record<string, unknown> | null;
}

// ---- request bodies -----------------------------------------------------

export interface CreateTermBody {
  name_en: string;
  domain_id?: string | null;
  term_type?: GlossaryTermType;
  name_ar?: string | null;
  definition_en?: string | null;
  definition_ar?: string | null;
  acronym?: string | null;
  examples?: string | null;
  business_rule?: string | null;
  source?: GlossaryTermSource;
}

export type UpdateTermBody = Partial<
  Pick<
    GlossaryTerm,
    | "name_en"
    | "name_ar"
    | "definition_en"
    | "definition_ar"
    | "acronym"
    | "examples"
    | "business_rule"
  >
>;

export interface ReviewBody {
  decision: GlossaryReviewDecision;
  note?: string | null;
}

export interface DeprecateBody {
  reason: string;
  replacement_term_id?: string | null;
}

export interface CreateDomainBody {
  name_en: string;
  name_ar?: string | null;
  description_en?: string | null;
  description_ar?: string | null;
  owner_user_id?: number | null;
}

export interface CreateSubdomainBody extends CreateDomainBody {
  steward_user_ids?: number[];
}

export interface DuplicateCheckResult {
  duplicate: boolean;
  existing_term_id?: string;
  existing_name_en?: string;
}

// ---- AI Assist ----------------------------------------------------------

export type AssistMode = "draft" | "rephrase" | "advise";

export interface AssistResponse {
  available: boolean;
  output: string | null;
  message: string | null;
}

export interface AssistDraftBody {
  term_name: string;
  context?: string | null;
  term_id?: string | null;
}

export interface AssistRephraseBody {
  current_definition: string;
  instruction?: string | null;
  term_id?: string | null;
}

export interface AssistAdviseBody {
  term_name: string;
  definition_draft?: string | null;
  related_terms?: string | null;
  term_id?: string | null;
}

// ---- DB Extraction ------------------------------------------------------

export interface ExtractionConnection {
  id: string;
  db_type: string;
  host: string;
  database: string | null;
  description: string | null;
  status: string | null;
}

export interface GlossaryCandidate {
  id: string;
  connection_id: string | null;
  schema_name: string | null;
  table_name: string | null;
  column_name: string | null;
  inferred_name_en: string;
  ai_draft_definition: string | null;
  status: "pending" | "accepted" | "dismissed";
  assigned_domain_id: string | null;
  assigned_to_user_id: number | null;
  promoted_term_id: string | null;
}

export interface ScanResult {
  created: number;
  skipped_existing: number;
  ai_drafting: boolean;
  tables_scanned: number;
}

export interface DraftStatus {
  total: number;
  drafted: number;
  remaining: number;
  active: boolean;
  llm_available: boolean;
}

export interface AcceptCandidateResult {
  accepted: boolean;
  duplicate: boolean;
  existing_term_id?: string;
  existing_name_en?: string;
  term_id?: string;
}

// ---- Import / Export ----------------------------------------------------

export interface ImportRowResult {
  row: number;
  term: string;
  status: "imported" | "warning" | "error";
  message: string;
}

export interface ImportSummary {
  file_name: string;
  batch_id: string;
  imported: number;
  warnings: number;
  errors: number;
  rows: ImportRowResult[];
}
