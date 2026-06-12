"use client";

/**
 * H — Import / Export.
 *
 * H1: two cards — Import from Excel (drag-drop, download template, ≤5,000 rows;
 *     imported terms become drafts) and Export glossary (scope + approved count
 *     + Export Excel).
 * H2: import results — Imported / Warnings / Errors stat cards, a per-row
 *     validation table, and Roll Back Import / Keep Imported Drafts actions.
 */
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Download, FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";

import {
  downloadImportTemplate,
  exportGlossary,
} from "@/lib/api/products/ndmo-compliance/glossary.api";
import {
  useExportCount,
  useImportGlossary,
  useRollbackImport,
} from "@/lib/hooks/ndmo-compliance/useImportExport";
import type { ImportSummary } from "@/lib/types/ndmo-compliance/glossary";
import { Banner, Button, Card, PageHeader, Select, T } from "../shared/ui";

export function ImportExportPage() {
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  if (summary) return <ImportResults summary={summary} onClear={() => setSummary(null)} />;
  return <ImportExportHome onImported={setSummary} />;
}

// ---- H1 -----------------------------------------------------------------

function ImportExportHome({ onImported }: { onImported: (s: ImportSummary) => void }) {
  const [scope, setScope] = useState<"all" | "my">("all");
  const countQ = useExportCount(scope);
  const importM = useImportGlossary();
  const fileRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  async function handleFile(file: File) {
    setErr(null);
    if (!/\.xlsx?$/i.test(file.name)) { setErr("Please upload an .xlsx file."); return; }
    try {
      onImported(await importM.mutateAsync(file));
    } catch (e: unknown) {
      setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Import failed.");
    }
  }

  async function doExport() {
    setExporting(true);
    try { await exportGlossary(scope); } finally { setExporting(false); }
  }

  return (
    <div>
      <PageHeader title="Import / Export" subtitle="Bulk-import terms from Excel or export the approved glossary." />
      {err && <Banner tone="danger">{err}</Banner>}

      <div className="grid grid-cols-2 gap-5">
        {/* Import */}
        <Card className="p-5">
          <h3 className="text-[15px] font-bold" style={{ color: T.primary }}>Import from Excel</h3>
          <p className="mt-1 text-[13px]" style={{ color: T.muted }}>
            Imported terms land as <strong>drafts</strong> in the approval workflow. Up to 5,000 rows.
          </p>

          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) handleFile(f); }}
            onClick={() => fileRef.current?.click()}
            className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-[12px] border-2 border-dashed py-10 text-center transition-colors"
            style={{ borderColor: drag ? T.brand : T.border, backgroundColor: drag ? T.brandTint : T.bg }}
          >
            {importM.isPending ? (
              <Loader2 className="h-7 w-7 animate-spin" style={{ color: T.brand }} />
            ) : (
              <UploadCloud className="h-7 w-7" style={{ color: T.muted }} />
            )}
            <p className="mt-2 text-[13.5px] font-medium" style={{ color: T.primary }}>
              {importM.isPending ? "Importing…" : "Drag an .xlsx here, or click to browse"}
            </p>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }} />
          </div>

          <button onClick={() => downloadImportTemplate()} className="mt-3 inline-flex items-center gap-1.5 text-[13px] font-semibold" style={{ color: T.brand }}>
            <Download className="h-4 w-4" /> Download template
          </button>
        </Card>

        {/* Export */}
        <Card className="p-5">
          <h3 className="text-[15px] font-bold" style={{ color: T.primary }}>Export glossary</h3>
          <p className="mt-1 text-[13px]" style={{ color: T.muted }}>
            Export approved terms (name EN/AR, definition EN/AR, domain, owner, status, version, approved date).
          </p>

          <div className="mt-4">
            <p className="mb-1.5 text-[13px] font-medium" style={{ color: T.primary }}>Scope</p>
            <Select value={scope} onChange={(e) => setScope(e.target.value as "all" | "my")} style={{ width: 220 }}>
              <option value="all">All domains</option>
              <option value="my">My domains</option>
            </Select>
          </div>

          <div className="mt-4 rounded-[10px] px-4 py-3" style={{ backgroundColor: T.successBg }}>
            <span className="text-[20px] font-bold" style={{ color: T.success }}>{countQ.data?.count ?? "—"}</span>
            <span className="ml-2 text-[13px]" style={{ color: T.success }}>approved terms in scope</span>
          </div>

          <Button variant="brand" className="mt-4" onClick={doExport} disabled={exporting || (countQ.data?.count ?? 0) === 0}>
            {exporting ? <><Loader2 className="h-4 w-4 animate-spin" /> Exporting…</> : <><FileSpreadsheet className="h-4 w-4" /> Export Excel</>}
          </Button>
        </Card>
      </div>
    </div>
  );
}

// ---- H2 -----------------------------------------------------------------

function ImportResults({ summary, onClear }: { summary: ImportSummary; onClear: () => void }) {
  const router = useRouter();
  const rollbackM = useRollbackImport();
  const [rolledBack, setRolledBack] = useState(false);

  async function rollback() {
    await rollbackM.mutateAsync(summary.batch_id);
    setRolledBack(true);
  }

  return (
    <div>
      <PageHeader
        title="Import Results"
        breadcrumb={summary.file_name}
        actions={
          rolledBack ? (
            <Button variant="brand" onClick={onClear}>Done</Button>
          ) : (
            <>
              <Button variant="danger-outline" onClick={rollback} disabled={rollbackM.isPending || summary.imported + summary.warnings === 0}>
                {rollbackM.isPending ? "Rolling back…" : "Roll Back Import"}
              </Button>
              <Button variant="brand" onClick={() => router.push("/ndmo-compliance/glossary")}>Keep Imported Drafts</Button>
            </>
          )
        }
      />

      {rolledBack && <Banner tone="info">The import was rolled back — all imported drafts from this batch were deleted.</Banner>}

      <div className="mb-5 grid grid-cols-3 gap-4">
        <Stat label="Imported" value={summary.imported} color={T.success} bg={T.successBg} />
        <Stat label="Warnings" value={summary.warnings} color={T.warn} bg={T.warnBg} />
        <Stat label="Errors" value={summary.errors} color={T.danger} bg={T.dangerBg} />
      </div>

      {summary.errors > 0 && (
        <Banner tone="warn">{summary.errors} row(s) were not imported. Fix them in the file and re-import.</Banner>
      )}

      <Card className="overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr style={{ borderBottom: `1px solid ${T.border}` }}>
              <Th>Row</Th><Th>Term</Th><Th>Status</Th><Th>Message</Th>
            </tr>
          </thead>
          <tbody>
            {summary.rows.map((r) => (
              <tr key={r.row} style={{ borderBottom: `1px solid ${T.border}` }}>
                <Td><span style={{ fontFamily: "ui-monospace, monospace", color: T.muted }}>{r.row}</span></Td>
                <Td><span className="font-medium" style={{ color: T.primary }}>{r.term}</span></Td>
                <Td><RowStatus status={r.status} /></Td>
                <Td><span style={{ color: T.muted }}>{r.message}</span></Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Stat({ label, value, color, bg }: { label: string; value: number; color: string; bg: string }) {
  return (
    <div className="rounded-[12px] p-4" style={{ backgroundColor: bg }}>
      <div className="text-[28px] font-bold" style={{ color }}>{value}</div>
      <div className="text-[13px] font-semibold" style={{ color }}>{label}</div>
    </div>
  );
}

function RowStatus({ status }: { status: "imported" | "warning" | "error" }) {
  const map = {
    imported: { fg: T.success, bg: T.successBg, label: "Imported", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
    warning: { fg: T.warn, bg: T.warnBg, label: "Warning", icon: null },
    error: { fg: T.danger, bg: T.dangerBg, label: "Error", icon: null },
  }[status];
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[12px] font-semibold" style={{ color: map.fg, backgroundColor: map.bg }}>
      {map.icon}{map.label}
    </span>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-2.5 text-[10.5px] font-bold uppercase tracking-wide" style={{ color: T.muted }}>{children}</th>;
}
function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 align-middle text-[13.5px]">{children}</td>;
}
