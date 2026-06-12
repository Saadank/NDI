"use client";

/**
 * Business Glossary — shared visual primitives + design tokens.
 *
 * Tokens are lifted from the design handoff (assets/glossary.css :root) so the
 * glossary subtree matches the mockups pixel-for-pixel.  The glossary renders
 * LTR/English (the rest of NDMO is RTL/Arabic) — its route layout sets
 * dir="ltr".  Where the app already has a component we reuse it; these are the
 * glossary-specific bits the app shell doesn't provide.
 */
import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type {
  GlossaryTermStatus,
  GlossaryTermType,
} from "@/lib/types/ndmo-compliance/glossary";

// ---- tokens (design handoff) -------------------------------------------
export const T = {
  brand: "#D76736",
  brandHover: "#C15827",
  brandTint: "#FFF5F0",
  ai: "#8A4FD8",
  aiTint: "#F0E7FC",
  bg: "#FAFAF8",
  card: "#FFFFFF",
  primary: "#171717",
  mutedBg: "#F5F5F4",
  muted: "#737373",
  border: "#E7E5E1",
  placeholder: "#BABABA",
  success: "#449235",
  successBg: "#EAF3E8",
  warn: "#B7791F",
  warnBg: "#FBF3E4",
  danger: "#E7000B",
  dangerBg: "#FCEAEA",
  info: "#2563EB",
  infoBg: "#EAF0FD",
  enterprise: "#6B4FD8",
  domain: "#3E6FCB",
} as const;

// ---- status + type badges ----------------------------------------------

const STATUS_STYLE: Record<GlossaryTermStatus, { fg: string; bg: string; label: string }> = {
  draft: { fg: T.muted, bg: T.mutedBg, label: "Draft" },
  under_review: { fg: T.warn, bg: T.warnBg, label: "Under Review" },
  changes_requested: { fg: T.danger, bg: T.dangerBg, label: "Changes Requested" },
  approved: { fg: T.success, bg: T.successBg, label: "Approved" },
  deprecated: { fg: T.muted, bg: T.mutedBg, label: "Deprecated" },
};

export function StatusBadge({ status }: { status: GlossaryTermStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-semibold"
      style={{ color: s.fg, backgroundColor: s.bg }}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: s.fg }} />
      {s.label}
    </span>
  );
}

export function TypeBadge({ type }: { type: GlossaryTermType }) {
  const isEnt = type === "enterprise";
  return (
    <span
      className="inline-block rounded-full px-2.5 py-0.5 text-[12px] font-semibold"
      style={{
        color: isEnt ? T.enterprise : T.domain,
        backgroundColor: isEnt ? "#6B4FD814" : "#3E6FCB14",
      }}
    >
      {isEnt ? "Enterprise" : "Domain"}
    </span>
  );
}

export function DomainBadge({ name }: { name: string }) {
  return (
    <span
      className="inline-block rounded-full px-2.5 py-0.5 text-[12px] font-medium"
      style={{ color: T.muted, backgroundColor: T.mutedBg }}
    >
      {name}
    </span>
  );
}

// ---- layout primitives --------------------------------------------------

export function Card({
  children,
  className,
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={cn("rounded-[14px] border bg-white", className)}
      style={{ borderColor: T.border, boxShadow: "0 8px 32px rgba(0,0,0,.05)", ...style }}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  breadcrumb,
  title,
  subtitle,
  actions,
}: {
  breadcrumb?: ReactNode;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        {breadcrumb && (
          <div className="mb-1 text-[12px]" style={{ color: T.muted }}>
            {breadcrumb}
          </div>
        )}
        <h1 className="text-[23px] font-bold leading-tight" style={{ color: T.primary }}>
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 text-[14px]" style={{ color: T.muted }}>
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

type BtnVariant = "brand" | "outline" | "ghost" | "success" | "warn" | "danger" | "danger-outline";

const BTN_STYLE: Record<BtnVariant, React.CSSProperties> = {
  brand: { backgroundColor: T.brand, color: "#fff", borderColor: T.brand },
  outline: { backgroundColor: "#fff", color: T.primary, borderColor: T.border },
  ghost: { backgroundColor: "transparent", color: T.muted, borderColor: "transparent" },
  success: { backgroundColor: T.success, color: "#fff", borderColor: T.success },
  warn: { backgroundColor: T.warn, color: "#fff", borderColor: T.warn },
  danger: { backgroundColor: T.danger, color: "#fff", borderColor: T.danger },
  "danger-outline": { backgroundColor: "#fff", color: T.danger, borderColor: "#F3C8CA" },
};

export function Button({
  children,
  variant = "outline",
  size = "md",
  onClick,
  disabled,
  type = "button",
  className,
}: {
  children: ReactNode;
  variant?: BtnVariant;
  size?: "sm" | "md" | "lg";
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  const h = size === "lg" ? "h-[42px]" : size === "sm" ? "h-[32px]" : "h-[38px]";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        h,
        "inline-flex items-center justify-center gap-1.5 rounded-[8px] border px-3.5 text-[13.5px] font-semibold transition-opacity disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      style={BTN_STYLE[variant]}
    >
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        "h-[38px] w-full rounded-[8px] border bg-white px-3 text-[13.5px] outline-none focus:ring-2",
        props.className,
      )}
      style={{ borderColor: T.border, color: T.primary, ...props.style }}
    />
  );
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={cn(
        "w-full rounded-[8px] border bg-white px-3 py-2 text-[13.5px] outline-none focus:ring-2",
        props.className,
      )}
      style={{ borderColor: T.border, color: T.primary, minHeight: 96, ...props.style }}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={cn(
        "h-[38px] w-full rounded-[8px] border bg-white px-3 text-[13.5px] outline-none focus:ring-2",
        props.className,
      )}
      style={{ borderColor: T.border, color: T.primary, ...props.style }}
    />
  );
}

export function Label({ children, required }: { children: ReactNode; required?: boolean }) {
  return (
    <label className="mb-1.5 block text-[13px] font-medium" style={{ color: T.primary }}>
      {children}
      {required && <span style={{ color: T.brand }}> *</span>}
    </label>
  );
}

export function Banner({
  tone = "info",
  children,
}: {
  tone?: "info" | "warn" | "danger" | "success";
  children: ReactNode;
}) {
  const map = {
    info: { fg: T.info, bg: T.infoBg },
    warn: { fg: T.warn, bg: T.warnBg },
    danger: { fg: T.danger, bg: T.dangerBg },
    success: { fg: T.success, bg: T.successBg },
  }[tone];
  return (
    <div
      className="mb-4 rounded-[10px] px-4 py-3 text-[13.5px]"
      style={{ color: map.fg, backgroundColor: map.bg }}
    >
      {children}
    </div>
  );
}

// ---- modal + drawer -----------------------------------------------------

export function Modal({
  title,
  children,
  onClose,
  footer,
  width = 460,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  width?: number;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,.35)" }}>
      <div
        className="w-full rounded-[14px] bg-white p-5"
        style={{ maxWidth: width, boxShadow: "0 24px 64px rgba(0,0,0,.22)" }}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[16px] font-bold" style={{ color: T.primary }}>
            {title}
          </h3>
          <button onClick={onClose} className="text-[20px] leading-none" style={{ color: T.muted }}>
            ×
          </button>
        </div>
        <div className="text-[13.5px]" style={{ color: T.primary }}>
          {children}
        </div>
        {footer && <div className="mt-5 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

export function Drawer({
  title,
  children,
  onClose,
  footer,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(0,0,0,.35)" }}>
      <div className="h-full w-[460px] overflow-y-auto bg-white p-6" style={{ boxShadow: "-12px 0 32px rgba(0,0,0,.12)" }}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-[17px] font-bold" style={{ color: T.primary }}>
            {title}
          </h3>
          <button onClick={onClose} className="text-[22px] leading-none" style={{ color: T.muted }}>
            ×
          </button>
        </div>
        <div className="space-y-4">{children}</div>
        {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

export function Mono({ children }: { children: ReactNode }) {
  return (
    <span className="text-[12.5px]" style={{ fontFamily: "var(--font-geist-mono, ui-monospace, monospace)", color: T.muted }}>
      {children}
    </span>
  );
}

export function BreadcrumbLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="hover:underline" style={{ color: T.muted }}>
      {children}
    </Link>
  );
}
