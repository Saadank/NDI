"use client";

import Link from "next/link";
import { Check, CheckCircle2, Clock, Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { post } from "@/lib/api/client";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";

// ─── Types ────────────────────────────────────────────────────────

type TenantType = "government" | "semi_gov" | "private";
type Step = 1 | 2 | 3 | 4;

const PRODUCTS = [
  { id: "data_sharing", label: "Data Sharing Platform", desc: "Share datasets securely across departments with full audit trails." },
  { id: "data_quality", label: "Data Quality Profiling", desc: "Automated profiling and quality scoring for your data assets." },
  { id: "ndi", label: "NDMO Compliance (NDI Assessment)", desc: "Built-in assessment tools for NDMO regulatory compliance." },
  { id: "dsr", label: "Data Subject Rights (DSR)", desc: "Manage data subject access, correction, and erasure requests." },
] as const;

// ─── Step indicator ───────────────────────────────────────────────

function StepIndicator({ current }: { current: Step }) {
  const steps = [
    { n: 1 as Step, label: "Tenant Identity" },
    { n: 2 as Step, label: "Products" },
    { n: 3 as Step, label: "Org Admin Invite" },
  ];
  return (
    <div className="flex items-center gap-0">
      {steps.map((s, i) => {
        const done = current > s.n || current === 4;
        const active = current === s.n;
        return (
          <div key={s.n} className="flex items-center">
            <div className="flex items-center gap-2">
              <div
                className="flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold"
                style={
                  done
                    ? { backgroundColor: "#D76736", color: "#FFFFFF" }
                    : active
                      ? { backgroundColor: "#D76736", color: "#FFFFFF" }
                      : { backgroundColor: "#EEEEEE", color: "#9E9E9E" }
                }
              >
                {done ? <Check className="h-3 w-3" /> : s.n}
              </div>
              <span
                className="text-[12px] font-medium"
                style={{ color: done || active ? "#D76736" : "#9E9E9E" }}
              >
                {s.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className="mx-4 h-px w-24 flex-shrink-0"
                style={{ backgroundColor: current > s.n ? "#D76736" : "#EEEEEE" }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────

export default function PlatformOnboardPage() {
  const { isReady } = useRoleGuard({ allow: ["platform_admin"] });
  const router = useRouter();

  const [step, setStep] = useState<Step>(1);

  // Step 1
  const [nameEn, setNameEn] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [slug, setSlug] = useState("");
  const [tenantType, setTenantType] = useState<TenantType>("government");

  // Step 2
  const [products, setProducts] = useState<string[]>(["data_sharing"]);

  // Step 3
  const [adminEmail, setAdminEmail] = useState("");
  const [adminName, setAdminName] = useState("");

  // Result (step 4)
  const [result, setResult] = useState<{
    org_id?: string;
    tenant_slug?: string;
    invite_expires_at?: string;
  } | null>(null);

  const [error, setError] = useState<string | null>(null);

  const onboard = useMutation({
    mutationFn: () =>
      post("/api/v1/platform/tenants/onboard", {
        name: nameEn.trim(),
        name_ar: nameAr.trim() || undefined,
        slug: slug.trim(),
        tenant_type: tenantType,
        products,
        admin_email: adminEmail.trim(),
        admin_name: adminName.trim() || undefined,
      }),
    onSuccess: (data) => {
      setResult(data as typeof result);
      setStep(4);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed to onboard"),
  });

  if (!isReady) return null;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Vendor warning */}
      <div
        className="flex items-center gap-2 px-8 py-2"
        style={{ backgroundColor: "#FFFBEB", borderBottom: "1px solid #FCD34D" }}
      >
        <span className="text-[11px]" style={{ color: "#92400E" }}>
          Vendor view — metadata only. No access to organisation request content or uploaded files.
        </span>
      </div>

      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <h1 className="text-lg font-bold text-auth-text">Onboard Company</h1>
        {step === 4 && (
          <Link
            href="/platform/organisations"
            className="flex h-9 items-center gap-1.5 rounded-md px-4 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#449235" }}
          >
            <Check className="h-3.5 w-3.5" />
            Done · Return to Orgs
          </Link>
        )}
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col items-center overflow-auto px-8 py-10">
        {/* Step indicator */}
        <div className="mb-8">
          <StepIndicator current={step} />
        </div>

        <div
          className="w-full max-w-[620px] rounded-xl p-8"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          {step === 1 && (
            <div className="flex flex-col gap-5">
              <p className="text-[12px] font-semibold" style={{ color: "#9E9E9E" }}>Step 1 of 3 · Tenant Identity</p>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">
                  Legal name (English) <span style={{ color: "#D76736" }}>*</span>
                </label>
                <input
                  value={nameEn}
                  onChange={(e) => {
                    setNameEn(e.target.value);
                    if (!slug) setSlug(e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""));
                  }}
                  placeholder="e.g. Ministry of Health"
                  className="h-10 rounded-md border px-3 text-[13px] outline-none focus:border-[#D76736]"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">
                  Legal name (Arabic) — optional
                </label>
                <input
                  value={nameAr}
                  onChange={(e) => setNameAr(e.target.value)}
                  dir="rtl"
                  placeholder="مثال: وزارة الصحة"
                  className="h-10 rounded-md border px-3 text-[13px] outline-none focus:border-[#D76736]"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">
                  Slug <span style={{ color: "#D76736" }}>*</span>
                </label>
                <div
                  className="flex h-10 items-center rounded-md border px-3"
                  style={{ borderColor: "#EEEEEE" }}
                >
                  <span className="text-[12px]" style={{ color: "#BABABA" }}>app.datarix.io / </span>
                  <input
                    value={slug}
                    onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                    placeholder="ministry-of-health"
                    className="flex-1 bg-transparent text-[13px] outline-none"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-[12px] font-semibold text-auth-text">
                  Tenant type <span style={{ color: "#D76736" }}>*</span>
                </label>
                <div className="flex gap-3">
                  {(["government", "semi_gov", "private"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setTenantType(t)}
                      className="flex h-9 flex-1 items-center justify-center rounded-md text-[13px] font-medium"
                      style={
                        tenantType === t
                          ? { backgroundColor: "#D76736", color: "#FFFFFF" }
                          : { border: "1px solid #EEEEEE", color: "#515157" }
                      }
                    >
                      {t === "government" ? "Government" : t === "semi_gov" ? "Semi-government" : "Private"}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex justify-between">
                <button
                  type="button"
                  onClick={() => router.push("/platform/organisations")}
                  className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
                  style={{ borderColor: "#EEEEEE", color: "#616161" }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  disabled={!nameEn.trim() || !slug.trim()}
                  className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
                  style={{ backgroundColor: "#D76736" }}
                >
                  Continue →
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-5">
              <div>
                <p className="text-[12px] font-semibold" style={{ color: "#9E9E9E" }}>Step 2 of 3 · Products</p>
                <p className="mt-1 text-[12px]" style={{ color: "#515157" }}>
                  Select all products this organisation has purchased. Each product is activated independently.
                </p>
              </div>

              <div className="flex flex-col gap-2">
                {PRODUCTS.map((p) => {
                  const checked = products.includes(p.id);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() =>
                        setProducts((prev) =>
                          prev.includes(p.id) ? prev.filter((x) => x !== p.id) : [...prev, p.id],
                        )
                      }
                      className="flex items-start gap-3 rounded-lg p-4 text-left"
                      style={{
                        border: `1px solid ${checked ? "#D76736" : "#EEEEEE"}`,
                        backgroundColor: checked ? "#FFF5F0" : "#FFFFFF",
                      }}
                    >
                      <div
                        className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded"
                        style={
                          checked
                            ? { backgroundColor: "#D76736" }
                            : { border: "2px solid #BABABA" }
                        }
                      >
                        {checked && <Check className="h-2.5 w-2.5 text-white" />}
                      </div>
                      <div>
                        <p className="text-[13px] font-semibold" style={{ color: checked ? "#D76736" : "#1A1A1A" }}>
                          {p.label}
                        </p>
                        <p className="text-[11px]" style={{ color: "#9E9E9E" }}>{p.desc}</p>
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="flex justify-between">
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
                  style={{ borderColor: "#EEEEEE", color: "#616161" }}
                >
                  ← Back
                </button>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  disabled={products.length === 0}
                  className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
                  style={{ backgroundColor: "#D76736" }}
                >
                  Continue →
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="flex flex-col gap-5">
              <p className="text-[12px] font-semibold" style={{ color: "#9E9E9E" }}>Step 3 of 3 · Org Admin Invite</p>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">
                  Email address <span style={{ color: "#D76736" }}>*</span>
                </label>
                <input
                  type="email"
                  value={adminEmail}
                  onChange={(e) => setAdminEmail(e.target.value)}
                  placeholder="name@organisation.gov.sa"
                  className="h-10 rounded-md border px-3 text-[13px] outline-none focus:border-[#D76736]"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-auth-text">
                  Full name — optional
                </label>
                <input
                  value={adminName}
                  onChange={(e) => setAdminName(e.target.value)}
                  placeholder="e.g. Khalid Al-Otaibi"
                  className="h-10 rounded-md border px-3 text-[13px] outline-none focus:border-[#D76736]"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </div>

              <div
                className="flex items-start gap-2 rounded-md p-3 text-[11px]"
                style={{ backgroundColor: "#F0FAF0", border: "1px solid #BBF7D0", color: "#2D6B21" }}
              >
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  An invitation email will be sent with a 72-hour magic link. The recipient sets a password via the
                  identity provider and lands on the portal to complete setup.
                </span>
              </div>

              {error && <p className="text-xs text-red-600">{error}</p>}

              <div className="flex justify-between">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
                  style={{ borderColor: "#EEEEEE", color: "#616161" }}
                >
                  ← Back
                </button>
                <button
                  type="button"
                  onClick={() => onboard.mutate()}
                  disabled={!adminEmail.trim() || onboard.isPending}
                  className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
                  style={{ backgroundColor: "#D76736" }}
                >
                  <Send className="h-3.5 w-3.5" />
                  {onboard.isPending ? "Sending…" : "Send invitation & finish"}
                </button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="flex flex-col gap-5">
              <div>
                <p className="text-[13px] font-bold text-auth-text">Provisioning complete</p>
                <p className="mt-1 text-[12px]" style={{ color: "#515157" }}>
                  All steps completed successfully. The invitation email has been sent.
                </p>
              </div>

              <div className="flex flex-col gap-3">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#449235" }} />
                  <div>
                    <p className="text-[13px] font-semibold" style={{ color: "#449235" }}>Organisation created</p>
                    <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      {nameEn} · {slug} · {tenantType === "government" ? "Government" : tenantType === "semi_gov" ? "Semi-Gov" : "Private"}
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#449235" }} />
                  <div>
                    <p className="text-[13px] font-semibold" style={{ color: "#449235" }}>Tenant configured</p>
                    <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      {products.length} products activated:{" "}
                      {products.map((p) => PRODUCTS.find((x) => x.id === p)?.label ?? p).join(", ")}
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#449235" }} />
                  <div>
                    <p className="text-[13px] font-semibold" style={{ color: "#449235" }}>Invitation email sent</p>
                    <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      Sent to {adminEmail} · Magic link valid for 72 hours.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <Clock className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#D76736" }} />
                  <div>
                    <p className="text-[13px] font-semibold" style={{ color: "#D76736" }}>Awaiting Org Admin acceptance</p>
                    <p className="text-[11px]" style={{ color: "#D76736" }}>
                      Link expires in 71 h 55 m. Resend if needed.
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex justify-end">
                <Link
                  href="/platform/organisations"
                  className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white"
                  style={{ backgroundColor: "#449235" }}
                >
                  <Check className="h-3.5 w-3.5" />
                  Done · Return to Orgs
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
