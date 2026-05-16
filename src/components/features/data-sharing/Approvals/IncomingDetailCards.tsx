"use client";

import { Database, PackageCheck, Paperclip } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { ShareRequest } from "@/lib/types/data-sharing/request.types";
import type { RequestFile } from "@/lib/types/data-sharing/file.types";

// Light card chrome — visually consistent with the Outgoing detail cards
// in ApprovalDetailMeta.tsx.

function CardHeader({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div
      className="flex h-10 items-center gap-2 px-4 rounded-t-lg"
      style={{ backgroundColor: "#F8FAFC", borderBottom: "1px solid #E5E7EB" }}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: "#6B7280" }} />
      <span className="text-[13px] font-semibold" style={{ color: "#374151" }}>
        {title}
      </span>
    </div>
  );
}

function SummaryField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2">
      <span
        className="w-[140px] shrink-0 text-[11px] leading-5"
        style={{ color: "#9CA3AF" }}
      >
        {label}
      </span>
      <span className="flex-1 text-[13px]" style={{ color: "#374151" }}>
        {children || "—"}
      </span>
    </div>
  );
}

// ─── Summary card ────────────────────────────────────────────────────────────

export function IncomingSummaryCard({
  r,
  senderGroup,
  fileCount,
}: {
  r: ShareRequest;
  senderGroup: string;
  fileCount: number;
}) {
  return (
    <section
      className="flex flex-col overflow-hidden rounded-lg"
      style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}
    >
      <CardHeader icon={PackageCheck} title="Request Summary" />
      <div className="flex flex-col gap-2 p-4">
        <SummaryField label="What is being shared">
          {r.purpose || "—"}
        </SummaryField>
        <SummaryField label="Sender Department">{senderGroup}</SummaryField>
        <SummaryField label="Classification">
          <span style={{ textTransform: "capitalize" }}>
            {r.data_classification}
          </span>
        </SummaryField>
        <SummaryField label="Format">
          {r.data_type === "file"
            ? `${fileCount} file${fileCount === 1 ? "" : "s"}`
            : "Structured / tabular dataset"}
        </SummaryField>
        {r.data_type === "structured" && r.estimated_data_subjects !== null && (
          <SummaryField label="Estimated rows">
            ~{r.estimated_data_subjects.toLocaleString()}
          </SummaryField>
        )}
      </div>
    </section>
  );
}

// ─── Files preview (read-only — no scan-status chips here) ──────────────────

export function IncomingFilesCard({ files }: { files: RequestFile[] }) {
  return (
    <section
      className="flex flex-col overflow-hidden rounded-lg"
      style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}
    >
      <CardHeader
        icon={Paperclip}
        title={`Files Received · ${files.length} file${files.length === 1 ? "" : "s"}`}
      />
      <div className="flex flex-col p-4">
        {files.length === 0 && (
          <p className="text-[13px]" style={{ color: "#9CA3AF" }}>
            No files attached.
          </p>
        )}
        {files.map((f, i) => (
          <div
            key={f.id}
            className="flex items-center gap-3 py-2"
            style={{
              borderBottom: i < files.length - 1 ? "1px solid #F5F5F5" : undefined,
            }}
          >
            <Paperclip className="h-4 w-4 shrink-0" style={{ color: "#9CA3AF" }} />
            <span
              className="flex-1 text-[13px] font-medium"
              style={{ color: "#111827" }}
            >
              {f.original_filename}
            </span>
            <span className="text-[11px]" style={{ color: "#6B7280" }}>
              {f.mime_type}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

// ─── Schema preview (Mode B receive — column names only, no SQL) ────────────

export function IncomingSchemaCard({ r }: { r: ShareRequest }) {
  const items = r.selected_items ?? [];
  return (
    <section
      className="flex flex-col overflow-hidden rounded-lg"
      style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB" }}
    >
      <CardHeader icon={Database} title="Schema Preview" />
      <div className="flex flex-col p-4 gap-2">
        {items.length === 0 ? (
          <p className="text-[13px]" style={{ color: "#9CA3AF" }}>
            Schema not yet provided.
          </p>
        ) : (
          items.map((it, i) => (
            <div
              key={`${it.schema ?? ""}.${it.table}-${i}`}
              className="flex flex-col gap-1 rounded-md p-3"
              style={{ backgroundColor: "#F8FAFC" }}
            >
              <span
                className="text-[12px] font-semibold"
                style={{ color: "#111827" }}
              >
                {[it.schema, it.table].filter(Boolean).join(".")}
              </span>
              {it.columns?.length ? (
                <span className="text-[11px]" style={{ color: "#6B7280" }}>
                  Columns: {it.columns.join(", ")}
                </span>
              ) : null}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
