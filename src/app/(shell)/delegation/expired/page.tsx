"use client";

import Link from "next/link";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";

// The backend doesn't yet expose a "past delegations" history endpoint, so
// this page is intentionally minimal — it deep-links to the active screen
// and the setup wizard. Once /platform/users/me/delegation/history lands,
// we'll wire the historical card here.
export default function DelegationExpiredPage() {
  const { isReady } = useRoleGuard({ allow: ["data_owner", "dpo"] });
  if (!isReady) return null;

  return (
    <main className="flex-1 flex flex-col gap-6 px-12 py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Delegation" },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>

      <div
        className="flex items-center gap-[10px] rounded-lg p-[14px]"
        style={{ backgroundColor: "#F5F5F5", border: "1px solid #EEEEEE" }}
      >
        <span
          className="inline-block h-2 w-2 shrink-0 rounded-[4px]"
          style={{ backgroundColor: "#BABABA" }}
        />
        <p className="text-[13px] font-normal" style={{ color: "#616161" }}>
          No active delegation. Past delegations are available in the audit
          trail.
        </p>
      </div>

      <div className="flex justify-end gap-3">
        <Link
          href="/delegation/active"
          className="inline-flex h-10 items-center rounded-md border px-5 text-sm font-medium text-auth-text hover:bg-auth-bg"
          style={{ borderColor: "#EEEEEE" }}
        >
          View active
        </Link>
        <Link
          href="/delegation"
          className="inline-flex h-10 items-center rounded-md px-5 text-sm font-medium text-white hover:opacity-90"
          style={{ backgroundColor: "#D76736" }}
        >
          Set Up New Delegation
        </Link>
      </div>
    </main>
  );
}
