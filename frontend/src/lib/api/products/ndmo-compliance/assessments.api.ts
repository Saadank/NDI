/**
 * NDMO Compliance — assessments API wrappers.
 */
import { get, post } from "@/lib/api/client";
import type {
  AssessmentDetail,
  AssessmentListItem,
  RunAssessmentBody,
  RunAssessmentResponse,
  SubmitReviewBody,
} from "@/lib/types/ndmo-compliance";

const BASE = "/api/v1/products/ndmo-compliance/assessments";

export function runAssessment(body: RunAssessmentBody = {}) {
  return post<RunAssessmentResponse, RunAssessmentBody>(`${BASE}/run`, body);
}

export function listAssessments(params: {
  status?: string;
  limit?: number;
  offset?: number;
} = {}) {
  return get<AssessmentListItem[]>(BASE, { params });
}

export function getAssessment(assessmentId: string) {
  return get<AssessmentDetail>(`${BASE}/${assessmentId}`);
}

export function submitReview(assessmentId: string, body: SubmitReviewBody) {
  return post<void, SubmitReviewBody>(`${BASE}/${assessmentId}/review`, body);
}
