"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckSquare,
  FileText,
  Paperclip,
  Plus,
  Square,
  Trash2,
  Upload,
} from "lucide-react";

import { useRequestDetail, useSubmitRequest, useUpdateRequest } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useApprovalSteps } from "@/lib/hooks/data-sharing/useApprovalSteps";
import { useDeleteFile, useRequestFiles, useUploadFile } from "@/lib/hooks/data-sharing/useFiles";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { DATA_CLASSIFICATIONS, LEGAL_BASIS_OPTIONS } from "@/lib/utils/constants";
import { formatBytes, formatDate } from "@/lib/utils/formatters";
import type {
  DataClassification,
  LegalBasis,
  RequiredDocument,
} from "@/lib/types/data-sharing/request.types";
import { FileDownloadButton } from "../FileDownloadButton";

export interface EditRequestProps {
  id: string;
}

// Strip the "[FLAG: reviewer]" prefix the Data Owner flag flow prepends so the
// requester reads a clean instruction.
function cleanComment(comment: string | null | undefined): string {
  if (!comment) return "";
  return comment.replace(/^\[FLAG:\s*[^\]]+\]\s*/i, "").trim();
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      className="flex flex-col overflow-hidden rounded-lg"
      style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
    >
      <div className="flex h-11 items-center px-5" style={{ borderBottom: "1px solid #EEEEEE" }}>
        <span className="text-[13px] font-semibold" style={{ color: "#1A1A1A" }}>{title}</span>
      </div>
      <div className="flex flex-col gap-4 px-5 py-4">{children}</div>
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <span className="text-[12px] font-medium" style={{ color: "#515157" }}>{children}</span>;
}

const inputStyle = {
  borderColor: "#E5E7EB",
} as const;

export function EditRequest({ id }: EditRequestProps) {
  const { isReady } = useRoleGuard({ allow: ["requester", "data_owner"] });
  const router = useRouter();

  const reqQuery = useRequestDetail(id);
  const filesQuery = useRequestFiles(id);
  const stepsQuery = useApprovalSteps(id);
  const updateMutation = useUpdateRequest(id);
  const submitMutation = useSubmitRequest(id);
  const uploadMutation = useUploadFile(id);
  const deleteMutation = useDeleteFile(id);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [err, setErr] = useState<string | null>(null);

  // Local editable form state, hydrated from the loaded request.
  const [form, setForm] = useState({
    title: "",
    purpose: "",
    legal_basis: "" as LegalBasis | string,
    data_classification: "internal" as DataClassification,
    personal_data_involved: false,
    estimated_data_subjects: "" as number | string,
    source_description: "",
    dpia_confirmed: false,
    custom_sql: "",
  });
  const [requiredDocs, setRequiredDocs] = useState<RequiredDocument[]>([]);

  const r = reqQuery.data;
  useEffect(() => {
    if (!r) return;
    setForm({
      title: r.title ?? "",
      purpose: r.purpose ?? "",
      legal_basis: r.legal_basis ?? "",
      data_classification: r.data_classification ?? "internal",
      personal_data_involved: Boolean(r.personal_data_involved),
      estimated_data_subjects: r.estimated_data_subjects ?? "",
      source_description: r.source_description ?? "",
      dpia_confirmed: Boolean(r.dpia_confirmed),
      custom_sql: r.custom_sql ?? "",
    });
    setRequiredDocs(r.required_documents ?? []);
  }, [r]);

  const steps = stepsQuery.data ?? [];
  const files = filesQuery.data ?? [];
  const changesStep = useMemo(
    () => [...steps].reverse().find((s) => s.status === "changes_requested"),
    [steps],
  );

  if (!isReady) return null;
  if (reqQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm" style={{ color: "#9E9E9E" }}>Loading…</p>
      </div>
    );
  }
  if (reqQuery.isError || !r) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm" style={{ color: "#EF4444" }}>Failed to load request.</p>
      </div>
    );
  }

  const editable = r.status === "draft" || r.status === "changes_requested";

  // Not editable → explain + send them back to the read-only detail.
  if (!editable) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <p className="text-sm" style={{ color: "#515157" }}>
          This request can&rsquo;t be edited — it&rsquo;s currently {r.status.replace("_", " ")}.
        </p>
        <Link
          href={`/data-sharing/${id}`}
          className="flex h-9 items-center rounded-md px-4 text-[13px] font-semibold text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          Back to request
        </Link>
      </div>
    );
  }

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const buildBody = () => ({
    title: form.title.trim(),
    purpose: form.purpose.trim(),
    legal_basis: form.legal_basis || "",
    data_classification: form.data_classification,
    personal_data_involved: form.personal_data_involved,
    estimated_data_subjects:
      form.estimated_data_subjects === "" ? null : Number(form.estimated_data_subjects),
    source_description: form.source_description.trim() || null,
    dpia_confirmed: form.dpia_confirmed,
    ...(r.data_type === "structured" && r.selection_mode === "query"
      ? { custom_sql: form.custom_sql }
      : {}),
    required_documents: requiredDocs,
  });

  const save = async () => {
    setErr(null);
    if (!form.title.trim()) { setErr("Title is required."); return; }
    if (!form.purpose.trim()) { setErr("Purpose is required."); return; }
    try {
      await updateMutation.mutateAsync(buildBody());
      return true;
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save changes.");
      return false;
    }
  };

  const saveAndResubmit = async () => {
    const ok = await save();
    if (!ok) return;
    try {
      await submitMutation.mutateAsync();
      router.push(`/data-sharing/${id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not resubmit. Fix the issue and try again.");
    }
  };

  const onPickFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    setErr(null);
    try {
      for (const file of Array.from(fileList)) {
        await uploadMutation.mutateAsync(file);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "File upload failed.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const liveFiles = files.filter((f) => f.status !== "deleted");
  const busy = updateMutation.isPending || submitMutation.isPending;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-14 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <span className="text-sm font-semibold text-auth-text">Edit Request · {r.request_number}</span>
        <Link
          href={`/data-sharing/${id}`}
          className="flex items-center gap-1 text-[13px]"
          style={{ color: "#9E9E9E" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to request
        </Link>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* What the reviewer asked for */}
        {r.status === "changes_requested" && (changesStep || requiredDocs.length > 0) && (
          <div
            className="flex items-start gap-3 rounded-lg px-4 py-3"
            style={{ backgroundColor: "#FFFBEB", border: "1px solid #FDE68A" }}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#D97706" }} />
            <div className="flex flex-col gap-1">
              <p className="text-[13px] font-semibold" style={{ color: "#B45309" }}>
                {changesStep?.assignee_name ?? "Reviewer"} sent this back
                {changesStep?.completed_at ? ` · ${formatDate(changesStep.completed_at)}` : ""}
              </p>
              {cleanComment(changesStep?.comment) && (
                <p className="text-xs" style={{ color: "#92400E" }}>
                  &ldquo;{cleanComment(changesStep?.comment)}&rdquo;
                </p>
              )}
              <p className="text-xs" style={{ color: "#92400E" }}>
                Apply the changes below and resubmit. Changing classification, legal basis, the
                personal-data flag, or data selection re-triggers DPO review.
              </p>
            </div>
          </div>
        )}

        <div className="flex gap-4">
          {/* Left: editable form */}
          <div className="flex flex-1 flex-col gap-4">
            <SectionCard title="Request Details">
              <div className="flex flex-col gap-1.5">
                <FieldLabel>Title</FieldLabel>
                <input
                  value={form.title}
                  onChange={(e) => set("title", e.target.value)}
                  className="h-10 rounded-md border px-3 text-[13px] outline-none"
                  style={inputStyle}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <FieldLabel>Purpose</FieldLabel>
                <textarea
                  value={form.purpose}
                  onChange={(e) => set("purpose", e.target.value)}
                  rows={3}
                  className="resize-none rounded-md border p-3 text-[13px] outline-none"
                  style={inputStyle}
                />
              </div>
              <div className="flex gap-4">
                <div className="flex flex-1 flex-col gap-1.5">
                  <FieldLabel>Classification</FieldLabel>
                  <select
                    value={form.data_classification}
                    onChange={(e) => set("data_classification", e.target.value as DataClassification)}
                    className="h-10 rounded-md border px-3 text-[13px] outline-none"
                    style={inputStyle}
                  >
                    {DATA_CLASSIFICATIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-1 flex-col gap-1.5">
                  <FieldLabel>Legal Basis</FieldLabel>
                  <select
                    value={form.legal_basis}
                    onChange={(e) => set("legal_basis", e.target.value)}
                    className="h-10 rounded-md border px-3 text-[13px] outline-none"
                    style={inputStyle}
                  >
                    <option value="">— Select —</option>
                    {LEGAL_BASIS_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex items-center gap-6">
                <label className="flex cursor-pointer items-center gap-2 text-[13px]" style={{ color: "#515157" }}>
                  <input
                    type="checkbox"
                    checked={form.personal_data_involved}
                    onChange={(e) => set("personal_data_involved", e.target.checked)}
                    className="accent-[#D76736]"
                  />
                  Personal data involved
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-[13px]" style={{ color: "#515157" }}>
                  <input
                    type="checkbox"
                    checked={form.dpia_confirmed}
                    onChange={(e) => set("dpia_confirmed", e.target.checked)}
                    className="accent-[#D76736]"
                  />
                  DPIA confirmed
                </label>
              </div>
              {form.personal_data_involved && (
                <div className="flex flex-col gap-1.5">
                  <FieldLabel>Estimated data subjects</FieldLabel>
                  <input
                    type="number"
                    min={0}
                    value={form.estimated_data_subjects}
                    onChange={(e) => set("estimated_data_subjects", e.target.value)}
                    className="h-10 w-48 rounded-md border px-3 text-[13px] outline-none"
                    style={inputStyle}
                  />
                </div>
              )}
              <div className="flex flex-col gap-1.5">
                <FieldLabel>Source description</FieldLabel>
                <textarea
                  value={form.source_description}
                  onChange={(e) => set("source_description", e.target.value)}
                  rows={2}
                  className="resize-none rounded-md border p-3 text-[13px] outline-none"
                  style={inputStyle}
                />
              </div>
              {r.data_type === "structured" && r.selection_mode === "query" && (
                <div className="flex flex-col gap-1.5">
                  <FieldLabel>Query (SQL)</FieldLabel>
                  <textarea
                    value={form.custom_sql}
                    onChange={(e) => set("custom_sql", e.target.value)}
                    rows={4}
                    className="resize-none rounded-md border p-3 font-mono text-[12px] outline-none"
                    style={inputStyle}
                  />
                </div>
              )}
            </SectionCard>

            {/* Supporting documents */}
            <SectionCard title="Supporting Documents">
              <p className="text-xs" style={{ color: "#9E9E9E" }}>
                Attach contracts, DPIAs, or any other documents the reviewer needs to approve this
                request.
              </p>
              {liveFiles.length > 0 && (
                <div className="flex flex-col">
                  {liveFiles.map((f, i) => (
                    <div
                      key={f.id}
                      className="flex items-center gap-3 py-2"
                      style={{ borderBottom: i < liveFiles.length - 1 ? "1px solid #F5F5F5" : undefined }}
                    >
                      <FileText className="h-4 w-4 shrink-0" style={{ color: "#9E9E9E" }} />
                      <span className="flex-1 truncate text-[13px] text-auth-text">{f.original_filename}</span>
                      <span className="text-xs" style={{ color: "#9E9E9E" }}>{formatBytes(f.file_size_bytes)}</span>
                      <FileDownloadButton fileId={f.id} status={f.status} variant="icon" />
                      <button
                        type="button"
                        onClick={() => deleteMutation.mutate(f.id)}
                        disabled={deleteMutation.isPending}
                        title="Remove"
                        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border disabled:opacity-40"
                        style={{ borderColor: "#E5E7EB", color: "#DC2626" }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => onPickFiles(e.target.files)}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadMutation.isPending}
                className="flex h-9 w-fit items-center gap-2 rounded-md border px-4 text-[13px] font-medium disabled:opacity-50"
                style={{ borderColor: "#D76736", color: "#D76736" }}
              >
                <Upload className="h-3.5 w-3.5" />
                {uploadMutation.isPending ? "Uploading…" : "Upload files"}
              </button>
            </SectionCard>
          </div>

          {/* Right: required-documents checklist */}
          <div className="flex w-[320px] shrink-0 flex-col gap-4">
            <SectionCard title="Required Documents">
              {requiredDocs.length === 0 && (
                <p className="text-xs" style={{ color: "#9E9E9E" }}>
                  No specific documents were requested. Add any you think are needed, then attach them
                  on the left.
                </p>
              )}
              {requiredDocs.map((doc, i) => (
                <div key={i} className="flex items-start gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setRequiredDocs((d) =>
                        d.map((x, j) => (j === i ? { ...x, satisfied: !x.satisfied } : x)),
                      )
                    }
                    className="mt-0.5 shrink-0"
                    style={{ color: doc.satisfied ? "#449235" : "#9E9E9E" }}
                  >
                    {doc.satisfied ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                  </button>
                  <span
                    className="flex-1 text-[13px]"
                    style={{
                      color: doc.satisfied ? "#449235" : "#1A1A1A",
                      textDecoration: doc.satisfied ? "line-through" : undefined,
                    }}
                  >
                    {doc.label}
                  </span>
                  <button
                    type="button"
                    onClick={() => setRequiredDocs((d) => d.filter((_, j) => j !== i))}
                    title="Remove"
                    style={{ color: "#BABABA" }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              <AddRequiredDoc onAdd={(label) => setRequiredDocs((d) => [...d, { label, satisfied: false }])} />
            </SectionCard>

            <div
              className="flex flex-col gap-2 rounded-lg p-4"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
            >
              {err && <p className="text-xs" style={{ color: "#DC2626" }}>{err}</p>}
              <button
                type="button"
                onClick={saveAndResubmit}
                disabled={busy}
                className="flex h-10 items-center justify-center gap-2 rounded-md text-[13px] font-semibold text-white disabled:opacity-60"
                style={{ backgroundColor: "#D76736" }}
              >
                <Paperclip className="h-3.5 w-3.5" />
                {submitMutation.isPending ? "Resubmitting…" : "Save & Resubmit"}
              </button>
              <button
                type="button"
                onClick={() => void save()}
                disabled={busy}
                className="flex h-10 items-center justify-center rounded-md border text-[13px] font-medium disabled:opacity-60"
                style={{ borderColor: "#E5E7EB", color: "#515157" }}
              >
                {updateMutation.isPending ? "Saving…" : "Save draft"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Inline "add a required document" row — preset suggestions + free text so the
// requester can record any document they (or the reviewer) flagged.
const DOC_SUGGESTIONS = ["Signed contract / DPA", "DPIA", "Consent evidence", "Data flow diagram"];

function AddRequiredDoc({ onAdd }: { onAdd: (label: string) => void }) {
  const [value, setValue] = useState("");
  const add = (label: string) => {
    const v = label.trim();
    if (!v) return;
    onAdd(v);
    setValue("");
  };
  return (
    <div className="flex flex-col gap-2 border-t pt-3" style={{ borderColor: "#F5F5F5" }}>
      <div className="flex flex-wrap gap-1.5">
        {DOC_SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => add(s)}
            className="rounded-full px-2.5 py-1 text-[11px]"
            style={{ backgroundColor: "#F3F4F6", color: "#374151", border: "1px solid #E5E7EB" }}
          >
            + {s}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); add(value); }
          }}
          placeholder="Add another document…"
          className="h-9 flex-1 rounded-md border px-3 text-[12px] outline-none"
          style={{ borderColor: "#E5E7EB" }}
        />
        <button
          type="button"
          onClick={() => add(value)}
          className="flex h-9 w-9 items-center justify-center rounded-md text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
