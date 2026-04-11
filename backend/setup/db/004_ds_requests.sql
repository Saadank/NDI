-- 004_ds_requests.sql
-- Data Sharing: share requests, workflow templates, steps

CREATE TABLE t_workflow_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    name VARCHAR(255) NOT NULL,
    sharing_type VARCHAR(50),
    data_classification VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL REFERENCES t_users(id)
);

CREATE INDEX idx_workflow_templates_tenant ON t_workflow_templates(tenant_id);

CREATE TABLE t_template_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES t_workflow_templates(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    assignee_role VARCHAR(100),
    execution_mode VARCHAR(50) NOT NULL DEFAULT 'sequential',
    sla_days INTEGER NOT NULL DEFAULT 3,
    condition_expr TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_template_steps_template ON t_template_steps(template_id);

CREATE TABLE t_share_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    request_number VARCHAR(50) UNIQUE NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    title VARCHAR(500) NOT NULL,
    purpose TEXT NOT NULL,
    legal_basis VARCHAR(100) NOT NULL,
    sharing_type VARCHAR(50) NOT NULL,
    data_classification VARCHAR(50) NOT NULL,
    personal_data_involved BOOLEAN NOT NULL,
    estimated_data_subjects INTEGER,
    data_subject_categories TEXT[],
    source_description TEXT,
    requester_id INTEGER NOT NULL REFERENCES t_users(id),
    receiving_tenant_id INTEGER REFERENCES t_tenants(id),
    workflow_template_id UUID REFERENCES t_workflow_templates(id),
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    expiry_at TIMESTAMPTZ,
    conditions TEXT,
    dpia_confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL REFERENCES t_users(id),
    updated_by INTEGER REFERENCES t_users(id),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_requests_tenant ON t_share_requests(tenant_id);
CREATE INDEX idx_requests_status ON t_share_requests(status);
CREATE INDEX idx_requests_requester ON t_share_requests(requester_id);

CREATE TABLE t_workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES t_share_requests(id),
    template_step_id UUID REFERENCES t_template_steps(id),
    step_order INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL,
    name VARCHAR(255),
    assignee_role VARCHAR(100),
    assignee_user_id INTEGER REFERENCES t_users(id),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    sla_deadline TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    completed_by INTEGER REFERENCES t_users(id),
    decision VARCHAR(50),
    comment TEXT,
    escalated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workflow_steps_request ON t_workflow_steps(request_id);
CREATE INDEX idx_workflow_steps_status ON t_workflow_steps(status);
