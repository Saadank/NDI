import Link from "next/link";
import { Shield, Info, Search, Calendar } from "lucide-react";

import { Breadcrumb } from "@/components/shared/Breadcrumb";

export default function DelegationSettingsPage() {
  return (
    <main className="flex-1 flex flex-col gap-6 px-[240px] py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Delegation" },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>

      {/* Role note */}
      <div
        className="flex items-center gap-2 rounded-md p-3"
        style={{ backgroundColor: "#F5F5F5" }}
      >
        <Shield className="h-4 w-4 shrink-0" style={{ color: "#9E9E9E" }} />
        <p className="text-xs font-normal" style={{ color: "#616161" }}>
          Available to Data Owners and the DPO only
        </p>
      </div>

      {/* Explainer */}
      <div
        className="flex gap-[10px] rounded-lg p-4"
        style={{ backgroundColor: "#FFF5F0", border: "1px solid #FDDCCC" }}
      >
        <Info className="h-4 w-4 shrink-0 mt-[1px]" style={{ color: "#D76736" }} />
        <div className="flex flex-col gap-1">
          <p className="text-[13px] font-normal" style={{ color: "#515157" }}>
            When delegation is on, your backup receives all incoming approval assignments.
          </p>
          <p className="text-[13px] font-normal" style={{ color: "#515157" }}>
            Every decision is logged under both names for a complete audit trail.
          </p>
        </div>
      </div>

      {/* Form card */}
      <section
        className="flex flex-col gap-6 rounded-lg p-8"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        {/* Backup Person */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium" style={{ color: "#616161" }}>
            Backup Person
          </label>
          <div
            className="flex h-10 items-center justify-between rounded-md px-3"
            style={{ border: "1px solid #EEEEEE" }}
          >
            <span className="text-sm font-normal" style={{ color: "#BABABA" }}>
              Search by name or email...
            </span>
            <Search className="h-4 w-4 shrink-0" style={{ color: "#BABABA" }} />
          </div>
          <p className="text-xs font-normal" style={{ color: "#9E9E9E" }}>
            Must have the same role capability — Data Owner or DPO
          </p>
        </div>

        {/* Delegation Period */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium" style={{ color: "#616161" }}>
            Delegation Period
          </label>
          <div className="flex gap-3">
            {/* Start Date */}
            <div className="flex flex-col gap-[6px] flex-1">
              <span className="text-[11px] font-normal" style={{ color: "#9E9E9E" }}>
                Start Date
              </span>
              <div
                className="flex h-10 items-center justify-between rounded-md px-3"
                style={{ border: "1px solid #EEEEEE" }}
              >
                <span className="text-sm font-normal text-auth-text">
                  21 Nov 2024
                </span>
                <Calendar className="h-4 w-4 shrink-0" style={{ color: "#BABABA" }} />
              </div>
            </div>

            {/* End Date */}
            <div className="flex flex-col gap-[6px] flex-1">
              <span className="text-[11px] font-normal" style={{ color: "#9E9E9E" }}>
                End Date
              </span>
              <div
                className="flex h-10 items-center justify-between rounded-md px-3"
                style={{ border: "1px solid #EEEEEE" }}
              >
                <span className="text-sm font-normal text-auth-text">
                  30 Nov 2024
                </span>
                <Calendar className="h-4 w-4 shrink-0" style={{ color: "#BABABA" }} />
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link
            href="/profile"
            className="inline-flex h-10 items-center rounded-md border border-auth-border bg-white px-5 text-sm font-medium text-auth-text hover:bg-auth-bg"
          >
            Cancel
          </Link>
          <button
            type="button"
            className="h-10 rounded-md px-5 text-sm font-medium text-white hover:opacity-90"
            style={{ backgroundColor: "#D76736" }}
          >
            Activate Delegation
          </button>
        </div>
      </section>
    </main>
  );
}
