"use client";

import { ChevronDown, UserCheck, FileText, Scale, HeartPulse, Landmark, ShieldCheck, X, Info } from "lucide-react";

interface Props {
  ownDeptError?: boolean;
  showLegalModal?: boolean;
  personalDataYes?: boolean;
  showDpia?: boolean;
  classification?: string;
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="text-[11px] font-semibold tracking-[0.8px] uppercase"
      style={{ color: "#9E9E9E" }}
    >
      {children}
    </p>
  );
}

function FieldLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="text-xs font-medium" style={{ color: "#616161" }}>
      {children}
      {required && <span className="ml-0.5" style={{ color: "#D76736" }}>*</span>}
    </label>
  );
}

function Radio({ checked }: { checked: boolean }) {
  return (
    <span
      className="flex h-4 w-4 items-center justify-center rounded-full"
      style={
        checked
          ? { backgroundColor: "#D76736" }
          : { border: "2px solid #BABABA", backgroundColor: "#FFFFFF" }
      }
    >
      {checked && <span className="h-[6px] w-[6px] rounded-full bg-white" />}
    </span>
  );
}

const LEGAL_BASIS_ITEMS = [
  {
    icon: <UserCheck className="h-4 w-4" />,
    iconBg: "#FFF5F0",
    iconColor: "#D76736",
    title: "Consent",
    desc: "The data subject has given clear consent for this specific purpose.",
  },
  {
    icon: <FileText className="h-4 w-4" />,
    iconBg: "#EEF2FF",
    iconColor: "#4F6BED",
    title: "Contract",
    desc: "Processing is necessary to perform or prepare a contract with the data subject.",
  },
  {
    icon: <Scale className="h-4 w-4" />,
    iconBg: "#FFF7E6",
    iconColor: "#D97706",
    title: "Legal obligation",
    desc: "Processing is required to comply with a legal duty (e.g. NDMO regulations, SAMA rules).",
  },
  {
    icon: <HeartPulse className="h-4 w-4" />,
    iconBg: "#FFF0F0",
    iconColor: "#EF4444",
    title: "Vital interest",
    desc: "Processing is necessary to protect someone's life or physical integrity.",
  },
  {
    icon: <Landmark className="h-4 w-4" />,
    iconBg: "#F0FAF0",
    iconColor: "#449235",
    title: "Public interest",
    desc: "Processing is necessary for a public task or the exercise of official authority.",
  },
  {
    icon: <ShieldCheck className="h-4 w-4" />,
    iconBg: "#F5F0FF",
    iconColor: "#7C3AED",
    title: "Legitimate interest",
    desc: "Your organisation has a genuine and proportionate interest — use only if no override risk.",
  },
];

export function RaiseRequestStep1({
  ownDeptError,
  showLegalModal,
  personalDataYes,
  showDpia,
  classification = "internal",
}: Props) {
  const classif = classification === "sensitive" ? "sensitive" : classification;

  return (
    <div className="relative flex flex-col gap-4">
      {/* REQUEST DETAILS */}
      <SectionHeader>Request Details</SectionHeader>

      {/* Title */}
      <div className="flex flex-col gap-[6px]">
        <FieldLabel required>Title</FieldLabel>
        <input
          type="text"
          placeholder="Short, descriptive name for this request"
          className="h-9 w-full rounded-md border px-3 text-[13px] text-auth-text outline-none placeholder:text-[#BABABA]"
          style={{ borderColor: "#EEEEEE" }}
        />
      </div>

      {/* Purpose */}
      <div className="flex flex-col gap-[6px]">
        <FieldLabel required>Purpose</FieldLabel>
        <textarea
          placeholder="Explain why you need this data and how it will be used..."
          className="h-16 w-full resize-none rounded-md border p-3 text-[13px] text-auth-text outline-none placeholder:text-[#BABABA]"
          style={{ borderColor: "#EEEEEE" }}
        />
      </div>

      {/* Priority */}
      <div className="flex flex-col gap-2">
        <FieldLabel required>Priority</FieldLabel>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Radio checked={true} />
            <span className="text-[13px] font-normal text-auth-text">Normal</span>
          </div>
          <div className="flex items-center gap-2">
            <Radio checked={false} />
            <span className="text-[13px] font-normal" style={{ color: "#515157" }}>Urgent</span>
            <span className="text-xs" style={{ color: "#9E9E9E" }}>(requires justification)</span>
          </div>
        </div>
      </div>

      <div className="h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />

      {/* SHARING DETAILS */}
      <SectionHeader>Sharing Details</SectionHeader>

      <div className="flex gap-6">
        {/* Sharing type */}
        <div className="flex flex-1 flex-col gap-2">
          <FieldLabel>Sharing type</FieldLabel>
          <div className="flex items-center gap-5">
            <div className="flex items-center gap-2">
              <Radio checked={true} />
              <span className="text-[13px] text-auth-text">Internal</span>
            </div>
            <div className="flex items-center gap-2">
              <Radio checked={false} />
              <span className="text-[13px]" style={{ color: "#515157" }}>External</span>
            </div>
          </div>
        </div>

        {/* Receiver department */}
        <div className="flex flex-1 flex-col gap-[6px]">
          <FieldLabel>Receiver department</FieldLabel>
          <div
            className="flex h-9 items-center justify-between rounded-md px-3"
            style={{
              border: `1px solid ${ownDeptError ? "#EF4444" : "#EEEEEE"}`,
            }}
          >
            <span
              className="text-[13px]"
              style={{ color: ownDeptError ? "#070709" : "#BABABA" }}
            >
              {ownDeptError ? "Finance" : "Select department..."}
            </span>
            <ChevronDown className="h-[14px] w-[14px]" style={{ color: "#9E9E9E" }} />
          </div>
          {ownDeptError && (
            <p className="text-xs" style={{ color: "#EF4444" }}>
              You cannot raise a request to your own department.
            </p>
          )}
        </div>
      </div>

      {/* Data classification */}
      <div className="flex flex-col gap-2">
        <FieldLabel required>Data classification</FieldLabel>
        <div className="flex items-center gap-5">
          {(["public", "internal", "confidential", "sensitive"] as const).map((opt) => {
            const checked = classif === opt;
            return (
              <div key={opt} className="flex items-center gap-2">
                <Radio checked={checked} />
                <span
                  className="text-[13px]"
                  style={{ color: checked ? "#070709" : "#515157" }}
                >
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* DPIA banner — shown when Sensitive is selected */}
      {showDpia && (
        <div className="flex flex-col gap-2.5">
          {/* Alert box */}
          <div
            className="flex gap-2.5 rounded-md p-3"
            style={{ backgroundColor: "#FFF5F0", border: "1px solid #FFCDB8" }}
          >
            <Info className="h-4 w-4 shrink-0 mt-0.5" style={{ color: "#D76736" }} />
            <div className="flex flex-col gap-1">
              <p className="text-xs font-semibold" style={{ color: "#D76736" }}>
                DPIA confirmation required
              </p>
              <p className="text-xs" style={{ color: "#515157" }}>
                Sensitive data requires a completed Data Protection Impact Assessment before submission.
              </p>
            </div>
          </div>
          {/* Checkbox */}
          <div className="flex items-center gap-2">
            <span
              className="flex h-4 w-4 shrink-0 items-center justify-center rounded"
              style={{ backgroundColor: "#D76736" }}
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 5L4 7L8 3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span className="text-[13px] text-auth-text">
              I confirm a DPIA has been reviewed and approved for this Sensitive data request
            </span>
          </div>
        </div>
      )}

      <div className="h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />

      {/* LEGAL & COMPLIANCE */}
      <SectionHeader>Legal &amp; Compliance</SectionHeader>

      {/* Legal basis */}
      <div className="flex flex-col gap-[6px]">
        <div className="flex items-center justify-between">
          <FieldLabel required>Legal basis</FieldLabel>
          <button type="button" className="text-xs font-medium" style={{ color: "#D76736" }}>
            Help me pick &rsaquo;
          </button>
        </div>
        <div
          className="flex h-9 items-center justify-between rounded-md px-3"
          style={{ border: "1px solid #EEEEEE" }}
        >
          <span className="text-[13px]" style={{ color: "#BABABA" }}>
            Select legal basis...
          </span>
          <ChevronDown className="h-[14px] w-[14px]" style={{ color: "#9E9E9E" }} />
        </div>
      </div>

      {/* Personal data + Retention */}
      <div className="flex gap-6">
        {/* Personal data toggle */}
        <div className="flex flex-1 flex-col gap-2">
          <FieldLabel>Personal data involved</FieldLabel>
          <div className="flex items-center gap-2">
            <span
              className="text-[13px]"
              style={{ color: personalDataYes ? "#9E9E9E" : "#070709", fontWeight: personalDataYes ? "400" : "600" }}
            >
              No
            </span>
            <div
              className="flex h-[22px] w-10 items-center rounded-full px-0.5"
              style={{
                backgroundColor: personalDataYes ? "#D76736" : "#EEEEEE",
                justifyContent: personalDataYes ? "flex-end" : "flex-start",
              }}
            >
              <div className="h-[18px] w-[18px] rounded-full bg-white shadow-sm" />
            </div>
            <span
              className="text-[13px]"
              style={{ color: personalDataYes ? "#070709" : "#9E9E9E", fontWeight: personalDataYes ? "600" : "400" }}
            >
              Yes
            </span>
          </div>
        </div>

        {/* Retention period */}
        <div className="flex flex-1 flex-col gap-[6px]">
          <FieldLabel required>Requested retention period</FieldLabel>
          <div
            className="flex h-9 items-center justify-between rounded-md px-3"
            style={{ border: "1px solid #EEEEEE" }}
          >
            <span className="text-[13px]" style={{ color: "#BABABA" }}>
              e.g. 90 days, 1 year, Indefinite...
            </span>
            <ChevronDown className="h-[14px] w-[14px]" style={{ color: "#9E9E9E" }} />
          </div>
        </div>
      </div>

      {/* Personal data extra fields — shown when toggle is ON */}
      {personalDataYes && (
        <>
          {/* Estimated data subjects */}
          <div className="flex flex-col gap-[6px]">
            <FieldLabel required>Estimated number of data subjects</FieldLabel>
            <input
              type="text"
              placeholder="e.g. 500, 1,000–5,000, Unknown"
              className="h-9 w-full rounded-md border px-3 text-[13px] text-auth-text outline-none placeholder:text-[#BABABA]"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>

          {/* Categories of personal data */}
          <div className="flex flex-col gap-[6px]">
            <FieldLabel required>Categories of personal data</FieldLabel>
            <div
              className="flex flex-wrap items-center gap-2 rounded-md px-3 py-2"
              style={{ border: "1px solid #D76736" }}
            >
              {["Health data", "Financial records"].map((tag) => (
                <span
                  key={tag}
                  className="flex items-center gap-1 rounded px-2 py-0.5 text-xs"
                  style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
                >
                  {tag}
                  <X className="h-2.5 w-2.5" />
                </span>
              ))}
              <span className="text-xs" style={{ color: "#BABABA" }}>
                + Add category
              </span>
            </div>
          </div>
        </>
      )}

      {/* Legal basis modal overlay */}
      {showLegalModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ backgroundColor: "#07070966" }}
        >
          <div
            className="flex flex-col rounded-xl overflow-hidden"
            style={{
              backgroundColor: "#FFFFFF",
              border: "1px solid #EEEEEE",
              width: 600,
            }}
          >
            {/* Modal header */}
            <div
              className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: "1px solid #EEEEEE" }}
            >
              <div className="flex flex-col gap-0.5">
                <h2 className="text-base font-bold text-auth-text">
                  Which legal basis applies?
                </h2>
                <p className="text-[13px] font-normal" style={{ color: "#9E9E9E" }}>
                  Under PDPL, one of these six bases must cover your data sharing.
                </p>
              </div>
              <button type="button" style={{ color: "#9E9E9E" }}>
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal body */}
            <div className="flex flex-col">
              {LEGAL_BASIS_ITEMS.map((item, i) => (
                <div
                  key={item.title}
                  className="flex items-center gap-3 px-6 py-4"
                  style={
                    i < LEGAL_BASIS_ITEMS.length - 1
                      ? { borderBottom: "1px solid #EEEEEE" }
                      : undefined
                  }
                >
                  <div
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
                    style={{ backgroundColor: item.iconBg, color: item.iconColor }}
                  >
                    {item.icon}
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <p className="text-[13px] font-semibold text-auth-text">{item.title}</p>
                    <p className="text-xs font-normal" style={{ color: "#9E9E9E" }}>
                      {item.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Modal footer */}
            <div
              className="flex justify-end px-6 py-3"
              style={{ borderTop: "1px solid #EEEEEE" }}
            >
              <button
                type="button"
                className="h-9 rounded-md border px-4 text-[13px] font-medium"
                style={{ borderColor: "#EEEEEE", color: "#616161" }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
