"use client";

/**
 * NDMO Compliance — Gap Report.
 *
 *   1. Executive summary block: NDI%, in-scope specs, gaps count, top 3
 *      domain weaknesses.
 *   2. Gap table: only specs with maturity_level < 5, sorted by
 *      weight × priority desc (priority-1 first, lower maturity first).
 *   3. Two exports:
 *        - "تصدير PDF"   → opens browser print dialog with a print-only
 *          stylesheet that hides the app shell.  Arabic RTL rendering
 *          is provided by the page's own dir="rtl" (from the NDMO layout).
 *        - "تصدير Excel" → dynamic-imports the `xlsx` package and emits
 *          a multi-sheet workbook (summary + gaps + per-domain rollup).
 *          If xlsx isn't installed, gracefully falls back to a CSV
 *          download for the gaps sheet.
 *   4. Cycle comparison: if a previous cycle's data is fetched (Phase 5
 *      will expand the backend; for now we render the slot as "—").
 */
import { useMemo, useState } from "react";
import { Download, FileDown, Printer } from "lucide-react";

import { useAssessments } from "@/lib/hooks/ndmo-compliance/useAssessments";
import {
  type AssessmentListItem,
  MATURITY_AR,
} from "@/lib/types/ndmo-compliance";
import { computeNdiBreakdown } from "../Dashboard/ndi-score";
import {
  BG,
  BG_CARD,
  BORDER,
  BRAND,
  MaturityBadge,
  NEUTRAL_TEXT,
  PriorityBadge,
  SUBTLE_TEXT,
  SUCCESS,
} from "../shared/badges";

const PRIORITY_WEIGHT: Record<1 | 2 | 3, number> = { 1: 3.0, 2: 2.0, 3: 1.0 };

export function GapReportPage() {
  const assessments = useAssessments({ limit: 1000 });
  const [exporting, setExporting] = useState(false);

  const data = assessments.data ?? [];
  const breakdown = useMemo(() => computeNdiBreakdown(data), [data]);

  const gaps = useMemo(() => {
    return data
      .filter((a) => a.maturity_level < 5)
      .map((a) => ({
        ...a,
        gap_weight: PRIORITY_WEIGHT[a.priority] * (5 - a.maturity_level),
      }))
      .sort(
        (a, b) =>
          b.gap_weight - a.gap_weight ||
          a.priority - b.priority ||
          a.maturity_level - b.maturity_level,
      );
  }, [data]);

  const topDomainWeaknesses = useMemo(() => {
    return Object.entries(breakdown.per_domain)
      .sort((a, b) => a[1] - b[1])
      .slice(0, 3);
  }, [breakdown.per_domain]);

  const onPrintPdf = () => {
    document.body.classList.add("ndmo-print-mode");
    setTimeout(() => {
      window.print();
      document.body.classList.remove("ndmo-print-mode");
    }, 50);
  };

  const onExcel = async () => {
    setExporting(true);
    try {
      await exportXlsxOrCsv(data, gaps, breakdown);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: BG }}>
      {/* Print-only CSS that hides the app shell when the user picks "Save as PDF" */}
      <style jsx global>{`
        @media print {
          body.ndmo-print-mode aside,
          body.ndmo-print-mode header,
          body.ndmo-print-mode nav,
          body.ndmo-print-mode [data-app-shell="topbar"],
          body.ndmo-print-mode [data-app-shell="sidebar"] {
            display: none !important;
          }
          body.ndmo-print-mode .ndmo-no-print { display: none !important; }
          body.ndmo-print-mode { background: white; }
        }
      `}</style>

      <div
        className="flex h-16 shrink-0 items-center justify-between px-8 ndmo-no-print"
        style={{ backgroundColor: BG_CARD, borderBottom: `1px solid ${BORDER}` }}
      >
        <div>
          <h1 className="text-lg font-bold" style={{ color: NEUTRAL_TEXT }}>تقرير الفجوة</h1>
          <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
            ملخص تنفيذي + جدول الفجوات مرتباً بالأهمية (الوزن × الأولوية)
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onPrintPdf}
            disabled={data.length === 0}
            className="flex h-9 items-center gap-2 rounded-md border px-4 text-[13px] font-medium disabled:opacity-60"
            style={{ borderColor: BORDER, color: NEUTRAL_TEXT, backgroundColor: BG_CARD }}
          >
            <Printer className="h-3.5 w-3.5" />
            تصدير PDF
          </button>
          <button
            type="button"
            onClick={onExcel}
            disabled={data.length === 0 || exporting}
            className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white disabled:opacity-60"
            style={{ backgroundColor: BRAND }}
          >
            {exporting ? <Download className="h-3.5 w-3.5 animate-pulse" /> : <FileDown className="h-3.5 w-3.5" />}
            تصدير Excel
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* Executive summary */}
        <div
          className="grid grid-cols-12 gap-4 rounded-xl p-5"
          style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
        >
          <div className="col-span-4 flex flex-col gap-1 border-l pe-4" style={{ borderColor: BORDER }}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.4px]" style={{ color: SUBTLE_TEXT }}>
              المؤشر الوطني للبيانات
            </p>
            <p className="text-[36px] font-bold leading-tight" style={{ color: BRAND }}>
              {breakdown.score_percent.toFixed(1)}%
            </p>
            <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
              {breakdown.assessed_count}/{breakdown.spec_count} مواصفة في النطاق · متوسط نضج {breakdown.average_maturity.toFixed(2)}
            </p>
          </div>
          <div className="col-span-4 flex flex-col gap-1 border-l pe-4" style={{ borderColor: BORDER }}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.4px]" style={{ color: SUBTLE_TEXT }}>
              إجمالي الفجوات
            </p>
            <p className="text-[36px] font-bold leading-tight" style={{ color: NEUTRAL_TEXT }}>
              {gaps.length}
            </p>
            <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
              مواصفة لم تصل إلى المستوى الريادي بعد
            </p>
          </div>
          <div className="col-span-4 flex flex-col gap-1 pe-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.4px]" style={{ color: SUBTLE_TEXT }}>
              أضعف ٣ مجالات
            </p>
            {topDomainWeaknesses.length === 0 ? (
              <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>—</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {topDomainWeaknesses.map(([code, score]) => (
                  <li key={code} className="text-[12px]" style={{ color: NEUTRAL_TEXT }}>
                    <strong>{code}</strong>{" "}
                    <span style={{ color: SUBTLE_TEXT }}>— {score.toFixed(1)}%</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Cycle comparison slot (Phase-5 expansion) */}
        <div
          className="flex items-center gap-3 rounded-xl p-4 ndmo-no-print"
          style={{ backgroundColor: BG_CARD, border: `1px dashed ${BORDER}`, color: SUBTLE_TEXT }}
        >
          <span className="text-[12px]">
            مقارنة مع الدورة السابقة: لم تتوفر بيانات دورة سابقة في هذا الإصدار. سيتم تفعيل هذه اللوحة في المرحلة 5.
          </span>
        </div>

        {/* Gap table */}
        <div
          className="flex flex-col rounded-xl"
          style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="flex h-10 items-center gap-2 px-5 text-[11px] font-semibold uppercase tracking-[0.4px]"
            style={{ color: SUBTLE_TEXT, borderBottom: `1px solid ${BORDER}` }}
          >
            <div className="w-20">رمز</div>
            <div className="flex-1">اسم المواصفة</div>
            <div className="w-16">المجال</div>
            <div className="w-28">الأولوية</div>
            <div className="w-44">المستوى الحالي</div>
            <div className="w-24 text-left">وزن الفجوة</div>
          </div>
          {gaps.length === 0 ? (
            <div
              className="px-5 py-12 text-center text-[12px]"
              style={{ color: SUCCESS }}
            >
              لا توجد فجوات — جميع المواصفات في النطاق وصلت إلى المستوى الريادي.
            </div>
          ) : (
            gaps.map((g) => (
              <div
                key={g.id}
                className="flex items-center gap-2 px-5 py-3 text-[13px]"
                style={{ borderBottom: `1px solid ${BORDER}`, color: NEUTRAL_TEXT }}
              >
                <div className="w-20">
                  <span
                    className="inline-block rounded px-2 py-0.5 text-[11px] font-semibold"
                    style={{ backgroundColor: "#FFF5F0", color: BRAND }}
                  >
                    {g.spec_code}
                  </span>
                </div>
                <div className="min-w-0 flex-1 truncate font-medium">{g.name_ar}</div>
                <div className="w-16 text-[11px]" style={{ color: SUBTLE_TEXT }}>
                  {g.domain_code}
                </div>
                <div className="w-28">
                  <PriorityBadge priority={g.priority} />
                </div>
                <div className="w-44">
                  <MaturityBadge level={g.maturity_level} />
                </div>
                <div className="w-24 text-left text-[12px] tabular-nums" style={{ color: SUBTLE_TEXT }}>
                  {g.gap_weight.toFixed(1)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Excel / CSV export
// ───────────────────────────────────────────────────────────────

interface GapItem extends AssessmentListItem {
  gap_weight: number;
}

async function exportXlsxOrCsv(
  all: AssessmentListItem[],
  gaps: GapItem[],
  breakdown: ReturnType<typeof computeNdiBreakdown>,
) {
  try {
    const xlsx = await import("xlsx").catch(() => null);
    if (!xlsx) {
      downloadGapsCsv(gaps);
      return;
    }
    const wb = xlsx.utils.book_new();

    // Summary sheet
    const summaryRows = [
      ["مؤشر NDI (%)", breakdown.score_percent],
      ["إجمالي المواصفات في النطاق", breakdown.spec_count],
      ["مواصفات مُقَيَّمَة", breakdown.assessed_count],
      ["متوسط النضج", breakdown.average_maturity],
      ["إجمالي الفجوات", gaps.length],
      [],
      ["نسبة النضج لكل أولوية"],
      ["أولوية ١", breakdown.per_priority[1]],
      ["أولوية ٢", breakdown.per_priority[2]],
      ["أولوية ٣", breakdown.per_priority[3]],
      [],
      ["نسبة النضج لكل مجال"],
      ...Object.entries(breakdown.per_domain).map(([code, pct]) => [code, pct]),
    ];
    const sumWs = xlsx.utils.aoa_to_sheet(summaryRows);
    xlsx.utils.book_append_sheet(wb, sumWs, "الملخص");

    // Gaps sheet
    const gapsRows = [
      [
        "رمز",
        "اسم المواصفة",
        "المجال",
        "الضابط",
        "الأولوية",
        "المستوى الحالي",
        "اسم المستوى",
        "وزن الفجوة",
        "الثقة",
      ],
      ...gaps.map((g) => [
        g.spec_code,
        g.name_ar,
        g.domain_code,
        g.control_code,
        g.priority,
        g.maturity_level,
        MATURITY_AR[g.maturity_level],
        Number(g.gap_weight.toFixed(2)),
        g.confidence != null ? Number(g.confidence.toFixed(3)) : null,
      ]),
    ];
    const gapsWs = xlsx.utils.aoa_to_sheet(gapsRows);
    xlsx.utils.book_append_sheet(wb, gapsWs, "الفجوات");

    // Full list
    const fullRows = [
      [
        "رمز",
        "اسم المواصفة",
        "المجال",
        "الأولوية",
        "المستوى",
        "الثقة",
        "الحالة",
        "آخر تحديث",
      ],
      ...all.map((a) => [
        a.spec_code,
        a.name_ar,
        a.domain_code,
        a.priority,
        a.maturity_level,
        a.confidence != null ? Number(a.confidence.toFixed(3)) : null,
        a.status,
        a.updated_at,
      ]),
    ];
    const fullWs = xlsx.utils.aoa_to_sheet(fullRows);
    xlsx.utils.book_append_sheet(wb, fullWs, "كل المواصفات");

    xlsx.writeFile(wb, `ndmo-gap-report-${new Date().toISOString().slice(0, 10)}.xlsx`);
  } catch (err) {
    console.error("xlsx export failed; falling back to CSV:", err);
    downloadGapsCsv(gaps);
  }
}

function downloadGapsCsv(gaps: GapItem[]) {
  const header = [
    "رمز",
    "اسم المواصفة",
    "المجال",
    "الضابط",
    "الأولوية",
    "المستوى الحالي",
    "اسم المستوى",
    "وزن الفجوة",
    "الثقة",
  ];
  const lines = [
    "﻿" + header.join(","),
    ...gaps.map((g) =>
      [
        g.spec_code,
        csvCell(g.name_ar),
        g.domain_code,
        g.control_code,
        g.priority,
        g.maturity_level,
        MATURITY_AR[g.maturity_level],
        g.gap_weight.toFixed(2),
        g.confidence != null ? g.confidence.toFixed(3) : "",
      ].join(","),
    ),
  ];
  const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ndmo-gap-report-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function csvCell(v: string): string {
  if (v.includes(",") || v.includes('"') || v.includes("\n")) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}
