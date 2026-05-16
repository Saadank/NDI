"use client";

import { ArrowLeft, GitMerge, Send, Save, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { uploadFileForRequest } from "@/lib/api/products/data-sharing/files.api";
import {
  createRequest,
  submitRequest,
} from "@/lib/api/products/data-sharing/requests.api";
import { useGroups } from "@/lib/hooks/platform/useGroups";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";
import { useWorkflowTemplates, useWorkflowTemplate } from "@/lib/hooks/data-sharing/useWorkflowTemplates";
import { useNewRequestStore } from "@/lib/store/new-request.store";
import {
  DATA_CLASSIFICATIONS,
  LEGAL_BASIS_OPTIONS,
} from "@/lib/utils/constants";
import type { CreateShareRequestBody } from "@/lib/types/data-sharing/request.types";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      className="flex h-[34px] items-center"
      style={{ borderBottom: "1px solid #F5F5F5" }}
    >
      <span
        className="w-[160px] shrink-0 text-[11px]"
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

export function Step3_Review() {
  const { isReady } = useRoleGuard({ allow: ["requester", "data_owner"] });
  const router = useRouter();
  const form = useNewRequestStore();
  const reset = useNewRequestStore((s) => s.reset);
  const groupsQuery = useGroups();
  const myGroupId = useAuthStore((s) => s.user?.group_id ?? null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSameReceiverModal, setShowSameReceiverModal] = useState(false);

  const templatesQuery = useWorkflowTemplates();
  const matchedTemplateId = useMemo(() => {
    if (!templatesQuery.data) return null;
    const match =
      templatesQuery.data.find(
        (t) =>
          t.is_active &&
          (t.sharing_type === null || t.sharing_type === form.sharing_type) &&
          (t.data_classification === null ||
            t.data_classification === form.data_classification),
      ) ?? templatesQuery.data.find((t) => t.is_active) ?? null;
    return match?.id ?? null;
  }, [templatesQuery.data, form.sharing_type, form.data_classification]);
  const templateDetailQuery = useWorkflowTemplate(matchedTemplateId);

  if (!isReady) return null;

  const matchedTemplate = templateDetailQuery.data ?? null;
  const receiverName =
    groupsQuery.data?.find((g) => g.id === form.receiver_group_id)?.name ??
    "—";
  const classificationLabel =
    DATA_CLASSIFICATIONS.find((c) => c.value === form.data_classification)
      ?.label ?? form.data_classification;
  const legalBasisLabel =
    LEGAL_BASIS_OPTIONS.find((l) => l.value === form.legal_basis)?.label ??
    "—";

  const handleSubmit = async () => {
    // Guard: source department cannot equal receiver department.
    if (
      form.receiver_group_id !== null &&
      myGroupId !== null &&
      String(form.receiver_group_id) === String(myGroupId)
    ) {
      setShowSameReceiverModal(true);
      return;
    }
    // Guard: no active workflow template matches this request's
    // (sharing_type, classification). Without one the backend's /submit
    // endpoint stamps the request as "submitted" but produces zero
    // workflow steps, leaving Data Owners with nothing to act on. Surface
    // the misconfiguration here instead of letting it silently break the
    // approval flow downstream.
    if (templatesQuery.isSuccess && matchedTemplateId === null) {
      setError(
        "No active workflow matches this request — ask your Org Admin to create an active workflow for " +
          `${form.sharing_type} / ${form.data_classification} requests before submitting.`,
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      // 1. Create the draft request.
      const body: CreateShareRequestBody = {
        title: form.title.trim(),
        purpose: form.purpose.trim(),
        legal_basis: form.legal_basis || "",
        request_direction: form.request_direction,
        sharing_type: form.sharing_type,
        // PUSH/EXTERNAL — inline recipient. Backend create_draft
        // upserts t_external_recipients + t_recipient_contacts and
        // stamps external_recipient_id/external_contact_id on the
        // request. receiver_group_id is left null for these.
        ...(form.sharing_type === "external"
          ? {
              external_recipient: {
                org_name: form.external_org_name.trim(),
                contact_email: form.external_contact_email.trim(),
                contact_name: form.external_contact_name.trim() || undefined,
              },
              external_dsa_text: form.external_dsa_text,
              receiver_group_id: null,
            }
          : {}),
        data_classification: form.data_classification,
        personal_data_involved: form.personal_data_involved,
        estimated_data_subjects: form.estimated_data_subjects ?? null,
        data_subject_categories:
          form.data_subject_categories.length > 0
            ? form.data_subject_categories
            : null,
        source_description: form.source_description || null,
        receiver_group_id: form.receiver_group_id,
        receiving_tenant_id: null,
        dpia_confirmed: form.dpia_confirmed,
        data_type: form.data_type,
        connection_id:
          form.data_type === "structured" ? form.connection_id : null,
        selection_mode:
          form.data_type === "structured" ? form.selection_mode : null,
        selected_items:
          form.data_type === "structured" && form.selection_mode === "tables"
            ? form.selected_items
            : null,
        custom_sql:
          form.data_type === "structured" && form.selection_mode === "query"
            ? form.custom_sql
            : null,
        delivery_channel: form.delivery_channel,
      };

      const draft = await createRequest(body);

      // 2. If file mode, upload each staged file. The actual File objects
      //    live on `window.__datarix_staged_files` because File can't survive
      //    sessionStorage round-trips. If the user reloaded between Step 2
      //    and Step 3 we lose those — surface that clearly instead of
      //    silently submitting a request with no files.
      if (form.data_type === "file") {
        const files =
          (typeof window !== "undefined"
            ? (window as unknown as { __datarix_staged_files?: File[] })
                .__datarix_staged_files
            : undefined) ?? [];
        if (form.staged_files.length > 0 && files.length === 0) {
          throw new Error(
            "Files were lost (page was reloaded). Go back to Step 2 and re-add them.",
          );
        }
        for (const file of files) {
          await uploadFileForRequest(draft.id, file);
        }
      }

      // 3. Submit (transitions draft → submitted, assigns workflow).
      await submitRequest(draft.id);

      // 4. Cleanup and bounce to the list.
      reset();
      if (typeof window !== "undefined") {
        (window as unknown as { __datarix_staged_files?: File[] }).__datarix_staged_files = [];
      }
      router.push("/data-sharing");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Submit failed";
      setError(msg);
      setSubmitting(false);
    }
  };

  const handleSaveDraft = async () => {
    setSubmitting(true);
    setError(null);
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
        receiving_tenant_id: null,
        dpia_confirmed: form.dpia_confirmed,
        data_type: form.data_type,
        connection_id:
          form.data_type === "structured" ? form.connection_id : null,
        selection_mode:
          form.data_type === "structured" ? form.selection_mode : null,
        selected_items:
          form.data_type === "structured" && form.selection_mode === "tables"
            ? form.selected_items
            : null,
        custom_sql:
          form.data_type === "structured" && form.selection_mode === "query"
            ? form.custom_sql
            : null,
        delivery_channel: form.delivery_channel,
      };
      await createRequest(body);
      reset();
      router.push("/data-sharing");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not save draft";
      setError(msg);
      setSubmitting(false);
    }
  };

  return (
    <>
    {showSameReceiverModal && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center"
        style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
      >
        <div
          className="flex w-[440px] flex-col gap-5 rounded-lg p-6"
          style={{ backgroundColor: "#FFFFFF" }}
        >
          <div className="flex items-start justify-between">
            <h2 className="text-[15px] font-semibold text-auth-text">
              Cannot submit — source equals receiver
            </h2>
            <button type="button" onClick={() => setShowSameReceiverModal(false)}>
              <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
            </button>
          </div>
          <p className="text-[13px]" style={{ color: "#515157" }}>
            The requesting department and receiver department are the same. A
            department cannot request data from itself. Go back to Step 1 and
            change the receiver department before submitting.
          </p>
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => setShowSameReceiverModal(false)}
              className="h-9 rounded-md border px-4 text-[13px]"
              style={{ borderColor: "#EEEEEE", color: "#515157" }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                setShowSameReceiverModal(false);
                router.push("/data-sharing/new");
              }}
              className="h-9 rounded-md px-4 text-[13px] font-medium text-white"
              style={{ backgroundColor: "#D76736" }}
            >
              Go to Step 1 · Change receiver
            </button>
          </div>
        </div>
      </div>
    )}
    <div className="flex flex-col gap-4">
      <div className="flex gap-4">
        <div className="flex flex-1 flex-col gap-4">
          <div
            className="flex flex-col overflow-hidden rounded-lg"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <div
              className="flex h-11 items-center justify-between px-5"
              style={{ borderBottom: "1px solid #EEEEEE" }}
            >
              <span
                className="text-[13px] font-semibold"
                style={{ color: "#1A1A1A" }}
              >
                Step 1 · Request Details
              </span>
              <button
                type="button"
                onClick={() => router.push("/data-sharing/new")}
                className="flex h-[26px] items-center rounded px-2.5 text-xs font-medium"
                style={{ border: "1px solid #D76736", color: "#D76736" }}
              >
                Edit
              </button>
            </div>
            <div className="flex flex-col px-5 py-2">
              <Field
                label="Direction"
                value={
                  form.request_direction === "push"
                    ? "Push — sending data to another dept"
                    : "Pull — requesting data from another dept"
                }
              />
              <Field label="Title" value={form.title} />
              <Field label="Purpose" value={form.purpose} />
              <Field label="Sharing Type" value={form.sharing_type} />
              <Field
                label={form.request_direction === "push" ? "Recipient Department" : "Source Department"}
                value={receiverName}
              />
              <Field label="Classification" value={classificationLabel} />
              <Field label="Legal Basis" value={legalBasisLabel} />
              <Field
                label="Personal Data"
                value={form.personal_data_involved ? "Yes" : "No"}
              />
              {form.personal_data_involved && (
                <>
                  <Field
                    label="Est. Data Subjects"
                    value={form.estimated_data_subjects ?? "—"}
                  />
                  <Field
                    label="Categories"
                    value={form.data_subject_categories.join(", ")}
                  />
                </>
              )}
              {form.data_classification === "sensitive" && (
                <Field
                  label="DPIA Confirmed"
                  value={form.dpia_confirmed ? "Yes" : "No"}
                />
              )}
              <Field
                label="Retention Period"
                value={form.retention_period != null ? `${form.retention_period} days` : "—"}
              />
              <Field
                label="Source Description"
                value={form.source_description}
              />
            </div>
          </div>

          <div
            className="flex flex-col overflow-hidden rounded-lg"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <div
              className="flex h-11 items-center justify-between px-5"
              style={{ borderBottom: "1px solid #EEEEEE" }}
            >
              <span
                className="text-[13px] font-semibold"
                style={{ color: "#1A1A1A" }}
              >
                Step 2 · Data Source —{" "}
                {form.data_type === "file" ? "File Upload" : "Structured Data"}
              </span>
              <button
                type="button"
                onClick={() => router.push("/data-sharing/new/step-2")}
                className="flex h-[26px] items-center rounded px-2.5 text-xs font-medium"
                style={{ border: "1px solid #D76736", color: "#D76736" }}
              >
                Edit
              </button>
            </div>
            <div className="flex flex-col px-5 py-2">
              {form.data_type === "file" ? (
                form.staged_files.length === 0 ? (
                  <p className="py-2 text-xs" style={{ color: "#BABABA" }}>
                    No files staged.
                  </p>
                ) : (
                  form.staged_files.map((f) => (
                    <Field
                      key={f.name}
                      label={f.name}
                      value={`${(f.size / 1024).toFixed(1)} KB`}
                    />
                  ))
                )
              ) : (
                <>
                  <Field label="Connection" value={form.connection_id ?? "—"} />
                  <Field label="Mode" value={form.selection_mode ?? "—"} />
                  {form.selection_mode === "tables" && (
                    <Field
                      label="Tables"
                      value={form.selected_items
                        .map((it) =>
                          [it.schema, it.table].filter(Boolean).join("."),
                        )
                        .join(", ")}
                    />
                  )}
                  {form.selection_mode === "query" && (
                    <Field
                      label="SQL"
                      value={
                        <code className="text-[11px]">
                          {form.custom_sql.slice(0, 80)}
                          {form.custom_sql.length > 80 ? "…" : ""}
                        </code>
                      }
                    />
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{
            width: 308,
            flexShrink: 0,
            backgroundColor: "#FFFFFF",
            border: "1px solid #EEEEEE",
          }}
        >
          <div
            className="flex h-11 items-center gap-2 px-5"
            style={{ borderBottom: "1px solid #EEEEEE" }}
          >
            <GitMerge className="h-4 w-4" style={{ color: "#D76736" }} />
            <span
              className="text-[13px] font-semibold"
              style={{ color: "#1A1A1A" }}
            >
              Approval Workflow
            </span>
          </div>
          <div className="px-5 py-4 flex flex-col gap-3">
            {templatesQuery.isLoading || templateDetailQuery.isLoading ? (
              <p className="text-xs" style={{ color: "#9E9E9E" }}>Loading workflow…</p>
            ) : matchedTemplate ? (
              <>
                <p className="text-[13px] font-semibold" style={{ color: "#1A1A1A" }}>
                  {matchedTemplate.name}
                </p>
                <div className="flex items-center gap-0">
                  {matchedTemplate.steps?.length ? (
                    matchedTemplate.steps
                      .slice()
                      .sort((a, b) => a.step_order - b.step_order)
                      .map((step, idx, arr) => (
                        <div key={step.id} className="flex items-center">
                          <div className="flex flex-col items-center gap-1">
                            <span
                              className="flex h-7 items-center justify-center rounded-full px-3 text-[11px] font-medium whitespace-nowrap"
                              style={{ backgroundColor: "#FFF5F0", color: "#D76736", border: "1px solid #D76736" }}
                            >
                              {step.name || step.step_type}
                            </span>
                            {step.assignee_role && (
                              <span className="text-[10px]" style={{ color: "#9E9E9E" }}>
                                {step.assignee_role.replace(/_/g, " ")}
                              </span>
                            )}
                          </div>
                          {idx < arr.length - 1 && (
                            <div className="mx-1.5 h-px w-6 shrink-0" style={{ backgroundColor: "#D76736" }} />
                          )}
                        </div>
                      ))
                  ) : (
                    <p className="text-xs" style={{ color: "#9E9E9E" }}>Steps will be assigned on submission.</p>
                  )}
                </div>
              </>
            ) : (
              <p className="text-xs" style={{ color: "#616161" }}>
                The workflow is selected automatically by the backend on submit
                based on your sharing type and data classification.
              </p>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div
          className="rounded-md p-3 text-xs"
          style={{
            backgroundColor: "#FEF2F2",
            border: "1px solid #FCA5A5",
            color: "#991B1B",
          }}
        >
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => router.push("/data-sharing/new/step-2")}
          className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#EEEEEE", color: "#616161" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Step 2
        </button>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSaveDraft}
            disabled={submitting}
            className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#9E9E9E", color: "#616161" }}
          >
            <Save className="h-3.5 w-3.5" />
            Save as Draft
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="flex h-9 items-center gap-1.5 rounded-md px-5 text-[13px] font-semibold text-white"
            style={{
              backgroundColor: submitting ? "#E1986F" : "#D76736",
              cursor: submitting ? "wait" : "pointer",
            }}
          >
            <Send className="h-3.5 w-3.5" />
            {submitting ? "Submitting…" : "Submit"}
          </button>
        </div>
      </div>
    </div>
    </>
  );
}
