"use client";

import { Database, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { getConnections } from "@/lib/api/products/data-sharing/connections.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { RoleBadge } from "@/components/shared/RoleBadge";

const DB_TYPE_LABELS: Record<string, string> = {
  postgresql: "PostgreSQL",
  mysql: "MySQL",
  snowflake: "Snowflake",
  bigquery: "BigQuery",
  mssql: "SQL Server",
};

export default function AdminConnectionsPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin", "platform_admin"] });

  const connectionsQuery = useQuery({
    queryKey: ["admin", "connections"],
    queryFn: getConnections,
    enabled: isReady,
  });

  if (!isReady) return null;

  const connections = connectionsQuery.data ?? [];

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Database Connections</h1>
          <RoleBadge label="Org Admin" />
        </div>
        <button
          type="button"
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          Add Connection
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>CONNECTION NAME</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>TYPE</span>
            <span className="w-[200px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>HOST</span>
            <span className="w-[100px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STATUS</span>
          </div>

          {connectionsQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : connectionsQuery.isError ? (
            <div className="py-20 text-center text-sm text-red-600">Failed to load connections.</div>
          ) : connections.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-20">
              <Database className="h-10 w-10" style={{ color: "#EEEEEE" }} />
              <p className="text-sm font-medium text-auth-text">No database connections</p>
              <p className="text-xs" style={{ color: "#9E9E9E" }}>Add a connection to allow requesters to select structured data.</p>
            </div>
          ) : (
            connections.map((c, i) => (
              <div
                key={c.id}
                className="flex h-14 items-center px-5 hover:bg-[#FFFBF9]"
                style={{ borderBottom: i < connections.length - 1 ? "1px solid #F5F5F5" : undefined }}
              >
                <div className="flex flex-1 items-center gap-3">
                  <Database className="h-4 w-4 shrink-0" style={{ color: "#D76736" }} />
                  <div>
                    <p className="text-[13px] font-medium text-auth-text">{c.database ?? c.host}</p>
                    {c.description && (
                      <p className="text-xs" style={{ color: "#9E9E9E" }}>{c.description}</p>
                    )}
                  </div>
                </div>
                <span className="w-[120px] text-xs" style={{ color: "#515157" }}>
                  {DB_TYPE_LABELS[c.db_type] ?? c.db_type}
                </span>
                <span className="w-[200px] text-xs" style={{ color: "#515157" }}>
                  {c.host}:{c.port}
                </span>
                <span
                  className="w-[100px] text-xs font-medium"
                  style={{ color: c.status === "active" ? "#449235" : "#9E9E9E" }}
                >
                  {c.status === "active" ? "Active" : c.status}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
