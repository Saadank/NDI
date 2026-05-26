// Mirrors t_connections row returned by GET
// /api/v1/products/data-sharing/connections/browse
// (`password_encrypted` is stripped server-side).
export interface Connection {
  id: string; // UUID
  tenant_id: number;
  db_type: string; // e.g. "postgresql", "mysql", "snowflake", "bigquery"
  host: string;
  port: number;
  database: string | null;
  username: string;
  description: string | null;
  status: string; // e.g. "active"
  created_at: string;
  updated_at: string;
  created_by: number | null;
}

// Schema introspection response from
// GET /api/v1/products/data-sharing/schemas/{connection_id}/browse
export interface ColumnInfo {
  name: string;
  type?: string;
  nullable?: boolean;
  primary_key?: boolean;
}

export interface TableInfo {
  name: string;
  columns: ColumnInfo[];
}

export interface SchemaInfo {
  name: string;
  tables: TableInfo[];
}

export interface ConnectionSchemaResponse {
  connection_id: string;
  schema_data: {
    schemas?: SchemaInfo[];
  };
}

// Legacy alias kept so older imports still resolve.
export type Schema = SchemaInfo;
