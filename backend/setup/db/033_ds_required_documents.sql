-- 033_ds_required_documents.sql
-- Issue 5: when a reviewer (DPO / Data Owner) sends a request back, they can
-- attach a checklist of supporting documents the requester must provide
-- before resubmitting (e.g. a signed contract, a DPIA). Stored as a JSONB
-- array of { "label": str, "satisfied": bool } so the requester sees a
-- checklist on the edit screen and uploads against it.
ALTER TABLE t_share_requests
ADD COLUMN IF NOT EXISTS required_documents JSONB;
