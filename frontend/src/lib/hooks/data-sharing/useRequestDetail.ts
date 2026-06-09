"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getRequest,
  submitRequest,
  updateRequest,
} from "@/lib/api/products/data-sharing/requests.api";
import type { UpdateShareRequestBody } from "@/lib/types/data-sharing/request.types";

export function useRequestDetail(id: string) {
  return useQuery({
    queryKey: ["data-sharing", "request", id],
    queryFn: () => getRequest(id),
    enabled: Boolean(id),
  });
}

export function useUpdateRequest(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateShareRequestBody) => updateRequest(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["data-sharing", "request", id] });
    },
  });
}

export function useSubmitRequest(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => submitRequest(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["data-sharing", "request", id] });
      void qc.invalidateQueries({ queryKey: ["data-sharing", "requests"] });
      void qc.invalidateQueries({ queryKey: ["data-sharing", "steps", id] });
    },
  });
}
