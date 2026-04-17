-- 009_ds_external_recipients.sql
-- External recipients (non-tenant orgs), their contacts, and magic-link pickup tokens.

CREATE TABLE IF NOT EXISTS t_external_recipients (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    org_name VARCHAR(255) NOT NULL,
    notes TEXT,
    dpa_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES t_users(id),
    updated_by INTEGER REFERENCES t_users(id)
);

CREATE INDEX IF NOT EXISTS idx_external_recipients_tenant_active
    ON t_external_recipients(tenant_id, is_active);
CREATE INDEX IF NOT EXISTS idx_external_recipients_tenant_name
    ON t_external_recipients(tenant_id, lower(org_name));


CREATE TABLE IF NOT EXISTS t_recipient_contacts (
    id SERIAL PRIMARY KEY,
    recipient_id INTEGER NOT NULL REFERENCES t_external_recipients(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    phone VARCHAR(50),
    email_verified_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES t_users(id),
    UNIQUE (recipient_id, email)
);

CREATE INDEX IF NOT EXISTS idx_recipient_contacts_recipient
    ON t_recipient_contacts(recipient_id);


CREATE TABLE IF NOT EXISTS t_pickup_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    share_request_id UUID NOT NULL REFERENCES t_share_requests(id),
    contact_id INTEGER NOT NULL REFERENCES t_recipient_contacts(id),
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    max_downloads INTEGER NOT NULL DEFAULT 10,
    download_count INTEGER NOT NULL DEFAULT 0,
    first_opened_at TIMESTAMPTZ,
    dpa_accepted_at TIMESTAMPTZ,
    dpa_ip INET,
    dpa_user_agent TEXT,
    revoked_at TIMESTAMPTZ,
    revoked_by INTEGER REFERENCES t_users(id),
    revoke_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES t_users(id)
);

CREATE INDEX IF NOT EXISTS idx_pickup_tokens_request
    ON t_pickup_tokens(share_request_id);
CREATE INDEX IF NOT EXISTS idx_pickup_tokens_contact
    ON t_pickup_tokens(contact_id);
CREATE INDEX IF NOT EXISTS idx_pickup_tokens_expires_active
    ON t_pickup_tokens(expires_at) WHERE revoked_at IS NULL;


-- Extend share requests with external recipient linkage and delivery channel.
ALTER TABLE t_share_requests
    ADD COLUMN IF NOT EXISTS external_recipient_id INTEGER REFERENCES t_external_recipients(id);
ALTER TABLE t_share_requests
    ADD COLUMN IF NOT EXISTS external_contact_id INTEGER REFERENCES t_recipient_contacts(id);
ALTER TABLE t_share_requests
    ADD COLUMN IF NOT EXISTS delivery_channel VARCHAR(20) NOT NULL DEFAULT 'portal';

-- When sharing_type='external', exactly one of receiving_tenant_id / external_recipient_id must be set.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_external_target'
    ) THEN
        ALTER TABLE t_share_requests
            ADD CONSTRAINT chk_external_target CHECK (
                sharing_type <> 'external'
                OR (receiving_tenant_id IS NOT NULL AND external_recipient_id IS NULL)
                OR (receiving_tenant_id IS NULL     AND external_recipient_id IS NOT NULL)
            );
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_requests_external_recipient
    ON t_share_requests(external_recipient_id) WHERE external_recipient_id IS NOT NULL;
