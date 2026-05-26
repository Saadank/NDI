"use client";

/**
 * NDMO Compliance Dashboard.
 *
 * Sections (top-to-bottom, RTL flow):
 *   1. Header bar with the entity name + cycle indicator + "Run Assessment" CTA
 *   2. NDI score card (large percentage + breakdown by priority)
 *   3. Six maturity-level cards (0..5) with counts
 *   4. Domain heatmap (14 domains × maturity buckets)
 *   5. "Needs your review" list — under_review status, sorted by priority then confidence asc
 *   6. Recent activity (latest 8 assessments updated_at desc)
 *
 * Data: aggregated client-side from /assessments and /documents endpoints
 * (no separate /dashboard endpoint yet — Phase-5 candidate optimisation).
 */
import { useMemo } from "react";
import Link from "next/link";
import { CheckCircle2, FileWarning, Loader2, PlayCircle, RefreshCw } from "lucide-react";

import { useAssessments, useRunAssessment } from "@/lib/hooks/ndmo-compliance/useAssessments";
import { useDocuments } from "@/lib/hooks/ndmo-compliance/useDocuments";
import {
  ASSESSMENT_STATUS_AR,
  MATURITY_AR,
  type AssessmentListItem,
} from "@/lib/types/ndmo-compliance";
import { computeNdiBreakdown, type NdiBreakdown } from "./ndi-score";

const BRAND = "#D76736";
const BRAND_SOFT = "#FFF5F0";
const SUCCESS = "#449235";
const SUCCESS_SOFT = "#44923526";
const WARN = "#D97706";
const NEUTRAL_TEXT = "#070709";
const SUBTLE_TEXT = "#616161";
const BG = "#FFFFF9";
const BG_CARD = "#FFFFFF";
const BORDER = "#EEEEEE";

const MATURITY_COLORS: Record<0 | 1 | 2 | 3 | 4 | 5, string> = {
  0: "#9E9E9E",
  1: "#F59E0B",
  2: "#EAB308",
  3: "#84CC16",
  4: "#22C55E",
  5: SUCCESS,
};

export function NdmoDashboard() {
  const assessments = useAssessments({ limit: 1000 });
  const documents = useDocuments({ limit: 500 });
  const runMutation = useRunAssessment();

  const breakdown = useMemo<NdiBreakdown | null>(() => {
    if (!assessments.data) return null;
    return computeNdiBreakdown(assessments.data);
  }, [assessments.data]);

  const reviewQueue = useMemo(() => {
    if (!assessments.data) return [];
    return [...assessments.data]
      .filter((a) => a.status === "under_review")
      .sort((a, b) => {
        if (a.priority !== b.priority) return a.priority - b.priority;
        return (a.confidence ?? 1) - (b.confidence ?? 1);
      })
      .slice(0, 8);
  }, [assessments.data]);

  const recentActivity = useMemo(() => {
    if (!assessments.data) return [];
    return [...assessments.data]
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .slice(0, 8);
  }, [assessments.data]);

  const readyDocs = useMemo(
    () => documents.data?.filter((d) => d.status === "ready").length ?? 0,
    [documents.data],
  );

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: BG }}>
      {/* ─── Header bar ─── */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: BG_CARD, borderBottom: `1px solid ${BORDER}` }}
      >
        <div className="flex flex-col">
          <h1 className="text-lg font-bold" style={{ color: NEUTRAL_TEXT }}>
            لوحة الامتثال — NDMO
          </h1>
          <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
            تقييم مدى التزام الجهة بمعايير إدارة البيانات الوطنية
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => assessments.refetch()}
            className="flex h-9 items-center gap-2 rounded-md border px-3 text-[13px] font-medium"
            style={{ borderColor: BORDER, color: NEUTRAL_TEXT, backgroundColor: BG_CARD }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            تحديث
          </button>
          <button
            type="button"
            disabled={runMutation.isPending}
            onClick={() => runMutation.mutate({ dry_run: false })}
            className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white disabled:opacity-60"
            style={{ backgroundColor: BRAND }}
          >
            {runMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <PlayCircle className="h-3.5 w-3.5" />
            )}
            تشغيل التقييم
          </button>
        </div>
      </div>

      {/* ─── Body ─── */}
      <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
        {/* Loading / empty states */}
        {assessments.isLoading && (
          <div className="flex h-40 items-center justify-center text-[13px]" style={{ color: SUBTLE_TEXT }}>
            جارٍ تحميل التقييمات…
          </div>
        )}

        {assessments.isError && (
          <div
            className="flex items-center gap-2 rounded-md px-4 py-3 text-[13px]"
            style={{ backgroundColor: "#FFF5F0", color: BRAND, border: `1px solid ${BRAND}` }}
          >
            <FileWarning className="h-4 w-4" />
            تعذّر تحميل بيانات التقييم. تحقق من تفعيل المنتج للجهة.
          </div>
        )}

        {assessments.data && (
          <>
            {/* NDI score card */}
            <div className="flex gap-4">
              <div
                className="flex w-[280px] shrink-0 flex-col gap-2 rounded-xl p-5"
                style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.6px]" style={{ color: SUBTLE_TEXT }}>
                  المؤشر الوطني للبيانات
                </p>
                <p className="text-[44px] font-bold leading-tight" style={{ color: BRAND }}>
                  {breakdown ? breakdown.score_percent.toFixed(1) : "—"}%
                </p>
                <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
                  {breakdown
                    ? `${breakdown.assessed_count}/${breakdown.spec_count} مواصفة في النطاق`
                    : "لا توجد بيانات تقييم بعد"}
                </p>
              </div>

              {/* Maturity-level summary cards */}
              <div className="grid flex-1 grid-cols-6 gap-3">
                {([0, 1, 2, 3, 4, 5] as const).map((lvl) => {
                  const count = breakdown?.per_level[lvl] ?? 0;
                  return (
                    <div
                      key={lvl}
                      className="flex flex-col gap-2 rounded-lg p-4"
                      style={{
                        backgroundColor: BG_CARD,
                        border: `1px solid ${BORDER}`,
                        borderTop: `3px solid ${MATURITY_COLORS[lvl]}`,
                      }}
                    >
                      <p className="text-[10px] font-semibold uppercase tracking-[0.4px]" style={{ color: SUBTLE_TEXT }}>
                        المستوى {lvl}
                      </p>
                      <p className="text-[22px] font-bold leading-tight" style={{ color: NEUTRAL_TEXT }}>
                        {count}
                      </p>
                      <p className="text-[11px]" style={{ color: SUBTLE_TEXT }}>{MATURITY_AR[lvl]}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Documents + cycle summary strip */}
            <div className="flex gap-4">
              <SummaryStat
                label="وثائق جاهزة للتقييم"
                value={`${readyDocs}`}
                hint={`من إجمالي ${documents.data?.length ?? 0} وثيقة مرفوعة`}
                tone="success"
              />
              <SummaryStat
                label="بانتظار المراجعة"
                value={`${
                  assessments.data.filter((a) => a.status === "under_review").length
                }`}
                hint="تقييمات لم تُعتمد بعد"
                tone="warn"
              />
              <SummaryStat
                label="مُعتمَدة"
                value={`${
                  assessments.data.filter((a) => a.status === "approved").length
                }`}
                hint="بعد مراجعة المحلل"
                tone="success"
              />
              <SummaryStat
                label="مرفوضة"
                value={`${
                  assessments.data.filter((a) => a.status === "rejected").length
                }`}
                hint="تتطلب أدلة إضافية"
                tone="neutral"
              />
            </div>

            {/* Domain heatmap */}
            <div
              className="flex flex-col gap-4 rounded-xl p-5"
              style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
            >
              <div className="flex items-center justify-between">
                <h2 className="text-[14px] font-bold" style={{ color: NEUTRAL_TEXT }}>
                  خريطة نضج المجالات
                </h2>
                <p className="text-[11px]" style={{ color: SUBTLE_TEXT }}>
                  متوسط مستوى النضج لكل مجال من 0 إلى 5
                </p>
              </div>
              <DomainHeatmap items={assessments.data} />
            </div>

            {/* Two-column bottom row: review queue + recent activity */}
            <div className="grid grid-cols-2 gap-4">
              <ListCard
                title="بانتظار مراجعتك"
                hint="مرتبة حسب الأولوية ثم الثقة (الأدنى أولاً)"
                items={reviewQueue}
                emptyText="لا توجد تقييمات بانتظار المراجعة حالياً."
              />
              <ListCard
                title="آخر النشاط"
                hint="أحدث 8 تقييمات تم تحديثها"
                items={recentActivity}
                emptyText="لا يوجد نشاط مسجل بعد."
                showStatus
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Sub-components
// ───────────────────────────────────────────────────────────────

function SummaryStat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone: "success" | "warn" | "neutral";
}) {
  const colors = {
    success: { fg: SUCCESS, bg: SUCCESS_SOFT },
    warn: { fg: WARN, bg: "#FEF3C7" },
    neutral: { fg: NEUTRAL_TEXT, bg: BRAND_SOFT },
  }[tone];
  return (
    <div
      className="flex flex-1 flex-col gap-1 rounded-lg p-4"
      style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.4px]" style={{ color: SUBTLE_TEXT }}>
        {label}
      </p>
      <p className="text-[22px] font-bold" style={{ color: colors.fg }}>
        {value}
      </p>
      <p className="text-[11px]" style={{ color: SUBTLE_TEXT }}>
        <span
          className="inline-block rounded px-1.5 py-0.5"
          style={{ backgroundColor: colors.bg, color: colors.fg, fontWeight: 500 }}
        >
          {hint}
        </span>
      </p>
    </div>
  );
}

function DomainHeatmap({ items }: { items: AssessmentListItem[] }) {
  // Group by domain_code -> {sum, count} for unweighted mean.
  const byDomain = new Map<string, { sum: number; count: number }>();
  for (const a of items) {
    const e = byDomain.get(a.domain_code) ?? { sum: 0, count: 0 };
    e.sum += a.maturity_level;
    e.count += 1;
    byDomain.set(a.domain_code, e);
  }
  const rows = [...byDomain.entries()]
    .map(([code, { sum, count }]) => ({ code, avg: count ? sum / count : 0, count }))
    .sort((a, b) => b.avg - a.avg);

  if (rows.length === 0) {
    return (
      <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
        لا توجد تقييمات لعرض الخريطة بعد.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {rows.map((r) => {
        const pct = (r.avg / 5) * 100;
        const bucket = Math.round(r.avg) as 0 | 1 | 2 | 3 | 4 | 5;
        return (
          <div key={r.code} className="flex items-center gap-3">
            <div className="w-16 text-[12px] font-semibold" style={{ color: NEUTRAL_TEXT }}>
              {r.code}
            </div>
            <div className="flex flex-1 items-center gap-2">
              <div className="h-3 flex-1 overflow-hidden rounded" style={{ backgroundColor: "#F4F4F4" }}>
                <div
                  className="h-full rounded"
                  style={{ width: `${pct}%`, backgroundColor: MATURITY_COLORS[bucket] }}
                />
              </div>
              <div className="w-24 text-[11px] tabular-nums" style={{ color: SUBTLE_TEXT }}>
                {r.avg.toFixed(2)} ({r.count} مواصفة)
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ListCard({
  title,
  hint,
  items,
  emptyText,
  showStatus = false,
}: {
  title: string;
  hint: string;
  items: AssessmentListItem[];
  emptyText: string;
  showStatus?: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-3 rounded-xl p-5"
      style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
    >
      <div className="flex items-baseline justify-between">
        <h2 className="text-[14px] font-bold" style={{ color: NEUTRAL_TEXT }}>
          {title}
        </h2>
        <p className="text-[11px]" style={{ color: SUBTLE_TEXT }}>
          {hint}
        </p>
      </div>
      {items.length === 0 ? (
        <p className="py-8 text-center text-[12px]" style={{ color: SUBTLE_TEXT }}>
          {emptyText}
        </p>
      ) : (
        <ul className="flex flex-col">
          {items.map((it) => (
            <li
              key={it.id}
              className="flex items-center justify-between gap-3 border-b py-2.5 last:border-b-0"
              style={{ borderColor: BORDER }}
            >
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <span
                  className="inline-block rounded px-2 py-0.5 text-[11px] font-semibold tabular-nums"
                  style={{ backgroundColor: BRAND_SOFT, color: BRAND }}
                >
                  {it.spec_code}
                </span>
                <Link
                  href={`/ndmo-compliance/specs/${it.id}`}
                  className="truncate text-[12px] font-medium hover:underline"
                  style={{ color: NEUTRAL_TEXT }}
                >
                  {it.name_ar}
                </Link>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className="text-[11px] tabular-nums"
                  style={{ color: MATURITY_COLORS[it.maturity_level] }}
                >
                  المستوى {it.maturity_level}
                </span>
                {showStatus && (
                  <span className="text-[11px]" style={{ color: SUBTLE_TEXT }}>
                    {ASSESSMENT_STATUS_AR[it.status]}
                  </span>
                )}
                {!showStatus && it.confidence != null && (
                  <span className="text-[11px] tabular-nums" style={{ color: SUBTLE_TEXT }}>
                    ثقة {(it.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Re-exported for testability.
export { CheckCircle2 };
