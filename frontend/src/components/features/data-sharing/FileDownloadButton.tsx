"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { getDownloadUrl } from "@/lib/api/products/data-sharing/files.api";
import type { FileStatus } from "@/lib/types/data-sharing/file.types";

// A file can be fetched once it is physically in the object store and not
// quarantined. Mirrors the backend `get_download_url` status gate.
export function isDownloadable(status: FileStatus): boolean {
  return status === "uploaded" || status === "clean";
}

interface Props {
  fileId: string;
  /** Disable + dim when the file isn't ready (e.g. still scanning / infected). */
  status?: FileStatus;
  /** "link" = orange text button; "icon" = compact icon button. */
  variant?: "link" | "icon";
}

/**
 * Resolves a short-lived presigned URL on click and opens it. Used by the
 * requester detail, the Data Owner approval screen, and the DPO review screen
 * so every role that can view a request can also download its files.
 */
export function FileDownloadButton({ fileId, status, variant = "link" }: Props) {
  const [loading, setLoading] = useState(false);
  const disabled = loading || (status !== undefined && !isDownloadable(status));

  const handleClick = async () => {
    if (disabled) return;
    setLoading(true);
    try {
      const { download_url } = await getDownloadUrl(fileId);
      window.open(download_url, "_blank", "noopener,noreferrer");
    } finally {
      setLoading(false);
    }
  };

  if (variant === "icon") {
    return (
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        title="Download"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border disabled:opacity-40"
        style={{ borderColor: "#E5E7EB", color: "#D76736" }}
      >
        <Download className="h-3.5 w-3.5" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      className="flex shrink-0 items-center gap-1 text-[13px] font-medium disabled:opacity-40"
      style={{ color: "#D76736" }}
    >
      <Download className="h-3.5 w-3.5" />
      {loading ? "…" : "Download"}
    </button>
  );
}
