"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { ArrowLeft, FileText, UploadCloud, X } from "lucide-react";

import { uploadFileForRequest } from "@/lib/api/products/data-sharing/files.api";
import {
  useDeleteFile,
  useRequestFiles,
  useUploadFile,
} from "@/lib/hooks/data-sharing/useFiles";
import { useRequestDetail } from "@/lib/hooks/data-sharing/useRequestDetail";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { REQUEST_STATUS_LABELS } from "@/lib/utils/constants";

export function PrepareAndUpload({ id }: { id: string }) {
  // Stewards (requester role) and the data owner who approved the request
  // both can deliver — backend enforces actual authorization, this is just
  // a UI gate.
  const { isReady } = useRoleGuard({ allow: ["requester", "data_owner"] });
  const reqQuery = useRequestDetail(id);

  if (!isReady) return null;
  const filesQuery = useRequestFiles(id);
  const upload = useUploadFile(id);
  const del = useDeleteFile(id);
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  if (reqQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-auth-text-subtle">Loading…</p>
      </div>
    );
  }
  if (reqQuery.isError || !reqQuery.data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-red-600">Failed to load request.</p>
      </div>
    );
  }

  const r = reqQuery.data;

  const handlePicked = async (files: FileList | null) => {
    if (!files) return;
    setError(null);
    try {
      for (const f of Array.from(files)) {
        // We use the lower-level helper directly (instead of the hook's
        // mutateAsync) so each file gets its own initiate+PUT call without
        // queueing through React Query's mutation chain.
        await uploadFileForRequest(id, f);
      }
      await filesQuery.refetch();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setError(msg);
    }
  };

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
          href="/prepare"
          className="flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs font-medium"
          style={{ borderColor: "#EEEEEE", color: "#616161" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </Link>
        <h1 className="text-lg font-bold text-auth-text">{r.title}</h1>
        <span
          className="rounded px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: "#F0FAF0", color: "#449235" }}
        >
          {REQUEST_STATUS_LABELS[r.status] ?? r.status}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <div
          className="rounded-lg p-4"
          style={{
            backgroundColor: "#F0FAF0",
            border: "1px solid #B7E4B0",
          }}
        >
          <p className="text-[13px] font-medium" style={{ color: "#1F6B14" }}>
            Approved — ready for delivery
          </p>
          <p className="mt-1 text-xs" style={{ color: "#365314" }}>
            {r.data_type === "file"
              ? "Upload the dataset files. They are scanned and made available to the receiver."
              : "Re-run the approved query and review the result before delivery."}
          </p>
        </div>

        {r.data_type === "file" ? (
          <>
            <div
              className="flex flex-col items-center gap-4 rounded-xl py-12"
              style={{ border: "2px dashed #EEEEEE", backgroundColor: "#FFFFFF" }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                handlePicked(e.dataTransfer.files);
              }}
            >
              <input
                ref={inputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => handlePicked(e.target.files)}
              />
              <div
                className="flex h-12 w-12 items-center justify-center rounded-full"
                style={{ backgroundColor: "#FFF5F0" }}
              >
                <UploadCloud className="h-6 w-6" style={{ color: "#D76736" }} />
              </div>
              <p className="text-sm font-medium text-auth-text">
                Drag and drop files here
              </p>
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="flex h-8 items-center gap-2 rounded-md border px-4 text-[13px] font-medium"
                style={{ borderColor: "#D76736", color: "#D76736" }}
                disabled={upload.isPending}
              >
                {upload.isPending ? "Uploading…" : "Browse files"}
              </button>
              <p className="text-xs" style={{ color: "#9E9E9E" }}>
                Max 4 GB per file · PDF, CSV, XLSX, JSON, ZIP
              </p>
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
                <span className="text-[13px] font-semibold text-auth-text">
                  Uploaded files (
                  {filesQuery.data?.length ?? 0})
                </span>
              </div>
              <div className="flex flex-col">
                {filesQuery.isLoading && (
                  <p className="px-5 py-4 text-xs text-auth-text-subtle">
                    Loading…
                  </p>
                )}
                {(filesQuery.data ?? []).map((f, i, arr) => (
                  <div
                    key={f.id}
                    className="flex h-12 items-center gap-3 px-5"
                    style={{
                      borderBottom:
                        i < arr.length - 1 ? "1px solid #F5F5F5" : undefined,
                    }}
                  >
                    <FileText
                      className="h-4 w-4"
                      style={{ color: "#9E9E9E" }}
                    />
                    <div className="flex flex-1 flex-col">
                      <span className="text-[13px]">{f.original_filename}</span>
                      <span className="text-[11px] text-auth-text-subtle">
                        {(f.file_size_bytes / 1024).toFixed(1)} KB · {f.status}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => del.mutate(f.id)}
                      className="text-[11px] text-auth-text-muted hover:text-red-600"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                {filesQuery.data && filesQuery.data.length === 0 && (
                  <p className="px-5 py-6 text-xs text-auth-text-placeholder">
                    No files uploaded yet.
                  </p>
                )}
              </div>
            </div>
          </>
        ) : (
          <div
            className="rounded-lg p-6"
            style={{
              backgroundColor: "#FFFFFF",
              border: "1px solid #EEEEEE",
            }}
          >
            <p className="text-[13px] font-semibold text-auth-text">
              Structured query
            </p>
            <p className="mt-2 text-xs text-auth-text-muted">
              {r.selection_mode === "query"
                ? "The approved SQL is shown below. Run it from your data tooling and confirm the row count before delivery."
                : "Tables selected for sharing are listed below."}
            </p>
            {r.selection_mode === "query" && r.custom_sql && (
              <pre
                className="mt-4 overflow-x-auto rounded-md p-4 font-mono text-xs"
                style={{
                  backgroundColor: "#1E1E2E",
                  color: "#D4D4D4",
                }}
              >
                {r.custom_sql}
              </pre>
            )}
            {r.selection_mode === "tables" && (
              <ul className="mt-4 flex flex-col gap-1">
                {(r.selected_items ?? []).map((it, i) => (
                  <li key={i} className="text-xs">
                    {[it.schema, it.table].filter(Boolean).join(".")}
                    {it.columns?.length
                      ? ` (${it.columns.join(", ")})`
                      : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
