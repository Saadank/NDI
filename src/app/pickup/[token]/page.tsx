"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock, Eye, EyeOff, ShieldCheck } from "lucide-react";

import { get, post } from "@/lib/api/client";

// ─── Types ────────────────────────────────────────────────────────

interface PickupInvitation {
  token: string;
  org_name: string;
  sender_name: string;
  sender_role: string;
  sender_dept: string;
  recipient_email: string;
  recipient_role: string;
  recipient_dept: string;
  expires_at: string;
  hours_remaining: number;
  status: "pending" | "accepted" | "expired";
}

interface AcceptBody {
  password: string;
  terms_accepted: boolean;
}

// ─── Helpers ─────────────────────────────────────────────────────

function hoursLabel(hours: number): string {
  if (hours <= 0) return "Expired";
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"}`;
  const days = Math.floor(hours / 24);
  const rem = hours % 24;
  if (rem === 0) return `${days} day${days === 1 ? "" : "s"}`;
  return `${days}d ${rem}h`;
}

function PasswordInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-md border px-3 pr-10 text-[13px] text-auth-text outline-none focus:border-[#D76736]"
        style={{ borderColor: "#EEEEEE" }}
      />
      <button
        type="button"
        tabIndex={-1}
        onClick={() => setShow((p) => !p)}
        className="absolute right-3 top-1/2 -translate-y-1/2"
        style={{ color: "#9E9E9E" }}
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────

export default function PickupPage() {
  const { token } = useParams<{ token: string }>();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const invitationQuery = useQuery({
    queryKey: ["pickup", token],
    queryFn: () => get<PickupInvitation>(`/api/v1/pickup/${token}`),
    retry: false,
  });

  const acceptMutation = useMutation({
    mutationFn: (body: AcceptBody) =>
      post(`/api/v1/pickup/${token}/accept`, body),
    onSuccess: () => setDone(true),
    onError: (e) =>
      setFormError(e instanceof Error ? e.message : "Something went wrong. Please try again."),
  });

  const inv = invitationQuery.data;

  // ── Loading ─────────────────────────────────────────────────────
  if (invitationQuery.isLoading) {
    return (
      <PickupShell>
        <div className="flex items-center justify-center py-20">
          <p className="text-sm" style={{ color: "#9E9E9E" }}>Loading invitation…</p>
        </div>
      </PickupShell>
    );
  }

  // ── Invalid token ───────────────────────────────────────────────
  if (invitationQuery.isError || !inv) {
    return (
      <PickupShell>
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <div
            className="flex h-14 w-14 items-center justify-center rounded-full"
            style={{ backgroundColor: "#FFF0F0" }}
          >
            <AlertTriangle className="h-7 w-7" style={{ color: "#D32F2F" }} />
          </div>
          <h2 className="text-lg font-bold text-auth-text">Invalid or expired link</h2>
          <p className="text-[13px]" style={{ color: "#9E9E9E", maxWidth: 340 }}>
            This invitation link is not valid or has already expired. Contact your administrator to resend the invitation.
          </p>
        </div>
      </PickupShell>
    );
  }

  // ── Expired ─────────────────────────────────────────────────────
  if (inv.status === "expired") {
    return (
      <PickupShell>
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <div
            className="flex h-14 w-14 items-center justify-center rounded-full"
            style={{ backgroundColor: "#FFFBEB" }}
          >
            <Clock className="h-7 w-7" style={{ color: "#D97706" }} />
          </div>
          <h2 className="text-lg font-bold text-auth-text">Invitation expired</h2>
          <p className="text-[13px]" style={{ color: "#9E9E9E", maxWidth: 340 }}>
            This invitation has expired. Please ask your administrator at{" "}
            <strong>{inv.org_name}</strong> to send a new invitation link.
          </p>
        </div>
      </PickupShell>
    );
  }

  // ── Already accepted / done ─────────────────────────────────────
  if (inv.status === "accepted" || done) {
    return (
      <PickupShell>
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <div
            className="flex h-14 w-14 items-center justify-center rounded-full"
            style={{ backgroundColor: "#F0FAF0" }}
          >
            <CheckCircle2 className="h-7 w-7" style={{ color: "#449235" }} />
          </div>
          <h2 className="text-lg font-bold text-auth-text">Account activated</h2>
          <p className="text-[13px]" style={{ color: "#9E9E9E", maxWidth: 340 }}>
            Your Datarix account has been set up. You can now sign in with your email and the password you just created.
          </p>
          <a
            href="/login"
            className="mt-2 flex h-10 items-center rounded-md px-6 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            Sign in
          </a>
        </div>
      </PickupShell>
    );
  }

  // ── Main: account setup ─────────────────────────────────────────
  const passwordsMatch = password === confirmPassword;
  const passwordStrong = password.length >= 8;
  const canSubmit =
    passwordStrong && passwordsMatch && termsAccepted && !acceptMutation.isPending;

  function handleSubmit() {
    setFormError(null);
    if (!passwordStrong) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    if (!passwordsMatch) {
      setFormError("Passwords do not match.");
      return;
    }
    if (!termsAccepted) {
      setFormError("Please accept the terms to continue.");
      return;
    }
    acceptMutation.mutate({ password, terms_accepted: true });
  }

  return (
    <PickupShell>
      <div
        className="flex flex-col gap-6 rounded-2xl bg-white p-8"
        style={{ boxShadow: "0 4px 24px #00000010", border: "1px solid #EEEEEE" }}
      >
        {/* Heading */}
        <div className="flex flex-col gap-1.5">
          <h1 className="text-[22px] font-bold text-auth-text leading-tight">
            You&apos;ve been invited to:{" "}
            <span style={{ color: "#D76736" }}>{inv.org_name}</span>
          </h1>
          <p className="text-[13px]" style={{ color: "#9E9E9E" }}>
            Verified by{" "}
            <span className="font-medium" style={{ color: "#515157" }}>
              {inv.sender_name}
            </span>{" "}
            · {inv.sender_role}, {inv.sender_dept}
          </p>
        </div>

        {/* Role badge */}
        <div className="flex">
          <span
            className="rounded-full px-3 py-1 text-[12px] font-semibold"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            {inv.recipient_role} · {inv.recipient_dept}
          </span>
        </div>

        {/* Divider */}
        <div style={{ height: 1, backgroundColor: "#EEEEEE" }} />

        {/* Form */}
        <div className="flex flex-col gap-4">
          {/* Email (read-only) */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">Email address</label>
            <input
              type="email"
              value={inv.recipient_email}
              readOnly
              className="h-10 w-full rounded-md border px-3 text-[13px] outline-none"
              style={{
                borderColor: "#EEEEEE",
                backgroundColor: "#FAFAFA",
                color: "#9E9E9E",
              }}
            />
          </div>

          {/* New password */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              New password <span style={{ color: "#D76736" }}>*</span>
            </label>
            <PasswordInput
              value={password}
              onChange={setPassword}
              placeholder="At least 8 characters"
            />
            {password.length > 0 && !passwordStrong && (
              <p className="text-[11px]" style={{ color: "#D32F2F" }}>
                Password must be at least 8 characters.
              </p>
            )}
          </div>

          {/* Confirm password */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-auth-text">
              Confirm password <span style={{ color: "#D76736" }}>*</span>
            </label>
            <PasswordInput
              value={confirmPassword}
              onChange={setConfirmPassword}
              placeholder="Repeat your password"
            />
            {confirmPassword.length > 0 && !passwordsMatch && (
              <p className="text-[11px]" style={{ color: "#D32F2F" }}>
                Passwords do not match.
              </p>
            )}
          </div>

          {/* Terms checkbox */}
          <label
            className="flex cursor-pointer items-start gap-2.5"
            style={{ color: "#515157" }}
          >
            <input
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-[#D76736]"
            />
            <span className="text-[13px]">
              I accept Datarix&apos;s{" "}
              <span className="underline" style={{ color: "#D76736" }}>
                terms of service
              </span>{" "}
              and{" "}
              <span className="underline" style={{ color: "#D76736" }}>
                PDPL processing notice
              </span>
            </span>
          </label>
        </div>

        {/* Error */}
        {(formError ?? (acceptMutation.isError && !formError)) && (
          <p className="text-[12px]" style={{ color: "#D32F2F" }}>
            {formError ?? (acceptMutation.error instanceof Error ? acceptMutation.error.message : "Something went wrong.")}
          </p>
        )}

        {/* Submit */}
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="flex h-11 w-full items-center justify-center rounded-md text-[14px] font-semibold text-white disabled:opacity-50"
          style={{ backgroundColor: "#D76736" }}
        >
          {acceptMutation.isPending ? "Setting up account…" : "Accept and continue"}
        </button>

        {/* Expiry notice */}
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
          <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
            Expires in {hoursLabel(inv.hours_remaining)} · If the link expires, ask your
            administrator to resend the invitation.
          </p>
        </div>
      </div>
    </PickupShell>
  );
}

// ─── Shell ────────────────────────────────────────────────────────

function PickupShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <span className="text-[17px] font-bold" style={{ color: "#D76736" }}>Datarix</span>
      </div>

      {/* Content */}
      <div className="mx-auto flex w-full max-w-[480px] flex-1 flex-col justify-center px-6 py-12">
        {children}
      </div>

      {/* Footer */}
      <div className="px-8 py-4" style={{ borderTop: "1px solid #EEEEEE" }}>
        <p className="text-center text-[11px]" style={{ color: "#BABABA" }}>
          Powered by Datarix · Secure data sharing in compliance with PDPL
        </p>
      </div>
    </div>
  );
}
