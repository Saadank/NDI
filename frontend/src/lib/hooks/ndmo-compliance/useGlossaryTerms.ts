"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelReview,
  createTerm,
  deleteTerm,
  deprecateTerm,
  getTerm,
  listReviewQueue,
  listTerms,
  reinstateTerm,
  reviewTerm,
  submitTerm,
  updateTerm,
  type ListTermsParams,
} from "@/lib/api/products/ndmo-compliance/glossary.api";
import type {
  CreateTermBody,
  DeprecateBody,
  ReviewBody,
  UpdateTermBody,
} from "@/lib/types/ndmo-compliance/glossary";

import { GLOSSARY_NS } from "./useGlossary";

export function useGlossaryTerms(params: ListTermsParams = {}) {
  return useQuery({
    queryKey: [GLOSSARY_NS, "terms", params],
    queryFn: () => listTerms(params),
  });
}

export function useGlossaryTerm(termId: string | undefined) {
  return useQuery({
    queryKey: [GLOSSARY_NS, "terms", termId],
    queryFn: () => getTerm(termId!),
    enabled: Boolean(termId),
  });
}

export function useReviewQueue() {
  return useQuery({
    queryKey: [GLOSSARY_NS, "review-queue"],
    queryFn: listReviewQueue,
  });
}

/** Invalidate everything term/queue/role-count related after a mutation. */
function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "terms"] });
  qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "review-queue"] });
  qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "me"] });
  qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "domains"] });
}

export function useCreateTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTermBody) => createTerm(body),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useUpdateTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateTermBody }) =>
      updateTerm(id, body),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTerm(id),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useSubmitTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => submitTerm(id),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useCancelReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelReview(id),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useReviewTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ReviewBody }) =>
      reviewTerm(id, body),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeprecateTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: DeprecateBody }) =>
      deprecateTerm(id, body),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useReinstateTerm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reinstateTerm(id),
    onSuccess: () => invalidateAll(qc),
  });
}
