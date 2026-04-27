"use client";

import Link from "next/link";
import { Calendar } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import { clearMyDelegation } from "@/lib/api/platform/delegation.api";
import { getCurrentUser, getUsers } from "@/lib/api/platform/users.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";

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
  const cancel = useMutation({
    mutationFn: clearMyDelegation,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["platform", "users", "me"] }),
  });

  if (!isReady) return null;

  // The auth_user payload includes delegation fields when the user has set
  // one. We look up the delegate's name in the users list so we can show
  // their initials and full name.
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

  const daysRemaining = end
    ? Math.max(
        0,
        Math.ceil((end.getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
      )
    : 0;

  if (!delegateId || !start || !end) {
    return (
      <main className="flex-1 flex flex-col gap-6 px-12 py-10">
        <Breadcrumb
          items={[
            { label: "Products", href: "/" },
            { label: "Delegation" },
          ]}
        />
        <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>
        <p className="text-sm text-auth-text-subtle">
          You have no active delegation.{" "}
          <Link href="/delegation" className="text-brand hover:underline">
            Set one up →
          </Link>
        </p>
      </main>
    );
  }

  const initials = delegate
    ? `${(delegate.first_name?.[0] ?? "").toUpperCase()}${(delegate.last_name?.[0] ?? "").toUpperCase()}`
    : "??";

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
        style={{ backgroundColor: "#F0FAF0", border: "1px solid #C6E8C4" }}
      >
        <span
          className="inline-block h-2 w-2 shrink-0 rounded-[4px]"
          style={{ backgroundColor: "#449235" }}
        />
        <p className="text-[13px] font-normal" style={{ color: "#2D6B21" }}>
          Delegation is currently active — your backup is receiving all incoming
          approval requests.
        </p>
      </div>

      <section
        className="flex flex-col rounded-lg overflow-hidden"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div
          className="flex items-center justify-between px-6 py-5"
          style={{ borderBottom: "1px solid #EEEEEE" }}
        >
          <div
            className="flex items-center gap-[6px] rounded-xl px-[10px] py-1"
            style={{ backgroundColor: "#449235" }}
          >
            <span
              className="inline-block h-[6px] w-[6px] shrink-0 rounded-[3px]"
              style={{ backgroundColor: "#FFFFFF" }}
            />
            <span className="text-[11px] font-semibold text-white">Active</span>
          </div>
          <span className="text-xs font-normal" style={{ color: "#9E9E9E" }}>
            {daysRemaining} day{daysRemaining === 1 ? "" : "s"} remaining
          </span>
        </div>

        <div className="flex flex-col gap-5 p-6">
          <div className="flex items-center gap-[14px]">
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-bold"
              style={{ backgroundColor: "#D7673626", color: "#D76736" }}
            >
              {initials}
            </div>
            <div className="flex flex-col gap-[3px]">
              <p className="text-[15px] font-semibold text-auth-text">
                {delegate
                  ? `${delegate.first_name ?? ""} ${delegate.last_name ?? ""}`.trim() ||
                    delegate.email
                  : `User #${delegateId}`}
              </p>
              <p className="text-[13px] font-normal" style={{ color: "#616161" }}>
                {delegate?.email ?? ""}
              </p>
            </div>
          </div>

          <div className="h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />

          <div className="flex items-center gap-[10px]">
            <Calendar className="h-4 w-4 shrink-0" style={{ color: "#9E9E9E" }} />
            <span className="text-sm font-normal" style={{ color: "#515157" }}>
              {start.toLocaleDateString()} → {end.toLocaleDateString()}
            </span>
          </div>

          <div className="flex justify-end gap-3">
            <Link
              href="/delegation"
              className="inline-flex h-10 items-center rounded-md border px-5 text-sm font-medium text-auth-text hover:bg-auth-bg"
              style={{ borderColor: "#EEEEEE" }}
            >
              Edit
            </Link>
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="h-10 rounded-md border px-5 text-sm font-medium hover:bg-red-50"
              style={{ borderColor: "#D76736", color: "#D76736" }}
            >
              {cancel.isPending ? "Ending…" : "End Early"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
