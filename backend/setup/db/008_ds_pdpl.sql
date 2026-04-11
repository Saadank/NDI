-- 008_ds_pdpl.sql
-- Data Sharing: breach events and DSR log

-- Breach events with 72hr SDAIA notification clock
CREATE TABLE t_breach_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    request_id UUID REFERENCES t_share_requests(id),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(50) NOT NULL DEFAULT 'medium',
    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sdaia_notification_deadline TIMESTAMPTZ NOT NULL,
    sdaia_notified_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    resolution TEXT,
    resolved_at TIMESTAMPTZ,
    reported_by INTEGER NOT NULL REFERENCES t_users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_breach_tenant ON t_breach_events(tenant_id);
CREATE INDEX idx_breach_status ON t_breach_events(status);
CREATE INDEX idx_breach_deadline ON t_breach_events(sdaia_notification_deadline)
    WHERE sdaia_notified_at IS NULL;

-- Data Subject Rights (DSR) log with 30-day PDPL deadline
CREATE TABLE t_dsr_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    subject_name VARCHAR(255) NOT NULL,
    subject_email VARCHAR(255),
    subject_id_type VARCHAR(100),
    subject_id_value VARCHAR(255),
    request_type VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'received',
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    response_deadline TIMESTAMPTZ NOT NULL,
    responded_at TIMESTAMPTZ,
    response_summary TEXT,
    assigned_to INTEGER REFERENCES t_users(id),
    created_by INTEGER NOT NULL REFERENCES t_users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dsr_tenant ON t_dsr_requests(tenant_id);
CREATE INDEX idx_dsr_status ON t_dsr_requests(status);
CREATE INDEX idx_dsr_deadline ON t_dsr_requests(response_deadline)
    WHERE responded_at IS NULL;
