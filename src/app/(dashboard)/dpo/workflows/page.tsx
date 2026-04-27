"use client";

import { GitBranch, GripVertical, Plus, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  getWorkflowTemplates,
  getWorkflowTemplate,
} from "@/lib/api/products/data-sharing/workflows.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import type { WorkflowTemplateStep } from "@/lib/api/products/data-sharing/workflows.api";

type DraftStep = Omit<WorkflowTemplateStep, "id" | "template_id" | "created_at"> & {
  _key: string;
};

const STEP_TYPES = ["approval", "review", "signature", "notification", "data_owner_approval", "dpo_review"] as const;
const ROLE_OPTIONS = ["data_owner", "dpo", "org_admin", "requester"] as const;

let _keyCounter = 0;
function newKey() { return `step-${++_keyCounter}`; }

function makeStep(order: number): DraftStep {
  return {
    _key: newKey(),
    step_order: order,
    step_type: "approval",
    name: "",
    assignee_role: "data_owner",
    execution_mode: "sequential",
    sla_days: 5,
    condition_expr: null,
  };
}

export default function WorkflowEditorPage() {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin"] });
  const qc = useQueryClient();

  const templatesQuery = useQuery({
    queryKey: ["data-sharing", "workflow-templates"],
    queryFn: getWorkflowTemplates,
    enabled: isReady,
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const templateQuery = useQuery({
    queryKey: ["data-sharing", "workflow-template", selectedId],
    queryFn: () => getWorkflowTemplate(selectedId!),
    enabled: selectedId !== null,
  });

  const [steps, setSteps] = useState<DraftStep[]>([]);
  const [dirty, setDirty] = useState(false);
  const [dragging, setDragging] = useState<string | null>(null);

  // Sync steps from fetched template
  const loadedStepsKey = templateQuery.data?.id;
  useMemo(() => {
    if (templateQuery.data) {
      setSteps(
        templateQuery.data.steps
          .slice()
          .sort((a, b) => a.step_order - b.step_order)
          .map((s) => ({
            _key: newKey(),
            step_order: s.step_order,
            step_type: s.step_type,
            name: s.name,
            assignee_role: s.assignee_role,
            execution_mode: s.execution_mode,
            sla_days: s.sla_days,
            condition_expr: s.condition_expr,
          })),
      );
      setDirty(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedStepsKey]);

  const addStep = () => {
    setSteps((prev) => [...prev, makeStep(prev.length + 1)]);
    setDirty(true);
  };

  const removeStep = (key: string) => {
    setSteps((prev) =>
      prev.filter((s) => s._key !== key).map((s, i) => ({ ...s, step_order: i + 1 })),
    );
    setDirty(true);
  };

  const updateStep = useCallback((key: string, field: keyof DraftStep, value: unknown) => {
    setSteps((prev) =>
      prev.map((s) => (s._key === key ? { ...s, [field]: value } : s)),
    );
    setDirty(true);
  }, []);

  // Drag-and-drop reorder
  const handleDragStart = (key: string) => setDragging(key);
  const handleDragOver = (e: React.DragEvent, targetKey: string) => {
    e.preventDefault();
    if (dragging === null || dragging === targetKey) return;
    setSteps((prev) => {
      const from = prev.findIndex((s) => s._key === dragging);
      const to = prev.findIndex((s) => s._key === targetKey);
      if (from < 0 || to < 0) return prev;
      const next = [...prev];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next.map((s, i) => ({ ...s, step_order: i + 1 }));
    });
    setDirty(true);
  };
  const handleDragEnd = () => setDragging(null);

  if (!isReady) return null;

  const templates = templatesQuery.data ?? [];
  const selected = templates.find((t) => t.id === selectedId);

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <GitBranch className="h-5 w-5" style={{ color: "#D76736" }} />
          <h1 className="text-lg font-bold text-auth-text">Workflow Editor</h1>
          <span
            className="rounded px-2 py-0.5 text-xs font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            DPO
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/dpo/templates"
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#515157" }}
          >
            View Templates
          </Link>
          {dirty && (
            <button
              type="button"
              className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
              style={{ backgroundColor: "#D76736" }}
            >
              <Save className="h-3.5 w-3.5" />
              Save Changes
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Template picker sidebar */}
        <div
          className="w-64 shrink-0 overflow-auto border-r"
          style={{ borderColor: "#EEEEEE", backgroundColor: "#FFFFFF" }}
        >
          <div
            className="sticky top-0 flex h-10 items-center px-4"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>
              TEMPLATES
            </span>
          </div>
          {templatesQuery.isLoading ? (
            <div className="py-8 text-center text-xs" style={{ color: "#9E9E9E" }}>Loading…</div>
          ) : templates.length === 0 ? (
            <div className="py-8 text-center text-xs" style={{ color: "#9E9E9E" }}>No templates</div>
          ) : (
            templates.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setSelectedId(t.id)}
                className="flex w-full flex-col items-start gap-0.5 px-4 py-3 transition-colors"
                style={{
                  backgroundColor: selectedId === t.id ? "#FFF5F0" : undefined,
                  borderBottom: "1px solid #F5F5F5",
                }}
              >
                <span
                  className="text-[13px] font-medium"
                  style={{ color: selectedId === t.id ? "#D76736" : "#070709" }}
                >
                  {t.name}
                </span>
                <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                  {t.sharing_type ?? "Any"} · {t.data_classification ?? "Any"}
                </span>
              </button>
            ))
          )}
        </div>

        {/* Step editor */}
        <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
          {!selectedId ? (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <GitBranch className="mx-auto mb-3 h-10 w-10" style={{ color: "#EEEEEE" }} />
                <p className="text-sm font-medium text-auth-text">Select a template to edit</p>
                <p className="mt-1 text-xs" style={{ color: "#9E9E9E" }}>
                  Choose a workflow template from the left panel
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-auth-text">
                    {selected?.name ?? "…"}
                  </h2>
                  <p className="text-xs" style={{ color: "#9E9E9E" }}>
                    {steps.length} step{steps.length !== 1 ? "s" : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={addStep}
                  className="flex h-8 items-center gap-1.5 rounded-md border px-3 text-[13px] font-medium"
                  style={{ borderColor: "#D76736", color: "#D76736" }}
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add Step
                </button>
              </div>

              {templateQuery.isLoading ? (
                <div className="py-20 text-center text-sm" style={{ color: "#9E9E9E" }}>Loading steps…</div>
              ) : steps.length === 0 ? (
                <div
                  className="flex flex-1 flex-col items-center justify-center gap-3 rounded-lg py-20"
                  style={{ border: "2px dashed #EEEEEE" }}
                >
                  <p className="text-sm" style={{ color: "#9E9E9E" }}>No steps yet</p>
                  <button
                    type="button"
                    onClick={addStep}
                    className="flex h-8 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium text-white"
                    style={{ backgroundColor: "#D76736" }}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add First Step
                  </button>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {steps.map((step) => (
                    <div
                      key={step._key}
                      draggable
                      onDragStart={() => handleDragStart(step._key)}
                      onDragOver={(e) => handleDragOver(e, step._key)}
                      onDragEnd={handleDragEnd}
                      className="flex items-start gap-3 rounded-lg p-4"
                      style={{
                        backgroundColor: "#FFFFFF",
                        border: `1px solid ${dragging === step._key ? "#D76736" : "#EEEEEE"}`,
                        opacity: dragging === step._key ? 0.5 : 1,
                      }}
                    >
                      <GripVertical
                        className="mt-1 h-4 w-4 shrink-0 cursor-grab"
                        style={{ color: "#CCCCCC" }}
                      />
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                        style={{ backgroundColor: "#D76736" }}>
                        {step.step_order}
                      </div>
                      <div className="flex flex-1 flex-wrap gap-3">
                        <div className="flex flex-col gap-1">
                          <label className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>
                            Step Name
                          </label>
                          <input
                            value={step.name}
                            onChange={(e) => updateStep(step._key, "name", e.target.value)}
                            placeholder="e.g. Data Owner Approval"
                            className="h-8 w-48 rounded-md border px-2.5 text-[13px] outline-none"
                            style={{ borderColor: "#EEEEEE" }}
                          />
                        </div>
                        <div className="flex flex-col gap-1">
                          <label className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>
                            Type
                          </label>
                          <select
                            value={step.step_type}
                            onChange={(e) => updateStep(step._key, "step_type", e.target.value)}
                            className="h-8 rounded-md border bg-white px-2 text-[13px] outline-none"
                            style={{ borderColor: "#EEEEEE" }}
                          >
                            {STEP_TYPES.map((t) => (
                              <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                            ))}
                          </select>
                        </div>
                        <div className="flex flex-col gap-1">
                          <label className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>
                            Assignee Role
                          </label>
                          <select
                            value={step.assignee_role ?? ""}
                            onChange={(e) => updateStep(step._key, "assignee_role", e.target.value || null)}
                            className="h-8 rounded-md border bg-white px-2 text-[13px] outline-none"
                            style={{ borderColor: "#EEEEEE" }}
                          >
                            <option value="">None</option>
                            {ROLE_OPTIONS.map((r) => (
                              <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
                            ))}
                          </select>
                        </div>
                        <div className="flex flex-col gap-1">
                          <label className="text-[11px] font-medium" style={{ color: "#9E9E9E" }}>
                            SLA (days)
                          </label>
                          <input
                            type="number"
                            min={1}
                            value={step.sla_days}
                            onChange={(e) => updateStep(step._key, "sla_days", Number(e.target.value))}
                            className="h-8 w-20 rounded-md border px-2.5 text-[13px] outline-none"
                            style={{ borderColor: "#EEEEEE" }}
                          />
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeStep(step._key)}
                        className="mt-1 shrink-0 rounded p-1 transition-colors hover:bg-red-50"
                        style={{ color: "#CCCCCC" }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
