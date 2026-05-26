/**
 * Shared visual primitives — maturity / status / priority badges,
 * plus the NDMO color palette used by every NDMO feature page.
 *
 * Centralised so the 5 screens stay visually consistent and any tweak
 * (e.g. tightening the level-3 hue) lands in one place.
 */
import {
  AssessmentStatus,
  ASSESSMENT_STATUS_AR,
  DocumentStatus,
  DOCUMENT_STATUS_AR,
  MATURITY_AR,
} from "@/lib/types/ndmo-compliance";

export const BRAND = "#D76736";
export const BRAND_SOFT = "#FFF5F0";
export const SUCCESS = "#449235";
export const SUCCESS_SOFT = "#44923526";
export const WARN = "#D97706";
export const WARN_SOFT = "#FEF3C7";
export const DANGER = "#E7000B";
export const DANGER_SOFT = "#FEE2E2";
export const NEUTRAL_TEXT = "#070709";
export const SUBTLE_TEXT = "#616161";
export const BG = "#FFFFF9";
export const BG_CARD = "#FFFFFF";
export const BORDER = "#EEEEEE";

export const MATURITY_COLORS: Record<0 | 1 | 2 | 3 | 4 | 5, string> = {
  0: "#9E9E9E",
  1: "#F59E0B",
  2: "#EAB308",
  3: "#84CC16",
  4: "#22C55E",
  5: SUCCESS,
};

export function MaturityBadge({ level }: { level: 0 | 1 | 2 | 3 | 4 | 5 }) {
  const color = MATURITY_COLORS[level];
  return (
    <span
      className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold tabular-nums"
      style={{ color, backgroundColor: `${color}1A` }}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      المستوى {level} — {MATURITY_AR[level]}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: 1 | 2 | 3 }) {
  const colors = {
    1: { fg: BRAND, bg: BRAND_SOFT, label: "أولوية ١" },
    2: { fg: WARN, bg: WARN_SOFT, label: "أولوية ٢" },
    3: { fg: SUBTLE_TEXT, bg: "#F4F4F4", label: "أولوية ٣" },
  }[priority];
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-[11px] font-semibold"
      style={{ color: colors.fg, backgroundColor: colors.bg }}
    >
      {colors.label}
    </span>
  );
}

export function AssessmentStatusBadge({ status }: { status: AssessmentStatus }) {
  const colors: Record<AssessmentStatus, { fg: string; bg: string }> = {
    pending: { fg: SUBTLE_TEXT, bg: "#F4F4F4" },
    in_progress: { fg: WARN, bg: WARN_SOFT },
    under_review: { fg: BRAND, bg: BRAND_SOFT },
    approved: { fg: SUCCESS, bg: SUCCESS_SOFT },
    rejected: { fg: DANGER, bg: DANGER_SOFT },
  };
  const c = colors[status];
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-[11px] font-semibold"
      style={{ color: c.fg, backgroundColor: c.bg }}
    >
      {ASSESSMENT_STATUS_AR[status]}
    </span>
  );
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const colors: Record<DocumentStatus, { fg: string; bg: string }> = {
    uploaded: { fg: SUBTLE_TEXT, bg: "#F4F4F4" },
    scanning: { fg: WARN, bg: WARN_SOFT },
    infected: { fg: DANGER, bg: DANGER_SOFT },
    clean: { fg: SUBTLE_TEXT, bg: "#F4F4F4" },
    extracting: { fg: WARN, bg: WARN_SOFT },
    embedding: { fg: WARN, bg: WARN_SOFT },
    ready: { fg: SUCCESS, bg: SUCCESS_SOFT },
    failed: { fg: DANGER, bg: DANGER_SOFT },
  };
  const c = colors[status];
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-[11px] font-semibold"
      style={{ color: c.fg, backgroundColor: c.bg }}
    >
      {DOCUMENT_STATUS_AR[status]}
    </span>
  );
}

export function NcaConditionalBadge() {
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-[11px] font-semibold"
      style={{ color: DANGER, backgroundColor: DANGER_SOFT }}
    >
      حسب لوائح الهيئة الوطنية للأمن السيبراني
    </span>
  );
}
