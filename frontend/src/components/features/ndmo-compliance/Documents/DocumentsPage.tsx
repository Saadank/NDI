"use client";

/**
 * NDMO Compliance — Documents screen.
 *
 * Layout: header bar (title + Run Assessment CTA) → drag-drop upload zone →
 * document list with status pill + processed_at + pipeline progress.
 *
 * Upload flow:
 *   1. POST /documents/initiate -> { document_id, presigned_put_url }
 *   2. Browser fetch(presigned_put_url, {method:'PUT', body: file})
 *      (presigned URL targets MinIO directly — bypasses the API server)
 *   3. MinIO bucket-notify webhook triggers the Restate ingestion workflow
 *      server-side.  Frontend re-fetches /documents to see status flips.
 */
import { useCallback, useRef, useState } from "react";
import { FileUp, Loader2, PlayCircle, RefreshCw, Upload } from "lucide-react";

import { initiateUpload } from "@/lib/api/products/ndmo-compliance/documents.api";
import { useDocuments } from "@/lib/hooks/ndmo-compliance/useDocuments";
import { useRunAssessment } from "@/lib/hooks/ndmo-compliance/useAssessments";
import {
  BG,
  BG_CARD,
  BORDER,
  BRAND,
  BRAND_SOFT,
  DocumentStatusBadge,
  NEUTRAL_TEXT,
  SUBTLE_TEXT,
} from "../shared/badges";
import type { NdmoDocument } from "@/lib/types/ndmo-compliance";

const ACCEPTED = ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx";
const MAX_SIZE_MB = 100;

interface UploadInFlight {
  file_name: string;
  size_bytes: number;
  status: "initiating" | "uploading" | "uploaded" | "failed";
  progress: number;
  error?: string;
}

export function DocumentsPage() {
  const docs = useDocuments({ limit: 500 });
  const runMutation = useRunAssessment();
  const fileInput = useRef<HTMLInputElement>(null);
  const [inflight, setInflight] = useState<UploadInFlight[]>([]);
  const [dragActive, setDragActive] = useState(false);

  const onPickClick = () => fileInput.current?.click();

  const onFiles = useCallback(
    async (files: File[]) => {
      const newOnes: UploadInFlight[] = files.map((f) => ({
        file_name: f.name,
        size_bytes: f.size,
        status: "initiating",
        progress: 0,
      }));
      setInflight((cur) => [...newOnes, ...cur]);
      for (const f of files) {
        await uploadOne(f, (patch) => {
          setInflight((cur) =>
            cur.map((it) => (it.file_name === f.name && it.size_bytes === f.size ? { ...it, ...patch } : it)),
          );
        });
      }
      docs.refetch();
    },
    [docs],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const files = Array.from(e.dataTransfer.files).filter((f) => f.size <= MAX_SIZE_MB * 1024 * 1024);
      if (files.length) onFiles(files);
    },
    [onFiles],
  );

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: BG }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: BG_CARD, borderBottom: `1px solid ${BORDER}` }}
      >
        <div>
          <h1 className="text-lg font-bold" style={{ color: NEUTRAL_TEXT }}>الوثائق</h1>
          <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
            ارفع وثائق الجهة (PDF / Word / Excel / PowerPoint) ليتم استخراجها وفهرستها
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => docs.refetch()}
            className="flex h-9 items-center gap-2 rounded-md border px-3 text-[13px] font-medium"
            style={{ borderColor: BORDER, color: NEUTRAL_TEXT, backgroundColor: BG_CARD }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            تحديث
          </button>
          <button
            type="button"
            disabled={runMutation.isPending}
            onClick={() => runMutation.mutate({ dry_run: false })}
            className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white disabled:opacity-60"
            style={{ backgroundColor: BRAND }}
          >
            {runMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PlayCircle className="h-3.5 w-3.5" />}
            تشغيل التقييم
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        {/* Drag-drop zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
          onClick={onPickClick}
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed py-10 transition-colors"
          style={{
            borderColor: dragActive ? BRAND : BORDER,
            backgroundColor: dragActive ? BRAND_SOFT : BG_CARD,
          }}
        >
          <Upload className="h-6 w-6" style={{ color: BRAND }} />
          <p className="text-[14px] font-semibold" style={{ color: NEUTRAL_TEXT }}>
            اسحب الملفات هنا أو انقر للاختيار
          </p>
          <p className="text-[12px]" style={{ color: SUBTLE_TEXT }}>
            PDF · Word · Excel · PowerPoint — حتى {MAX_SIZE_MB} ميغابايت لكل ملف
          </p>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept={ACCEPTED}
            className="hidden"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              if (files.length) onFiles(files);
              if (fileInput.current) fileInput.current.value = "";
            }}
          />
        </div>

        {/* In-flight uploads (browser-side) */}
        {inflight.length > 0 && (
          <div
            className="flex flex-col gap-2 rounded-xl p-4"
            style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
          >
            <p className="text-[12px] font-semibold" style={{ color: NEUTRAL_TEXT }}>
              رفعٌ قيد التنفيذ
            </p>
            {inflight.map((it) => (
              <InflightRow key={`${it.file_name}-${it.size_bytes}`} item={it} />
            ))}
          </div>
        )}

        {/* Server-side document list */}
        <div
          className="flex flex-col rounded-xl"
          style={{ backgroundColor: BG_CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="flex h-10 items-center gap-2 px-5 text-[11px] font-semibold uppercase tracking-[0.4px]"
            style={{ color: SUBTLE_TEXT, borderBottom: `1px solid ${BORDER}` }}
          >
            <div className="flex-1">اسم الملف</div>
            <div className="w-32">النوع</div>
            <div className="w-24 text-left">الصفحات</div>
            <div className="w-32">الحجم</div>
            <div className="w-40">الحالة</div>
            <div className="w-40">آخر تحديث</div>
          </div>
          {docs.isLoading && (
            <div className="px-5 py-8 text-center text-[12px]" style={{ color: SUBTLE_TEXT }}>
              جارٍ التحميل…
            </div>
          )}
          {docs.data && docs.data.length === 0 && (
            <div className="px-5 py-12 text-center text-[12px]" style={{ color: SUBTLE_TEXT }}>
              لم يتم رفع وثائق بعد. اسحب ملفاً إلى المنطقة بالأعلى للبدء.
            </div>
          )}
          {docs.data?.map((d) => (
            <DocumentRow key={d.id} doc={d} />
          ))}
        </div>
      </div>
    </div>
  );
}

function InflightRow({ item }: { item: UploadInFlight }) {
  const labelByStatus: Record<UploadInFlight["status"], string> = {
    initiating: "تحضير الرفع…",
    uploading: "جارٍ الرفع…",
    uploaded: "تم الرفع",
    failed: "فشل الرفع",
  };
  return (
    <div className="flex items-center gap-3 py-1.5">
      <FileUp className="h-4 w-4 shrink-0" style={{ color: BRAND }} />
      <div className="min-w-0 flex-1 truncate text-[12px] font-medium" style={{ color: NEUTRAL_TEXT }}>
        {item.file_name}
      </div>
      <div className="text-[11px]" style={{ color: SUBTLE_TEXT }}>{formatBytes(item.size_bytes)}</div>
      <div className="w-48">
        <div className="h-1.5 overflow-hidden rounded" style={{ backgroundColor: "#F4F4F4" }}>
          <div className="h-full rounded transition-all" style={{ width: `${item.progress}%`, backgroundColor: BRAND }} />
        </div>
        <p className="mt-1 text-[10px] tabular-nums" style={{ color: SUBTLE_TEXT }}>
          {labelByStatus[item.status]}
          {item.error && ` — ${item.error}`}
        </p>
      </div>
    </div>
  );
}

function DocumentRow({ doc }: { doc: NdmoDocument }) {
  return (
    <div
      className="flex items-center gap-2 px-5 py-3"
      style={{ borderBottom: `1px solid ${BORDER}` }}
    >
      <div className="min-w-0 flex-1 truncate text-[13px] font-medium" style={{ color: NEUTRAL_TEXT }}>
        {doc.file_name}
      </div>
      <div className="w-32 text-[12px]" style={{ color: SUBTLE_TEXT }}>
        {doc.mime_type ?? "—"}
      </div>
      <div className="w-24 text-left text-[12px] tabular-nums" style={{ color: SUBTLE_TEXT }}>
        {doc.page_count ?? "—"}
      </div>
      <div className="w-32 text-[12px] tabular-nums" style={{ color: SUBTLE_TEXT }}>
        {doc.size_bytes != null ? formatBytes(doc.size_bytes) : "—"}
      </div>
      <div className="w-40">
        <DocumentStatusBadge status={doc.status} />
      </div>
      <div className="w-40 text-[12px] tabular-nums" style={{ color: SUBTLE_TEXT }}>
        {formatRelative(doc.processed_at ?? doc.uploaded_at)}
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Direct-to-MinIO upload via presigned PUT
// ───────────────────────────────────────────────────────────────

async function uploadOne(
  file: File,
  patch: (p: Partial<UploadInFlight>) => void,
): Promise<void> {
  try {
    const initiated = await initiateUpload({
      file_name: file.name,
      mime_type: file.type || "application/octet-stream",
      size_bytes: file.size,
    });
    patch({ status: "uploading", progress: 5 });

    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", initiated.presigned_put_url, true);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          patch({ progress: Math.min(99, Math.round((e.loaded / e.total) * 100)) });
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          patch({ status: "uploaded", progress: 100 });
          resolve();
        } else {
          patch({ status: "failed", error: `HTTP ${xhr.status}` });
          reject(new Error(`MinIO PUT failed: ${xhr.status}`));
        }
      };
      xhr.onerror = () => {
        patch({ status: "failed", error: "Network error" });
        reject(new Error("Network error"));
      };
      xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
      xhr.send(file);
    });
  } catch (err) {
    patch({ status: "failed", error: (err as Error).message });
  }
}

// ───────────────────────────────────────────────────────────────
// Formatting
// ───────────────────────────────────────────────────────────────

function formatBytes(n: number): string {
  if (n < 1024) return `${n} بايت`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} كيلوبايت`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} ميغابايت`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} غيغابايت`;
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ar-SA", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}
