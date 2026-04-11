-- 001_platform_core.sql
-- Platform Core: tenants, users, invitations, products registry

-- Tenants
CREATE TABLE t_tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    name_ar VARCHAR(255),
    slug VARCHAR(100) NOT NULL UNIQUE,
    tenant_type VARCHAR(50) NOT NULL DEFAULT 'internal_org',
    dpo_name VARCHAR(255),
    dpo_email VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- Tenant history for auditing
CREATE TABLE t_tenants_hist (
    hist_id SERIAL PRIMARY KEY,
    id INTEGER NOT NULL,
    name VARCHAR(255),
    name_ar VARCHAR(255),
    slug VARCHAR(100),
    tenant_type VARCHAR(50),
    dpo_name VARCHAR(255),
    dpo_email VARCHAR(255),
    is_active BOOLEAN,
    version INTEGER,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(255)
);

CREATE OR REPLACE FUNCTION fn_tenants_hist() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO t_tenants_hist (id, name, name_ar, slug, tenant_type, dpo_name, dpo_email, is_active, version, changed_by)
    VALUES (OLD.id, OLD.name, OLD.name_ar, OLD.slug, OLD.tenant_type, OLD.dpo_name, OLD.dpo_email, OLD.is_active, OLD.version, current_user);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tenants_hist
    BEFORE UPDATE ON t_tenants
    FOR EACH ROW EXECUTE FUNCTION fn_tenants_hist();

-- Platform admins (your team)
CREATE TABLE t_platform_admins (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    keycloak_id VARCHAR(255) UNIQUE,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Users (belong to a tenant)
CREATE TABLE t_users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    keycloak_id VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    platform_role VARCHAR(50) NOT NULL DEFAULT 'org_admin',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_tenant ON t_users(tenant_id);
CREATE INDEX idx_users_email ON t_users(email);

-- Invitations
CREATE TABLE t_invitations (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    email VARCHAR(255) NOT NULL,
    role VARCHAR(100) NOT NULL,
    product_slug VARCHAR(100),
    product_role VARCHAR(100),
    token VARCHAR(500) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    invited_by INTEGER NOT NULL REFERENCES t_users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_invitations_token ON t_invitations(token);
CREATE INDEX idx_invitations_email ON t_invitations(email);

-- Products catalogue (seeded at install time)
CREATE TABLE t_products (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    name_ar VARCHAR(255),
    description TEXT,
    description_ar TEXT,
    icon_key VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Which products each tenant has enabled
CREATE TABLE t_tenant_products (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    product_id INTEGER NOT NULL REFERENCES t_products(id),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    enabled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    enabled_by INTEGER NOT NULL REFERENCES t_platform_admins(id),
    disabled_at TIMESTAMPTZ,
    disabled_by INTEGER REFERENCES t_platform_admins(id),
    UNIQUE(tenant_id, product_id)
);

-- Per-user, per-product role assignment
CREATE TABLE t_user_product_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES t_users(id),
    product_id INTEGER NOT NULL REFERENCES t_products(id),
    role VARCHAR(100) NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_by INTEGER NOT NULL REFERENCES t_users(id),
    UNIQUE(user_id, product_id)
);

-- Seed products catalogue
INSERT INTO t_products (slug, name, name_ar, description, icon_key, sort_order) VALUES
    ('data_sharing',  'Data Sharing Platform',       'منصة مشاركة البيانات',     'Governed, PDPL-compliant data sharing between departments and organisations.', 'share',   1),
    ('data_quality',  'Data Quality Profiling',      'جودة البيانات',             'Profile, measure, and monitor data quality across your data sources.',          'quality', 2),
    ('ndmo',          'NDMO Compliance',              'امتثال NDMO',              'Manage compliance with NDMO data governance framework requirements.',             'shield',  3),
    ('dsr',           'Data Subject Rights',          'حقوق أصحاب البيانات',      'Receive, track, and respond to data subject rights requests within PDPL deadlines.', 'person', 4);
