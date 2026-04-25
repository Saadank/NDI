import { Breadcrumb } from "@/components/shared/Breadcrumb";

export default function DelegationActivePage() {
  return (
    <main className="flex-1 flex flex-col gap-6 px-[240px] py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Delegation" },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">Delegation Settings</h1>

      {/* Status bar */}
      <div
        className="flex items-center gap-[10px] rounded-lg p-[14px]"
        style={{ backgroundColor: "#F0FAF0", border: "1px solid #C6E8C4" }}
      >
        <span
          className="inline-block h-2 w-2 shrink-0 rounded-[4px]"
          style={{ backgroundColor: "#449235" }}
        />
        <p className="text-[13px] font-normal" style={{ color: "#2D6B21" }}>
          Delegation is currently active — your backup is receiving all incoming approval requests.
        </p>
      </div>

      {/* Active card */}
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
            9 days remaining
          </span>
        </div>

        {/* Card body */}
        <div className="flex flex-col gap-5 p-6">
          {/* Backup person row */}
          <div className="flex items-center gap-[14px]">
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-bold"
              style={{ backgroundColor: "#D7673626", color: "#D76736" }}
            >
              KM
            </div>
            <div className="flex flex-col gap-[3px]">
              <p className="text-[15px] font-semibold text-auth-text">
                Khaled Al-Mutairi
              </p>
              <p className="text-[13px] font-normal" style={{ color: "#616161" }}>
                Data Owner · Finance Division
              </p>
            </div>
          </div>

          {/* Divider */}
          <div className="h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />

          {/* Period row */}
          <div className="flex items-center gap-[10px]">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4 shrink-0"
              style={{ color: "#9E9E9E" }}
            >
              <rect width="18" height="18" x="3" y="4" rx="2" ry="2" />
              <line x1="16" x2="16" y1="2" y2="6" />
              <line x1="8" x2="8" y1="2" y2="6" />
              <line x1="3" x2="21" y1="10" y2="10" />
            </svg>
            <span className="text-sm font-normal" style={{ color: "#515157" }}>
              21 Nov 2024 → 30 Nov 2024
            </span>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              className="h-10 rounded-md border px-5 text-sm font-medium text-auth-text hover:bg-auth-bg"
              style={{ borderColor: "#EEEEEE" }}
            >
              Edit Period
            </button>
            <button
              type="button"
              className="h-10 rounded-md border px-5 text-sm font-medium hover:bg-red-50"
              style={{ borderColor: "#D76736", color: "#D76736" }}
            >
              End Early
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
