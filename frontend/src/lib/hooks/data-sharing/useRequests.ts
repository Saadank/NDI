"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelRequest,
  createRequest,
  getRequests,
  submitRequest,
} from "@/lib/api/products/data-sharing/requests.api";
import type { CreateShareRequestBody } from "@/lib/types/data-sharing/request.types";

export function useRequests(params: {
  page?: number;
  limit?: number;
  status?: string;
}) {
  return useQuery({
    queryKey: ["data-sharing", "requests", params],
    queryFn: () => getRequests(params),
  });
}

export function useCreateRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateShareRequestBody) => createRequest(body),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["data-sharing", "requests"] }),
  });
}

export function useSubmitRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => submitRequest(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["data-sharing", "requests"] }),
  });
}

export function useCancelRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelRequest(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["data-sharing", "requests"] }),
  });
}
