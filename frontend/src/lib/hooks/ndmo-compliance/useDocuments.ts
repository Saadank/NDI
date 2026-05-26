"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getDocument,
  getDocumentStatus,
  initiateUpload,
  listDocuments,
} from "@/lib/api/products/ndmo-compliance/documents.api";
import type { InitiateUploadBody } from "@/lib/types/ndmo-compliance";

const NS = "ndmo-compliance";

export function useDocuments(params: { cycle_id?: number; limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: [NS, "documents", params],
    queryFn: () => listDocuments(params),
  });
}

export function useDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: [NS, "documents", documentId],
    queryFn: () => getDocument(documentId!),
    enabled: Boolean(documentId),
  });
}

export function useDocumentStatus(documentId: string | undefined) {
  return useQuery({
    queryKey: [NS, "documents", documentId, "status"],
    queryFn: () => getDocumentStatus(documentId!),
    enabled: Boolean(documentId),
    // Poll while the document is still processing.
    refetchInterval: (q) => {
      const node = q.state.data;
      const flat = flattenStatuses(node ?? null);
      const stillRunning = flat.some((s) => s === "in_progress" || s === "pending");
      return stillRunning ? 3000 : false;
    },
  });
}

export function useInitiateUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: InitiateUploadBody) => initiateUpload(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NS, "documents"] }),
  });
}

function flattenStatuses(node: { status: string; children?: any[] } | null): string[] {
  if (!node) return [];
  const out = [node.status];
  for (const c of node.children ?? []) out.push(...flattenStatuses(c));
  return out;
}
