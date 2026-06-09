"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import axios from "axios";

import { AuthButton } from "@/components/shared/AuthButton";
import { AuthCard, AuthCardHeader } from "@/components/shared/AuthCard";
import { AuthField, AuthInput } from "@/components/shared/AuthField";
import { OrDivider } from "@/components/shared/OrDivider";
import { useLogin } from "@/lib/hooks/platform/useAuth";

// Pulls the most useful error string out of an axios error so the user sees
// what the *backend* actually said (e.g. "User not registered on the
// platform"), not a hardcoded message that hides the real cause.
function describeLoginError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)
      ?.detail;
    if (detail) return detail;
    if (err.response?.status === 401) return "Invalid email or password.";
    if (err.code === "ERR_NETWORK")
      return "Cannot reach the backend at " +
        (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") +
        ". Is it running?";
    return `Login failed (${err.response?.status ?? "network error"}).`;
  }
  if (err instanceof Error) return err.message;
  return "Login failed.";
}

const schema = z.object({
  username: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();
  const loginMutation = useLogin();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  const onSubmit = handleSubmit((values) => {
    loginMutation.mutate(values, {
      onSuccess: () => {
        // Land on the Product Portal ("/") so the user picks a product first,
        // unless the middleware bounced them here from a protected deep link
        // (?next=…), in which case return them there.  The startsWith("/")
        // guard prevents an open redirect to an external URL.
        const next = new URLSearchParams(window.location.search).get("next");
        router.push(next && next.startsWith("/") ? next : "/");
      },
    });
  });

  return (
    <AuthCard>
      <AuthCardHeader
        title="Sign in to Datarix"
        description="Welcome back. Enter your credentials to continue."
      />

      <form className="flex flex-col gap-5" onSubmit={onSubmit}>
        <AuthField
          label="Email address"
          htmlFor="username"
          error={errors.username?.message}
        >
          <AuthInput
            id="username"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            {...register("username")}
          />
        </AuthField>

        <AuthField
          label="Password"
          htmlFor="password"
          error={errors.password?.message}
          rightSlot={
            <Link
              href="/login/forgot-password"
              className="text-xs font-normal text-brand hover:underline"
            >
              Forgot password?
            </Link>
          }
        >
          <div className="relative">
            <AuthInput
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="••••••••"
              hasTrailing
              {...register("password")}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-auth-text-subtle hover:text-auth-text-muted"
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
        </AuthField>

        {loginMutation.isError && (
          <p className="text-sm text-red-600">
            {describeLoginError(loginMutation.error)}
          </p>
        )}

        <div className="flex flex-col gap-3">
          <AuthButton
            type="submit"
            variant="brand"
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? "Signing in…" : "Sign in"}
          </AuthButton>

          <OrDivider />

          <Link href="/login/sso" className="contents">
            <AuthButton type="button" variant="outline">
              Continue with SSO
            </AuthButton>
          </Link>
        </div>
      </form>
    </AuthCard>
  );
}
