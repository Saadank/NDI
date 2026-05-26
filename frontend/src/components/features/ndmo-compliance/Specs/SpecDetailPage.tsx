"use client";

/**
 * NDMO Compliance — Specification detail.
 *
 * URL: /ndmo-compliance/specs/[id]   (id = assessment UUID)
 *
 * Layout:
 *   Header card  : spec code, name, domain, control, priority, NCA flag,
 *                  AI maturity verdict + confidence
 *   Rationale    : AI rationale_ar
 *   Gaps         : ai_result.gaps_ar (warning panel if non-empty)
 *   Citations    : each citation = quoted text + source file + page link
 *   Required el. : checklist rendered from spec.required_elements
 *   Review       : 3 buttons (approve / changes requested / reject + override)
 *                  + analyst notes textarea
 *   History      : current ai_result + any previous review notes
 */
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  FileText,
  Loader2,
  X,
} from "lucide-react";

import { useAssessment, useSubmitReview } from "@/lib/hooks/ndmo-compliance/useAssessments";
import { ReviewDecision } from "@/lib/types/ndmo-compliance";
import {
  AssessmentStatusBadge,
  BG,
  BG_CARD,
  BORDER,
  BRAND,
  BRAND_SOFT,
  DANGER,
  DANGER_SOFT,
  MaturityBadge,
  MATURITY_COLORS,
  NEUTRAL_TEXT,
  NcaConditionalBadge,
  PriorityBadge,
  SUBTLE_TEXT,
  SUCCESS,
  SUCCESS_SOFT,
  WARN,
  WARN_SOFT,
} from "../shared/badges";

export function SpecDetailPage({ id }: { id: string }) {
  const detail = useAssessment(id);
  const submit = useSubmitReview();
  const router = useRouter();

  const [note, setNote] = useState("");
  const [overrideLevel, setOverrideLevel] = useState<number | null>(null);

  const onAction = (decision: ReviewDecision) => {
    submit.mutate(
      {
        id,
        body: {
          decision,
          note: note.trim() || undefined,
          override_maturity_level:
            decision === "rejected" && overrideLevel != null ? (overrideLevel as 0 | 1 | 2 | 3 | 4 | 5) : undefined,
        },
      },
      {
        onSuccess: () => {
          setNote("");
          setOverrideLevel(null);
        },
      },
    );
  };

  if (detail.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center" style={{ backgroundColor: BG }}>
        <p className="text-[13px]" style={{ color: SUBTLE_TEXT }}>جارٍ التحميل…</p>
      </div>
    );
  }
  if (detail.isError || !detail.data) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3" style={{ backgroundColor: BG }}>
        <p className="text-[13px]" style={{ color: SUBTLE_TEXT }}>تعذّر تحميل التقييم.</p>
        <button
          type="button"
          onClick={() => router.push("/ndmo-compliance/specs")}
          className="text-[13px] font-medium"
          style={{ color: BRAND }}
        >
          العودة إلى قائمة المواصفات
        </button>
      </div>
    );
  }

  const a = detail.data;
  const ai = a.ai_result ?? {};
  const hasGaps = Boolean(ai.gaps_ar && ai.gaps_ar.trim());
  const requiredEntries = Object.entries(a as unknown as Record<string, unknown>);
  void requiredEntries; // kept for future extension when the field is hydrated client-side

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: BG }}>
      {/* Top header bar */}
      <div
        className="flex h-16 shrink-0 items-center gap-3 px-8"
        style={{ backgroundColor: BG_CARD, borderBottom: `1px solid ${BORDER}` }}
      >
        <Link
          href="/ndmo-compliance/specs"
          className="flex items-center gap-1 text-[12px] font-medium"
          style={{ color: SUBTLE_TEXT }}
        >
          <ArrowRight className="h-3.5 w-3.5" />
          العودة إلى المواصفات
        </Link>
        <div className="mx-2 h-5 w-px" style={{ backgroundColor: BORDER }} />
        <h1 className="text-lg font-bold" style={{ color: NEUTRAL_TEXT }}>
          {a.spec_code} — {a.spec_name_ar}
        </h1>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* Header card */}
        <div
          className="grid grid-cols-12 gap-4 rounded-xl p-5"
          style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
        >
          <div className="col-span-7 flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="rounded px-2 py-0.5 text-[11px] font-semibold"
                style={{ backgroundColor: BRAND_SOFT, color: BRAND }}
              >
                {a.spec_code}
              </span>
              <PriorityBadge priority={a.priority} />
              <AssessmentStatusBadge status={a.status} />
              {a.nca_conditional && <NcaConditionalBadge />}
            </div>
            <p className="text-[15px] font-bold leading-snug" style={{ color: NEUTRAL_TEXT }}>
              {a.spec_name_ar}
            </p>
            <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
              المجال: <strong>{a.domain_name_ar}</strong> ({a.domain_code})
              <span className="mx-1">·</span>
              الضابط: <strong>{a.control_name_ar}</strong> ({a.control_code})
            </p>
          </div>
          <div
            className="col-span-5 flex flex-col items-end justify-between gap-2 rounded-lg p-4"
            style={{ backgroundColor: "#FAFAFA", border: `1px solid ${BORDER}` }}
          >
            <p className="text-[11px] font-semibold uppercase tracking-[0.4px]" style={{ color: SUBTLE_TEXT }}>
              تقييم النموذج
            </p>
            <div className="flex items-baseline gap-2">
              <p
                className="text-[34px] font-bold leading-none"
                style={{ color: MATURITY_COLORS[a.maturity_level] }}
              >
                {a.maturity_level}
              </p>
              <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>/ ٥</p>
            </div>
            <MaturityBadge level={a.maturity_level} />
            <p className="text-[11px]" style={{ color: SUBTLE_TEXT }}>
              ثقة النموذج: <strong>{a.confidence != null ? (a.confidence * 100).toFixed(0) + "%" : "—"}</strong>
            </p>
          </div>
        </div>

        {/* Rationale */}
        {ai.rationale_ar && (
          <Section title="مبررات التقييم">
            <p className="text-[13px] leading-relaxed" style={{ color: NEUTRAL_TEXT }}>
              {ai.rationale_ar}
            </p>
          </Section>
        )}

        {/* AI gap warning */}
        {hasGaps && (
          <div
            className="flex gap-3 rounded-xl p-4"
            style={{ backgroundColor: WARN_SOFT, border: `1px solid ${WARN}` }}
          >
            <AlertTriangle className="h-5 w-5 shrink-0" style={{ color: WARN }} />
            <div className="flex flex-col gap-1">
              <p className="text-[13px] font-semibold" style={{ color: WARN }}>
                الفجوات للوصول إلى المستوى التالي
              </p>
              <p className="text-[12px] leading-relaxed" style={{ color: NEUTRAL_TEXT }}>
                {ai.gaps_ar}
              </p>
            </div>
          </div>
        )}

        {/* Citations */}
        <Section
          title={`الاستشهادات (${a.citations.length})`}
          hint="مقتطفات من وثائق الجهة استند إليها النموذج في حكمه"
        >
          {a.citations.length === 0 ? (
            <p className="py-4 text-center text-[12px]" style={{ color: SUBTLE_TEXT }}>
              لا توجد استشهادات — قد تكون الأدلة غير كافية.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {a.citations.map((c) => (
                <li
                  key={c.chunk_id}
                  className="rounded-lg p-3"
                  style={{ backgroundColor: "#FAFAFA", border: `1px solid ${BORDER}` }}
                >
                  <div className="mb-1 flex items-center gap-3 text-[11px]" style={{ color: SUBTLE_TEXT }}>
                    <FileText className="h-3.5 w-3.5" />
                    <span className="font-semibold" style={{ color: NEUTRAL_TEXT }}>{c.source_file}</span>
                    <span>· صفحة {c.page_number}</span>
                  </div>
                  <p className="text-[12px] leading-relaxed" style={{ color: NEUTRAL_TEXT }}>
                    "{c.citation_text}"
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Section>

        {/* Review actions */}
        <Section title="مراجعة المحلل" hint="اعتمد، اطلب أدلة إضافية، أو ارفض مع تعديل المستوى">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="ملاحظات للسجل المراجَع (اختياري)…"
            className="w-full resize-y rounded-md border p-3 text-[13px] outline-none focus:border-[#D76736]"
            style={{ borderColor: BORDER, color: NEUTRAL_TEXT, backgroundColor: BG_CARD, minHeight: 90 }}
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={submit.isPending}
              onClick={() => onAction("approved")}
              className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-semibold text-white disabled:opacity-60"
              style={{ backgroundColor: SUCCESS }}
            >
              <Check className="h-3.5 w-3.5" />
              اعتماد
            </button>
            <button
              type="button"
              disabled={submit.isPending}
              onClick={() => onAction("changes_requested")}
              className="flex h-9 items-center gap-2 rounded-md border px-4 text-[13px] font-semibold"
              style={{ borderColor: WARN, color: WARN, backgroundColor: WARN_SOFT }}
            >
              طلب أدلة إضافية
            </button>
            <div
              className="flex items-center gap-2 rounded-md border px-3 py-1"
              style={{ borderColor: DANGER }}
            >
              <label className="text-[11px]" style={{ color: DANGER }}>تعديل المستوى:</label>
              <select
                value={overrideLevel ?? ""}
                onChange={(e) => setOverrideLevel(e.target.value === "" ? null : Number(e.target.value))}
                className="border-none bg-transparent text-[12px] outline-none"
                style={{ color: DANGER }}
              >
                <option value="">بدون تعديل</option>
                {[0, 1, 2, 3, 4, 5].map((l) => (
                  <option key={l} value={l}>المستوى {l}</option>
                ))}
              </select>
              <button
                type="button"
                disabled={submit.isPending}
                onClick={() => onAction("rejected")}
                className="flex h-7 items-center gap-1 rounded px-3 text-[12px] font-semibold text-white disabled:opacity-60"
                style={{ backgroundColor: DANGER }}
              >
                {submit.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <X className="h-3 w-3" />}
                رفض
              </button>
            </div>
          </div>
          {submit.isSuccess && (
            <p className="mt-2 text-[12px]" style={{ color: SUCCESS }}>تم حفظ المراجعة.</p>
          )}
          {submit.isError && (
            <p className="mt-2 text-[12px]" style={{ color: DANGER }}>
              تعذّر حفظ المراجعة. حاول مجدداً.
            </p>
          )}
        </Section>

        {/* Review history (current row only — multi-cycle history is Phase 5) */}
        <Section title="سجل المراجعة">
          <div className="flex flex-col gap-2 text-[12px]" style={{ color: NEUTRAL_TEXT }}>
            <p>
              <span style={{ color: SUBTLE_TEXT }}>قرار المراجعة:</span>{" "}
              {a.review_decision ?? "لم تتم المراجعة بعد"}
            </p>
            {a.review_note && (
              <p
                className="rounded-lg p-2"
                style={{ backgroundColor: SUCCESS_SOFT, color: NEUTRAL_TEXT }}
              >
                <strong style={{ color: SUCCESS }}>ملاحظة المراجع: </strong>{a.review_note}
              </p>
            )}
            <p style={{ color: SUBTLE_TEXT }}>
              آخر تحديث: {new Date(a.updated_at).toLocaleString("ar-SA")}
            </p>
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="flex flex-col gap-3 rounded-xl p-5"
      style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
    >
      <div className="flex items-baseline justify-between">
        <h2 className="text-[14px] font-bold" style={{ color: NEUTRAL_TEXT }}>{title}</h2>
        {hint && <p className="text-[11px]" style={{ color: SUBTLE_TEXT }}>{hint}</p>}
      </div>
      {children}
    </div>
  );
}
