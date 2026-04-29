"use client";

import { GripVertical, Pencil, Plus, Save, Trash2, X } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { post, put } from "@/lib/api/client";
import {
  getWorkflowTemplates,
  getWorkflowTemplate,
} from "@/lib/api/products/data-sharing/workflows.api";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatDate } from "@/lib/utils/formatters";
import type {
  WorkflowTemplate,
  WorkflowTemplateStep,
} from "@/lib/api/products/data-sharing/workflows.api";

// ─── Types ────────────────────────────────────────────────────────

type DraftStep = Omit<WorkflowTemplateStep, "id" | "template_id" | "created_at"> & {
  _key: string;
};

let _keyCounter = 0;
function newKey() { return `step-${++_keyCounter}`; }

function makeStep(order: number): DraftStep {
  return {
    _key: newKey(),
    step_order: order,
    step_type: "approval",
    name: `Step ${order}`,
    assignee_role: "data_owner",
    execution_mode: "sequential",
    sla_days: 3,
    condition_expr: null,
  };
}

// ─── Small helpers ────────────────────────────────────────────────

const SCOPE_COLOR: Record<string, string> = {
  internal: "#3B4FD6",
  external: "#D76736",
};

const SCOPE_BG: Record<string, string> = {
  internal: "#EEF2FF",
  external: "#FFF5F0",
};

const CLASS_COLORS: Record<string, { bg: string; color: string }> = {
  sensitive:     { bg: "#FFF5F0", color: "#D76736" },
  confidential:  { bg: "#FFF5F0", color: "#D76736" },
  restricted:    { bg: "#F5F0FF", color: "#7C3AED" },
  internal:      { bg: "#EEF2FF", color: "#3B4FD6" },
  public:        { bg: "#F0FAF0", color: "#449235" },
};

const ROLE_OPTIONS = ["data_owner", "dpo", "org_admin", "data_steward", "requester"] as const;
const STEP_TYPES = ["approval", "review", "dpo_review", "data_owner_approval", "signature", "notification"] as const;

function ScopeBadge({ value }: { value: string | null }) {
  if (!value) return <span className="text-xs" style={{ color: "#BABABA" }}>All</span>;
  return (
    <span
      className="rounded px-2 py-0.5 text-[10px] font-semibold capitalize"
      style={{ backgroundColor: SCOPE_BG[value] ?? "#F5F5F5", color: SCOPE_COLOR[value] ?? "#515157" }}
    >
      {value}
    </span>
  );
}

function ClassBadge({ value }: { value: string | null }) {
  if (!value) return <span className="text-xs" style={{ color: "#BABABA" }}>All</span>;
  const { bg, color } = CLASS_COLORS[value.toLowerCase()] ?? { bg: "#F5F5F5", color: "#515157" };
  return (
    <span className="rounded px-2 py-0.5 text-[10px] font-semibold capitalize" style={{ backgroundColor: bg, color }}>
      {value}
    </span>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className="rounded px-2 py-0.5 text-[10px] font-semibold"
      style={active ? { backgroundColor: "#F0FAF0", color: "#449235" } : { backgroundColor: "#F5F5F5", color: "#9E9E9E" }}
    >
      {active ? "Active" : "Draft"}
    </span>
  );
}

// ─── Step row ─────────────────────────────────────────────────────

function roleLabel(role: string | null) {
  if (!role) return "Unassigned";
  return role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StepRow({
  step,
  isSelected,
  onSelect,
  onUpdate,
  onRemove,
  onDragStart,
  onDragOver,
  onDragEnd,
  isDragging,
}: {
  step: DraftStep;
  isSelected: boolean;
  onSelect: (key: string) => void;
  onUpdate: (key: string, field: keyof DraftStep, value: unknown) => void;
  onRemove: (key: string) => void;
  onDragStart: (key: string) => void;
  onDragOver: (e: React.DragEvent, key: string) => void;
  onDragEnd: () => void;
  isDragging: boolean;
}) {
  const isSpecial = step.step_type === "dpo_review" || step.step_type === "data_owner_approval";
  return (
    <div
      draggable
      onDragStart={() => onDragStart(step._key)}
      onDragOver={(e) => onDragOver(e, step._key)}
      onDragEnd={onDragEnd}
      onClick={() => !isSelected && onSelect(step._key)}
      className="flex items-start gap-3 rounded-lg px-4 py-3"
      style={{
        border: `1px solid ${isSelected || isDragging ? "#D76736" : "#EEEEEE"}`,
        opacity: isDragging ? 0.5 : 1,
        cursor: isSelected ? "default" : "pointer",
        backgroundColor: "#FFFFFF",
        marginBottom: 6,
      }}
    >
      {/* Step number circle */}
      <div
        className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12px] font-bold"
        style={{
          backgroundColor: isSelected ? "#D76736" : "#F5F5F5",
          color: isSelected ? "#FFFFFF" : "#9E9E9E",
        }}
      >
        {step.step_order}
      </div>

      {isSelected ? (
        <div className="flex flex-1 flex-col gap-2">
          <div className="flex items-center gap-2">
            <input
              value={step.name}
              onChange={(e) => onUpdate(step._key, "name", e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 rounded border px-2 py-1 text-[13px] font-semibold outline-none"
              style={{ borderColor: "#EEEEEE" }}
            />
            {isSpecial && (
              <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}>
                {step.step_type === "dpo_review" ? "PDPL Review" : "DO Approval"}
              </span>
            )}
          </div>
          <select
            value={step.assignee_role ?? ""}
            onChange={(e) => onUpdate(step._key, "assignee_role", e.target.value || null)}
            onClick={(e) => e.stopPropagation()}
            className="h-8 rounded-md border px-2 text-[12px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          >
            {ROLE_OPTIONS.map((r) => (
              <option key={r} value={r}>{roleLabel(r)}</option>
            ))}
          </select>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-0.5">
          <span className="text-[13px] font-semibold text-auth-text">{step.name}</span>
          <span className="text-[11px]" style={{ color: "#9E9E9E" }}>{roleLabel(step.assignee_role)}</span>
        </div>
      )}

      {/* SLA */}
      {isSelected ? (
        <div className="flex shrink-0 items-center gap-1">
          <input
            type="number"
            min={1}
            value={step.sla_days}
            onChange={(e) => onUpdate(step._key, "sla_days", Number(e.target.value))}
            onClick={(e) => e.stopPropagation()}
            className="h-8 w-16 rounded-md border px-2 text-center text-[12px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          />
          <span className="text-[11px]" style={{ color: "#9E9E9E" }}>days</span>
        </div>
      ) : (
        <span className="shrink-0 text-[12px]" style={{ color: "#9E9E9E" }}>
          {step.sla_days} {step.sla_days === 1 ? "day" : "days"}
        </span>
      )}

      <div className="flex shrink-0 items-center gap-0.5">
        <GripVertical className="h-4 w-4" style={{ color: "#BABABA", cursor: "grab" }} />
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove(step._key); }}
          className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#FFF0F0]"
          style={{ color: "#9E9E9E" }}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

// ─── Save Workflow Changes modal ──────────────────────────────────

function SaveWorkflowModal({
  version,
  onCancel,
  onConfirm,
  isPending,
}: {
  version: number;
  onCancel: () => void;
  onConfirm: (applyToActive: boolean, justification: string) => void;
  isPending: boolean;
}) {
  const [applyToActive, setApplyToActive] = useState(false);
  const [justification, setJustification] = useState("");
  const INFLIGHT_COUNT = 6;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "#07070966" }}
    >
      <div
        className="flex w-[480px] flex-col gap-5 rounded-xl p-6"
        style={{ backgroundColor: "#FFFFFF", boxShadow: "0 24px 64px #00000026" }}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-auth-text">Save Workflow Changes</h2>
          <button type="button" onClick={onCancel}>
            <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
          </button>
        </div>

        <p className="text-[13px]" style={{ color: "#616161" }}>
          By default, changes apply only to requests submitted from now on. In-flight requests
          will continue using version v{version} of this workflow.
        </p>

        {/* Toggle */}
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-medium text-auth-text">Apply to active requests too?</span>
          <button
            type="button"
            onClick={() => setApplyToActive((v) => !v)}
            className="flex h-[24px] w-[44px] items-center rounded-full px-0.5"
            style={{ backgroundColor: applyToActive ? "#D76736" : "#EEEEEE", justifyContent: applyToActive ? "flex-end" : "flex-start" }}
          >
            <span className="h-[20px] w-[20px] rounded-full bg-white shadow-sm" />
          </button>
        </div>

        {/* Justification */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-semibold text-auth-text">
            Justification <span style={{ color: "#D76736" }}>Required</span>
          </label>
          <textarea
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            placeholder="Explain why this workflow is being updated…"
            rows={3}
            className="resize-none rounded-md border p-3 text-[13px] outline-none"
            style={{ borderColor: "#EEEEEE" }}
          />
        </div>

        {/* In-flight warning */}
        {applyToActive && (
          <div
            className="flex flex-col gap-1 rounded-md px-4 py-3 text-[12px]"
            style={{ backgroundColor: "#FFF5F0", border: "1px solid #FFCDB8" }}
          >
            <p className="font-semibold" style={{ color: "#D76736" }}>
              {INFLIGHT_COUNT} in-flight requests will be affected
            </p>
            <p style={{ color: "#9E9E9E" }}>
              Any newly added step is inserted at each request's current position — not backdated.
            </p>
          </div>
        )}

        <p className="text-[11px]" style={{ color: "#9E9E9E" }}>
          This justification is recorded in the audit trail for every affected request.
        </p>

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="flex h-9 items-center rounded-md border px-4 text-[13px]"
            style={{ borderColor: "#EEEEEE", color: "#515157" }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(applyToActive, justification)}
            disabled={!justification.trim() || isPending}
            className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: "#D76736" }}
          >
            {isPending ? "Saving…" : "Save workflow"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Editor panel ─────────────────────────────────────────────────

function WorkflowEditorPanel({
  templateId,
  onClose,
}: {
  templateId: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const templateQuery = useQuery({
    queryKey: ["data-sharing", "workflow-template", templateId],
    queryFn: () => getWorkflowTemplate(templateId),
  });

  const [steps, setSteps] = useState<DraftStep[]>([]);
  const [dirty, setDirty] = useState(false);
  const [dragging, setDragging] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [sharingType, setSharingType] = useState<string>("");
  const [classification, setClassification] = useState<string>("");
  const [showSaveModal, setShowSaveModal] = useState(false);

  const loadedKey = templateQuery.data?.id;
  useMemo(() => {
    if (templateQuery.data) {
      const t = templateQuery.data;
      setSharingType(t.sharing_type ?? "");
      setClassification(t.data_classification ?? "");
      setSteps(
        [...t.steps]
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
  }, [loadedKey]);

  const save = useMutation({
    mutationFn: ({ applyToActive, justification }: { applyToActive: boolean; justification: string }) =>
      put(`/api/v1/products/data-sharing/workflows/templates/${templateId}`, {
        sharing_type: sharingType || null,
        data_classification: classification || null,
        apply_to_active: applyToActive,
        justification,
        steps: steps.map((s) => ({
          step_order: s.step_order,
          step_type: s.step_type,
          name: s.name,
          assignee_role: s.assignee_role,
          execution_mode: s.execution_mode,
          sla_days: s.sla_days,
          condition_expr: s.condition_expr,
        })),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["data-sharing", "workflow-templates"] });
      setDirty(false);
      setShowSaveModal(false);
    },
  });

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
    setSteps((prev) => prev.map((s) => (s._key === key ? { ...s, [field]: value } : s)));
    setDirty(true);
  }, []);

  const handleDragStart = (key: string) => setDragging(key);
  const handleDragOver = (e: React.DragEvent, targetKey: string) => {
    e.preventDefault();
    if (!dragging || dragging === targetKey) return;
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

  const template = templateQuery.data;

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Editor header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-auth-text">
            Workflow Editor · {template?.name ?? "…"}
          </h1>
          {template && (
            <span
              className="rounded px-2 py-0.5 text-[11px] font-semibold"
              style={{ backgroundColor: "#F0FAF0", color: "#449235" }}
            >
              {template.is_active ? "Active" : "Draft"} v{template.version}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
            style={{ borderColor: "#EEEEEE", color: "#616161" }}
          >
            Discard
          </button>
          <button
            type="button"
            onClick={() => setShowSaveModal(true)}
            disabled={!dirty || save.isPending}
            className="flex h-9 items-center gap-1.5 rounded-md px-4 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: "#D76736" }}
          >
            <Save className="h-3.5 w-3.5" />
            Save changes
          </button>
        </div>
      </div>

      {showSaveModal && (
        <SaveWorkflowModal
          version={template?.version ?? 1}
          onCancel={() => setShowSaveModal(false)}
          onConfirm={(applyToActive, justification) => save.mutate({ applyToActive, justification })}
          isPending={save.isPending}
        />
      )}

      <div className="flex flex-1 flex-col overflow-auto px-8 py-6">
        {/* Scope filters */}
        <div className="mb-4 flex items-center gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-semibold" style={{ color: "#9E9E9E" }}>Sharing type</label>
            <select
              value={sharingType}
              onChange={(e) => { setSharingType(e.target.value); setDirty(true); }}
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE", minWidth: 160 }}
            >
              <option value="">All</option>
              <option value="internal">Internal</option>
              <option value="external">External</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-semibold" style={{ color: "#9E9E9E" }}>Classification</label>
            <select
              value={classification}
              onChange={(e) => { setClassification(e.target.value); setDirty(true); }}
              className="h-9 rounded-md border px-3 text-[13px] outline-none"
              style={{ borderColor: "#EEEEEE", minWidth: 160 }}
            >
              <option value="">All</option>
              <option value="public">Public</option>
              <option value="internal">Internal</option>
              <option value="confidential">Confidential</option>
              <option value="sensitive">Sensitive</option>
              <option value="restricted">Restricted</option>
            </select>
          </div>
        </div>

        {/* Steps */}
        {templateQuery.isLoading ? (
          <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
        ) : (
          <div className="flex flex-col" style={{ maxWidth: 640 }}>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[12px] font-semibold" style={{ color: "#9E9E9E" }}>
                Steps · {steps.length} total
              </span>
              <span className="text-[11px]" style={{ color: "#9E9E9E" }}>Drag to reorder</span>
            </div>
            {steps.map((s) => (
              <StepRow
                key={s._key}
                step={s}
                isSelected={selectedKey === s._key}
                onSelect={setSelectedKey}
                onUpdate={updateStep}
                onRemove={removeStep}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDragEnd={() => setDragging(null)}
                isDragging={dragging === s._key}
              />
            ))}
            <button
              type="button"
              onClick={addStep}
              className="mt-2 self-start text-[13px] font-medium"
              style={{ color: "#D76736" }}
            >
              + Add step
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────

export default function WorkflowEditorPage() {
  const { isReady } = useRoleGuard({ allow: ["dpo", "platform_admin"] });
  const [editId, setEditId] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const qc = useQueryClient();

  const templatesQuery = useQuery({
    queryKey: ["data-sharing", "workflow-templates"],
    queryFn: getWorkflowTemplates,
    enabled: isReady,
  });

  const createMutation = useMutation({
    mutationFn: (name: string) =>
      post("/api/v1/products/data-sharing/workflows/templates", { name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["data-sharing", "workflow-templates"] });
      setShowNew(false);
    },
  });

  const [newName, setNewName] = useState("");

  if (!isReady) return null;
  if (editId) return <WorkflowEditorPanel templateId={editId} onClose={() => setEditId(null)} />;

  const templates = templatesQuery.data ?? [];

  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      {/* Header */}
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <h1 className="text-lg font-bold text-auth-text">Workflow Editor</h1>
        <div className="flex items-center gap-2">
          <span
            className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
            style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#D76736" }} />
            DPO · Data Sharing
          </span>
          <button
            type="button"
            onClick={() => setShowNew(true)}
            className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-semibold text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            <Plus className="h-3.5 w-3.5" />
            New workflow
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <h2 className="text-[14px] font-semibold text-auth-text">Approval Workflows</h2>

        <div
          className="flex flex-col overflow-hidden rounded-lg"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          {/* Column headers */}
          <div
            className="flex h-10 shrink-0 items-center px-5"
            style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
          >
            <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>WORKFLOW</span>
            <span className="w-[180px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>SCOPE</span>
            <span className="w-[70px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STEPS</span>
            <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>VERSION</span>
            <span className="w-[140px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>LAST EDITED</span>
            <span className="w-[90px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>STATUS</span>
            <span className="w-[40px]" />
          </div>

          {templatesQuery.isLoading ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
          ) : templates.length === 0 ? (
            <div className="py-20 text-center text-sm text-auth-text-subtle">
              No workflows yet — create your first one above.
            </div>
          ) : (
            templates.map((t, i) => (
              <div
                key={t.id}
                className="flex h-[60px] items-center px-5"
                style={{ borderBottom: i < templates.length - 1 ? "1px solid #F5F5F5" : undefined }}
              >
                <div className="flex flex-1 flex-col gap-0.5">
                  <span className="text-[13px] font-semibold text-auth-text">{t.name}</span>
                  <span className="text-[11px]" style={{ color: "#9E9E9E" }}>
                    {t.sharing_type ? `${t.sharing_type} ·` : "All ·"}{" "}
                    {t.data_classification ?? "All classifications"}
                  </span>
                </div>
                <div className="flex w-[180px] items-center gap-1.5">
                  <ScopeBadge value={t.sharing_type} />
                  {t.data_classification && <ClassBadge value={t.data_classification} />}
                </div>
                <span className="w-[70px] text-sm font-semibold" style={{ color: "#515157" }}>
                  {t.step_count != null ? t.step_count : "—"}
                </span>
                <div className="flex w-[120px] items-center gap-1">
                  {Array.from(
                    { length: Math.min(t.version, 3) },
                    (_, i) => t.version - Math.min(t.version, 3) + 1 + i,
                  ).map((v) => (
                    <span
                      key={v}
                      className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                      style={{
                        backgroundColor: v === t.version ? "#D76736" : "#F5F5F5",
                        color: v === t.version ? "#FFFFFF" : "#9E9E9E",
                      }}
                    >
                      v{v}
                    </span>
                  ))}
                </div>
                <span className="w-[140px] text-xs" style={{ color: "#9E9E9E" }}>
                  {formatDate(t.created_at)}
                </span>
                <div className="w-[90px]">
                  <StatusBadge active={t.is_active} />
                </div>
                <button
                  type="button"
                  onClick={() => setEditId(t.id)}
                  className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-[#F5F5F5]"
                  style={{ color: "#9E9E9E" }}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* New workflow modal */}
      {showNew && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ backgroundColor: "#00000066" }}
        >
          <div
            className="flex w-[400px] flex-col gap-4 rounded-2xl bg-white p-6"
            style={{ boxShadow: "0 24px 64px #00000026" }}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-auth-text">New workflow</h2>
              <button type="button" onClick={() => setShowNew(false)}>
                <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
              </button>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-auth-text">Workflow name *</label>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. External Sensitive Workflow"
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowNew(false)}
                className="flex h-9 items-center rounded-md border px-4 text-[13px] font-medium"
                style={{ borderColor: "#EEEEEE", color: "#616161" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => createMutation.mutate(newName.trim())}
                disabled={!newName.trim() || createMutation.isPending}
                className="flex h-9 items-center rounded-md px-5 text-[13px] font-semibold text-white disabled:opacity-60"
                style={{ backgroundColor: "#D76736" }}
              >
                {createMutation.isPending ? "Creating…" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
