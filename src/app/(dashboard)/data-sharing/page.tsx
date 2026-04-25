import Link from "next/link";
import { Plus, Search } from "lucide-react";

import { RequestsTable } from "@/components/features/data-sharing/RequestsTable";

export default function DataSharingPage() {
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
              Search requests...
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

          <RequestsTable />
        </div>
      </div>
    </div>
  );
}
