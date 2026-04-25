import Link from "next/link";

import { AuthButton } from "@/components/shared/AuthButton";
import { AuthCard, AuthCardHeader } from "@/components/shared/AuthCard";
import { AuthField, AuthInput } from "@/components/shared/AuthField";

export default function LoginSsoPage() {
  return (
    <AuthCard>
      <AuthCardHeader
        title="Sign in with SSO"
        description="Enter your work email and we'll redirect you to your organisation's identity provider."
      />

      <form className="flex flex-col gap-5">
        <AuthField label="Work email" htmlFor="work-email">
          <AuthInput
            id="work-email"
            type="email"
            autoComplete="email"
            placeholder="name@company.com"
          />
        </AuthField>
      </form>

      <div className="flex flex-col items-center gap-[14px]">
        <AuthButton type="submit" variant="brand">
          Continue
        </AuthButton>
        <Link
          href="/login"
          className="text-[13px] font-normal text-auth-text-muted hover:text-auth-text"
        >
          ← Back to email sign-in
        </Link>
      </div>
    </AuthCard>
  );
}
