-- 011_request_direction.sql
-- Datarix supports two request directions per the working spec
-- (extension to v4.0 §3.3, which only describes PULL):
--
--   pull — the requester (in dept A) is asking for data held by dept B.
--   push — the requester (in dept A) is sending data they already have
--          to dept B.
--
-- The DB columns requester_group_id / receiver_group_id are *not* the
-- same as the spec's "source / receiver" departments — the mapping
-- flips by direction (see workflow_engine.py for the table). Defaulting
-- to 'pull' on existing rows preserves today's behaviour exactly.

ALTER TABLE t_share_requests
ADD COLUMN request_direction VARCHAR(10) NOT NULL DEFAULT 'pull'
CHECK (request_direction IN ('pull', 'push'));

CREATE INDEX idx_requests_direction ON t_share_requests(request_direction);
