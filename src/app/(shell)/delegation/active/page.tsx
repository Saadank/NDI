"use client";

import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import { clearMyDelegation } from "@/lib/api/platform/delegation.api";
import { getCurrentUser, getUsers } from "@/lib/api/platform/users.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate } from "@/lib/utils/formatters";

export default function DelegationActivePage() {
  const { isReady } = useRoleGuard({ allow: ["data_owner", "dpo"] });
  const qc = useQueryClient();

  const meQuery = useQuery({
    queryKey: ["platform", "users", "me"],
    queryFn: getCurrentUser,
    enabled: isReady,
  });
  const usersQuery = useQuery({
    queryKey: ["platform", "users"],
    queryFn: () => getUsers({ page: 1, limit: 100 }),
    enabled: isReady,
  });
  const endEarly = useMutation({
    mutationFn: clearMyDelegation,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["platform", "users", "me"] }),
  });

  if (!isReady) return null;

  const me = meQuery.data as
    | undefined
    | (Record<string, unknown> & {
        delegation_to_user_id?: number | null;
        delegation_start?: string | null;
        delegation_end?: string | null;
      });

  const delegateId = me?.delegation_to_user_id ?? null;
  const delegate = (usersQuery.data?.data ?? []).find(
    (u) => u.id === String(delegateId) || (u as unknown as { id: number }).id === delegateId,
  );
  const start = me?.delegation_start ? new Date(me.delegation_start) : null;
  const end = me?.delegation_end ? new Date(me.delegation_end) : null;

  // Business days remaining (approximate: skip Fri+Sat)
  const businessDaysRemaining = (() => {
    if (!end) return 0;
    let count = 0;
    const cur = new Date();
    cur.setHours(0, 0, 0, 0);
    const fin = new Date(end);
    fin.setHours(0, 0, 0, 0);
    while (cur <= fin) {
      const day = cur.getDay();
      if (day !== 5 && day !== 6) count++;
      cur.setDate(cur.getDate() + 1);
    }
    return count;
  })();

  const initials = delegate
    ? `${(delegate.first_name?.[0] ?? "").toUpperCase()}${(delegate.last_name?.[0] ?? "").toUpperCase()}`
    : "??";

  const delegateName = delegate
    ? `${delegate.first_name ?? ""} ${delegate.last_name ?? ""}`.trim() || delegate.email
    : `User #${String(delegateId)}`;

  if (!delegateId || !start || !end) {
    return (
      <main className="flex flex-1 flex-col gap-6 px-60 py-10">
        <Breadcrumb items={[{ label: "Products", href: "/" }, { label: "Profile", href: "/profile" }, { label: "Delegation Settings" }]} />
        <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>
        <p className="text-sm text-auth-text-subtle">
          No active delegation.{" "}
          <Link href="/delegation" className="underline" style={{ color: "#D76736" }}>Set one up →</Link>
        </p>
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col gap-6 px-60 py-10">
      <Breadcrumb items={[{ label: "Products", href: "/" }, { label: "Profile", href: "/profile" }, { label: "Delegation Settings" }]} />
      <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>

      {/* Active banner */}
      <div
        className="flex items-center gap-3 rounded-lg px-4 py-3"
        style={{ backgroundColor: "#F0FAF0", border: "1px solid #C6E8C4" }}
      >
        <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: "#449235" }} />
        <p className="text-[13px]" style={{ color: "#2D6B21" }}>
          <span className="font-semibold">Delegation is active.</span>{" "}
          Your backup is acting on your behalf. All decisions are logged with both names in the audit trail.
        </p>
      </div>

      {/* Card */}
      <div
        className="flex flex-col gap-5 rounded-lg p-6"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center justify-between">
          <span className="text-[15px] font-semibold text-auth-text">Active delegation window</span>
          <span
            className="rounded-full px-3 py-0.5 text-[11px] font-semibold"
            style={{ backgroundColor: "#449235", color: "#FFFFFF" }}
          >
            Active
          </span>
        </div>

        {/* Backup person */}
        <div className="flex flex-col gap-1">
          <span className="text-[11px] font-medium uppercase tracking-[0.5px]" style={{ color: "#9E9E9E" }}>Backup</span>
          <div className="flex items-center gap-3">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-bold"
              style={{ backgroundColor: "#D7673626", color: "#D76736" }}
            >
              {initials}
            </div>
            <span className="text-[14px] font-semibold text-auth-text">{delegateName}</span>
            {(delegate as unknown as { ds_role?: string } | undefined)?.ds_role && (
              <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}>
                {(delegate as unknown as { ds_role?: string }).ds_role}
              </span>
            )}
          </div>
        </div>

        <div className="h-px" style={{ backgroundColor: "#EEEEEE" }} />

        {/* Active window */}
        <div className="flex flex-col gap-1">
          <span className="text-[11px] font-medium uppercase tracking-[0.5px]" style={{ color: "#9E9E9E" }}>Active window</span>
          <div className="flex items-center gap-2">
            <span className="text-[14px] text-auth-text">
              {formatDate(start.toISOString())} → {formatDate(end.toISOString())}
            </span>
            <span className="text-[13px] font-medium" style={{ color: "#D76736" }}>
              · {businessDaysRemaining} business day{businessDaysRemaining === 1 ? "" : "s"} remaining
            </span>
          </div>
        </div>

        <p className="text-[12px]" style={{ color: "#9E9E9E" }}>
          Your backup acts on all incoming approval assignments during this window. Both names appear on every audit-trail entry they create.
        </p>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link
            href="/delegation"
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium text-auth-text"
            style={{ borderColor: "#EEEEEE" }}
          >
            Edit window / backup
          </Link>
          <button
            type="button"
            onClick={() => endEarly.mutate()}
            disabled={endEarly.isPending}
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium disabled:opacity-50"
            style={{ borderColor: "#D76736", color: "#D76736" }}
          >
            {endEarly.isPending ? "Ending…" : "End early"}
          </button>
        </div>
      </div>
    </main>
  );
}
