import { useQuery } from "@tanstack/react-query";
import {
  getWorkflowTemplates,
  getWorkflowTemplate,
} from "@/lib/api/products/data-sharing/workflows.api";

export function useWorkflowTemplates() {
  return useQuery({
    queryKey: ["workflow-templates"],
    queryFn: getWorkflowTemplates,
    staleTime: 5 * 60 * 1000,
  });
}

export function useWorkflowTemplate(id: string | null) {
  return useQuery({
    queryKey: ["workflow-template", id],
    queryFn: () => getWorkflowTemplate(id!),
    enabled: id !== null,
    staleTime: 5 * 60 * 1000,
  });
}
