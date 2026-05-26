-- 023_ndmo_core.sql
-- NDMO Compliance — Phase 1: core schema (catalog + cycles + assessments).
--
-- Schema isolation: all NDMO objects live in the dedicated `ndmo` schema so
-- the product can be dropped/backed-up/permissioned as a single unit. Cross-
-- schema FKs to public.t_tenants / public.t_users are intentional — NDMO
-- depends on platform identity, not the other way around.
--
-- Catalog tables (domains, controls, specifications) are GLOBAL — the 14
-- domains / 77 controls / 190+ specifications are published by NDMO and are
-- identical for every tenant.  Per-tenant tables (cycles, documents,
-- assessments, citations, notifications) all carry tenant_id.
--
-- This file is idempotent.  CREATE TABLE IF NOT EXISTS everywhere; re-running
-- on an existing DB is a no-op.
--
-- Re-uses platform assets:
--   - public.t_tenants, public.t_users        (platform core, 001_)
--   - public.t_tenant_products                (product entitlement, 001_)
--   - public.t_audit_events                   (audit, 002_)
--
-- Slug decision: keeps t_products.slug = 'ndmo'.  No data migration.

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS ndmo;

-- ===========================================================================
-- CATALOG (global — NDMO-published, identical for every tenant)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_domains — the 14 assessable NDMO domains.
-- Examples: DG (Data Governance), MCM (Metadata & Catalogue Management),
-- DQ (Data Quality), PDP (Personal Data Protection).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_domains (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(10)  NOT NULL UNIQUE,            -- DG, MCM, DQ, ...
    name_ar         VARCHAR(255) NOT NULL,                   -- مجال حوكمة البيانات
    name_en         VARCHAR(255),                            -- Data Governance
    description_ar  TEXT,
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ndmo_domains_sort ON ndmo.t_ndmo_domains(sort_order);

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_controls — 77 controls grouped under the 14 domains.
-- Code format DG.1, DQ.2, etc.  (For DC the source uses "DC.1" too — only the
-- spec level uses "DC1.X" in that one domain.)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_controls (
    id              SERIAL PRIMARY KEY,
    domain_id       INTEGER NOT NULL REFERENCES ndmo.t_ndmo_domains(id),
    code            VARCHAR(20)  NOT NULL UNIQUE,            -- DG.1, MCM.3, ...
    name_ar         VARCHAR(512) NOT NULL,
    description_ar  TEXT,
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ndmo_controls_domain ON ndmo.t_ndmo_controls(domain_id);
CREATE INDEX IF NOT EXISTS idx_ndmo_controls_sort   ON ndmo.t_ndmo_controls(domain_id, sort_order);

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_specifications — 190–191 specifications, one row per spec.
-- code accepts both numbering schemes in the source document:
--   * dotted form  : DG.1.1, BIA.3.2, MCM.4.5
--   * non-dotted   : DC1.1, DC2.3                            (DC domain only)
-- priority: 1 (year 1), 2 (year 2), or 3 (year 3) per NDMO phased-rollout.
-- nca_conditional: TRUE if the source notes a priority override per the
-- National Cybersecurity Authority's policies (the "حسب لوائح وسياسات
-- الهيئة الوطنية للأمن السيبراني" annotation seen on a small number of specs).
-- maturity_levels: JSONB of shape {"0": {...}, ..., "5": {...}} per spec —
-- description + supporting-evidence codes for each maturity level.
-- required_elements: JSONB structured row from __مؤشر نضيء_.xlsx.
-- search_query: the standard's official question text (best RAG retrieval
-- query for this spec).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_specifications (
    id                  SERIAL PRIMARY KEY,
    control_id          INTEGER NOT NULL REFERENCES ndmo.t_ndmo_controls(id),
    code                VARCHAR(30)  NOT NULL UNIQUE,
    name_ar             VARCHAR(512) NOT NULL,
    description_ar      TEXT,
    priority            SMALLINT NOT NULL CHECK (priority IN (1, 2, 3)),
    nca_conditional     BOOLEAN NOT NULL DEFAULT FALSE,
    maturity_levels     JSONB NOT NULL DEFAULT '{}'::jsonb,
    required_elements   JSONB NOT NULL DEFAULT '{}'::jsonb,
    acceptance_criteria TEXT,
    search_query        TEXT,
    related_specs       TEXT[] NOT NULL DEFAULT '{}',
    issue_date          DATE,
    raw_source          JSONB NOT NULL DEFAULT '{}'::jsonb,  -- audit trail of which files contributed
    sort_order          SMALLINT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ndmo_specs_control     ON ndmo.t_ndmo_specifications(control_id);
CREATE INDEX IF NOT EXISTS idx_ndmo_specs_priority    ON ndmo.t_ndmo_specifications(priority);
CREATE INDEX IF NOT EXISTS idx_ndmo_specs_ctrl_prio   ON ndmo.t_ndmo_specifications(control_id, priority);

-- ===========================================================================
-- TENANT-SCOPED RUNTIME TABLES
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_cycles — an assessment cycle for one tenant in one period.
-- active_priorities controls which priorities count for this year (per the
-- 3-year phased rollout: year 1 = [1], year 2 = [1,2], year 3 = [1,2,3]).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_cycles (
    id                 SERIAL PRIMARY KEY,
    tenant_id          INTEGER NOT NULL REFERENCES public.t_tenants(id),
    year               SMALLINT NOT NULL,
    quarter            SMALLINT,
    active_priorities  SMALLINT[] NOT NULL,                  -- e.g. {1} or {1,2}
    status             VARCHAR(30) NOT NULL DEFAULT 'planning'
                       CHECK (status IN ('planning','active','completed','archived')),
    started_at         TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    created_by         INTEGER NOT NULL REFERENCES public.t_users(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, year, quarter)
);

CREATE INDEX IF NOT EXISTS idx_ndmo_cycles_tenant ON ndmo.t_ndmo_cycles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ndmo_cycles_status ON ndmo.t_ndmo_cycles(tenant_id, status);

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_documents — evidence files uploaded by the Compliance Analyst.
-- Mirrors the cortex File entity.  minio_key follows the existing tenant
-- prefix convention used elsewhere in the platform.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    cycle_id        INTEGER REFERENCES ndmo.t_ndmo_cycles(id),
    file_name       VARCHAR(512) NOT NULL,
    minio_key       VARCHAR(512) NOT NULL,
    mime_type       VARCHAR(100),
    size_bytes      BIGINT,
    status          VARCHAR(30) NOT NULL DEFAULT 'uploaded'
                    CHECK (status IN ('uploaded','scanning','infected','clean',
                                      'extracting','embedding','ready','failed')),
    page_count      INTEGER,
    sha256          VARCHAR(64),
    uploaded_by     INTEGER NOT NULL REFERENCES public.t_users(id),
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ndmo_docs_tenant ON ndmo.t_ndmo_documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ndmo_docs_cycle  ON ndmo.t_ndmo_documents(tenant_id, cycle_id);
CREATE INDEX IF NOT EXISTS idx_ndmo_docs_status ON ndmo.t_ndmo_documents(tenant_id, status);

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_assessments — one row per (specification, cycle) for each tenant.
-- maturity_level: the 0..5 verdict from the AI engine (or the human reviewer
-- after override).  confidence in [0,1].  ai_result holds the full JSON
-- response from the LLM for audit/debugging.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_assessments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           INTEGER NOT NULL REFERENCES public.t_tenants(id),
    specification_id    INTEGER NOT NULL REFERENCES ndmo.t_ndmo_specifications(id),
    cycle_id            INTEGER NOT NULL REFERENCES ndmo.t_ndmo_cycles(id),
    maturity_level      SMALLINT NOT NULL CHECK (maturity_level BETWEEN 0 AND 5),
    status              VARCHAR(30) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','in_progress','under_review',
                                          'approved','rejected')),
    confidence          NUMERIC(4,3) CHECK (confidence IS NULL
                                            OR (confidence >= 0 AND confidence <= 1)),
    ai_result           JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by         INTEGER REFERENCES public.t_users(id),
    review_decision     VARCHAR(30)
                        CHECK (review_decision IS NULL OR review_decision IN
                               ('approved','changes_requested','rejected')),
    review_note         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, specification_id, cycle_id)
);

CREATE INDEX IF NOT EXISTS idx_ndmo_assess_tenant      ON ndmo.t_ndmo_assessments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ndmo_assess_cycle_stat  ON ndmo.t_ndmo_assessments(tenant_id, cycle_id, status);
CREATE INDEX IF NOT EXISTS idx_ndmo_assess_spec        ON ndmo.t_ndmo_assessments(tenant_id, specification_id);

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_citations — per-assessment evidence chunks (page-level citation).
-- chunk_id is the identifier inside Qdrant {tenant_id}-chunks collection.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_citations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   UUID NOT NULL REFERENCES ndmo.t_ndmo_assessments(id) ON DELETE CASCADE,
    chunk_id        VARCHAR(128) NOT NULL,
    citation_text   TEXT NOT NULL,
    source_file     VARCHAR(512) NOT NULL,
    page_number     SMALLINT NOT NULL,
    confidence      NUMERIC(4,3),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ndmo_cit_assessment ON ndmo.t_ndmo_citations(assessment_id);

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_notifications — separate from public.t_notifications (which is
-- FK'd to t_share_requests and therefore unusable here).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    user_id         INTEGER NOT NULL REFERENCES public.t_users(id),
    type            VARCHAR(50) NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ndmo_notif_user_unread
    ON ndmo.t_ndmo_notifications(tenant_id, user_id, created_at DESC)
    WHERE read_at IS NULL;

-- ---------------------------------------------------------------------------
-- ndmo.t_ndmo_seed_runs — append-only audit of one-shot seed operations.
-- Lets operators check "was this DB seeded?  with which source-file versions?".
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_ndmo_seed_runs (
    id              SERIAL PRIMARY KEY,
    seeded_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    seeder_version  VARCHAR(50) NOT NULL,
    input_dir       TEXT,
    file_hashes     JSONB NOT NULL DEFAULT '{}'::jsonb,
    counts          JSONB NOT NULL DEFAULT '{}'::jsonb,      -- {domains, controls, specs, ...}
    notes           TEXT
);
