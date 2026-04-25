import * as React from "react";

import { cn } from "@/lib/utils";

type ButtonVariant = "brand" | "outline";

interface AuthButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export const AuthButton = React.forwardRef<
  HTMLButtonElement,
  AuthButtonProps
>(function AuthButton(
  { variant = "brand", className, children, ...props },
  ref,
) {
  const base =
    "inline-flex h-10 w-full items-center justify-center rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40";
  const variants: Record<ButtonVariant, string> = {
    brand:
      "bg-brand text-brand-foreground hover:bg-brand-hover active:bg-brand-hover",
    outline:
      "border border-auth-border bg-white text-auth-text hover:bg-auth-bg",
  };

  return (
    <button
      ref={ref}
      {...props}
      className={cn(base, variants[variant], className)}
    >
      {children}
    </button>
  );
});
