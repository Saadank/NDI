"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface AuthFieldProps {
  label: string;
  htmlFor: string;
  rightSlot?: React.ReactNode;
  children: React.ReactNode;
  error?: string;
  className?: string;
}

export function AuthField({
  label,
  htmlFor,
  rightSlot,
  children,
  error,
  className,
}: AuthFieldProps) {
  return (
    <div className={cn("flex flex-col gap-[6px]", className)}>
      <div className="flex items-center justify-between">
        <label
          htmlFor={htmlFor}
          className="text-[13px] font-medium text-auth-text"
        >
          {label}
        </label>
        {rightSlot}
      </div>
      {children}
      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}

type AuthInputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  hasTrailing?: boolean;
};

export const AuthInput = React.forwardRef<HTMLInputElement, AuthInputProps>(
  function AuthInput({ className, hasTrailing, ...props }, ref) {
    return (
      <input
        ref={ref}
        {...props}
        className={cn(
          "h-10 w-full rounded-md border border-auth-border bg-white px-3 text-sm text-auth-text",
          "placeholder:text-auth-text-placeholder",
          "outline-none transition-colors",
          "focus:border-brand/60 focus:ring-2 focus:ring-brand/20",
          hasTrailing && "pr-10",
          className,
        )}
      />
    );
  },
);
