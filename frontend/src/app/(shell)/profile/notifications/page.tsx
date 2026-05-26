"use client";

import Link from "next/link";
import { useState } from "react";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import {
  PrefHeader,
  PrefRow,
  type PrefChannel,
  type PrefRowData,
} from "@/components/features/profile/NotificationPrefs";

const initialRows: PrefRowData[] = [
  { id: "r1", label: "Request submitted to you for approval", value: "both" },
  {
    id: "r2",
    label: "A request you raised being approved or rejected",
    value: "in-app",
  },
  { id: "r3", label: "SLA approaching or breached", value: "both" },
  { id: "r4", label: "Delegation activating", value: "in-app" },
  { id: "r5", label: "Data ready to download", value: "in-app" },
  { id: "r6", label: "Retention expiring in 48 hours", value: "both" },
  { id: "r7", label: "A file deleted on expiry", value: "email" },
];

const shadedIds = new Set(["r3", "r6", "r7"]);

export default function NotificationPreferencesPage() {
  const [rows, setRows] = useState<PrefRowData[]>(initialRows);

  const update = (id: string, channel: PrefChannel) => {
    setRows((prev) =>
      prev.map((r) => (r.id === id ? { ...r, value: channel } : r)),
    );
  };

  return (
    <main className="flex-1 flex flex-col gap-6 px-[240px] py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Profile", href: "/profile" },
          { label: "Notification Preferences" },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">
        Notification Preferences
      </h1>

      <section className="flex flex-col rounded-lg border border-auth-border bg-white overflow-hidden">
        <PrefHeader />
        <div className="flex-1">
          {rows.map((row, i) => (
            <PrefRow
              key={row.id}
              row={row}
              shaded={shadedIds.has(row.id)}
              last={i === rows.length - 1}
              onChange={update}
            />
          ))}
        </div>

        <div className="flex justify-end gap-3 p-5 border-t border-auth-border">
          <Link
            href="/profile"
            className="inline-flex h-10 items-center rounded-md border border-auth-border bg-white px-5 text-sm font-medium text-auth-text hover:bg-auth-bg"
          >
            Discard
          </Link>
          <button
            type="button"
            className="h-10 rounded-md bg-brand px-5 text-sm font-medium text-white hover:bg-brand-hover"
          >
            Save Preferences
          </button>
        </div>
      </section>
    </main>
  );
}
