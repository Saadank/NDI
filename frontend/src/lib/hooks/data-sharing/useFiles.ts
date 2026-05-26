"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteRequestFile,
  getRequestFiles,
  uploadFileForRequest,
} from "@/lib/api/products/data-sharing/files.api";

export function useRequestFiles(requestId: string) {
  return useQuery({
    queryKey: ["data-sharing", "files", requestId],
    queryFn: () => getRequestFiles(requestId),
    enabled: Boolean(requestId),
  });
}

export function useUploadFile(requestId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadFileForRequest(requestId, file),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["data-sharing", "files", requestId],
      }),
  });
}

export function useDeleteFile(requestId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) => deleteRequestFile(fileId),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["data-sharing", "files", requestId],
      }),
  });
}
