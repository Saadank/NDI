"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Calendar, Search } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import { setMyDelegation } from "@/lib/api/platform/delegation.api";
import { getUsers } from "@/lib/api/platform/users.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";

export default function DelegationSettingsPage() {
  const { isReady } = useRoleGuard({ allow: ["data_owner", "dpo"] });
  const router = useRouter();
  const qc = useQueryClient();

  const [delegateId, setDelegateId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const usersQuery = useQuery({
    queryKey: ["platform", "users"],
    queryFn: () => getUsers({ page: 1, limit: 100 }),
    staleTime: 60_000,
    enabled: isReady,
  });

  const activate = useMutation({
    mutationFn: () =>
      setMyDelegation({
        delegate_to_user_id: delegateId,
        delegation_start: start ? new Date(start).toISOString() : null,
        delegation_end: end ? new Date(end).toISOString() : null,
        reason: null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["platform", "users", "me"] });
      router.push("/delegation/active");
    },
  });

  if (!isReady) return null;

  const users = usersQuery.data?.data ?? [];
  const filtered = search
    ? users.filter((u) =>
        `${u.first_name ?? ""} ${u.last_name ?? ""} ${u.email}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      )
    : users;

  const canActivate = delegateId !== null && !!start && !!end;

  return (
    <main className="flex flex-1 flex-col gap-6 px-60 py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Profile", href: "/profile" },
          { label: "Delegation Settings" },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>

      <div
        className="flex flex-col gap-5 rounded-lg p-6"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        {/* Card header */}
        <div className="flex items-center justify-between">
          <span className="text-[15px] font-semibold text-auth-text">Set up delegation</span>
          <span
            className="rounded-full px-3 py-0.5 text-[11px] font-semibold"
            style={{ backgroundColor: "#F5F5F5", color: "#9E9E9E" }}
          >
            Inactive
          </span>
        </div>

        <p className="text-[13px] leading-relaxed" style={{ color: "#616161" }}>
          While delegation is active, your nominated backup receives all incoming approval
          assignments and acts on them in your place. Every decision they make is tagged with
          both your name and theirs in the audit trail.
        </p>

        {/* Backup person */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-medium" style={{ color: "#616161" }}>
            Backup person
          </label>
          <div className="relative">
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setDelegateId(null);
              }}
              placeholder="Search by name or email…"
              className="h-10 w-full rounded-md border px-3 pr-9 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
            <Search className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "#BABABA" }} />
            {search && !delegateId && filtered.length > 0 && (
              <div
                className="absolute left-0 top-full z-10 mt-1 w-full overflow-hidden rounded-md shadow-md"
                style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
              >
                {filtered.slice(0, 6).map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => {
                      setDelegateId(Number(u.id));
                      setSearch(`${u.first_name ?? ""} ${u.last_name ?? ""}`.trim() || u.email);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-[13px] hover:bg-[#FAFAFA]"
                  >
                    <div
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
                      style={{ backgroundColor: "#D7673626", color: "#D76736" }}
                    >
                      {(u.first_name?.[0] ?? "").toUpperCase()}{(u.last_name?.[0] ?? "").toUpperCase()}
                    </div>
                    <div className="flex flex-col">
                      <span className="font-medium text-auth-text">
                        {u.first_name} {u.last_name}
                      </span>
                      <span className="text-[11px]" style={{ color: "#9E9E9E" }}>{u.email}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Date range */}
        <div className="flex gap-4">
          <div className="flex flex-1 flex-col gap-1.5">
            <label className="text-[12px] font-medium" style={{ color: "#616161" }}>Start date</label>
            <div
              className="flex h-10 items-center gap-2 rounded-md border px-3"
              style={{ borderColor: "#EEEEEE" }}
            >
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="flex-1 bg-transparent text-[13px] outline-none"
                placeholder="DD / MM / YYYY"
              />
              <Calendar className="h-4 w-4 shrink-0" style={{ color: "#BABABA" }} />
            </div>
          </div>
          <div className="flex flex-1 flex-col gap-1.5">
            <label className="text-[12px] font-medium" style={{ color: "#616161" }}>End date</label>
            <div
              className="flex h-10 items-center gap-2 rounded-md border px-3"
              style={{ borderColor: "#EEEEEE" }}
            >
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="flex-1 bg-transparent text-[13px] outline-none"
                placeholder="DD / MM / YYYY"
              />
              <Calendar className="h-4 w-4 shrink-0" style={{ color: "#BABABA" }} />
            </div>
          </div>
        </div>

        {/* View past delegations */}
        <Link
          href="/delegation/expired"
          className="flex items-center justify-between text-[13px]"
          style={{ color: "#9E9E9E" }}
        >
          View past delegations
          <span>›</span>
        </Link>

        {/* Activate button */}
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => activate.mutate()}
            disabled={!canActivate || activate.isPending}
            className="h-10 rounded-md px-6 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: "#D76736" }}
          >
            {activate.isPending ? "Saving…" : "Activate delegation"}
          </button>
        </div>
      </div>
    </main>
  );
}
