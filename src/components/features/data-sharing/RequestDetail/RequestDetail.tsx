"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { useRequestDetail } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useRequestFiles } from "@/lib/hooks/data-sharing/useFiles";
import { useApprovalSteps } from "@/lib/hooks/data-sharing/useApprovalSteps";
import { REQUEST_STATUS_LABELS } from "@/lib/utils/constants";

export interface RequestDetailProps {
  id: string;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      className="flex h-[34px] items-center"
      style={{ borderBottom: "1px solid #F5F5F5" }}
    >
      <span
        className="w-[180px] shrink-0 text-[11px]"
        style={{ color: "#9E9E9E" }}
      >
        {label}
      </span>
      <span
        className="flex-1 text-xs font-medium"
        style={{ color: "#1A1A1A" }}
      >
        {value || <span style={{ color: "#BABABA" }}>—</span>}
      </span>
    </div>
  );
}

export function RequestDetail({ id }: RequestDetailProps) {
  const reqQuery = useRequestDetail(id);
  const filesQuery = useRequestFiles(id);
  const stepsQuery = useApprovalSteps(id);

  if (reqQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm" style={{ color: "#9E9E9E" }}>
          Loading…
        </p>
      </div>
    );
  }
  if (reqQuery.isError || !reqQuery.data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm" style={{ color: "#EF4444" }}>
          Failed to load request.
        </p>
      </div>
    );
  }

  const r = reqQuery.data;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center gap-3 px-8"
        style={{
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #EEEEEE",
        }}
      >
        <Link
          href="/data-sharing"
          className="flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs font-medium"
          style={{ borderColor: "#EEEEEE", color: "#616161" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </Link>
        <h1 className="text-lg font-bold text-auth-text">{r.title}</h1>
        <span
          className="rounded px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
        >
          {REQUEST_STATUS_LABELS[r.status] ?? r.status}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <div className="flex gap-4">
          <div className="flex flex-1 flex-col gap-4">
            <div
              className="flex flex-col overflow-hidden rounded-lg"
              style={{
                backgroundColor: "#FFFFFF",
                border: "1px solid #EEEEEE",
              }}
            >
              <div
                className="flex h-11 items-center px-5"
                style={{ borderBottom: "1px solid #EEEEEE" }}
              >
                <span
                  className="text-[13px] font-semibold"
                  style={{ color: "#1A1A1A" }}
                >
                  Request Details
                </span>
              </div>
              <div className="flex flex-col px-5 py-2">
                <Field label="Request #" value={r.request_number} />
                <Field label="Purpose" value={r.purpose} />
                <Field label="Sharing Type" value={r.sharing_type} />
                <Field label="Classification" value={r.data_classification} />
                <Field label="Legal Basis" value={r.legal_basis || "—"} />
                <Field
                  label="Personal Data"
                  value={r.personal_data_involved ? "Yes" : "No"}
                />
                {r.personal_data_involved && (
                  <Field
                    label="Est. Data Subjects"
                    value={r.estimated_data_subjects ?? "—"}
                  />
                )}
                <Field label="Data Type" value={r.data_type} />
                {r.data_type === "structured" && (
                  <>
                    <Field label="Connection" value={r.connection_id ?? "—"} />
                    <Field label="Mode" value={r.selection_mode ?? "—"} />
                  </>
                )}
                <Field
                  label="Created"
                  value={new Date(r.created_at).toLocaleString()}
                />
                <Field
                  label="Updated"
                  value={new Date(r.updated_at).toLocaleString()}
                />
              </div>
            </div>

            {r.data_type === "file" && (
              <div
                className="flex flex-col overflow-hidden rounded-lg"
                style={{
                  backgroundColor: "#FFFFFF",
                  border: "1px solid #EEEEEE",
                }}
              >
                <div
                  className="flex h-11 items-center px-5"
                  style={{ borderBottom: "1px solid #EEEEEE" }}
                >
                  <span
                    className="text-[13px] font-semibold"
                    style={{ color: "#1A1A1A" }}
                  >
                    Files
                  </span>
                </div>
                <div className="flex flex-col gap-1 px-5 py-3">
                  {filesQuery.isLoading && (
                    <p className="text-xs" style={{ color: "#9E9E9E" }}>
                      Loading…
                    </p>
                  )}
                  {(filesQuery.data ?? []).map((f) => (
                    <div
                      key={f.id}
                      className="flex h-9 items-center justify-between"
                      style={{ borderBottom: "1px solid #F5F5F5" }}
                    >
                      <span className="text-xs">{f.original_filename}</span>
                      <span className="text-xs" style={{ color: "#9E9E9E" }}>
                        {(f.file_size_bytes / 1024).toFixed(1)} KB · {f.status}
                      </span>
                    </div>
                  ))}
                  {filesQuery.data && filesQuery.data.length === 0 && (
                    <p className="text-xs" style={{ color: "#BABABA" }}>
                      No files attached.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          <div
            className="flex flex-col overflow-hidden rounded-lg"
            style={{
              width: 360,
              flexShrink: 0,
              backgroundColor: "#FFFFFF",
              border: "1px solid #EEEEEE",
            }}
          >
            <div
              className="flex h-11 items-center px-5"
              style={{ borderBottom: "1px solid #EEEEEE" }}
            >
              <span
                className="text-[13px] font-semibold"
                style={{ color: "#1A1A1A" }}
              >
                Approval Workflow
              </span>
            </div>
            <div className="flex flex-col gap-2 px-4 py-4">
              {stepsQuery.isLoading && (
                <p className="text-xs" style={{ color: "#9E9E9E" }}>
                  Loading…
                </p>
              )}
              {(stepsQuery.data ?? []).map((step, i) => (
                <div
                  key={step.id}
                  className="flex items-start gap-2.5"
                  style={{ padding: "10px 0" }}
                >
                  <span
                    className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
                    style={
                      step.status === "approved"
                        ? { backgroundColor: "#449235", color: "#FFFFFF" }
                        : step.status === "rejected"
                          ? { backgroundColor: "#D32F2F", color: "#FFFFFF" }
                          : i === 0
                            ? { backgroundColor: "#D76736", color: "#FFFFFF" }
                            : { backgroundColor: "#EEEEEE", color: "#9E9E9E" }
                    }
                  >
                    {i + 1}
                  </span>
                  <div className="flex flex-col gap-0.5">
                    <span
                      className="text-xs font-semibold"
                      style={{ color: "#1A1A1A" }}
                    >
                      {step.assignee_name}
                    </span>
                    <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                      {step.status}
                      {step.comment ? ` — ${step.comment}` : ""}
                    </span>
                  </div>
                </div>
              ))}
              {stepsQuery.data && stepsQuery.data.length === 0 && (
                <p className="text-xs" style={{ color: "#BABABA" }}>
                  No workflow steps yet.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
