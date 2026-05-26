"use client";

import { Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { getWorkflowTemplates } from "@/lib/api/products/data-sharing/workflows.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";

export default function WorkflowTemplatesListPage() {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin"] });
  const templatesQuery = useQuery({
    queryKey: ["data-sharing", "workflow-templates"],
    queryFn: getWorkflowTemplates,
    enabled: isReady,
  });

  if (!isReady) return null;

  const templates = templatesQuery.data ?? [];

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">Workflow Templates</h1>
          <span
            className="rounded px-2 py-0.5 text-xs font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            DPO
          </span>
        </div>
        <button
          type="button"
          className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-3.5 w-3.5" />
          New Template
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{
              backgroundColor: "#FAFAFA",
              borderBottom: "1px solid #EEEEEE",
            }}
          >
            <span
              className="flex-1 text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              NAME
            </span>
            <span
              className="w-[140px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              SHARING TYPE
            </span>
            <span
              className="w-[160px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              CLASSIFICATION
            </span>
            <span
              className="w-[80px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              VERSION
            </span>
            <span
              className="w-[100px] text-[11px] font-semibold tracking-[0.6px]"
              style={{ color: "#9E9E9E" }}
            >
              STATUS
            </span>
          </div>

          {templatesQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              Loading…
            </div>
          ) : templatesQuery.isError ? (
            <div className="py-20 text-center text-sm text-red-600">
              Failed to load templates.
            </div>
          ) : templates.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              No workflow templates configured.
            </div>
          ) : (
            templates.map((t, i) => (
              <div
                key={t.id}
                className="flex h-14 items-center px-5 hover:bg-[#FFFBF9]"
                style={{
                  borderBottom:
                    i < templates.length - 1 ? "1px solid #EEEEEE" : undefined,
                }}
              >
                <span className="flex-1 text-[13px] font-semibold text-auth-text">
                  {t.name}
                </span>
                <span className="w-[140px] text-xs" style={{ color: "#9E9E9E" }}>
                  {t.sharing_type ?? "Any"}
                </span>
                <span className="w-[160px] text-xs" style={{ color: "#9E9E9E" }}>
                  {t.data_classification ?? "Any"}
                </span>
                <span className="w-[80px] text-xs" style={{ color: "#9E9E9E" }}>
                  v{t.version}
                </span>
                <span
                  className="inline-flex w-[100px] items-center"
                  style={{ color: t.is_active ? "#449235" : "#9E9E9E" }}
                >
                  <span className="text-xs font-medium">
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
