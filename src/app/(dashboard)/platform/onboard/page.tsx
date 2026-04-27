"use client";

import { CheckCircle2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { post } from "@/lib/api/client";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { RoleBadge } from "@/components/shared/RoleBadge";

interface OnboardPayload {
  organisation_name: string;
  slug: string;
  admin_email: string;
  admin_first_name: string;
  admin_last_name: string;
  plan: string;
}

const BASE = "/api/v1/platform/tenants/onboard";

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[13px] font-medium text-auth-text">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}

export default function PlatformOnboardPage() {
  const { isReady } = useRoleGuard({ allow: ["platform_admin"] });
  const router = useRouter();

  const [form, setForm] = useState<OnboardPayload>({
    organisation_name: "",
    slug: "",
    admin_email: "",
    admin_first_name: "",
    admin_last_name: "",
    plan: "standard",
  });
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof OnboardPayload>(k: K, v: OnboardPayload[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const onboardMutation = useMutation({
    mutationFn: () => post<{ id: string }>(BASE, form),
    onSuccess: () => setSuccess(true),
    onError: (err: Error) => setError(err.message || "Failed to onboard organisation."),
  });

  if (!isReady) return null;

  if (success) {
    return (
      <div className="flex flex-1 items-center justify-center" style={{ backgroundColor: "#FFFFF9" }}>
        <div className="flex flex-col items-center gap-4 text-center">
          <CheckCircle2 className="h-16 w-16" style={{ color: "#449235" }} />
          <h2 className="text-lg font-bold text-auth-text">Organisation onboarded!</h2>
          <p className="text-sm" style={{ color: "#9E9E9E" }}>
            An invitation email has been sent to the admin account.
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => { setSuccess(false); setForm({ organisation_name: "", slug: "", admin_email: "", admin_first_name: "", admin_last_name: "", plan: "standard" }); }}
              className="h-9 rounded-md border px-4 text-[13px]"
              style={{ borderColor: "#EEEEEE", color: "#515157" }}
            >
              Onboard Another
            </button>
            <button
              type="button"
              onClick={() => router.push("/platform/organisations")}
              className="h-9 rounded-md px-4 text-[13px] font-medium text-white"
              style={{ backgroundColor: "#D76736" }}
            >
              View Organisations
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center px-8 gap-3"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <h1 className="text-lg font-bold text-auth-text">Onboard Company</h1>
        <RoleBadge label="Platform Admin" />
      </div>

      <div className="flex flex-1 justify-center overflow-auto px-8 py-8">
        <div className="w-full max-w-[560px] flex flex-col gap-8">
          {/* Organisation details */}
          <div
            className="flex flex-col gap-4 rounded-lg p-6"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <h2 className="text-[13px] font-semibold text-auth-text">Organisation Details</h2>
            <Field label="Organisation Name" required>
              <input
                type="text"
                value={form.organisation_name}
                onChange={(e) => {
                  set("organisation_name", e.target.value);
                  if (!form.slug) set("slug", e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""));
                }}
                placeholder="e.g. Acme Corporation"
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
              />
            </Field>
            <Field label="Slug" required>
              <input
                type="text"
                value={form.slug}
                onChange={(e) => set("slug", e.target.value)}
                placeholder="e.g. acme-corp"
                className="h-9 rounded-md border px-3 text-[13px] outline-none font-mono"
                style={{ borderColor: "#EEEEEE" }}
              />
              <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
                Used in URLs and system identifiers. Lowercase letters, numbers, and hyphens only.
              </p>
            </Field>
            <Field label="Plan">
              <select
                value={form.plan}
                onChange={(e) => set("plan", e.target.value)}
                className="h-9 rounded-md border bg-white px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
              >
                <option value="standard">Standard</option>
                <option value="professional">Professional</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </Field>
          </div>

          {/* Admin account */}
          <div
            className="flex flex-col gap-4 rounded-lg p-6"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <h2 className="text-[13px] font-semibold text-auth-text">Admin Account</h2>
            <div className="flex gap-3">
              <Field label="First Name" required>
                <input
                  type="text"
                  value={form.admin_first_name}
                  onChange={(e) => set("admin_first_name", e.target.value)}
                  placeholder="First"
                  className="h-9 rounded-md border px-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </Field>
              <Field label="Last Name" required>
                <input
                  type="text"
                  value={form.admin_last_name}
                  onChange={(e) => set("admin_last_name", e.target.value)}
                  placeholder="Last"
                  className="h-9 rounded-md border px-3 text-[13px] outline-none"
                  style={{ borderColor: "#EEEEEE" }}
                />
              </Field>
            </div>
            <Field label="Email Address" required>
              <input
                type="email"
                value={form.admin_email}
                onChange={(e) => set("admin_email", e.target.value)}
                placeholder="admin@company.com"
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
              />
            </Field>
          </div>

          {error && (
            <div
              className="rounded-md p-3 text-xs"
              style={{ backgroundColor: "#FEF2F2", border: "1px solid #FCA5A5", color: "#991B1B" }}
            >
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => router.push("/platform/organisations")}
              className="h-9 rounded-md border px-4 text-[13px]"
              style={{ borderColor: "#EEEEEE", color: "#515157" }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => onboardMutation.mutate()}
              disabled={
                !form.organisation_name || !form.slug || !form.admin_email || onboardMutation.isPending
              }
              className="h-9 rounded-md px-6 text-[13px] font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: "#D76736" }}
            >
              {onboardMutation.isPending ? "Onboarding…" : "Onboard Company"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
