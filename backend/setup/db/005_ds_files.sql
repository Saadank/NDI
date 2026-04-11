-- 005_ds_files.sql
-- Data Sharing: file metadata

CREATE TABLE t_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES t_share_requests(id),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    original_filename VARCHAR(500) NOT NULL,
    storage_key VARCHAR(500) NOT NULL UNIQUE,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(255),
    sha256_hash VARCHAR(64) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending_upload',
    uploaded_by INTEGER REFERENCES t_users(id),
    uploaded_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    deletion_reason VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_files_request ON t_files(request_id);
CREATE INDEX idx_files_status ON t_files(status);
CREATE INDEX idx_files_expires ON t_files(expires_at) WHERE status = 'uploaded';
