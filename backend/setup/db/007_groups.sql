-- 007_groups.sql
-- Department groups within tenants

CREATE TABLE t_groups (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    name VARCHAR(255) NOT NULL,
    name_ar VARCHAR(255),
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, slug)
);

CREATE INDEX idx_groups_tenant ON t_groups(tenant_id);

-- Each user belongs to one group
ALTER TABLE t_users ADD COLUMN group_id INTEGER REFERENCES t_groups(id);

-- Requests track requester and receiver groups
ALTER TABLE t_share_requests ADD COLUMN requester_group_id INTEGER REFERENCES t_groups(id);
ALTER TABLE t_share_requests ADD COLUMN receiver_group_id INTEGER REFERENCES t_groups(id);

CREATE INDEX idx_requests_receiver_group ON t_share_requests(receiver_group_id);
