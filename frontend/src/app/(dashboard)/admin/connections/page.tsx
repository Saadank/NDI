"use client";

import { Database, Eye, EyeOff, Pencil, Play, Plus, Trash2, User, X } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { del, post, put } from "@/lib/api/client";
import { getConnections } from "@/lib/api/products/data-sharing/connections.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatRelativeTime } from "@/lib/utils/formatters";
import type { Connection } from "@/lib/types/data-sharing/connection.types";

const DB_TYPE_LABELS: Record<string, string> = {
  postgresql: "PostgreSQL",
  mysql: "MySQL",
  snowflake: "Snowflake",
  bigquery: "BigQuery",
  mssql: "SQL Server",
  oracle: "Oracle",
};

type HealthStatus = "healthy" | "warning" | "failed" | "unknown";

function getHealth(c: Connection): HealthStatus {
  const ext = (c as unknown as { health_status?: string }).health_status;
  if (ext === "healthy" || ext === "warning" || ext === "failed") return ext;
  return c.status === "active" ? "healthy" : "unknown";
}

function HealthDot({ status }: { status: HealthStatus }) {
  const map: Record<HealthStatus, { color: string; label: string; bg: string }> = {
    healthy: { color: "#449235", label: "Healthy", bg: "#F0FAF0" },
    warning: { color: "#B45309", label: "Warning", bg: "#FFFBEB" },
    failed: { color: "#D32F2F", label: "Failed", bg: "#FEF2F2" },
    unknown: { color: "#9E9E9E", label: "Unknown", bg: "#F5F5F5" },
  };
  const { color, label, bg } = map[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
      style={{ backgroundColor: bg, color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

export default function AdminConnectionsPage() {
  const { isReady } = useRoleGuard({ allow: ["org_admin", "platform_admin"] });
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const qc = useQueryClient();

  const connectionsQuery = useQuery({
    queryKey: ["admin", "connections"],
    queryFn: getConnections,
    enabled: isReady,
  });

  const testMutation = useMutation({
    mutationFn: (id: string) =>
      post(`/api/v1/products/data-sharing/connections/${id}/test`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "connections"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      del(`/api/v1/products/data-sharing/connections/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "connections"] }),
  });

  if (!isReady) return null;

  const connections = connectionsQuery.data ?? [];

  if (editId) {
    const conn = connections.find((c) => c.id === editId);
    return <EditConnectionView connection={conn ?? null} onClose={() => setEditId(null)} />;
  }

  if (showAdd) {
    return <AddConnectionPage onClose={() => setShowAdd(false)} onSaved={() => { qc.invalidateQueries({ queryKey: ["admin", "connections"] }); setShowAdd(false); }} />;
  }

  return (
    <>
      <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
        <div
          className="flex h-16 shrink-0 items-center justify-between px-8"
          style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
        >
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-auth-text">Database Connections</h1>
            {connections.length > 0 && (
              <span
                className="rounded px-2 py-0.5 text-xs font-medium"
                style={{ backgroundColor: "#F5F5F5", color: "#515157" }}
              >
                {connections.length} connections
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            <Plus className="h-3.5 w-3.5" />
            Add connection
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
          <div
            className="flex flex-col overflow-hidden rounded-lg"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            {/* Column headers */}
            <div
              className="flex h-10 shrink-0 items-center px-5"
              style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
            >
              <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                CONNECTION NAME
              </span>
              <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                TYPE
              </span>
              <span className="w-[200px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                HOST · PORT
              </span>
              <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                DATABASE
              </span>
              <span className="w-[110px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                HEALTH
              </span>
              <span className="w-[130px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
                LAST TESTED
              </span>
              <span className="w-[88px]" />
            </div>

            {connectionsQuery.isLoading ? (
              <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
            ) : connectionsQuery.isError ? (
              <div className="py-20 text-center text-sm text-red-600">Failed to load connections.</div>
            ) : connections.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-20">
                <Database className="h-10 w-10" style={{ color: "#EEEEEE" }} />
                <p className="text-sm font-medium text-auth-text">No database connections</p>
                <p className="text-xs" style={{ color: "#9E9E9E" }}>
                  Add a connection to allow requesters to select structured data.
                </p>
              </div>
            ) : (
              <>
                {connections.map((c, i) => {
                  const health = getHealth(c);
                  const lastTested = (c as unknown as { last_tested_at?: string | null }).last_tested_at;
                  return (
                    <div
                      key={c.id}
                      className="flex h-[64px] items-center px-5"
                      style={{ borderBottom: i < connections.length - 1 ? "1px solid #F5F5F5" : undefined }}
                    >
                      <div className="flex flex-1 flex-col gap-0.5">
                        <span className="text-[13px] font-semibold text-auth-text">{c.database ?? c.host}</span>
                        {c.description && (
                          <span className="text-[11px]" style={{ color: "#9E9E9E" }}>{c.description}</span>
                        )}
                      </div>
                      <span
                        className="w-[120px] text-[12px] font-medium"
                        style={{ color: "#515157" }}
                      >
                        {DB_TYPE_LABELS[c.db_type] ?? c.db_type}
                      </span>
                      <span className="w-[200px] text-xs" style={{ color: "#9E9E9E" }}>
                        {c.host}:{c.port}
                      </span>
                      <span className="w-[120px] text-xs truncate" style={{ color: "#515157" }}>
                        {c.database ?? "—"}
                      </span>
                      <span className="w-[110px]">
                        <HealthDot status={health} />
                      </span>
                      <span className="w-[130px] text-xs" style={{ color: "#9E9E9E" }}>
                        {lastTested ? formatRelativeTime(lastTested) : "Never"}
                      </span>
                      <div className="flex w-[88px] items-center gap-1">
                        <button
                          type="button"
                          onClick={() => testMutation.mutate(c.id)}
                          disabled={testMutation.isPending}
                          title="Test connection"
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#F5F5F5]"
                          style={{ color: "#9E9E9E" }}
                        >
                          <Play className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          title="Edit"
                          onClick={() => setEditId(c.id)}
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#F5F5F5]"
                          style={{ color: "#9E9E9E" }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteMutation.mutate(c.id)}
                          title="Delete"
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#FFF0F0]"
                          style={{ color: "#B91C1C" }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
                <div
                  className="flex h-10 items-center justify-between px-5"
                  style={{ borderTop: "1px solid #F5F5F5" }}
                >
                  <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                    Showing {connections.length} of {connections.length} connections
                  </span>
                  <span className="text-[11px]" style={{ color: "#9E9E9E" }}>← Page 1 of 1 →</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

    </>
  );
}

// ─── Edit Connection full-page view ──────────────────────────────

function EditConnectionView({
  connection,
  onClose,
}: {
  connection: Connection | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(connection?.description ?? "");
  const [host, setHost] = useState(connection?.host ?? "");
  const [port, setPort] = useState(String(connection?.port ?? ""));
  const [database, setDatabase] = useState(connection?.database ?? "");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"ok" | "fail" | null>(null);
  const [showPass, setShowPass] = useState(false);

  const [saveError, setSaveError] = useState<string | null>(null);
  const saveMutation = useMutation({
    mutationFn: () =>
      put(`/api/v1/products/data-sharing/connections/${connection?.id}`, {
        description: name.trim() || undefined,
        host: host.trim(),
        port: Number(port),
        database: database.trim() || undefined,
        username: username.trim() || undefined,
        password: password.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "connections"] });
      setSaveError(null);
      onClose();
    },
    onError: (e) =>
      setSaveError(
        e instanceof Error ? e.message : "Failed to save connection",
      ),
  });

  const handleTest = async () => {
    if (!connection) return;
    setTesting(true);
    try {
      await post(`/api/v1/products/data-sharing/connections/${connection.id}/test`, {});
      setTestResult("ok");
    } catch {
      setTestResult("fail");
    } finally {
      setTesting(false);
    }
  };

  const lastTested = (connection as unknown as { last_tested_at?: string | null } | null)?.last_tested_at;
  const health = connection ? getHealth(connection) : "unknown";
  const activeRequests = (connection as unknown as { active_request_count?: number } | null)?.active_request_count ?? 0;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-bold text-auth-text">Edit Connection</h1>
          <span className="text-lg font-bold" style={{ color: "#9E9E9E" }}>·</span>
          <span className="text-lg font-bold" style={{ color: "#9E9E9E" }}>{connection?.description ?? connection?.database ?? "—"}</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="flex items-center gap-1.5 text-[13px] font-medium"
          style={{ color: "#616161" }}
        >
          <X className="h-4 w-4" />
          Cancel
        </button>
      </div>

      <div className="flex flex-1 gap-6 overflow-auto px-8 py-6">
        {/* Left: form card */}
        <div
          className="flex flex-1 flex-col gap-5 rounded-lg p-6"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div>
            <p className="text-[14px] font-semibold text-auth-text">Connection Settings</p>
            <p className="text-[12px]" style={{ color: "#9E9E9E" }}>
              Editing {connection?.description ?? connection?.database}
            </p>
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-auth-text">
                Display name <span style={{ color: "#D76736" }}>*</span>
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
              />
            </div>

            <div className="flex gap-4">
              <div className="flex flex-1 flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">
                  Host <span style={{ color: "#D76736" }}>*</span>
                </label>
                <input
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  className="h-9 rounded-md border px-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>
              <div className="flex w-28 flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">
                  Port <span style={{ color: "#D76736" }}>*</span>
                </label>
                <input
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                  className="h-9 rounded-md border px-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-auth-text">
                Database name <span style={{ color: "#D76736" }}>*</span>
              </label>
              <input
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
              />
            </div>

            {/* Re-enter credentials warning */}
            <div
              className="flex items-center justify-between rounded-md px-4 py-2.5"
              style={{ backgroundColor: "#FFF5F0", border: "1px solid #FDDCCC" }}
            >
              <span className="text-[12px] font-medium" style={{ color: "#D76736" }}>
                Re-enter credentials to update
              </span>
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                Credentials are write-only and cannot be retrieved
              </span>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-auth-text">
                Read-only username <span style={{ color: "#D76736" }}>*</span>
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: "#9E9E9E" }} />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={connection ? "Re-enter username" : ""}
                  className="h-9 w-full rounded-md border pl-8 pr-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-auth-text">
                New password <span style={{ color: "#D76736" }}>*</span>
              </label>
              <div className="relative">
                <input
                  type={showPass ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter new password..."
                  className="h-9 w-full rounded-md border pl-3 pr-9 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
                <button
                  type="button"
                  onClick={() => setShowPass((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: "#9E9E9E" }}
                >
                  {showPass ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
              <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
                Leave blank to keep existing password — or enter a new one to replace it
              </p>
            </div>
          </div>

          {testResult === "ok" && (
            <p className="text-[13px]" style={{ color: "#449235" }}>Connection test passed.</p>
          )}
          {testResult === "fail" && (
            <p className="text-[13px]" style={{ color: "#D32F2F" }}>Connection test failed.</p>
          )}

          {saveError && (
            <p className="text-[13px]" style={{ color: "#D32F2F" }}>{saveError}</p>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleTest}
              disabled={testing}
              className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium disabled:opacity-50"
              style={{ borderColor: "#EEEEEE", color: "#515157" }}
            >
              <Play className="h-3.5 w-3.5" />
              {testing ? "Testing…" : "Test connection"}
            </button>
            <button
              type="button"
              onClick={() => saveMutation.mutate()}
              disabled={!host.trim() || saveMutation.isPending}
              className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: "#1A1A1A" }}
            >
              {saveMutation.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>

        {/* Right panel: connection info */}
        <div
          className="flex w-[260px] shrink-0 flex-col gap-4 rounded-lg p-6"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <p className="text-[12px] font-semibold uppercase tracking-[0.5px]" style={{ color: "#9E9E9E" }}>
            Connection Info
          </p>

          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-0.5">
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>Type</span>
              <span className="text-[13px] font-medium text-auth-text">
                {DB_TYPE_LABELS[connection?.db_type ?? ""] ?? connection?.db_type ?? "—"}
              </span>
            </div>

            <div className="flex flex-col gap-0.5">
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>Last test</span>
              <div className="flex items-center gap-1.5">
                <HealthDot status={health} />
              </div>
              {lastTested && (
                <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                  {formatRelativeTime(lastTested)}
                </span>
              )}
            </div>

            <div className="flex flex-col gap-0.5">
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>Active requests</span>
              <span className="text-[13px] font-medium text-auth-text">{activeRequests}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Add Connection wizard (3-step full page) ─────────────────────

interface TestResult {
  success: boolean;
  latency_ms?: number;
  tables_count?: number;
  error?: string;
}

function AddConnectionPage({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const qc = useQueryClient();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [name, setName] = useState("");
  const [dbType, setDbType] = useState("postgresql");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("5432");
  const [database, setDatabase] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const testMutation = useMutation({
    mutationFn: () =>
      post<TestResult>("/api/v1/products/data-sharing/connections/test", {
        db_type: dbType, host: host.trim(), port: Number(port),
        database: database.trim() || undefined, username: username.trim(), password: password.trim(),
      }),
    onSuccess: (data) => setTestResult(data),
    onError: (e) => setTestResult({ success: false, error: e instanceof Error ? e.message : "Connection failed" }),
  });

  const create = useMutation({
    mutationFn: () =>
      post("/api/v1/products/data-sharing/connections", {
        db_type: dbType, description: name.trim() || undefined,
        host: host.trim(), port: Number(port), database: database.trim() || undefined,
        username: username.trim(), password: password.trim(),
      }),
    onSuccess: () => onSaved(),
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  const STEP_LABELS = ["Type & Name", "Connection Details", "Test & Save"];

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div className="flex h-16 shrink-0 items-center justify-between px-8" style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Add Connection</h1>
          <span className="text-[13px]" style={{ color: "#9E9E9E" }}>Step {step} of 3</span>
        </div>
        <button type="button" onClick={onClose} className="flex items-center gap-1.5 text-[13px]" style={{ color: "#616161" }}>
          <X className="h-4 w-4" />
          Cancel
        </button>
      </div>

      <div className="flex flex-1 flex-col overflow-auto px-8 py-6">
        {/* Step indicator */}
        <div className="mb-6 flex items-center gap-0">
          {STEP_LABELS.map((label, idx) => {
            const s = idx + 1;
            const done = s < step;
            const active = s === step;
            return (
              <div key={s} className="flex items-center">
                <div className="flex items-center gap-2">
                  <div
                    className="flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold"
                    style={{ backgroundColor: done || active ? "#D76736" : "#EEEEEE", color: done || active ? "#FFFFFF" : "#9E9E9E" }}
                  >
                    {done ? "✓" : s}
                  </div>
                  <span className="text-[12px]" style={{ color: active ? "#D76736" : done ? "#449235" : "#9E9E9E" }}>{label}</span>
                </div>
                {idx < 2 && <div className="mx-3 h-px w-12" style={{ backgroundColor: s < step ? "#D76736" : "#EEEEEE" }} />}
              </div>
            );
          })}
        </div>

        <div className="flex flex-col gap-5 rounded-lg p-6" style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE", maxWidth: 560 }}>
          {step === 1 && (
            <>
              <p className="text-[13px] font-semibold text-auth-text">Connection Settings</p>
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">Database type <span style={{ color: "#D76736" }}>*</span></label>
                <select
                  value={dbType}
                  onChange={(e) => { setDbType(e.target.value); setPort(e.target.value === "mysql" ? "3306" : e.target.value === "mssql" ? "1433" : e.target.value === "oracle" ? "1521" : "5432"); }}
                  className="h-9 rounded-md border px-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                >
                  {Object.entries(DB_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">Display name <span style={{ color: "#D76736" }}>*</span></label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. HR Production" className="h-9 rounded-md border px-3 text-[13px] outline-none" style={{ borderColor: "#EEEEEE" }} />
              </div>
              <div className="flex justify-end">
                <button type="button" onClick={() => setStep(2)} disabled={!name.trim()} className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60" style={{ backgroundColor: "#D76736" }}>
                  Next: Connection Details →
                </button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <p className="text-[13px] font-semibold text-auth-text">Connection Details</p>
              <p className="text-[11px]" style={{ color: "#9E9E9E" }}>{DB_TYPE_LABELS[dbType] ?? dbType} · {name}</p>
              <div className="flex gap-4">
                <div className="flex flex-1 flex-col gap-1.5">
                  <label className="text-[12px] font-semibold text-auth-text">Host <span style={{ color: "#D76736" }}>*</span></label>
                  <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="hr-db.internal" className="h-9 rounded-md border px-3 text-[13px] outline-none" style={{ borderColor: "#EEEEEE" }} />
                </div>
                <div className="flex w-24 flex-col gap-1.5">
                  <label className="text-[12px] font-semibold text-auth-text">Port <span style={{ color: "#D76736" }}>*</span></label>
                  <input value={port} onChange={(e) => setPort(e.target.value)} className="h-9 rounded-md border px-3 text-[13px] outline-none" style={{ borderColor: "#EEEEEE" }} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">Database name <span style={{ color: "#D76736" }}>*</span></label>
                <input value={database} onChange={(e) => setDatabase(e.target.value)} className="h-9 rounded-md border px-3 text-[13px] outline-none" style={{ borderColor: "#EEEEEE" }} />
              </div>
              <div className="rounded-md px-4 py-2.5 text-[12px]" style={{ backgroundColor: "#FFFBEB", border: "1px solid #FCD34D", color: "#92400E" }}>
                Read-only credentials required — the platform enforces SELECT-only queries. Ensure these credentials have read-only privileges only.
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">Read-only username <span style={{ color: "#D76736" }}>*</span></label>
                <input value={username} onChange={(e) => setUsername(e.target.value)} className="h-9 rounded-md border px-3 text-[13px] outline-none" style={{ borderColor: "#EEEEEE" }} />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">Read-only password <span style={{ color: "#D76736" }}>*</span></label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="h-9 rounded-md border px-3 text-[13px] outline-none" style={{ borderColor: "#EEEEEE" }} />
              </div>
              <div className="flex items-center justify-between">
                <button type="button" onClick={() => setStep(1)} className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium" style={{ borderColor: "#EEEEEE", color: "#616161" }}>← Back</button>
                <button type="button" onClick={() => setStep(3)} disabled={!host.trim() || !username.trim() || !password.trim()} className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60" style={{ backgroundColor: "#D76736" }}>
                  Next: Test & Save →
                </button>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <p className="text-[13px] font-semibold text-auth-text">Test & Save</p>
              {!testResult ? (
                <button type="button" onClick={() => testMutation.mutate()} disabled={testMutation.isPending} className="flex h-9 items-center gap-1.5 self-start rounded-md border px-5 text-[13px] font-medium disabled:opacity-60" style={{ borderColor: "#EEEEEE", color: "#515157" }}>
                  <Play className="h-3.5 w-3.5" />
                  {testMutation.isPending ? "Testing…" : "Test connection"}
                </button>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="flex items-start gap-3 rounded-lg px-4 py-4" style={{ backgroundColor: testResult.success ? "#F0FAF0" : "#FFF0F0", border: `1px solid ${testResult.success ? "#BBF7D0" : "#FCA5A5"}` }}>
                    <span className="text-[18px]">{testResult.success ? "✓" : "✗"}</span>
                    <div className="flex flex-col gap-1">
                      <p className="text-[13px] font-semibold" style={{ color: testResult.success ? "#14532D" : "#991B1B" }}>
                        {testResult.success ? "Connection successful" : "Connection failed"}
                      </p>
                      {testResult.success && testResult.latency_ms !== undefined && (
                        <p className="text-[12px]" style={{ color: "#166534" }}>Latency: {testResult.latency_ms}ms{testResult.tables_count !== undefined ? ` · ${testResult.tables_count} tables` : ""}</p>
                      )}
                      {!testResult.success && testResult.error && (
                        <p className="text-[12px]" style={{ color: "#991B1B" }}>{testResult.error}</p>
                      )}
                    </div>
                  </div>
                  {!testResult.success && (
                    <button type="button" onClick={() => setTestResult(null)} className="self-start text-[13px]" style={{ color: "#D76736" }}>Try again</button>
                  )}
                </div>
              )}
              {error && <p className="text-xs text-red-600">{error}</p>}
              <div className="flex items-center justify-between">
                <button type="button" onClick={() => { setStep(2); setTestResult(null); }} className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium" style={{ borderColor: "#EEEEEE", color: "#616161" }}>← Back</button>
                <button type="button" onClick={() => create.mutate()} disabled={!testResult?.success || create.isPending} className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60" style={{ backgroundColor: "#D76736" }}>
                  {create.isPending ? "Saving…" : "Save connection"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

