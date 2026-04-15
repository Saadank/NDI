-- 008_ds_structured.sql
-- Data Sharing: structured data (DB connection + table selection or custom SQL)

-- 'file' (existing unstructured upload) or 'structured' (query result exported to CSV)
ALTER TABLE t_share_requests ADD COLUMN data_type VARCHAR(50) NOT NULL DEFAULT 'file';

-- Which connection the query runs against (null for file requests)
ALTER TABLE t_share_requests ADD COLUMN connection_id UUID REFERENCES t_connections(id);

-- 'tables' (user picked schema/table/columns) or 'query' (user wrote SQL)
ALTER TABLE t_share_requests ADD COLUMN selection_mode VARCHAR(50);

-- JSONB array of {schema, table, columns:[]} when selection_mode='tables'
ALTER TABLE t_share_requests ADD COLUMN selected_items JSONB;

-- Raw SQL when selection_mode='query'
ALTER TABLE t_share_requests ADD COLUMN custom_sql TEXT;

CREATE INDEX idx_requests_data_type ON t_share_requests(data_type);
CREATE INDEX idx_requests_connection ON t_share_requests(connection_id);
