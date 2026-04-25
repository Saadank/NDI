import Link from "next/link";

import { Breadcrumb } from "@/components/shared/Breadcrumb";

export default function DelegationExpiredPage() {
  return (
    <main className="flex-1 flex flex-col gap-6 px-[240px] py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Delegation" },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>

      {/* Expired bar */}
      <div
        className="flex items-center gap-[10px] rounded-lg p-[14px]"
        style={{ backgroundColor: "#F5F5F5", border: "1px solid #EEEEEE" }}
      >
        <span
          className="inline-block h-2 w-2 shrink-0 rounded-[4px]"
          style={{ backgroundColor: "#BABABA" }}
        />
        <p className="text-[13px] font-normal" style={{ color: "#616161" }}>
          This delegation window ended on 30 Nov 2024. No requests are being routed to a backup.
        </p>
      </div>

      {/* Expired card */}
      <section
        className="flex flex-col rounded-lg overflow-hidden"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        {/* Card header */}
        <div
          className="flex items-center justify-between px-6 py-5"
          style={{ borderBottom: "1px solid #EEEEEE" }}
        >
          <div
            className="rounded-xl px-[10px] py-1"
            style={{ backgroundColor: "#EEEEEE" }}
          >
            <span className="text-[11px] font-semibold" style={{ color: "#616161" }}>
              Expired
            </span>
          </div>
          <span className="text-xs font-normal" style={{ color: "#9E9E9E" }}>
            21 Nov → 30 Nov 2024 · 9 days
          </span>
        </div>

        {/* Card body */}
        <div className="flex flex-col gap-5 p-6">
          {/* Backup person row */}
          <div className="flex items-center gap-[14px]">
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-bold"
              style={{ backgroundColor: "#EEEEEE", color: "#9E9E9E" }}
            >
              KM
            </div>
            <div className="flex flex-col gap-[3px]">
              <p className="text-[15px] font-semibold" style={{ color: "#515157" }}>
                Khaled Al-Mutairi
              </p>
              <p className="text-[13px] font-normal" style={{ color: "#9E9E9E" }}>
                Data Owner · Finance Division
              </p>
            </div>
          </div>

          {/* Divider */}
          <div className="h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />

          {/* Stats row */}
          <div className="flex gap-8">
            <div className="flex flex-col gap-1">
              <span className="text-[22px] font-bold text-auth-text">14</span>
              <span className="text-xs font-normal" style={{ color: "#9E9E9E" }}>
                Approvals handled by backup
              </span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[22px] font-bold text-auth-text">9</span>
              <span className="text-xs font-normal" style={{ color: "#9E9E9E" }}>
                Days covered
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end">
            <Link
              href="/delegation"
              className="inline-flex h-10 items-center rounded-md px-5 text-sm font-medium text-white hover:opacity-90"
              style={{ backgroundColor: "#D76736" }}
            >
              Set Up New Delegation
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
