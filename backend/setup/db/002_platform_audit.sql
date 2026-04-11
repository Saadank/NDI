-- 002_platform_audit.sql
-- Shared append-only audit events table

CREATE TABLE t_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    request_id UUID,
    actor_id INTEGER REFERENCES t_users(id),
    actor_ip INET,
    action_type VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255),
    before_state JSONB,
    after_state JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_tenant ON t_audit_events(tenant_id, created_at DESC);
CREATE INDEX idx_audit_request ON t_audit_events(request_id, created_at DESC);
CREATE INDEX idx_audit_actor ON t_audit_events(actor_id, created_at DESC);
