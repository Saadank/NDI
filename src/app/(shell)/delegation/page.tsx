"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Calendar, Info, Search, Shield } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import {
  clearMyDelegation,
  setMyDelegation,
} from "@/lib/api/platform/delegation.api";
import { getUsers } from "@/lib/api/platform/users.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useQuery } from "@tanstack/react-query";

export default function DelegationSettingsPage() {
  // BRD §2.3: only data owners and the DPO can set out-of-office delegation.
  const { isReady } = useRoleGuard({ allow: ["data_owner", "dpo"] });
  const router = useRouter();
  const qc = useQueryClient();

  const [delegateId, setDelegateId] = useState<number | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  // List teammates the caller can delegate to. Backend filters by tenant.
  const usersQuery = useQuery({
    queryKey: ["platform", "users"],
    queryFn: () => getUsers({ page: 1, limit: 100 }),
    staleTime: 60_000,
  });

  const activate = useMutation({
    mutationFn: () =>
      setMyDelegation({
        delegate_to_user_id: delegateId,
        delegation_start: start ? new Date(start).toISOString() : null,
        delegation_end: end ? new Date(end).toISOString() : null,
        reason: reason.trim() || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform", "users", "me"] });
      router.push("/delegation/active");
    },
    onError: (e) =>
      setError(e instanceof Error ? e.message : "Failed to activate"),
  });

  const cancel = useMutation({
    mutationFn: clearMyDelegation,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform", "users", "me"] });
      router.push("/profile");
    },
  });

  if (!isReady) return null;

  const canActivate = delegateId !== null && start && end;

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
        className="flex items-center gap-2 rounded-md p-3"
        style={{ backgroundColor: "#F5F5F5" }}
      >
        <Shield className="h-4 w-4 shrink-0" style={{ color: "#9E9E9E" }} />
        <p className="text-xs font-normal" style={{ color: "#616161" }}>
          Available to Data Owners and the DPO only
        </p>
      </div>

      <div
        className="flex gap-[10px] rounded-lg p-4"
        style={{ backgroundColor: "#FFF5F0", border: "1px solid #FDDCCC" }}
      >
        <Info
          className="h-4 w-4 shrink-0 mt-[1px]"
          style={{ color: "#D76736" }}
        />
        <div className="flex flex-col gap-1">
          <p className="text-[13px]" style={{ color: "#515157" }}>
            When delegation is on, your backup receives all incoming approval
            assignments.
          </p>
          <p className="text-[13px]" style={{ color: "#515157" }}>
            Every decision is logged under both names for a complete audit
            trail.
          </p>
        </div>
      </div>

      <section
        className="flex flex-col gap-6 rounded-lg p-8"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium" style={{ color: "#616161" }}>
            Backup Person
          </label>
          <div className="relative">
            <select
              value={delegateId ?? ""}
              onChange={(e) =>
                setDelegateId(e.target.value ? Number(e.target.value) : null)
              }
              className="h-10 w-full appearance-none rounded-md border bg-white pl-3 pr-9 text-sm outline-none"
              style={{ borderColor: "#EEEEEE" }}
            >
              <option value="">
                {usersQuery.isLoading
                  ? "Loading users…"
                  : "Choose a teammate…"}
              </option>
              {(usersQuery.data?.data ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.first_name} {u.last_name} ({u.email})
                </option>
              ))}
            </select>
            <Search
              className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2"
              style={{ color: "#BABABA" }}
            />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium" style={{ color: "#616161" }}>
            Delegation Period
          </label>
          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-[6px]">
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                Start Date
              </span>
              <div
                className="flex h-10 items-center justify-between rounded-md px-3"
                style={{ border: "1px solid #EEEEEE" }}
              >
                <input
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  className="flex-1 bg-transparent text-sm outline-none"
                />
                <Calendar
                  className="h-4 w-4 shrink-0"
                  style={{ color: "#BABABA" }}
                />
              </div>
            </div>

            <div className="flex flex-1 flex-col gap-[6px]">
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                End Date
              </span>
              <div
                className="flex h-10 items-center justify-between rounded-md px-3"
                style={{ border: "1px solid #EEEEEE" }}
              >
                <input
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  className="flex-1 bg-transparent text-sm outline-none"
                />
                <Calendar
                  className="h-4 w-4 shrink-0"
                  style={{ color: "#BABABA" }}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium" style={{ color: "#616161" }}>
            Reason (optional)
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. annual leave"
            className="h-10 w-full rounded-md border px-3 text-sm outline-none"
            style={{ borderColor: "#EEEEEE" }}
          />
        </div>

        {error && (
          <p className="text-xs text-red-600">{error}</p>
        )}

        <div className="flex justify-between">
          <button
            type="button"
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending}
            className="inline-flex h-10 items-center rounded-md border bg-white px-4 text-sm font-medium hover:bg-auth-bg"
            style={{ borderColor: "#EEEEEE", color: "#B91C1C" }}
          >
            {cancel.isPending ? "Clearing…" : "Clear delegation"}
          </button>

          <div className="flex gap-3">
            <Link
              href="/profile"
              className="inline-flex h-10 items-center rounded-md border border-auth-border bg-white px-5 text-sm font-medium text-auth-text hover:bg-auth-bg"
            >
              Cancel
            </Link>
            <button
              type="button"
              onClick={() => activate.mutate()}
              disabled={!canActivate || activate.isPending}
              className="h-10 rounded-md px-5 text-sm font-medium text-white"
              style={{
                backgroundColor: canActivate ? "#D76736" : "#D0D0D0",
                cursor: canActivate ? "pointer" : "not-allowed",
              }}
            >
              {activate.isPending ? "Saving…" : "Activate Delegation"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
