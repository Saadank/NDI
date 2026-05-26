"use client";

/**
 * NDMO Compliance — Specifications list.
 *
 * Reads from /assessments (which already JOINs spec metadata).  Rows are
 * grouped by maturity_level (0..5), each level rendered as a collapsible
 * section.  Top of the page: a search box (matches spec_code or name_ar)
 * + four filter chips (domain / status / priority / confidence range) +
 * an "Export CSV" button.
 *
 * Group ordering: 0 → 5 (urgent-first).  Inside a group: sort by priority
 * asc then spec_code.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronLeft, Download, Search } from "lucide-react";

import { useAssessments } from "@/lib/hooks/ndmo-compliance/useAssessments";
import {
  type AssessmentListItem,
  type AssessmentStatus,
  MATURITY_AR,
} from "@/lib/types/ndmo-compliance";
import {
  AssessmentStatusBadge,
  BG,
  BG_CARD,
  BORDER,
  MaturityBadge,
  MATURITY_COLORS,
  NEUTRAL_TEXT,
  PriorityBadge,
  SUBTLE_TEXT,
  BRAND,
} from "../shared/badges";

const ALL_STATUSES: AssessmentStatus[] = [
  "pending",
  "in_progress",
  "under_review",
  "approved",
  "rejected",
];

const CONFIDENCE_BUCKETS = [
  { id: "all", label: "كل مستويات الثقة", min: 0, max: 1 },
  { id: "low", label: "أقل من ٦٠٪", min: 0, max: 0.6 },
  { id: "mid", label: "٦٠٪–٨٠٪", min: 0.6, max: 0.8 },
  { id: "high", label: "أعلى من ٨٠٪", min: 0.8, max: 1.001 },
] as const;

export function SpecsListPage() {
  const assessments = useAssessments({ limit: 1000 });
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState<string>("all");
  const [status, setStatus] = useState<AssessmentStatus | "all">("all");
  const [priority, setPriority] = useState<number | "all">("all");
  const [conf, setConf] = useState<(typeof CONFIDENCE_BUCKETS)[number]["id"]>("all");
  const [openLevels, setOpenLevels] = useState<Record<number, boolean>>({
    0: true, 1: true, 2: true, 3: true, 4: true, 5: true,
  });

  const domains = useMemo(() => {
    const set = new Set<string>();
    assessments.data?.forEach((a) => set.add(a.domain_code));
    return Array.from(set).sort();
  }, [assessments.data]);

  const filtered = useMemo(() => {
    if (!assessments.data) return [];
    const qLower = q.trim().toLowerCase();
    const bucket = CONFIDENCE_BUCKETS.find((b) => b.id === conf)!;
    return assessments.data.filter((a) => {
      if (qLower) {
        const hay = `${a.spec_code} ${a.name_ar}`.toLowerCase();
        if (!hay.includes(qLower)) return false;
      }
      if (domain !== "all" && a.domain_code !== domain) return false;
      if (status !== "all" && a.status !== status) return false;
      if (priority !== "all" && a.priority !== priority) return false;
      if (conf !== "all") {
        const c = a.confidence ?? 1;
        if (c < bucket.min || c >= bucket.max) return false;
      }
      return true;
    });
  }, [assessments.data, q, domain, status, priority, conf]);

  const grouped = useMemo(() => {
    const buckets: Record<number, AssessmentListItem[]> = { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [] };
    for (const a of filtered) buckets[a.maturity_level].push(a);
    for (const lvl of Object.keys(buckets) as unknown as Array<keyof typeof buckets>) {
      buckets[lvl].sort(
        (a, b) => a.priority - b.priority || a.spec_code.localeCompare(b.spec_code),
      );
    }
    return buckets;
  }, [filtered]);

  const onExportCsv = () => downloadCsv(filtered);

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: BG }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: BG_CARD, borderBottom: `1px solid ${BORDER}` }}
      >
        <div>
          <h1 className="text-lg font-bold" style={{ color: NEUTRAL_TEXT }}>المواصفات</h1>
          <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
            {filtered.length} مواصفة معروضة من إجمالي {assessments.data?.length ?? 0}
          </p>
        </div>
        <button
          type="button"
          onClick={onExportCsv}
          disabled={filtered.length === 0}
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white disabled:opacity-60"
          style={{ backgroundColor: BRAND }}
        >
          <Download className="h-3.5 w-3.5" />
          تصدير CSV
        </button>
      </div>

      {/* Filters bar */}
      <div
        className="flex flex-wrap items-center gap-2 px-8 py-4"
        style={{ backgroundColor: BG_CARD, borderBottom: `1px solid ${BORDER}` }}
      >
        <div className="relative flex h-9 items-center" style={{ minWidth: 280 }}>
          <Search className="absolute right-3 h-3.5 w-3.5" style={{ color: SUBTLE_TEXT }} />
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="بحث برمز المواصفة أو الاسم…"
            className="h-9 w-full rounded-md border pe-9 ps-3 text-[12px] outline-none focus:border-[#D76736]"
            style={{ borderColor: BORDER, color: NEUTRAL_TEXT, backgroundColor: BG_CARD }}
          />
        </div>
        <FilterSelect
          label="المجال"
          value={domain}
          onChange={setDomain}
          options={[["all", "كل المجالات"], ...domains.map((d) => [d, d] as [string, string])]}
        />
        <FilterSelect
          label="الحالة"
          value={status}
          onChange={(v) => setStatus(v as AssessmentStatus | "all")}
          options={[
            ["all", "كل الحالات"],
            ...ALL_STATUSES.map((s) => [s, s] as [string, string]),
          ]}
        />
        <FilterSelect
          label="الأولوية"
          value={String(priority)}
          onChange={(v) => setPriority(v === "all" ? "all" : Number(v) as 1 | 2 | 3)}
          options={[
            ["all", "كل الأولويات"],
            ["1", "أولوية ١"],
            ["2", "أولوية ٢"],
            ["3", "أولوية ٣"],
          ]}
        />
        <FilterSelect
          label="الثقة"
          value={conf}
          onChange={(v) => setConf(v as typeof conf)}
          options={CONFIDENCE_BUCKETS.map((b) => [b.id, b.label] as [string, string])}
        />
      </div>

      {/* Grouped list */}
      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {assessments.isLoading && (
          <div className="flex h-40 items-center justify-center text-[13px]" style={{ color: SUBTLE_TEXT }}>
            جارٍ التحميل…
          </div>
        )}
        {assessments.data && filtered.length === 0 && (
          <div className="flex h-40 items-center justify-center text-[13px]" style={{ color: SUBTLE_TEXT }}>
            لا توجد مواصفات تطابق المرشحات الحالية.
          </div>
        )}
        {([0, 1, 2, 3, 4, 5] as const).map((lvl) => {
          const items = grouped[lvl];
          if (!items.length) return null;
          const open = openLevels[lvl];
          return (
            <div
              key={lvl}
              className="flex flex-col rounded-xl"
              style={{
                backgroundColor: BG_CARD,
                border: `1px solid ${BORDER}`,
                borderTop: `3px solid ${MATURITY_COLORS[lvl]}`,
              }}
            >
              <button
                type="button"
                onClick={() =>
                  setOpenLevels((cur) => ({ ...cur, [lvl]: !open }))
                }
                className="flex h-12 items-center justify-between px-5"
                style={{ borderBottom: open ? `1px solid ${BORDER}` : "none" }}
              >
                <div className="flex items-center gap-3">
                  <MaturityBadge level={lvl} />
                  <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
                    {items.length} مواصفة
                  </p>
                </div>
                {open ? (
                  <ChevronDown className="h-4 w-4" style={{ color: SUBTLE_TEXT }} />
                ) : (
                  <ChevronLeft className="h-4 w-4" style={{ color: SUBTLE_TEXT }} />
                )}
              </button>
              {open && items.map((a) => <SpecRow key={a.id} a={a} />)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <label className="flex h-9 items-center gap-2 rounded-md border px-2 text-[12px]" style={{ borderColor: BORDER }}>
      <span style={{ color: SUBTLE_TEXT }}>{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border-none bg-transparent text-[12px] outline-none"
        style={{ color: NEUTRAL_TEXT }}
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </label>
  );
}

function SpecRow({ a }: { a: AssessmentListItem }) {
  return (
    <Link
      href={`/ndmo-compliance/specs/${a.id}`}
      className="flex items-center gap-3 px-5 py-3 hover:bg-[#FAFAFA]"
      style={{ borderBottom: `1px solid ${BORDER}` }}
    >
      <span
        className="inline-block w-20 rounded px-2 py-0.5 text-[11px] font-semibold tabular-nums"
        style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
      >
        {a.spec_code}
      </span>
      <div className="min-w-0 flex-1 truncate text-[13px] font-medium" style={{ color: NEUTRAL_TEXT }}>
        {a.name_ar}
      </div>
      <div className="flex w-16 justify-start text-[11px]" style={{ color: SUBTLE_TEXT }}>
        {a.domain_code}
      </div>
      <PriorityBadge priority={a.priority} />
      <div className="w-20 text-left text-[11px] tabular-nums" style={{ color: SUBTLE_TEXT }}>
        {a.confidence != null ? `${(a.confidence * 100).toFixed(0)}%` : "—"}
      </div>
      <AssessmentStatusBadge status={a.status} />
    </Link>
  );
}

// ───────────────────────────────────────────────────────────────
// CSV export
// ───────────────────────────────────────────────────────────────

function downloadCsv(rows: AssessmentListItem[]) {
  const header = [
    "رمز المواصفة",
    "الاسم",
    "المجال",
    "الضابط",
    "الأولوية",
    "مستوى النضج",
    "اسم المستوى",
    "الثقة",
    "الحالة",
    "آخر تحديث",
  ];
  const csvRows: string[] = [
    "﻿" + header.map(csvCell).join(","),
    ...rows.map((r) =>
      [
        r.spec_code,
        r.name_ar,
        r.domain_code,
        r.control_code,
        String(r.priority),
        String(r.maturity_level),
        MATURITY_AR[r.maturity_level],
        r.confidence != null ? r.confidence.toFixed(3) : "",
        r.status,
        r.updated_at,
      ].map(csvCell).join(","),
    ),
  ];
  const blob = new Blob([csvRows.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ndmo-specifications-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function csvCell(v: string): string {
  if (v.includes(",") || v.includes('"') || v.includes("\n")) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}
