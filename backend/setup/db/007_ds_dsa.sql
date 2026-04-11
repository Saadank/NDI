-- 007_ds_dsa.sql
-- Data Sharing: Data Sharing Agreements

CREATE TABLE t_data_sharing_agreements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    request_id UUID REFERENCES t_share_requests(id),
    counterparty_tenant_id INTEGER REFERENCES t_tenants(id),
    title VARCHAR(500) NOT NULL,
    document_storage_key VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    accepted_by_source BOOLEAN DEFAULT FALSE,
    accepted_by_source_at TIMESTAMPTZ,
    accepted_by_source_user INTEGER REFERENCES t_users(id),
    accepted_by_receiver BOOLEAN DEFAULT FALSE,
    accepted_by_receiver_at TIMESTAMPTZ,
    accepted_by_receiver_user INTEGER REFERENCES t_users(id),
    effective_date DATE,
    expiry_date DATE,
    conditions TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL REFERENCES t_users(id)
);

CREATE INDEX idx_dsa_tenant ON t_data_sharing_agreements(tenant_id);
CREATE INDEX idx_dsa_request ON t_data_sharing_agreements(request_id);
