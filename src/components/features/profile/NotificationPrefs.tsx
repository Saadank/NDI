"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export type PrefChannel = "in-app" | "email" | "both";

export interface PrefRowData {
  id: string;
  label: string;
  value: PrefChannel;
}

const CHANNELS: PrefChannel[] = ["in-app", "email", "both"];

interface RadioProps {
  checked: boolean;
}

function Radio({ checked }: RadioProps) {
  return (
    <span
      className={cn(
        "flex h-4 w-4 items-center justify-center rounded-full",
        checked ? "bg-brand" : "bg-white border-2",
      )}
      style={checked ? undefined : { borderColor: "#BABABA" }}
      aria-hidden
    />
  );
}

export function PrefHeader() {
  return (
    <div className="flex items-center border-b border-auth-border px-5 py-4">
      <p className="flex-1 text-xs font-semibold text-auth-text-subtle">
        Notification type
      </p>
      <div className="flex">
        {["In-app", "Email", "Both"].map((col) => (
          <span
            key={col}
            className="w-24 text-center text-xs font-semibold text-auth-text-subtle"
          >
            {col}
          </span>
        ))}
      </div>
    </div>
  );
}

interface PrefRowProps {
  row: PrefRowData;
  shaded?: boolean;
  last?: boolean;
  onChange?: (id: string, channel: PrefChannel) => void;
}

export function PrefRow({ row, shaded, last, onChange }: PrefRowProps) {
  return (
    <div
      className={cn(
        "flex h-[52px] items-center px-5",
        !last && "border-b border-auth-border",
      )}
      style={shaded ? { backgroundColor: "#FFFBF9" } : undefined}
    >
      <p className="flex-1 text-[13px] font-normal text-auth-text">
        {row.label}
      </p>
      <div className="flex">
        {CHANNELS.map((ch) => (
          <button
            key={ch}
            type="button"
            onClick={() => onChange?.(row.id, ch)}
            aria-label={ch}
            className="flex w-24 items-center justify-center"
          >
            <Radio checked={row.value === ch} />
          </button>
        ))}
      </div>
    </div>
  );
}
