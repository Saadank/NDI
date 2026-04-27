"use client";

import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { useState } from "react";

import { RequestsTable } from "@/components/features/data-sharing/RequestsTable";
import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useAuthStore } from "@/lib/store/auth.store";

type Tab = "mine" | "incoming" | "all";

export default function DataSharingPage() {
  const [tab, setTab] = useState<Tab>("mine");
  const requestsQuery = useRequests({ page: 1, limit: 50 });
  const myGroupId = useAuthStore((s) => s.user?.group_id ?? null);
  const myUserId = useAuthStore((s) => s.user?.id ?? null);

  const all = requestsQuery.data?.data ?? [];
  const counts = {
    mine: all.filter((r) => r.requester_id === myUserId).length,
    incoming: all.filter((r) => r.receiver_group_id === myGroupId).length,
    all: all.length,
  };

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #EEEEEE",
        }}
      >
        <h1 className="text-lg font-bold text-auth-text">My Requests</h1>
        <Link
          href="/data-sharing/new"
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          Raise New Request
        </Link>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <div className="flex" style={{ borderBottom: "1px solid #EEEEEE" }}>
          {(
            [
              { id: "mine", label: "I Raised", count: counts.mine },
              {
                id: "incoming",
                label: "My Department Owes",
                count: counts.incoming,
              },
              { id: "all", label: "All", count: counts.all },
            ] as { id: Tab; label: string; count: number }[]
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className="flex items-center gap-2 px-4 py-2.5"
              style={
                tab === t.id
                  ? { borderBottom: "2px solid #D76736", marginBottom: -1 }
                  : undefined
              }
            >
              <span
                className="text-sm"
                style={{
                  color: tab === t.id ? "#D76736" : "#9E9E9E",
                  fontWeight: tab === t.id ? 600 : 400,
                }}
              >
                {t.label}
              </span>
              <span
                className="flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold"
                style={
                  tab === t.id
                    ? { backgroundColor: "#D76736", color: "#FFFFFF" }
                    : { backgroundColor: "#EEEEEE", color: "#9E9E9E" }
                }
              >
                {t.count}
              </span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <div
            className="flex h-9 flex-1 items-center gap-2 rounded-md px-3"
            style={{
              backgroundColor: "#FFFFFF",
              border: "1px solid #EEEEEE",
            }}
          >
            <Search
              className="h-3.5 w-3.5 shrink-0"
              style={{ color: "#9E9E9E" }}
            />
            <span className="text-[13px]" style={{ color: "#BABABA" }}>
              Search requests…
            </span>
          </div>
        </div>

        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{
            backgroundColor: "#FFFFFF",
            border: "1px solid #EEEEEE",
          }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{
              backgroundColor: "#FAFAFA",
              borderBottom: "1px solid #EEEEEE",
            }}
          >
            <span
              className="flex-1 text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              REQUEST
            </span>
            <span
              className="w-40 text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              {tab === "incoming" ? "FROM DEPARTMENT" : "TO DEPARTMENT"}
            </span>
            <span
              className="w-[130px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              CLASSIFICATION
            </span>
            <span
              className="w-[150px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              STATUS
            </span>
            <span
              className="w-[100px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              SLA DUE
            </span>
          </div>

          <RequestsTable scope={tab} />
        </div>
      </div>
    </div>
  );
}
