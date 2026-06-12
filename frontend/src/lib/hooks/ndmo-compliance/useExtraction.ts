"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  acceptCandidate,
  assignCandidate,
  clearCandidates,
  dismissCandidate,
  getDraftStatus,
  listCandidates,
  listExtractionConnections,
  runScan,
  startDrafting,
} from "@/lib/api/products/ndmo-compliance/glossary.api";

import { GLOSSARY_NS } from "./useGlossary";

/** Poll AI-draft progress.  Keeps polling while a run is active OR while any
 *  candidate still lacks a definition (so "Resume" appears after an interrupt). */
export function useDraftStatus(enabled: boolean) {
  return useQuery({
    queryKey: [GLOSSARY_NS, "extraction", "draft-status"],
    queryFn: getDraftStatus,
    enabled,
    refetchInterval: (q) => (q.state.data?.active ? 3000 : false),
  });
}

export function useStartDrafting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => startDrafting(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "extraction", "draft-status"] });
      qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "extraction", "candidates"] });
    },
  });
}

export function useExtractionConnections() {
  return useQuery({
    queryKey: [GLOSSARY_NS, "extraction", "connections"],
    queryFn: listExtractionConnections,
  });
}

export function useCandidates(
  params: { status?: string; schema?: string; table?: string } = {},
  options: { poll?: boolean } = {},
) {
  return useQuery({
    queryKey: [GLOSSARY_NS, "extraction", "candidates", params],
    queryFn: () => listCandidates(params),
    // While AI drafting runs in the background, poll so definitions appear.
    refetchInterval: options.poll ? 4000 : false,
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "extraction"] });
  qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "terms"] });
}

export function useRunScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { connection_id: string; ai_draft: boolean }) => runScan(body),
    onSuccess: () => invalidate(qc),
  });
}

export function useAcceptCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, domainId, force }: { id: string; domainId?: string; force?: boolean }) =>
      acceptCandidate(id, { domain_id: domainId, force }),
    onSuccess: () => invalidate(qc),
  });
}

export function useAssignCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, domainId }: { id: string; domainId: string }) =>
      assignCandidate(id, { domain_id: domainId }),
    onSuccess: () => invalidate(qc),
  });
}

export function useDismissCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) => dismissCandidate(id, reason),
    onSuccess: () => invalidate(qc),
  });
}

export function useClearCandidates() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (table?: string) => clearCandidates(table),
    onSuccess: () => invalidate(qc),
  });
}
