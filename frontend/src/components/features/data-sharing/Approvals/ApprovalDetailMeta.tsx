"use client";

import { Check, Database, FileCode, FileSpreadsheet, FileText, Info, Paperclip, ShieldAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { formatBytes } from "@/lib/utils/formatters";
import type { ShareRequest } from "@/lib/types/data-sharing/request.types";
import type { RequestFile, FileStatus } from "@/lib/types/data-sharing/file.types";
import { FileDownloadButton } from "../FileDownloadButton";

// ─── Shared card header ───────────────────────────────────────────────────────

function CardHeader({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex h-10 items-center gap-2 px-4 rounded-t-lg"
      style={{ backgroundColor: "#F8FAFC", borderBottom: "1px solid #E5E7EB" }}>
      <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: "#6B7280" }} />
      <span className="text-[13px] font-semibold" style={{ color: "#374151" }}>{title}</span>
    </div>
  );
}

// ─── Metadata card ────────────────────────────────────────────────────────────

function MetaField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <span className="w-[110px] shrink-0 text-[11px] leading-5" style={{ color: "#9CA3AF" }}>{label}</span>
      <span className="flex-1 text-[13px]" style={{ color: "#374151" }}>{children || "—"}</span>
    </div>
  );
}

export function MetaCard({ r }: { r: ShareRequest }) {
  const pdRow = r.personal_data_involved ? (
    <span className="flex items-center gap-1">
      <ShieldAlert className="h-3 w-3 shrink-0" style={{ color: "#DC2626" }} />
      <span style={{ color: "#DC2626" }}>
        Yes{r.data_subject_categories?.length ? ` — includes ${r.data_subject_categories.join(", ")}` : ""}
      </span>
    </span>
  ) : "No";

  return (
    <section className="flex flex-col overflow-hidden rounded-lg" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}>
      <CardHeader icon={Info} title="Request Metadata" />
      <div className="flex flex-col gap-2 p-4">
        <MetaField label="Legal Basis">{r.legal_basis || "—"}</MetaField>
        <MetaField label="Personal Data">{pdRow}</MetaField>
        <MetaField label="Classification">
          <span style={{ textTransform: "capitalize" }}>{r.data_classification}</span>
        </MetaField>
        <MetaField label="Approved Format">
          {r.data_type === "file" ? "File upload" : "CSV or standard tabular"}
        </MetaField>
        <div className="flex flex-col gap-1">
          <span className="text-[11px]" style={{ color: "#9CA3AF" }}>Purpose</span>
          <span className="text-[13px]" style={{ color: "#374151" }}>{r.purpose || "—"}</span>
        </div>
      </div>
    </section>
  );
}

// ─── Files card (Mode A) ──────────────────────────────────────────────────────

function fileIconAndColor(filename: string): { Icon: LucideIcon; color: string } {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "csv") return { Icon: FileText, color: "#3B82F6" };
  if (ext === "xlsx" || ext === "xls") return { Icon: FileSpreadsheet, color: "#16A34A" };
  if (ext === "json") return { Icon: FileCode, color: "#9333EA" };
  return { Icon: FileText, color: "#9CA3AF" };
}

// Scan-status chip per Pencil frame 05. For Data Owner review, files should
// be in `clean` status (scan passed) — render a green "Scanned clean" chip.
// Other statuses get a contextual color so issues surface in this view too.
function ScanChip({ status }: { status: FileStatus }) {
  const map: Record<FileStatus, { label: string; bg: string; fg: string; border: string }> = {
    clean: { label: "Scanned clean", bg: "#ECFDF5", fg: "#047857", border: "#A7F3D0" },
    scanning: { label: "Scanning…", bg: "#EFF6FF", fg: "#1D4ED8", border: "#BFDBFE" },
    pending_upload: { label: "Awaiting upload", bg: "#F3F4F6", fg: "#6B7280", border: "#E5E7EB" },
    uploaded: { label: "Uploaded — queued", bg: "#F3F4F6", fg: "#6B7280", border: "#E5E7EB" },
    infected: { label: "Infected", bg: "#FEF2F2", fg: "#991B1B", border: "#FECACA" },
    failed: { label: "Scan failed", bg: "#FEF2F2", fg: "#991B1B", border: "#FECACA" },
    deleted: { label: "Deleted", bg: "#F3F4F6", fg: "#6B7280", border: "#E5E7EB" },
  };
  const s = map[status];
  return (
    <span
      className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
      style={{ backgroundColor: s.bg, color: s.fg, border: `1px solid ${s.border}` }}
    >
      {status === "clean" && <Check className="h-2.5 w-2.5" />}
      {s.label}
    </span>
  );
}

export function FilesCard({ files }: { files: RequestFile[] }) {
  return (
    <section className="flex flex-col overflow-hidden rounded-lg" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}>
      <CardHeader icon={Paperclip} title={`Attached Files · ${files.length} file${files.length !== 1 ? "s" : ""}`} />
      <div className="flex flex-col p-4">
        {files.length === 0 && (
          <p className="text-[13px]" style={{ color: "#9CA3AF" }}>No files attached yet.</p>
        )}
        {files.map((f, i) => {
          const { Icon, color } = fileIconAndColor(f.original_filename);
          return (
            <div
              key={f.id}
              className="flex items-center gap-3 py-2"
              style={{ borderBottom: i < files.length - 1 ? "1px solid #F5F5F5" : undefined }}
            >
              <Icon className="h-5 w-5 shrink-0" style={{ color }} />
              <div className="flex flex-1 flex-col gap-0.5">
                <span className="text-[12px] font-semibold" style={{ color: "#111827" }}>{f.original_filename}</span>
                <span className="text-[11px]" style={{ color: "#6B7280" }}>
                  {f.mime_type} · {formatBytes(f.file_size_bytes)}
                </span>
              </div>
              <ScanChip status={f.status} />
              <FileDownloadButton fileId={f.id} status={f.status} variant="icon" />
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ─── Query preview card (Mode B — SQL) ───────────────────────────────────────

// Lightweight SQL keyword highlighter. We don't pull in a heavy syntax engine
// for one card — just colour the common keywords + string literals to match
// the Pencil dark code-block aesthetic.
const SQL_KEYWORDS = [
  "SELECT", "FROM", "WHERE", "AND", "OR", "ORDER", "BY", "GROUP", "HAVING",
  "LIMIT", "OFFSET", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "ON", "AS",
  "BETWEEN", "IN", "IS", "NULL", "NOT", "DISTINCT", "DESC", "ASC", "UNION",
  "INSERT", "UPDATE", "DELETE", "CASE", "WHEN", "THEN", "ELSE", "END",
];

function HighlightedSql({ sql }: { sql: string }) {
  // Tokenise on whitespace boundaries, but keep punctuation attached.
  const tokens = sql.split(/(\s+|,|\(|\))/g);
  return (
    <pre
      className="overflow-x-auto rounded-md p-3.5 text-[12px] leading-relaxed"
      style={{
        backgroundColor: "#0F172A",
        border: "1px solid #1E293B",
        color: "#E2E8F0",
        fontFamily:
          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      }}
    >
      {tokens.map((t, i) => {
        if (/^\s+$/.test(t)) return t;
        const upper = t.toUpperCase();
        if (SQL_KEYWORDS.includes(upper))
          return <span key={i} style={{ color: "#60A5FA", fontWeight: 600 }}>{t}</span>;
        if (/^'[^']*'$/.test(t))
          return <span key={i} style={{ color: "#86EFAC" }}>{t}</span>;
        if (/^\d+$/.test(t))
          return <span key={i} style={{ color: "#FCD34D" }}>{t}</span>;
        return <span key={i}>{t}</span>;
      })}
    </pre>
  );
}

export function QueryCard({ r }: { r: ShareRequest }) {
  if (!r.custom_sql) return null;
  // Pencil frame 06 shows a connection chip with engine + db name + legal
  // basis + approved row count. The backend wires the connection by id only,
  // so we surface what we have and leave the row-count hint optional.
  return (
    <section className="flex flex-col overflow-hidden rounded-lg" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}>
      <CardHeader icon={Database} title="Query Preview · PostgreSQL" />
      <div className="flex flex-col gap-3 p-4">
        {r.connection_id && (
          <div
            className="flex items-center gap-1.5 rounded-md px-3 py-2"
            style={{ backgroundColor: "#EFF6FF", border: "1px solid #BFDBFE" }}
          >
            <Database className="h-3 w-3 shrink-0" style={{ color: "#2563EB" }} />
            <span className="text-[12px]" style={{ color: "#1D4ED8" }}>
              PostgreSQL · {r.connection_id}
              {r.legal_basis ? ` · ${r.legal_basis}` : ""}
              {r.estimated_data_subjects
                ? ` · ~${r.estimated_data_subjects.toLocaleString()} rows approved`
                : ""}
            </span>
          </div>
        )}
        <HighlightedSql sql={r.custom_sql} />
        {/* Live row preview is rendered by /api once the backend exposes a
            preview endpoint; for now we surface a neutral hint so reviewers
            know what the next render will show. */}
        <div
          className="flex items-center justify-between rounded-md px-3 py-2 text-[11px]"
          style={{ backgroundColor: "#F8FAFC", border: "1px dashed #CBD5E1", color: "#64748B" }}
        >
          <span>100-row preview will render here once the data preview API is wired.</span>
        </div>
      </div>
    </section>
  );
}

// ─── Selected tables card (Mode B — tables) ───────────────────────────────────

export function TablesCard({ r }: { r: ShareRequest }) {
  const items = r.selected_items ?? [];
  if (!items.length) return null;
  return (
    <section className="flex flex-col overflow-hidden rounded-lg" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}>
      <CardHeader icon={Database} title="Selected Tables" />
      <div className="flex flex-col">
        {items.map((it, i) => (
          <div key={i} className="flex h-9 items-center px-4 text-[13px]"
            style={{ borderBottom: i < items.length - 1 ? "1px solid #F5F5F5" : undefined, color: "#374151" }}>
            {[it.schema, it.table].filter(Boolean).join(".")}
            {it.columns?.length ? ` (${it.columns.join(", ")})` : ""}
          </div>
        ))}
      </div>
    </section>
  );
}
