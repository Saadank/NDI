"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getExportCount,
  importGlossary,
  rollbackImport,
} from "@/lib/api/products/ndmo-compliance/glossary.api";

import { GLOSSARY_NS } from "./useGlossary";

export function useExportCount(scope: "all" | "my") {
  return useQuery({
    queryKey: [GLOSSARY_NS, "export-count", scope],
    queryFn: () => getExportCount(scope),
  });
}

export function useImportGlossary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => importGlossary(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "terms"] });
      qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "domains"] });
    },
  });
}

export function useRollbackImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => rollbackImport(batchId),
    onSuccess: () => qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "terms"] }),
  });
}
