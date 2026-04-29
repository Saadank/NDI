"use client";

import { ChevronDown, FileText, Heart, Info, Save, Scale, ShieldCheck, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { createRequest } from "@/lib/api/products/data-sharing/requests.api";
import {
  DATA_CLASSIFICATIONS,
  LEGAL_BASIS_OPTIONS,
} from "@/lib/utils/constants";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";
import { useNewRequestStore } from "@/lib/store/new-request.store";
import type {
  CreateShareRequestBody,
  DataClassification,
  LegalBasis,
  SharingType,
} from "@/lib/types/data-sharing/request.types";

function FieldLabel({
  children,
  required,
}: {
  children: React.ReactNode;
  required?: boolean;
}) {
  return (
    <label className="text-xs font-medium" style={{ color: "#616161" }}>
      {children}
      {required && (
        <span className="ml-0.5" style={{ color: "#D76736" }}>
          *
        </span>
      )}
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

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="text-[11px] font-semibold uppercase tracking-[0.8px]"
      style={{ color: "#9E9E9E" }}
    >
      {children}
    </p>
  );
}

const LEGAL_BASIS_INFO: {
  value: LegalBasis;
  label: string;
  description: string;
  icon: React.ReactNode;
  iconBg: string;
}[] = [
  {
    value: "consent",
    label: "Consent",
    description: "Your data subjects have given clear consent for the specific purpose.",
    icon: <Users className="h-3.5 w-3.5 text-white" />,
    iconBg: "#D76736",
  },
  {
    value: "contract",
    label: "Contract",
    description: "Processing is necessary to perform or prepare a contract with the data subject.",
    icon: <FileText className="h-3.5 w-3.5 text-white" />,
    iconBg: "#3B82F6",
  },
  {
    value: "legal_obligation",
    label: "Legal obligation",
    description: "Processing is required to comply with a legal duty (e.g. NDMO regulations, SAMA rules).",
    icon: <Scale className="h-3.5 w-3.5 text-white" />,
    iconBg: "#D76736",
  },
  {
    value: "vital_interest",
    label: "Vital interest",
    description: "Processing is necessary to protect someone's life or physical integrity.",
    icon: <Heart className="h-3.5 w-3.5 text-white" />,
    iconBg: "#8B5CF6",
  },
  {
    value: "public_interest",
    label: "Public interest",
    description: "Processing is necessary for a public task or the exercise of official authority.",
    icon: <ShieldCheck className="h-3.5 w-3.5 text-white" />,
    iconBg: "#449235",
  },
  {
    value: "legitimate_interest",
    label: "Legitimate interest",
    description: "Your organisation has a genuine and proportionate interest — use only if no overriding risk.",
    icon: <ShieldCheck className="h-3.5 w-3.5 text-white" />,
    iconBg: "#3B82F6",
  },
];

function LegalBasisModal({
  onClose,
  onSelect,
}: {
  onClose: () => void;
  onSelect: (v: LegalBasis) => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
    >
      <div
        className="flex w-[480px] flex-col gap-4 rounded-lg p-6"
        style={{ backgroundColor: "#FFFFFF" }}
      >
        <div className="flex flex-col gap-1">
          <h2 className="text-[15px] font-semibold text-auth-text">
            Which legal basis applies?
          </h2>
          <p className="text-xs" style={{ color: "#9E9E9E" }}>
            Under PDPL, all of these six bases must cover your data sharing.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          {LEGAL_BASIS_INFO.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => { onSelect(opt.value); onClose(); }}
              className="flex items-start gap-3 rounded-md p-3 text-left transition-colors hover:bg-[#FAFAFA]"
              style={{ border: "1px solid #EEEEEE" }}
            >
              <span
                className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
                style={{ backgroundColor: opt.iconBg }}
              >
                {opt.icon}
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="text-[13px] font-semibold text-auth-text">
                  {opt.label}
                </span>
                <span className="text-[12px]" style={{ color: "#9E9E9E" }}>
                  {opt.description}
                </span>
              </div>
            </button>
          ))}
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md border px-5 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#515157" }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export function Step1_BasicInfo() {
  // Raising new requests is restricted to requesters and data owners. DPOs
  // and org admins still need to log in but are bounced back to "/" if they
  // hit this URL directly.
  const { isReady } = useRoleGuard({ allow: ["requester", "data_owner"] });
  const router = useRouter();
  const form = useNewRequestStore();
  const setField = useNewRequestStore((s) => s.set);

  const myGroupId = useAuthStore((s) => s.user?.group_id ?? null);
  const groupsQuery = useGroups();

  if (!isReady) return null;

  const isSensitive = form.data_classification === "sensitive";

  const ownDeptError =
    form.receiver_group_id !== null &&
    myGroupId !== null &&
    String(form.receiver_group_id) === String(myGroupId);

  const canProceed =
    form.title.trim().length > 0 &&
    form.purpose.trim().length > 0 &&
    !!form.receiver_group_id &&
    !ownDeptError &&
    (!isSensitive || form.dpia_confirmed) &&
    (!(isSensitive || form.data_classification === "confidential") ||
      form.legal_basis.length > 0) &&
    (!form.personal_data_involved ||
      (form.legal_basis.length > 0 &&
        form.estimated_data_subjects !== null));

  const goNext = () => {
    if (!canProceed) return;
    router.push("/data-sharing/new/step-2");
  };

  const [savingDraft, setSavingDraft] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [showLegalModal, setShowLegalModal] = useState(false);

  // Step 1 "Save as Draft" — wireframe shows it bottom-left. We post the
  // current Step 1 fields so the partial draft shows up in My Requests.
  const saveDraft = async () => {
    setSavingDraft(true);
    setDraftError(null);
    try {
      const body: CreateShareRequestBody = {
        title: form.title.trim() || "Untitled draft",
        purpose: form.purpose.trim() || " ",
        legal_basis: form.legal_basis || "",
        sharing_type: form.sharing_type,
        data_classification: form.data_classification,
        personal_data_involved: form.personal_data_involved,
        estimated_data_subjects: form.estimated_data_subjects ?? null,
        data_subject_categories:
          form.data_subject_categories.length > 0
            ? form.data_subject_categories
            : null,
        source_description: form.source_description || null,
        receiver_group_id: form.receiver_group_id,
        dpia_confirmed: form.dpia_confirmed,
        data_type: form.data_type,
        delivery_channel: form.delivery_channel,
      };
      await createRequest(body);
      router.push("/data-sharing");
    } catch (e) {
      setDraftError(e instanceof Error ? e.message : "Could not save draft");
      setSavingDraft(false);
    }
  };

  return (
    <>
    {showLegalModal && (
      <LegalBasisModal
        onClose={() => setShowLegalModal(false)}
        onSelect={(v) => setField("legal_basis", v)}
      />
    )}
    <div className="flex flex-col gap-4">
      <SectionHeader>Request Details</SectionHeader>

      <div className="flex flex-col gap-[6px]">
        <FieldLabel required>Title</FieldLabel>
        <input
          type="text"
          value={form.title}
          onChange={(e) => setField("title", e.target.value)}
          placeholder="Short, descriptive name for this request"
          className="h-9 w-full rounded-md border px-3 text-[13px] text-auth-text outline-none placeholder:text-[#BABABA]"
          style={{ borderColor: "#EEEEEE" }}
        />
      </div>

      <div className="flex flex-col gap-[6px]">
        <FieldLabel required>Purpose</FieldLabel>
        <textarea
          value={form.purpose}
          onChange={(e) => setField("purpose", e.target.value)}
          placeholder="Explain why you need this data and how it will be used..."
          className="h-20 w-full resize-none rounded-md border p-3 text-[13px] text-auth-text outline-none placeholder:text-[#BABABA]"
          style={{ borderColor: "#EEEEEE" }}
        />
      </div>

      <div className="h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />

      <SectionHeader>Sharing Details</SectionHeader>

      <div className="flex gap-6">
        <div className="flex flex-1 flex-col gap-2">
          <FieldLabel>Sharing type</FieldLabel>
          <div className="flex items-center gap-5">
            {(["internal", "external"] as const).map((t) => (
              <button
                type="button"
                key={t}
                className="flex cursor-pointer items-center gap-2"
                onClick={() => setField("sharing_type", t as SharingType)}
              >
                <Radio checked={form.sharing_type === t} />
                <span className="text-[13px] capitalize text-auth-text">{t}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-[6px]">
          <FieldLabel required>Receiver department</FieldLabel>
          <div className="relative">
            <select
              value={form.receiver_group_id ?? ""}
              onChange={(e) =>
                setField(
                  "receiver_group_id",
                  e.target.value ? Number(e.target.value) : null,
                )
              }
              disabled={
                groupsQuery.isLoading ||
                groupsQuery.isError ||
                !(groupsQuery.data ?? []).some((g) => g.is_active)
              }
              className="h-9 w-full appearance-none rounded-md border bg-white pl-3 pr-8 text-[13px] outline-none disabled:cursor-not-allowed disabled:bg-[#F8F8F8]"
              style={{
                borderColor: ownDeptError ? "#EF4444" : "#EEEEEE",
                color: form.receiver_group_id ? "#070709" : "#BABABA",
              }}
            >
              <option value="">
                {groupsQuery.isLoading
                  ? "Loading departments…"
                  : groupsQuery.isError
                    ? "Failed to load departments"
                    : (groupsQuery.data ?? []).filter((g) => g.is_active)
                          .length === 0
                      ? "No departments configured"
                      : "Select department..."}
              </option>
              {(groupsQuery.data ?? [])
                .filter((g) => g.is_active)
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-3 top-1/2 h-[14px] w-[14px] -translate-y-1/2"
              style={{ color: "#9E9E9E" }}
            />
          </div>
          {ownDeptError && (
            <p className="text-xs" style={{ color: "#EF4444" }}>
              You cannot raise a request to your own department.
            </p>
          )}
          {!groupsQuery.isLoading &&
            !groupsQuery.isError &&
            (groupsQuery.data ?? []).filter((g) => g.is_active).length ===
              0 && (
              <p className="text-xs" style={{ color: "#B45309" }}>
                The backend returned no active departments for your tenant.
                Run the seed (
                <code>backend/setup/keycloak/seed_test_data.py</code>) or check{" "}
                <code>t_groups</code>.
              </p>
            )}
          {groupsQuery.isError && (
            <p className="text-xs" style={{ color: "#EF4444" }}>
              {groupsQuery.error instanceof Error
                ? groupsQuery.error.message
                : "Failed to load departments"}
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <FieldLabel required>Data classification</FieldLabel>
        <div className="flex flex-wrap items-center gap-5">
          {DATA_CLASSIFICATIONS.map((opt) => (
            <button
              type="button"
              key={opt.value}
              className="flex cursor-pointer items-center gap-2"
              onClick={() =>
                setField(
                  "data_classification",
                  opt.value as DataClassification,
                )
              }
            >
              <Radio checked={form.data_classification === opt.value} />
              <span
                className="text-[13px]"
                style={{
                  color:
                    form.data_classification === opt.value
                      ? "#070709"
                      : "#515157",
                }}
              >
                {opt.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      {isSensitive && (
        <div className="flex flex-col gap-2.5">
          <div
            className="flex gap-2.5 rounded-md p-3"
            style={{
              backgroundColor: "#FFF5F0",
              border: "1px solid #FFCDB8",
            }}
          >
            <Info
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: "#D76736" }}
            />
            <div className="flex flex-col gap-1">
              <p
                className="text-xs font-semibold"
                style={{ color: "#D76736" }}
              >
                DPIA confirmation required
              </p>
              <p className="text-xs" style={{ color: "#515157" }}>
                Sensitive data requires a completed Data Protection Impact
                Assessment before submission.
              </p>
            </div>
          </div>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              className="h-4 w-4 accent-[#D76736]"
              checked={form.dpia_confirmed}
              onChange={(e) => setField("dpia_confirmed", e.target.checked)}
            />
            <span className="text-[13px] text-auth-text">
              I confirm a DPIA has been reviewed and approved for this Sensitive
              data request
            </span>
          </label>
        </div>
      )}

      <div className="h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />

      <SectionHeader>Legal &amp; Compliance</SectionHeader>

      <div className="flex flex-col gap-[6px]">
        <div className="flex items-center justify-between">
          <FieldLabel
            required={
              form.personal_data_involved ||
              form.data_classification === "confidential" ||
              form.data_classification === "sensitive"
            }
          >
            Legal basis
          </FieldLabel>
          <button
            type="button"
            onClick={() => setShowLegalModal(true)}
            className="text-[12px] font-medium"
            style={{ color: "#D76736" }}
          >
            Help me pick →
          </button>
        </div>
        <div className="relative">
          <select
            value={form.legal_basis}
            onChange={(e) =>
              setField("legal_basis", e.target.value as LegalBasis)
            }
            className="h-9 w-full appearance-none rounded-md border bg-white pl-3 pr-8 text-[13px] outline-none"
            style={{
              borderColor: "#EEEEEE",
              color: form.legal_basis ? "#070709" : "#BABABA",
            }}
          >
            <option value="">Select legal basis...</option>
            {LEGAL_BASIS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-3 top-1/2 h-[14px] w-[14px] -translate-y-1/2"
            style={{ color: "#9E9E9E" }}
          />
        </div>
      </div>

      <div className="flex gap-6">
        <div className="flex flex-1 flex-col gap-2">
          <FieldLabel>Personal data involved</FieldLabel>
          <button
            type="button"
            className="flex cursor-pointer items-center gap-2"
            onClick={() =>
              setField("personal_data_involved", !form.personal_data_involved)
            }
          >
            <span
              className="text-[13px]"
              style={{
                color: form.personal_data_involved ? "#9E9E9E" : "#070709",
                fontWeight: form.personal_data_involved ? "400" : "600",
              }}
            >
              No
            </span>
            <span
              className="flex h-[22px] w-10 items-center rounded-full px-0.5"
              style={{
                backgroundColor: form.personal_data_involved
                  ? "#D76736"
                  : "#EEEEEE",
                justifyContent: form.personal_data_involved
                  ? "flex-end"
                  : "flex-start",
              }}
            >
              <span className="h-[18px] w-[18px] rounded-full bg-white shadow-sm" />
            </span>
            <span
              className="text-[13px]"
              style={{
                color: form.personal_data_involved ? "#070709" : "#9E9E9E",
                fontWeight: form.personal_data_involved ? "600" : "400",
              }}
            >
              Yes
            </span>
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-[6px]">
          <FieldLabel>Requested retention period</FieldLabel>
          <div className="flex gap-3">
            {([30, 60, 90, 180] as const).map((days) => {
              const selected = form.retention_period === days;
              return (
                <button
                  key={days}
                  type="button"
                  onClick={() => setField("retention_period", days)}
                  className="flex items-center gap-2"
                >
                  <span
                    className="flex h-4 w-4 items-center justify-center rounded-full border-2 transition-colors"
                    style={{ borderColor: selected ? "#D76736" : "#CCCCCC" }}
                  >
                    {selected && (
                      <span className="h-2 w-2 rounded-full bg-brand" />
                    )}
                  </span>
                  <span
                    className="text-[13px]"
                    style={{ color: selected ? "#070709" : "#515157", fontWeight: selected ? "600" : "400" }}
                  >
                    {days} days
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {form.personal_data_involved && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-[6px]">
            <FieldLabel required>
              Estimated number of data subjects
            </FieldLabel>
            <input
              type="number"
              min={0}
              value={form.estimated_data_subjects ?? ""}
              onChange={(e) =>
                setField(
                  "estimated_data_subjects",
                  e.target.value ? Number(e.target.value) : null,
                )
              }
              placeholder="e.g. 500"
              className="h-9 w-full rounded-md border px-3 text-[13px] outline-none placeholder:text-[#BABABA]"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>

          <div className="flex flex-col gap-[6px]">
            <FieldLabel>
              Categories of personal data (comma-separated)
            </FieldLabel>
            <input
              type="text"
              value={form.data_subject_categories.join(", ")}
              onChange={(e) =>
                setField(
                  "data_subject_categories",
                  e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                )
              }
              placeholder="e.g. Health data, Financial records"
              className="h-9 w-full rounded-md border px-3 text-[13px] outline-none placeholder:text-[#BABABA]"
              style={{ borderColor: "#EEEEEE" }}
            />
          </div>
        </div>
      )}

      <div className="flex flex-col gap-[6px]">
        <FieldLabel>Source description</FieldLabel>
        <input
          type="text"
          value={form.source_description}
          onChange={(e) => setField("source_description", e.target.value)}
          placeholder="Where does this data live? (system, dataset, etc.)"
          className="h-9 w-full rounded-md border px-3 text-[13px] outline-none placeholder:text-[#BABABA]"
          style={{ borderColor: "#EEEEEE" }}
        />
      </div>

      {draftError && (
        <p className="text-xs" style={{ color: "#EF4444" }}>
          {draftError}
        </p>
      )}

      <div className="mt-2 flex items-center justify-between">
        <button
          type="button"
          onClick={saveDraft}
          disabled={savingDraft}
          className="flex h-9 items-center gap-[6px] rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#EEEEEE", color: "#616161" }}
        >
          <Save className="h-[14px] w-[14px]" />
          {savingDraft ? "Saving…" : "Save as Draft"}
        </button>
        <button
          type="button"
          onClick={goNext}
          disabled={!canProceed}
          className="flex h-10 items-center gap-2 rounded-md px-5 text-[13px] font-semibold transition-opacity"
          style={{
            backgroundColor: canProceed ? "#D76736" : "#D0D0D0",
            color: canProceed ? "#FFFFFF" : "#9E9E9E",
            cursor: canProceed ? "pointer" : "not-allowed",
          }}
        >
          Next
        </button>
      </div>
    </div>
    </>
  );
}
