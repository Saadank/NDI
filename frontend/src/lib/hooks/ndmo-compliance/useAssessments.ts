"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getAssessment,
  listAssessments,
  runAssessment,
  submitReview,
} from "@/lib/api/products/ndmo-compliance/assessments.api";
import type {
  RunAssessmentBody,
  SubmitReviewBody,
} from "@/lib/types/ndmo-compliance";

const NS = "ndmo-compliance";

export function useAssessments(params: { status?: string; limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: [NS, "assessments", params],
    queryFn: () => listAssessments(params),
  });
}

export function useAssessment(assessmentId: string | undefined) {
  return useQuery({
    queryKey: [NS, "assessments", assessmentId],
    queryFn: () => getAssessment(assessmentId!),
    enabled: Boolean(assessmentId),
  });
}

export function useRunAssessment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RunAssessmentBody) => runAssessment(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NS, "assessments"] }),
  });
}

export function useSubmitReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: SubmitReviewBody }) =>
      submitReview(id, body),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: [NS, "assessments"] });
      qc.invalidateQueries({ queryKey: [NS, "assessments", id] });
    },
  });
}
