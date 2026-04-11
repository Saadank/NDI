-- 003_ds_connections.sql
-- Data Sharing: DB connections, schemas

CREATE TABLE t_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    db_type VARCHAR(50) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    database VARCHAR(255),
    username VARCHAR(255) NOT NULL,
    password_encrypted TEXT NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL REFERENCES t_users(id),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_connections_tenant ON t_connections(tenant_id);

CREATE TABLE t_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES t_connections(id),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    schema_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_schemas_connection ON t_schemas(connection_id);
