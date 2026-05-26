"use client";

import * as React from "react";
import { Eye, EyeOff } from "lucide-react";

import { cn } from "@/lib/utils";

interface PasswordInputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  focused?: boolean;
  initialRevealed?: boolean;
}

export const PasswordInput = React.forwardRef<
  HTMLInputElement,
  PasswordInputProps
>(function PasswordInput(
  { className, focused, initialRevealed = false, ...props },
  ref,
) {
  const [revealed, setRevealed] = React.useState(initialRevealed);
  return (
    <div
      className={cn(
        "relative flex h-10 items-center rounded-md border bg-white",
        focused ? "border-brand ring-2 ring-brand/20" : "border-auth-border",
        className,
      )}
    >
      <input
        ref={ref}
        {...props}
        type={revealed ? "text" : "password"}
        className="h-full w-full rounded-md bg-transparent px-3 pr-10 text-sm text-auth-text outline-none"
      />
      <button
        type="button"
        onClick={() => setRevealed((v) => !v)}
        aria-label={revealed ? "Hide password" : "Show password"}
        className="absolute right-3 top-1/2 -translate-y-1/2"
        style={{ color: "#BABABA" }}
      >
        {revealed ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
      </button>
    </div>
  );
});
