"use client";

import Link from "next/link";

import { AuthButton } from "@/components/shared/AuthButton";
import { AuthCard, AuthCardHeader } from "@/components/shared/AuthCard";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp";

export default function LoginTotpPage() {
  return (
    <AuthCard className="gap-6">
      <AuthCardHeader
        title="Two-factor authentication"
        description="Enter the 6-digit code from your authenticator app to complete sign-in."
      />

      <div className="flex flex-col items-center gap-3">
        <p className="text-center text-xs font-normal text-auth-text-subtle">
          Signed in as ahmed.alqahtani@aramco.com ·{" "}
          <Link
            href="/login"
            className="hover:text-auth-text-muted hover:underline"
          >
            Not you? Sign out
          </Link>
        </p>

        <InputOTP maxLength={6} containerClassName="w-full">
          <InputOTPGroup className="w-full gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <InputOTPSlot
                key={i}
                index={i}
                className="h-12 w-full rounded-md border-auth-border bg-white text-lg"
              />
            ))}
          </InputOTPGroup>
        </InputOTP>
      </div>

      <div className="flex flex-col items-center gap-[14px]">
        <AuthButton type="submit" variant="brand">
          Verify
        </AuthButton>
        <div className="flex items-center gap-2 text-xs text-auth-text-muted">
          <Link href="#" className="hover:text-auth-text hover:underline">
            Use a backup code
          </Link>
          <span className="text-auth-text-placeholder">·</span>
          <Link href="#" className="hover:text-auth-text hover:underline">
            Resend / switch method
          </Link>
        </div>
      </div>
    </AuthCard>
  );
}
