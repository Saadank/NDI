"use client";

import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  CircleCheck,
  Database,
  Play,
  Search,
  UploadCloud,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useConnections } from "@/lib/hooks/data-sharing/useConnections";
import { useSchemas } from "@/lib/hooks/data-sharing/useSchemas";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useNewRequestStore } from "@/lib/store/new-request.store";
import type {
  DataType,
  SelectedTableItem,
} from "@/lib/types/data-sharing/request.types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ─── File upload state ────────────────────────────────────────────────────────

type FileStatus = "uploading" | "failed" | "complete";

export interface LocalFile {
  id: string;
  file: File;
  status: FileStatus;
  progress: number;
}

// ─── Mode Switcher ────────────────────────────────────────────────────────────

function ModeSwitcher({
  mode,
  onChange,
}: {
  mode: DataType;
  onChange: (m: DataType) => void;
}) {
  return (
    <div
      className="flex h-14 overflow-hidden rounded-lg"
      style={{ border: "1px solid #EEEEEE", backgroundColor: "#FFFFFF" }}
    >
      <button
        type="button"
        onClick={() => onChange("file")}
        className="flex flex-1 items-center gap-3 px-5"
        style={mode === "file" ? { backgroundColor: "#FFF5F0" } : {}}
      >
        <UploadCloud
          className="h-[18px] w-[18px] shrink-0"
          style={{ color: mode === "file" ? "#D76736" : "#9E9E9E" }}
        />
        <div className="flex flex-col items-start gap-0.5">
          <p
            className="text-[13px] font-medium"
            style={{ color: mode === "file" ? "#D76736" : "#9E9E9E" }}
          >
            File Upload
          </p>
          <p
            className="text-[11px]"
            style={{ color: mode === "file" ? "#D76736CC" : "#BABABA" }}
          >
            Upload files to share
          </p>
        </div>
      </button>
      <span className="w-px self-stretch" style={{ backgroundColor: "#EEEEEE" }} />
      <button
        type="button"
        onClick={() => onChange("structured")}
        className="flex flex-1 items-center gap-3 px-5"
        style={mode === "structured" ? { backgroundColor: "#FFF5F0" } : {}}
      >
        <Database
          className="h-[18px] w-[18px] shrink-0"
          style={{ color: mode === "structured" ? "#D76736" : "#9E9E9E" }}
        />
        <div className="flex flex-col items-start gap-0.5">
          <p
            className="text-[13px] font-medium"
            style={{ color: mode === "structured" ? "#D76736" : "#9E9E9E" }}
          >
            Structured Data
          </p>
          <p
            className="text-[11px]"
            style={{ color: mode === "structured" ? "#D76736CC" : "#BABABA" }}
          >
            Query a database connection
          </p>
        </div>
      </button>
    </div>
  );
}

// ─── File Mode ────────────────────────────────────────────────────────────────

function FileMode({
  files,
  onFiles,
}: {
  files: LocalFile[];
  onFiles: (updater: (prev: LocalFile[]) => LocalFile[]) => void;
}) {
  const setField = useNewRequestStore((s) => s.set);
  const inputRef = useRef<HTMLInputElement>(null);

  // Simulate upload progress for files in "uploading" state
  useEffect(() => {
    const hasUploading = files.some((f) => f.status === "uploading");
    if (!hasUploading) return;

    const id = setTimeout(() => {
      onFiles((prev) =>
        prev.map((f) => {
          if (f.status !== "uploading") return f;
          const prog = Math.min(100, f.progress + Math.floor(Math.random() * 25 + 15));
          return { ...f, progress: prog, status: prog >= 100 ? "complete" : "uploading" };
        }),
      );
    }, 450);

    return () => clearTimeout(id);
  }, [files, onFiles]);

  // Sync complete files to store for Step 3
  useEffect(() => {
    const complete = files.filter((f) => f.status === "complete");
    setField(
      "staged_files",
      complete.map((f) => ({ name: f.file.name, size: f.file.size, type: f.file.type })),
    );
    if (typeof window !== "undefined") {
      (
        window as unknown as { __datarix_staged_files?: File[] }
      ).__datarix_staged_files = complete.map((f) => f.file);
    }
  }, [files, setField]);

  const handlePicked = (list: FileList | null) => {
    if (!list) return;
    const newFiles: LocalFile[] = Array.from(list).map((file) => ({
      id: `${file.name}-${Date.now()}-${Math.random()}`,
      file,
      status: "uploading",
      progress: 0,
    }));
    onFiles((prev) => [...prev, ...newFiles]);
  };

  const removeFile = (id: string) => {
    onFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const uploadingCount = files.filter((f) => f.status === "uploading").length;
  const failedCount = files.filter((f) => f.status === "failed").length;

  const headerText =
    files.length === 0
      ? null
      : uploadingCount > 0
        ? `UPLOADING ${files.length} ${files.length === 1 ? "FILE" : "FILES"}`
        : failedCount > 0
          ? `${files.length} ${files.length === 1 ? "FILE" : "FILES"} — ${failedCount} FAILED SCAN`
          : `${files.length} ${files.length === 1 ? "FILE" : "FILES"} — ALL READY`;

  return (
    <div className="flex flex-1 flex-col gap-4 p-6">
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => handlePicked(e.target.files)}
      />

      {files.length === 0 ? (
        <div
          className="flex flex-col items-center gap-4 rounded-xl py-12"
          style={{ border: "2px dashed #EEEEEE" }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handlePicked(e.dataTransfer.files);
          }}
        >
          <UploadCloud className="h-10 w-10" style={{ color: "#D76736" }} />
          <p className="text-sm font-medium text-auth-text">Drag and drop files here</p>
          <p className="text-xs" style={{ color: "#BABABA" }}>
            or
          </p>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="flex h-8 items-center gap-2 rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#D76736", color: "#D76736" }}
          >
            Browse files
          </button>
          <p className="text-xs" style={{ color: "#9E9E9E" }}>
            Max 4 GB per file · PDF, CSV, XLSX, JSON, ZIP
          </p>
        </div>
      ) : (
        <>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.8px]"
            style={{ color: "#9E9E9E" }}
          >
            {headerText}
          </p>

          <div className="flex flex-col gap-2">
            {files.map((f) => {
              if (f.status === "failed") {
                return (
                  <div
                    key={f.id}
                    className="flex items-center gap-3 rounded-lg px-4 py-3"
                    style={{ backgroundColor: "#FFF0F0", border: "1px solid #FCA5A5" }}
                  >
                    <div className="flex flex-1 flex-col gap-0.5">
                      <span className="text-[13px] font-medium" style={{ color: "#D32F2F" }}>
                        {f.file.name}
                      </span>
                      <span className="text-xs" style={{ color: "#EF4444" }}>
                        Virus detected — remove this file
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(f.id)}
                      className="h-7 rounded px-3 text-xs font-medium"
                      style={{ backgroundColor: "#EF4444", color: "#FFFFFF" }}
                    >
                      Remove
                    </button>
                  </div>
                );
              }

              if (f.status === "uploading") {
                return (
                  <div
                    key={f.id}
                    className="flex items-start gap-3 rounded-lg px-4 py-3"
                    style={{ border: "1px solid #EEEEEE" }}
                  >
                    <div className="flex flex-1 flex-col gap-1.5">
                      <span className="text-[13px] font-medium text-auth-text">
                        {f.file.name}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                          Uploading {fmtSize(f.file.size)}
                        </span>
                        <div
                          className="flex-1 overflow-hidden rounded-full"
                          style={{ height: 4, backgroundColor: "#EEEEEE" }}
                        >
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${f.progress}%`, backgroundColor: "#D76736" }}
                          />
                        </div>
                        <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                          {f.progress}%
                        </span>
                      </div>
                    </div>
                    <button type="button" onClick={() => removeFile(f.id)} className="mt-1">
                      <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
                    </button>
                  </div>
                );
              }

              // complete
              return (
                <div
                  key={f.id}
                  className="flex items-center gap-3 rounded-lg px-4 py-3"
                  style={{ border: "1px solid #EEEEEE" }}
                >
                  <CircleCheck className="h-5 w-5 shrink-0" style={{ color: "#449235" }} />
                  <div className="flex flex-1 flex-col gap-0.5">
                    <span className="text-[13px] font-medium text-auth-text">
                      {f.file.name}
                    </span>
                    <span className="text-xs" style={{ color: "#9E9E9E" }}>
                      Scan passed · {fmtSize(f.file.size)}
                    </span>
                  </div>
                  <button type="button" onClick={() => removeFile(f.id)}>
                    <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
                  </button>
                </div>
              );
            })}
          </div>

          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="self-start text-[13px] font-medium"
            style={{ color: "#D76736" }}
          >
            + Add more files
          </button>
        </>
      )}
    </div>
  );
}

// ─── Structured Mode ──────────────────────────────────────────────────────────

interface PreviewRow {
  [col: string]: string | number | null;
}

function StructuredMode() {
  const connectionId = useNewRequestStore((s) => s.connection_id);
  const selectionMode = useNewRequestStore((s) => s.selection_mode);
  const customSql = useNewRequestStore((s) => s.custom_sql);
  const selectedItems = useNewRequestStore((s) => s.selected_items);
  const setField = useNewRequestStore((s) => s.set);

  const connectionsQuery = useConnections();
  const schemasQuery = useSchemas(connectionId ?? "");

  const [connSearch, setConnSearch] = useState("");
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [previewRows, setPreviewRows] = useState<PreviewRow[] | null>(null);
  const [previewTotal, setPreviewTotal] = useState<number>(0);
  const [previewWarning, setPreviewWarning] = useState(false);

  const selectedConnection = (connectionsQuery.data ?? []).find(
    (c) => c.id === connectionId,
  );

  const filteredConnections = (connectionsQuery.data ?? []).filter((c) => {
    if (!connSearch) return true;
    const q = connSearch.toLowerCase();
    return (
      (c.description ?? "").toLowerCase().includes(q) ||
      c.host.toLowerCase().includes(q) ||
      c.db_type.toLowerCase().includes(q)
    );
  });

  const allTables = (schemasQuery.data?.schema_data?.schemas ?? []).flatMap(
    (s) => s.tables.map((t) => ({ schema: s.name, table: t, fullName: `${s.name}.${t.name}` })),
  );

  const toggleTableExpand = (fullName: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(fullName)) next.delete(fullName);
      else next.add(fullName);
      return next;
    });
  };

  const toggleColumn = (schema: string, tableName: string, colName: string) => {
    const key = `${schema}.${tableName}`;
    const existing = selectedItems.find(
      (it) => it.schema === schema && it.table === tableName,
    );
    const cols = existing?.columns ?? [];
    const newCols = cols.includes(colName)
      ? cols.filter((c) => c !== colName)
      : [...cols, colName];

    const next: SelectedTableItem[] = newCols.length === 0
      ? selectedItems.filter((it) => !(it.schema === schema && it.table === tableName))
      : [
          ...selectedItems.filter((it) => !(it.schema === schema && it.table === tableName)),
          { schema, table: tableName, columns: newCols },
        ];
    setField("selected_items", next);
    // Treat as "tables" mode when using tree
    if (!selectionMode) setField("selection_mode", "tables");
  };

  const removeSelectedCol = (schema: string, tableName: string, col: string) => {
    toggleColumn(schema, tableName, col);
  };

  const clearAllSelected = () => setField("selected_items", []);

  const totalSelectedCols = selectedItems.reduce(
    (sum, it) => sum + (it.columns?.length ?? 0),
    0,
  );

  const handleRunSql = () => {
    // Simulate SQL preview (real impl would POST to a preview endpoint)
    const mockRows: PreviewRow[] = [
      { employee_id: 1001, full_name: "Ahmed Al-Rashidi" },
      { employee_id: 1002, full_name: "Fatima Al-Zahrawi" },
      { employee_id: 1003, full_name: "Khalid Al-Mutairi" },
    ];
    const mockTotal = 14200;
    setPreviewRows(mockRows);
    setPreviewTotal(mockTotal);
    setPreviewWarning(mockTotal > 1000);
  };

  // ── No connection selected: show picker ──
  if (!connectionId) {
    return (
      <div className="flex flex-1 flex-col gap-4 p-6">
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.8px]"
          style={{ color: "#616161" }}
        >
          Select a Data Source
        </p>

        {/* Search */}
        <div
          className="flex h-9 items-center gap-2 rounded-md px-3"
          style={{ border: "1px solid #EEEEEE" }}
        >
          <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
          <input
            value={connSearch}
            onChange={(e) => setConnSearch(e.target.value)}
            placeholder="Search connections…"
            className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
          />
        </div>

        {connectionsQuery.isLoading && (
          <p className="text-[13px]" style={{ color: "#9E9E9E" }}>
            Loading connections…
          </p>
        )}
        {connectionsQuery.isError && (
          <p className="text-[13px]" style={{ color: "#EF4444" }}>
            Failed to load connections.
          </p>
        )}

        <div className="flex flex-col gap-2">
          {filteredConnections.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                setField("connection_id", c.id);
                setField("selection_mode", "tables");
              }}
              className="flex items-center gap-3 rounded-lg px-4 py-3 text-left"
              style={{ border: "1px solid #EEEEEE" }}
            >
              <Database className="h-4 w-4 shrink-0" style={{ color: "#9E9E9E" }} />
              <div className="flex-1">
                <p className="text-[13px] font-semibold text-auth-text">
                  {c.description || c.host}
                </p>
                <p className="text-xs" style={{ color: "#9E9E9E" }}>
                  {c.db_type} · {c.host}:{c.port}
                </p>
              </div>
            </button>
          ))}
        </div>

        <p className="text-xs" style={{ color: "#9E9E9E" }}>
          Select a connection, then choose schema or write a SQL query
        </p>
      </div>
    );
  }

  // ── SQL mode ──
  if (selectionMode === "query") {
    const firstSelectedTable = selectedItems[0]?.table ?? "";
    const breadcrumb = [selectedConnection?.description ?? selectedConnection?.host ?? "Connection", firstSelectedTable]
      .filter(Boolean)
      .join(" · ");

    return (
      <div className="flex flex-1 flex-col gap-0">
        {/* Dark editor header */}
        <div
          className="flex h-10 shrink-0 items-center justify-between px-4"
          style={{ backgroundColor: "#1E2030", borderRadius: "0" }}
        >
          <span className="text-[13px] font-medium" style={{ color: "#9E9E9E" }}>
            {breadcrumb}
          </span>
          <button
            type="button"
            onClick={handleRunSql}
            disabled={!customSql.trim()}
            className="flex h-6 items-center gap-1.5 rounded px-2.5 text-[12px] font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: "#D76736" }}
          >
            <Play className="h-3 w-3" />
            Run
          </button>
        </div>

        {/* Dark textarea */}
        <textarea
          value={customSql}
          onChange={(e) => setField("custom_sql", e.target.value)}
          placeholder={"SELECT e.employee_id,\n    e.full_name\nFROM employees e\nWHERE e.department_id = 10\nLIMIT 1000"}
          className="flex-1 resize-none p-4 font-mono text-[13px] outline-none"
          style={{
            backgroundColor: "#1E2030",
            color: "#A6E22E",
            minHeight: 160,
          }}
          spellCheck={false}
        />

        {/* Preview */}
        {previewRows && (
          <div className="flex flex-col" style={{ borderTop: "1px solid #EEEEEE" }}>
            {previewWarning && (
              <div
                className="flex items-start gap-2 px-4 py-3"
                style={{ backgroundColor: "#FFFBEB", borderBottom: "1px solid #FDE68A" }}
              >
                <AlertTriangle
                  className="mt-0.5 h-4 w-4 shrink-0"
                  style={{ color: "#D97706" }}
                />
                <p className="text-xs" style={{ color: "#92400E" }}>
                  Query returns {previewTotal.toLocaleString()} rows — only the first 1,000 will
                  be showed. Add a WHERE clause to narrow the result.
                </p>
              </div>
            )}

            {/* Query display */}
            <div
              className="px-4 py-3 font-mono text-xs"
              style={{ backgroundColor: "#F8F8F8", borderBottom: "1px solid #EEEEEE", color: "#9E9E9E" }}
            >
              {customSql || "SELECT ..."}
            </div>

            {/* Preview table */}
            {previewRows.length > 0 && (
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr style={{ borderBottom: "1px solid #EEEEEE", backgroundColor: "#FAFAFA" }}>
                    {Object.keys(previewRows[0]).map((col) => (
                      <th
                        key={col}
                        className="px-4 py-2 text-[11px] font-semibold tracking-[0.6px]"
                        style={{ color: "#9E9E9E" }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, i) => (
                    <tr
                      key={i}
                      style={{ borderBottom: i < previewRows.length - 1 ? "1px solid #F5F5F5" : undefined }}
                    >
                      {Object.values(row).map((val, j) => (
                        <td key={j} className="px-4 py-2.5 text-[13px] text-auth-text">
                          {String(val ?? "—")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <p className="px-4 py-2 text-xs" style={{ color: "#9E9E9E" }}>
              Showing {previewRows.length} of {Math.min(1000, previewTotal).toLocaleString()} preview rows
              ({previewTotal.toLocaleString()} total in query result)
            </p>
          </div>
        )}

        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderTop: "1px solid #EEEEEE" }}
        >
          <button
            type="button"
            onClick={() => setField("selection_mode", "tables")}
            className="text-[13px]"
            style={{ color: "#9E9E9E" }}
          >
            ← Browse schema
          </button>
        </div>
      </div>
    );
  }

  // ── Tables mode: two-panel schema tree ──
  return (
    <div className="flex flex-1">
      {/* Left: schema tree */}
      <div
        className="flex w-[260px] shrink-0 flex-col"
        style={{ borderRight: "1px solid #EEEEEE" }}
      >
        <div
          className="flex h-10 shrink-0 items-center gap-2 px-4"
          style={{ borderBottom: "1px solid #EEEEEE", backgroundColor: "#FAFAFA" }}
        >
          <Database className="h-3.5 w-3.5 shrink-0" style={{ color: "#D76736" }} />
          <span className="truncate text-[12px] font-semibold text-auth-text">
            {selectedConnection?.description ?? selectedConnection?.host ?? "Connection"}
          </span>
        </div>

        <div className="flex flex-col overflow-auto py-2">
          {schemasQuery.isLoading && (
            <p className="px-4 py-3 text-[13px]" style={{ color: "#9E9E9E" }}>
              Loading schema…
            </p>
          )}
          {schemasQuery.isError && (
            <p className="px-4 py-3 text-[13px]" style={{ color: "#EF4444" }}>
              Failed to load schema.
            </p>
          )}

          {allTables.map(({ schema, table, fullName }) => {
            const isExpanded = expandedTables.has(fullName);
            const tableSelected = selectedItems.find(
              (it) => it.schema === schema && it.table === table.name,
            );
            const selectedCols = tableSelected?.columns ?? [];

            return (
              <div key={fullName}>
                <button
                  type="button"
                  onClick={() => toggleTableExpand(fullName)}
                  className="flex w-full items-center gap-2 px-4 py-1.5 text-left hover:bg-[#FAFAFA]"
                >
                  <ChevronRight
                    className="h-3.5 w-3.5 shrink-0 transition-transform"
                    style={{
                      color: "#9E9E9E",
                      transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                    }}
                  />
                  <Database className="h-3.5 w-3.5 shrink-0" style={{ color: selectedCols.length > 0 ? "#D76736" : "#9E9E9E" }} />
                  <span
                    className="text-[13px]"
                    style={{
                      color: selectedCols.length > 0 ? "#D76736" : "#1A1A1A",
                      fontWeight: selectedCols.length > 0 ? 600 : 400,
                    }}
                  >
                    {table.name}
                  </span>
                </button>

                {isExpanded && (
                  <div className="flex flex-col">
                    {table.columns.map((col) => {
                      const isChecked = selectedCols.includes(col.name);
                      return (
                        <button
                          key={col.name}
                          type="button"
                          onClick={() => toggleColumn(schema, table.name, col.name)}
                          className="flex items-center gap-2 py-1 pl-10 pr-4 text-left hover:bg-[#FAFAFA]"
                        >
                          <span
                            className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded"
                            style={{
                              border: `1.5px solid ${isChecked ? "#D76736" : "#CCCCCC"}`,
                              backgroundColor: isChecked ? "#D76736" : "transparent",
                            }}
                          >
                            {isChecked && (
                              <CheckCircle2 className="h-3 w-3 text-white" />
                            )}
                          </span>
                          <span
                            className="text-[12px]"
                            style={{ color: isChecked ? "#D76736" : "#515157" }}
                          >
                            {col.name}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Switch to SQL button */}
        <div
          className="mt-auto px-4 py-3"
          style={{ borderTop: "1px solid #EEEEEE" }}
        >
          <button
            type="button"
            onClick={() => setField("selection_mode", "query")}
            className="text-[12px]"
            style={{ color: "#9E9E9E" }}
          >
            Write custom SQL →
          </button>
        </div>
      </div>

      {/* Right: selected columns */}
      <div className="flex flex-1 flex-col p-5">
        <div className="mb-3 flex items-center justify-between">
          <span
            className="text-[11px] font-semibold uppercase tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            Selected Columns ({totalSelectedCols})
          </span>
          {totalSelectedCols > 0 && (
            <button
              type="button"
              onClick={clearAllSelected}
              className="text-[12px]"
              style={{ color: "#D76736" }}
            >
              Clear all
            </button>
          )}
        </div>

        {totalSelectedCols === 0 ? (
          <p className="text-[13px]" style={{ color: "#BABABA" }}>
            Expand a table and select columns to include
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {selectedItems.flatMap((it) =>
              (it.columns ?? []).map((col) => (
                <span
                  key={`${it.table}.${col}`}
                  className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12px]"
                  style={{ backgroundColor: "#FFF5F0", border: "1px solid #FFCDB8", color: "#D76736" }}
                >
                  {it.table}.{col}
                  <button
                    type="button"
                    onClick={() => removeSelectedCol(it.schema ?? "", it.table, col)}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              )),
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function Step2_DataSelection() {
  const { isReady } = useRoleGuard({ allow: ["requester", "data_owner"] });
  const router = useRouter();
  const dataType = useNewRequestStore((s) => s.data_type);
  const setField = useNewRequestStore((s) => s.set);
  const connectionId = useNewRequestStore((s) => s.connection_id);
  const selectionMode = useNewRequestStore((s) => s.selection_mode);
  const customSql = useNewRequestStore((s) => s.custom_sql);
  const selectedItems = useNewRequestStore((s) => s.selected_items);

  const [localFiles, setLocalFiles] = useState<LocalFile[]>([]);

  if (!isReady) return null;

  const fileCanProceed =
    localFiles.length > 0 && localFiles.every((f) => f.status === "complete");

  const structuredCanProceed =
    !!connectionId &&
    ((selectionMode === "tables" &&
      selectedItems.some((it) => (it.columns?.length ?? 0) > 0)) ||
      (selectionMode === "query" && customSql.trim().length > 0));

  const canProceed = dataType === "file" ? fileCanProceed : structuredCanProceed;

  return (
    <div className="flex flex-col gap-4">
      <ModeSwitcher mode={dataType} onChange={(m) => setField("data_type", m)} />

      <div
        className="flex flex-1 flex-col overflow-hidden rounded-lg"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        {dataType === "file" ? (
          <FileMode files={localFiles} onFiles={setLocalFiles} />
        ) : (
          <StructuredMode />
        )}
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => router.push("/data-sharing/new")}
          className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#EEEEEE", color: "#616161" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Step 1
        </button>
        <button
          type="button"
          disabled={!canProceed}
          onClick={() => canProceed && router.push("/data-sharing/new/step-3")}
          className="flex h-10 items-center gap-2 rounded-lg px-5 text-sm font-semibold"
          style={{
            backgroundColor: canProceed ? "#D76736" : "#D0D0D0",
            color: canProceed ? "#FFFFFF" : "#9E9E9E",
            cursor: canProceed ? "pointer" : "not-allowed",
          }}
        >
          Next
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
