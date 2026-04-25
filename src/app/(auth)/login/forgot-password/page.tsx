import Link from "next/link";
import { Check } from "lucide-react";

import { AuthCard } from "@/components/shared/AuthCard";

export default function ForgotPasswordPage() {
  return (
    <AuthCard>
      <div className="flex flex-col items-center gap-5">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-success-soft">
          <Check className="h-7 w-7 text-success" strokeWidth={2.5} />
        </div>
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-[22px] font-bold leading-tight text-auth-text">
            Check your email
          </h1>
          <p className="text-sm font-normal leading-[1.5] text-auth-text-muted">
            We&apos;ve sent a password reset link to your email address. The
            link is valid for 60 minutes — check your spam folder if you
            don&apos;t see it.
          </p>
        </div>
      </div>

      <div className="flex flex-col items-center gap-[10px]">
        <Link
          href="#"
          className="text-[13px] font-normal text-brand hover:underline"
        >
          Resend email
        </Link>
        <Link
          href="/login"
          className="text-[13px] font-normal text-auth-text-muted hover:text-auth-text"
        >
          ← Back to sign-in
        </Link>
      </div>
    </AuthCard>
  );
}
