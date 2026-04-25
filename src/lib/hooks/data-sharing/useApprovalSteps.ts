"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  approveStep,
  getRequestSteps,
  rejectStep,
  requestChangesOnStep,
} from "@/lib/api/products/data-sharing/steps.api";
import type { StepStatus } from "@/lib/types/data-sharing/step.types";

export function useApprovalSteps(requestId: string) {
  return useQuery({
    queryKey: ["data-sharing", "steps", requestId],
    queryFn: () => getRequestSteps(requestId),
    enabled: Boolean(requestId),
  });
}

export function useActOnStep(requestId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      stepId: string;
      status: StepStatus;
      comment?: string;
    }) => {
      if (vars.status === "approved") return approveStep(vars.stepId, vars.comment);
      if (vars.status === "rejected") return rejectStep(vars.stepId, vars.comment);
      return requestChangesOnStep(vars.stepId, vars.comment);
    },
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["data-sharing", "steps", requestId],
      }),
  });
}
