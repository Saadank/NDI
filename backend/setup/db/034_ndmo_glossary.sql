-- 034_ndmo_glossary.sql
-- NDMO Compliance — Business Glossary feature (BRD: Feature Addendum v1.0).
--
-- A governed, domain-organised vocabulary of business terms with a full
-- authoring + approval lifecycle, AI-assisted drafting, DB metadata
-- extraction, and bulk import/export.
--
-- Conventions (consistent with 032_ndmo_core.sql):
--   * All objects live in the `ndmo` schema.
--   * Per-tenant tables carry tenant_id INTEGER REFERENCES public.t_tenants(id).
--   * Cross-schema FKs to public.t_users / public.t_tenants are intentional —
--     glossary depends on platform identity.
--   * Artefact PKs are UUID (gen_random_uuid) per the Datarix convention and
--     BRD §9.3 (stable UUIDs so Phase-2 DQ-rule linkage needs no migration).
--   * Status/type values use CHECK constraints (not Postgres ENUM types),
--     matching the rest of the NDMO schema.
--
-- Idempotent: CREATE ... IF NOT EXISTS everywhere; re-running is a no-op.
--
-- Slice scope: every table is created now (so Phase-2 + the extraction /
-- import slices need no schema change), but the extraction (t_glossary_db_
-- candidates) and LLM-audit (t_glossary_llm_calls) tables are unused until
-- their respective slices land.

-- ===========================================================================
-- DOMAINS — self-referencing n-level hierarchy (BRD §4)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_domains — flexible, org-specific domain tree.
-- parent_id NULL = top-level domain.  Each node has one Data Owner; stewards
-- are a many-to-many in t_glossary_domain_stewards.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_domains (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    parent_id       UUID REFERENCES ndmo.t_glossary_domains(id),
    name_en         VARCHAR(255) NOT NULL,
    name_ar         VARCHAR(255),
    description_en  TEXT,
    description_ar  TEXT,
    owner_user_id   INTEGER REFERENCES public.t_users(id),
    status          VARCHAR(16) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'archived')),
    created_by      INTEGER NOT NULL REFERENCES public.t_users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_glossary_domains_tenant
    ON ndmo.t_glossary_domains(tenant_id);
CREATE INDEX IF NOT EXISTS idx_glossary_domains_parent
    ON ndmo.t_glossary_domains(tenant_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_glossary_domains_owner
    ON ndmo.t_glossary_domains(tenant_id, owner_user_id);

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_domain_stewards — stewards assigned per domain (M:N).
-- This table (together with t_glossary_domains.owner_user_id) is the source
-- of truth for the domain-scoped RBAC model: a user's glossary role is
-- DERIVED from which domains they own / steward, not stored on the user.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_domain_stewards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    domain_id       UUID NOT NULL REFERENCES ndmo.t_glossary_domains(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES public.t_users(id),
    assigned_by     INTEGER NOT NULL REFERENCES public.t_users(id),
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (domain_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_glossary_stewards_user
    ON ndmo.t_glossary_domain_stewards(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_glossary_stewards_domain
    ON ndmo.t_glossary_domain_stewards(domain_id);

-- ===========================================================================
-- TERMS — the core record + its lifecycle satellites (BRD §5)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_terms — one row per business term.
-- domain_id NULL => Enterprise (cross-domain) term, approved by Org Admin.
-- published_version_id / pending_version_id implement the dual-version edit
-- flow (BRD §6.2 / WF-03): a published term stays live while an edit is
-- under review.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_terms (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            INTEGER NOT NULL REFERENCES public.t_tenants(id),
    domain_id            UUID REFERENCES ndmo.t_glossary_domains(id),
    name_en              VARCHAR(255) NOT NULL,
    name_ar              VARCHAR(255),
    definition_en        TEXT,
    definition_ar        TEXT,
    acronym              VARCHAR(50),
    examples             TEXT,
    business_rule        TEXT,                       -- Phase-2 DQ-linkage seed
    status               VARCHAR(20) NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft', 'under_review', 'approved',
                                           'deprecated', 'changes_requested')),
    term_type            VARCHAR(16) NOT NULL DEFAULT 'domain'
                         CHECK (term_type IN ('domain', 'enterprise')),
    source               VARCHAR(16) NOT NULL DEFAULT 'manual'
                         CHECK (source IN ('manual', 'llm_assisted', 'db_extracted')),
    owner_user_id        INTEGER REFERENCES public.t_users(id),
    steward_user_id      INTEGER REFERENCES public.t_users(id),
    created_by           INTEGER NOT NULL REFERENCES public.t_users(id),
    version              INTEGER NOT NULL DEFAULT 1,
    published_version_id UUID,                        -- FK added below (deferred)
    pending_version_id   UUID,
    import_batch_id      UUID,                         -- groups bulk-imported drafts (rollback)
    -- deprecation (BRD WF-07)
    deprecation_reason   TEXT,
    replaced_by_term_id  UUID REFERENCES ndmo.t_glossary_terms(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at          TIMESTAMPTZ,
    deprecated_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_glossary_terms_tenant
    ON ndmo.t_glossary_terms(tenant_id);
CREATE INDEX IF NOT EXISTS idx_glossary_terms_domain
    ON ndmo.t_glossary_terms(tenant_id, domain_id);
CREATE INDEX IF NOT EXISTS idx_glossary_terms_status
    ON ndmo.t_glossary_terms(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_glossary_terms_type
    ON ndmo.t_glossary_terms(tenant_id, term_type);
-- Case-insensitive name lookups for duplicate detection (BRD §6.4 / FR-036)
CREATE INDEX IF NOT EXISTS idx_glossary_terms_name_lower
    ON ndmo.t_glossary_terms(tenant_id, domain_id, lower(name_en));

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_term_versions — immutable snapshot per approved version.
-- Every approved change writes a new row (BRD §6.2 / FR-016).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_term_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    term_id         UUID NOT NULL REFERENCES ndmo.t_glossary_terms(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    snapshot        JSONB NOT NULL DEFAULT '{}'::jsonb,
    changed_by      INTEGER NOT NULL REFERENCES public.t_users(id),
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (term_id, version)
);

CREATE INDEX IF NOT EXISTS idx_glossary_versions_term
    ON ndmo.t_glossary_term_versions(term_id, version DESC);

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_term_reviews — full, immutable review history (BRD §5.2).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_term_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    term_id         UUID NOT NULL REFERENCES ndmo.t_glossary_terms(id) ON DELETE CASCADE,
    version         INTEGER,
    reviewer_id     INTEGER NOT NULL REFERENCES public.t_users(id),
    decision        VARCHAR(20) NOT NULL
                    CHECK (decision IN ('approve', 'request_changes', 'reject')),
    note            TEXT,
    reviewed_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_glossary_reviews_term
    ON ndmo.t_glossary_term_reviews(term_id, reviewed_at DESC);

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_term_relations — explicit relationships between terms
-- (BRD §6.2 / FR-017).  May cross domains.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_term_relations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    source_term_id  UUID NOT NULL REFERENCES ndmo.t_glossary_terms(id) ON DELETE CASCADE,
    target_term_id  UUID NOT NULL REFERENCES ndmo.t_glossary_terms(id) ON DELETE CASCADE,
    relation_type   VARCHAR(20) NOT NULL
                    CHECK (relation_type IN ('synonym', 'related', 'parent_of', 'calculated_from')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_term_id, target_term_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_glossary_relations_source
    ON ndmo.t_glossary_term_relations(source_term_id);
CREATE INDEX IF NOT EXISTS idx_glossary_relations_target
    ON ndmo.t_glossary_term_relations(target_term_id);

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_domain_notes — domain-specific notes on Enterprise terms,
-- without altering the master definition (BRD §4.3 / FR-018 / WF-08).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_domain_notes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    term_id         UUID NOT NULL REFERENCES ndmo.t_glossary_terms(id) ON DELETE CASCADE,
    domain_id       UUID NOT NULL REFERENCES ndmo.t_glossary_domains(id) ON DELETE CASCADE,
    note_en         TEXT NOT NULL,
    note_ar         TEXT,
    created_by      INTEGER NOT NULL REFERENCES public.t_users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (term_id, domain_id)
);

CREATE INDEX IF NOT EXISTS idx_glossary_domain_notes_term
    ON ndmo.t_glossary_domain_notes(term_id);

-- ===========================================================================
-- DB EXTRACTION + LLM AUDIT — created now, used in later slices (BRD §6.3/6.4)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_db_candidates — candidate terms mined from source-DB column
-- metadata (BRD §6.4).  connection_id references the platform connector
-- registry; left as a loose INTEGER (no FK) to avoid coupling the glossary
-- schema to the connector table layout.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_db_candidates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           INTEGER NOT NULL REFERENCES public.t_tenants(id),
    connection_id       UUID,                       -- public.t_connections.id (loose, no FK)
    schema_name         VARCHAR(255),
    table_name          VARCHAR(255),
    column_name         VARCHAR(255),
    inferred_name_en    VARCHAR(255) NOT NULL,
    ai_draft_definition TEXT,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'accepted', 'dismissed')),
    assigned_domain_id  UUID REFERENCES ndmo.t_glossary_domains(id),
    assigned_to_user_id INTEGER REFERENCES public.t_users(id),
    dismiss_reason      TEXT,
    promoted_term_id    UUID REFERENCES ndmo.t_glossary_terms(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_glossary_candidates_tenant_status
    ON ndmo.t_glossary_db_candidates(tenant_id, status);

-- ---------------------------------------------------------------------------
-- ndmo.t_glossary_llm_calls — audit log of LLM assist calls.  Content hashes
-- only, never full text (BRD §6.3 / FR-023, NFR-4).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ndmo.t_glossary_llm_calls (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    term_id         UUID REFERENCES ndmo.t_glossary_terms(id) ON DELETE SET NULL,
    purpose         VARCHAR(16) NOT NULL
                    CHECK (purpose IN ('draft', 'rephrase', 'advise')),
    input_hash      VARCHAR(64),
    output_hash     VARCHAR(64),
    tokens_used     INTEGER,
    latency_ms      INTEGER,
    success         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_glossary_llm_calls_tenant
    ON ndmo.t_glossary_llm_calls(tenant_id, created_at DESC);

-- ===========================================================================
-- Deferred FKs for the dual-version pointers (added after the versions table
-- exists).  Wrapped in DO blocks so the migration stays idempotent.
-- ===========================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_glossary_terms_published_version'
    ) THEN
        ALTER TABLE ndmo.t_glossary_terms
            ADD CONSTRAINT fk_glossary_terms_published_version
            FOREIGN KEY (published_version_id)
            REFERENCES ndmo.t_glossary_term_versions(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_glossary_terms_pending_version'
    ) THEN
        ALTER TABLE ndmo.t_glossary_terms
            ADD CONSTRAINT fk_glossary_terms_pending_version
            FOREIGN KEY (pending_version_id)
            REFERENCES ndmo.t_glossary_term_versions(id);
    END IF;
END$$;
