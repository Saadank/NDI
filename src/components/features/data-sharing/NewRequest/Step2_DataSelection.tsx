"use client";

import {
  ArrowLeft,
  ArrowRight,
  CircleCheck,
  Database,
  FileText,
  UploadCloud,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useConnections } from "@/lib/hooks/data-sharing/useConnections";
import { useSchemas } from "@/lib/hooks/data-sharing/useSchemas";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useNewRequestStore } from "@/lib/store/new-request.store";
import type { DataType } from "@/lib/types/data-sharing/request.types";

function ModeSwitcher({
  mode,
  onChange,
}: {
  mode: DataType;
  onChange: (m: DataType) => void;
}) {
  return (
    <div
      className="flex h-14 overflow-hidden rounded-lg"
      style={{ border: "1px solid #EEEEEE", backgroundColor: "#FFFFFF" }}
    >
      <button
        type="button"
        onClick={() => onChange("file")}
        className="flex flex-1 items-center gap-3 px-5"
        style={mode === "file" ? { backgroundColor: "#FFF5F0" } : {}}
      >
        <UploadCloud
          className="h-[18px] w-[18px] shrink-0"
          style={{ color: mode === "file" ? "#D76736" : "#9E9E9E" }}
        />
        <div className="flex flex-col items-start gap-0.5">
          <p
            className="text-[13px] font-medium"
            style={{ color: mode === "file" ? "#D76736" : "#9E9E9E" }}
          >
            File Upload
          </p>
          <p
            className="text-[11px] font-normal"
            style={{ color: mode === "file" ? "#D76736CC" : "#BABABA" }}
          >
            Upload files to share
          </p>
        </div>
      </button>
      <span
        className="w-px self-stretch"
        style={{ backgroundColor: "#EEEEEE" }}
      />
      <button
        type="button"
        onClick={() => onChange("structured")}
        className="flex flex-1 items-center gap-3 px-5"
        style={mode === "structured" ? { backgroundColor: "#FFF5F0" } : {}}
      >
        <Database
          className="h-[18px] w-[18px] shrink-0"
          style={{ color: mode === "structured" ? "#D76736" : "#9E9E9E" }}
        />
        <div className="flex flex-col items-start gap-0.5">
          <p
            className="text-[13px] font-medium"
            style={{ color: mode === "structured" ? "#D76736" : "#9E9E9E" }}
          >
            Structured Data
          </p>
          <p
            className="text-[11px] font-normal"
            style={{
              color: mode === "structured" ? "#D76736CC" : "#BABABA",
            }}
          >
            Query a database connection
          </p>
        </div>
      </button>
    </div>
  );
}

function FileMode() {
  const stagedFiles = useNewRequestStore((s) => s.staged_files);
  const setField = useNewRequestStore((s) => s.set);
  const inputRef = useRef<HTMLInputElement>(null);
  const [pickedFiles, setPickedFiles] = useState<File[]>([]);

  // If the user came back to Step 2 (e.g. from Step 3 via Edit), the staged
  // metadata is still in the store and the actual File objects are still on
  // the window global from earlier — pull them back into local state so any
  // subsequent add doesn't clobber them.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const existing =
      (window as unknown as { __datarix_staged_files?: File[] })
        .__datarix_staged_files ?? [];
    if (existing.length > 0 && pickedFiles.length === 0) {
      setPickedFiles(existing);
    }
    // Run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // We hold actual File objects in module-local state and just store metadata
  // in the persisted Zustand slice. The Step 3 submit handler reads this map
  // when uploading.
  const handlePicked = (files: FileList | null) => {
    if (!files) return;
    const arr = Array.from(files);
    const merged = [...pickedFiles, ...arr];
    setPickedFiles(merged);
    setField(
      "staged_files",
      merged.map((f) => ({ name: f.name, size: f.size, type: f.type })),
    );
    // Also stash the actual File objects on window so step 3 can access them.
    if (typeof window !== "undefined") {
      (window as unknown as { __datarix_staged_files?: File[] }).__datarix_staged_files = merged;
    }
  };

  const removeAt = (i: number) => {
    const next = pickedFiles.filter((_, idx) => idx !== i);
    setPickedFiles(next);
    setField(
      "staged_files",
      next.map((f) => ({ name: f.name, size: f.size, type: f.type })),
    );
    if (typeof window !== "undefined") {
      (window as unknown as { __datarix_staged_files?: File[] }).__datarix_staged_files = next;
    }
  };

  return (
    <div className="flex flex-1 flex-col gap-4 p-6">
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => handlePicked(e.target.files)}
      />

      <div
        className="flex flex-col items-center gap-4 rounded-xl py-12"
        style={{ border: "2px dashed #EEEEEE" }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handlePicked(e.dataTransfer.files);
        }}
      >
        <div
          className="flex h-12 w-12 items-center justify-center rounded-full"
          style={{ backgroundColor: "#FFF5F0" }}
        >
          <UploadCloud className="h-6 w-6" style={{ color: "#D76736" }} />
        </div>
        <div className="flex flex-col items-center gap-1">
          <p className="text-sm font-medium text-auth-text">
            Drag and drop files here
          </p>
          <p className="text-xs" style={{ color: "#BABABA" }}>
            or
          </p>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex h-8 items-center gap-2 rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#D76736", color: "#D76736" }}
        >
          Browse files
        </button>
        <p className="text-xs" style={{ color: "#9E9E9E" }}>
          Files are uploaded after you submit on Step 3
        </p>
      </div>

      {stagedFiles.length > 0 && (
        <div className="flex flex-col gap-1">
          <p
            className="mb-2 text-[11px] font-semibold uppercase tracking-[0.8px]"
            style={{ color: "#9E9E9E" }}
          >
            {stagedFiles.length} {stagedFiles.length === 1 ? "file" : "files"}{" "}
            staged
          </p>
          {stagedFiles.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="flex items-center gap-3 rounded-lg px-4 py-3"
              style={{ border: "1px solid #EEEEEE" }}
            >
              <FileText
                className="h-4 w-4 shrink-0"
                style={{ color: "#9E9E9E" }}
              />
              <div className="flex flex-1 flex-col gap-0.5">
                <span className="text-[13px] font-medium text-auth-text">
                  {f.name}
                </span>
                <span className="text-xs" style={{ color: "#9E9E9E" }}>
                  {(f.size / 1024).toFixed(1)} KB · {f.type || "unknown"}
                </span>
              </div>
              <button type="button" onClick={() => removeAt(i)}>
                <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StructuredMode() {
  const connectionId = useNewRequestStore((s) => s.connection_id);
  const selectionMode = useNewRequestStore((s) => s.selection_mode);
  const customSql = useNewRequestStore((s) => s.custom_sql);
  const selectedItems = useNewRequestStore((s) => s.selected_items);
  const setField = useNewRequestStore((s) => s.set);

  const connectionsQuery = useConnections();
  const schemasQuery = useSchemas(connectionId ?? "");

  return (
    <div className="flex flex-1 flex-col gap-4 p-6">
      <p
        className="text-[11px] font-semibold uppercase tracking-[0.8px]"
        style={{ color: "#616161" }}
      >
        Select a Data Source
      </p>

      {connectionsQuery.isLoading && (
        <p className="text-[13px]" style={{ color: "#9E9E9E" }}>
          Loading connections…
        </p>
      )}
      {connectionsQuery.isError && (
        <p className="text-[13px]" style={{ color: "#EF4444" }}>
          Failed to load connections.
        </p>
      )}

      {(connectionsQuery.data ?? []).map((c) => {
        const isSelected = c.id === connectionId;
        return (
          <button
            key={c.id}
            type="button"
            onClick={() => {
              setField("connection_id", c.id);
              if (!selectionMode) setField("selection_mode", "tables");
            }}
            className="flex h-14 items-center gap-3 rounded-lg px-3 text-left"
            style={{
              backgroundColor: isSelected ? "#FFF5F0" : "#FFFFFF",
              border: `1px solid ${isSelected ? "#D76736" : "#EEEEEE"}`,
            }}
          >
            <Database
              className="h-5 w-5 shrink-0"
              style={{ color: isSelected ? "#D76736" : "#9E9E9E" }}
            />
            <div className="flex flex-1 flex-col gap-0.5">
              <p
                className="text-[13px] font-semibold"
                style={{ color: "#1A1A1A" }}
              >
                {c.description || `${c.host}/${c.database ?? ""}`}
              </p>
              <p className="text-xs" style={{ color: "#616161" }}>
                {c.db_type} · {c.host}:{c.port}
              </p>
            </div>
            {isSelected && (
              <CircleCheck
                className="h-[18px] w-[18px] shrink-0"
                style={{ color: "#D76736" }}
              />
            )}
          </button>
        );
      })}

      {connectionId && (
        <>
          <div className="mt-2 h-px w-full" style={{ backgroundColor: "#EEEEEE" }} />
          <div className="flex items-center gap-3">
            {(["tables", "query"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setField("selection_mode", m)}
                className="flex h-9 items-center rounded-md px-3 text-[13px] font-medium"
                style={
                  selectionMode === m
                    ? {
                        backgroundColor: "#FFF5F0",
                        color: "#D76736",
                        border: "1px solid #D76736",
                      }
                    : {
                        backgroundColor: "#FFFFFF",
                        color: "#616161",
                        border: "1px solid #EEEEEE",
                      }
                }
              >
                {m === "tables" ? "Pick tables" : "Custom SQL"}
              </button>
            ))}
          </div>

          {selectionMode === "tables" && (
            <div className="flex flex-col gap-2">
              {schemasQuery.isLoading && (
                <p className="text-[13px]" style={{ color: "#9E9E9E" }}>
                  Loading schema…
                </p>
              )}
              {schemasQuery.isError && (
                <p className="text-[13px]" style={{ color: "#EF4444" }}>
                  Failed to introspect schema.
                </p>
              )}
              {(schemasQuery.data?.schema_data?.schemas ?? []).map((s) => (
                <div key={s.name} className="flex flex-col gap-1">
                  <p
                    className="text-[11px] font-semibold uppercase tracking-[0.6px]"
                    style={{ color: "#616161" }}
                  >
                    {s.name}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {s.tables.map((t) => {
                      const isPicked = selectedItems.some(
                        (it) => it.schema === s.name && it.table === t.name,
                      );
                      return (
                        <button
                          key={`${s.name}.${t.name}`}
                          type="button"
                          onClick={() => {
                            const next = isPicked
                              ? selectedItems.filter(
                                  (it) =>
                                    !(it.schema === s.name && it.table === t.name),
                                )
                              : [
                                  ...selectedItems,
                                  { schema: s.name, table: t.name },
                                ];
                            setField("selected_items", next);
                          }}
                          className="flex h-8 items-center rounded-md px-3 text-xs"
                          style={{
                            backgroundColor: isPicked ? "#FFF5F0" : "#FFFFFF",
                            border: `1px solid ${isPicked ? "#D76736" : "#EEEEEE"}`,
                            color: isPicked ? "#D76736" : "#1A1A1A",
                          }}
                        >
                          {t.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {selectionMode === "query" && (
            <textarea
              value={customSql}
              onChange={(e) => setField("custom_sql", e.target.value)}
              placeholder="SELECT ... FROM ... WHERE ..."
              className="h-40 w-full resize-y rounded-md border p-3 font-mono text-xs outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
          )}
        </>
      )}
    </div>
  );
}

export function Step2_DataSelection() {
  const { isReady } = useRoleGuard({ allow: ["requester", "data_owner"] });
  const router = useRouter();
  const dataType = useNewRequestStore((s) => s.data_type);

  if (!isReady) return null;
  const setField = useNewRequestStore((s) => s.set);
  const stagedFiles = useNewRequestStore((s) => s.staged_files);
  const connectionId = useNewRequestStore((s) => s.connection_id);
  const selectionMode = useNewRequestStore((s) => s.selection_mode);
  const customSql = useNewRequestStore((s) => s.custom_sql);
  const selectedItems = useNewRequestStore((s) => s.selected_items);

  const canProceed =
    dataType === "file"
      ? stagedFiles.length > 0
      : !!connectionId &&
        ((selectionMode === "tables" && selectedItems.length > 0) ||
          (selectionMode === "query" && customSql.trim().length > 0));

  return (
    <div className="flex flex-col gap-4">
      <ModeSwitcher mode={dataType} onChange={(m) => setField("data_type", m)} />

      <div
        className="flex flex-1 flex-col rounded-lg overflow-hidden"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        {dataType === "file" ? <FileMode /> : <StructuredMode />}
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => router.push("/data-sharing/new")}
          className="flex h-9 items-center gap-1.5 rounded-md border px-4 text-[13px] font-medium"
          style={{ borderColor: "#EEEEEE", color: "#616161" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Step 1
        </button>
        <button
          type="button"
          disabled={!canProceed}
          onClick={() =>
            canProceed && router.push("/data-sharing/new/step-3")
          }
          className="flex h-10 items-center gap-2 rounded-lg px-5 text-sm font-semibold"
          style={{
            backgroundColor: canProceed ? "#D76736" : "#D0D0D0",
            color: canProceed ? "#FFFFFF" : "#9E9E9E",
            cursor: canProceed ? "pointer" : "not-allowed",
          }}
        >
          Next
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
