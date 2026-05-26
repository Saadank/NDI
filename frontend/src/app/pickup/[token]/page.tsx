"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  ShieldCheck,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────

interface Artifact {
  id: string;
  filename: string;
  size_bytes: number;
  mime_type: string | null;
  sha256_hash: string | null;
  uploaded_at: string | null;
}

interface RequestSummary {
  title: string;
  purpose: string;
  requester_org: string | null;
  expires_at: string;
  dpa_required: boolean;
  dpa_accepted: boolean;
  download_count: number;
  max_downloads: number;
}

interface PickupOverview {
  request: RequestSummary;
  artifacts: Artifact[] | null;
}

// ─── API helpers (no auth — these are public pickup endpoints) ────

const API_BASE = "/api/v1/pickup";

async function fetchOverview(token: string): Promise<PickupOverview> {
  const res = await fetch(`${API_BASE}/${token}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Error ${res.status}`);
  }
  return res.json();
}

async function acceptDpa(token: string): Promise<PickupOverview> {
  const res = await fetch(`${API_BASE}/${token}/accept-dpa`, {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Error ${res.status}`);
  }
  return res.json();
}

// ─── Formatting helpers ───────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

// ─── Main page ────────────────────────────────────────────────────

export default function PickupPage() {
  const { token } = useParams<{ token: string }>();
  const queryClient = useQueryClient();
  const [dpaError, setDpaError] = useState<string | null>(null);

  const overviewQuery = useQuery({
    queryKey: ["pickup", token],
    queryFn: () => fetchOverview(token),
    retry: false,
    refetchOnWindowFocus: false,
  });

  const dpaMutation = useMutation({
    mutationFn: () => acceptDpa(token),
    onSuccess: (data) => {
      queryClient.setQueryData(["pickup", token], data);
      setDpaError(null);
    },
    onError: (e) =>
      setDpaError(
        e instanceof Error ? e.message : "Something went wrong. Please try again.",
      ),
  });

  // ── Loading ─────────────────────────────────────────────────────
  if (overviewQuery.isLoading) {
    return (
      <PickupShell>
        <div className="flex items-center justify-center py-20">
          <p className="text-sm" style={{ color: "#9E9E9E" }}>
            Loading secure pickup portal…
          </p>
        </div>
      </PickupShell>
    );
  }

  // ── Error / invalid token ────────────────────────────────────────
  if (overviewQuery.isError || !overviewQuery.data) {
    const msg =
      overviewQuery.error instanceof Error
        ? overviewQuery.error.message
        : "This pickup link is not valid or has already expired.";
    return (
      <PickupShell>
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <div
            className="flex h-14 w-14 items-center justify-center rounded-full"
            style={{ backgroundColor: "#FFF0F0" }}
          >
            <AlertTriangle className="h-7 w-7" style={{ color: "#D32F2F" }} />
          </div>
          <h2 className="text-lg font-bold text-auth-text">
            Invalid or expired link
          </h2>
          <p
            className="text-[13px]"
            style={{ color: "#9E9E9E", maxWidth: 340 }}
          >
            {msg}
          </p>
        </div>
      </PickupShell>
    );
  }

  const { request, artifacts } = overviewQuery.data;
  const expiresAt = new Date(request.expires_at);
  const isExpired = expiresAt <= new Date();
  const exhausted = request.download_count >= request.max_downloads;

  // ── Expired ─────────────────────────────────────────────────────
  if (isExpired) {
    return (
      <PickupShell>
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <div
            className="flex h-14 w-14 items-center justify-center rounded-full"
            style={{ backgroundColor: "#FFFBEB" }}
          >
            <Clock className="h-7 w-7" style={{ color: "#D97706" }} />
          </div>
          <h2 className="text-lg font-bold text-auth-text">Link expired</h2>
          <p
            className="text-[13px]"
            style={{ color: "#9E9E9E", maxWidth: 340 }}
          >
            This secure pickup link expired on {formatDate(request.expires_at)}.
            Please contact the sender to request a new link.
          </p>
        </div>
      </PickupShell>
    );
  }

  // ── Main: DPA gate or file download ─────────────────────────────
  return (
    <PickupShell>
      <div
        className="flex flex-col gap-6 rounded-2xl bg-white p-8"
        style={{
          boxShadow: "0 4px 24px #00000010",
          border: "1px solid #EEEEEE",
        }}
      >
        {/* Header */}
        <div className="flex flex-col gap-1.5">
          <h1 className="text-[22px] font-bold text-auth-text leading-tight">
            Secure file pickup
          </h1>
          {request.requester_org && (
            <p className="text-[13px]" style={{ color: "#9E9E9E" }}>
              Sent by{" "}
              <span className="font-medium" style={{ color: "#515157" }}>
                {request.requester_org}
              </span>
            </p>
          )}
        </div>

        {/* Request details */}
        <div
          className="rounded-lg p-4"
          style={{ backgroundColor: "#F9FAFB", border: "1px solid #EEEEEE" }}
        >
          <p className="text-[13px] font-semibold text-auth-text">
            {request.title}
          </p>
          {request.purpose && (
            <p
              className="mt-1 text-[12px]"
              style={{ color: "#9E9E9E" }}
            >
              {request.purpose}
            </p>
          )}
        </div>

        {/* Divider */}
        <div style={{ height: 1, backgroundColor: "#EEEEEE" }} />

        {/* DPA gate */}
        {!request.dpa_accepted ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-start gap-3">
              <ShieldCheck
                className="mt-0.5 h-5 w-5 shrink-0"
                style={{ color: "#D76736" }}
              />
              <div>
                <p className="text-[13px] font-semibold text-auth-text">
                  Data-sharing agreement required
                </p>
                <p
                  className="mt-1 text-[12px]"
                  style={{ color: "#9E9E9E" }}
                >
                  You must accept the data-sharing agreement before downloading
                  the files. Your acceptance is logged for compliance purposes.
                </p>
              </div>
            </div>

            {dpaError && (
              <p className="text-[12px]" style={{ color: "#D32F2F" }}>
                {dpaError}
              </p>
            )}

            <button
              type="button"
              onClick={() => dpaMutation.mutate()}
              disabled={dpaMutation.isPending}
              className="flex h-11 w-full items-center justify-center rounded-md text-[14px] font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: "#D76736" }}
            >
              {dpaMutation.isPending
                ? "Recording acceptance…"
                : "Accept data-sharing agreement"}
            </button>
          </div>
        ) : (
          /* File list */
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <CheckCircle2
                className="h-5 w-5"
                style={{ color: "#449235" }}
              />
              <p
                className="text-[13px] font-semibold"
                style={{ color: "#449235" }}
              >
                Agreement accepted — files ready
              </p>
            </div>

            {exhausted && (
              <div
                className="rounded-lg p-3 text-[12px]"
                style={{
                  backgroundColor: "#FFF0F0",
                  color: "#D32F2F",
                  border: "1px solid #FFD6D6",
                }}
              >
                This link has reached its download limit ({request.max_downloads}{" "}
                downloads used). Contact the sender if you need the files again.
              </div>
            )}

            {artifacts && artifacts.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {artifacts.map((artifact) => (
                  <li
                    key={artifact.id}
                    className="flex items-center justify-between rounded-lg p-3"
                    style={{
                      border: "1px solid #EEEEEE",
                      backgroundColor: "#FAFAFA",
                    }}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <FileText
                        className="h-4 w-4 shrink-0"
                        style={{ color: "#9E9E9E" }}
                      />
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-medium text-auth-text">
                          {artifact.filename}
                        </p>
                        <p
                          className="text-[11px]"
                          style={{ color: "#9E9E9E" }}
                        >
                          {formatBytes(artifact.size_bytes)}
                        </p>
                      </div>
                    </div>

                    {!exhausted && (
                      <a
                        href={`/api/v1/pickup/${token}/files/${artifact.id}/download`}
                        className="ml-3 flex h-8 shrink-0 items-center gap-1.5 rounded-md px-3 text-[12px] font-semibold text-white"
                        style={{ backgroundColor: "#D76736" }}
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p
                className="text-center text-[13px]"
                style={{ color: "#9E9E9E" }}
              >
                No files are attached to this share yet.
              </p>
            )}
          </div>
        )}

        {/* Expiry / download counter */}
        <div
          className="flex items-center justify-between pt-2"
          style={{ borderTop: "1px solid #EEEEEE" }}
        >
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
            <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
              Expires {formatDate(request.expires_at)}
            </p>
          </div>
          <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
            {request.download_count} / {request.max_downloads} downloads
          </p>
        </div>
      </div>
    </PickupShell>
  );
}

// ─── Shell ────────────────────────────────────────────────────────

function PickupShell({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex min-h-screen flex-col"
      style={{ backgroundColor: "#FFFFF9" }}
    >
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center px-8"
        style={{
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #EEEEEE",
        }}
      >
        <span
          className="text-[17px] font-bold"
          style={{ color: "#D76736" }}
        >
          Datarix
        </span>
      </div>

      {/* Content */}
      <div className="mx-auto flex w-full max-w-[520px] flex-1 flex-col justify-center px-6 py-12">
        {children}
      </div>

      {/* Footer */}
      <div className="px-8 py-4" style={{ borderTop: "1px solid #EEEEEE" }}>
        <p
          className="text-center text-[11px]"
          style={{ color: "#BABABA" }}
        >
          Powered by Datarix · Secure data sharing in compliance with PDPL
        </p>
      </div>
    </div>
  );
}
