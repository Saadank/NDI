-- 006_ds_notifications.sql
-- Data Sharing: in-app notifications

CREATE TABLE t_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES t_users(id),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    type VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    body TEXT,
    request_id UUID REFERENCES t_share_requests(id),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user ON t_notifications(user_id, is_read, created_at DESC);
CREATE INDEX idx_notifications_tenant ON t_notifications(tenant_id);

-- Email queue (processed by notification worker)
CREATE TABLE t_email_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    to_email VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    html_body TEXT NOT NULL,
    request_id UUID REFERENCES t_share_requests(id),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMPTZ
);

CREATE INDEX idx_email_queue_status ON t_email_queue(status) WHERE status = 'pending';
