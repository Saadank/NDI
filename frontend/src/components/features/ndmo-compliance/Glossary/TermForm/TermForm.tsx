"use client";

/**
 * C — New Term  &  D — Edit Term  (shared form).
 *
 * New: a single form card; Save as Draft or Submit for Review.
 * Edit of an *approved* term: side-by-side published (read-only) vs new draft,
 * labelled "Creating vN".  Editing a published term forks an under_review
 * version server-side while the published version stays live (WF-03).
 *
 * The AI Assist panel (right column) is a Slice-2 deliverable — its slot is
 * left in place but not yet wired.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { useGlossaryDomains } from "@/lib/hooks/ndmo-compliance/useGlossaryDomains";
import { useGlossaryRole } from "@/lib/hooks/ndmo-compliance/useGlossary";
import {
  useCreateTerm,
  useGlossaryTerm,
  useSubmitTerm,
  useUpdateTerm,
} from "@/lib/hooks/ndmo-compliance/useGlossaryTerms";
import type { GlossaryTermType } from "@/lib/types/ndmo-compliance/glossary";
import {
  Banner,
  Button,
  Card,
  Input,
  Label,
  PageHeader,
  Select,
  Textarea,
  T,
  BreadcrumbLink,
} from "../shared/ui";
import { AiAssistPanel } from "./AiAssistPanel";

interface FormState {
  name_en: string;
  name_ar: string;
  acronym: string;
  domain_id: string;
  term_type: GlossaryTermType;
  definition_en: string;
  definition_ar: string;
  examples: string;
  business_rule: string;
}

const EMPTY: FormState = {
  name_en: "", name_ar: "", acronym: "", domain_id: "", term_type: "domain",
  definition_en: "", definition_ar: "", examples: "", business_rule: "",
};

export function TermForm({ mode, termId }: { mode: "new" | "edit"; termId?: string }) {
  const router = useRouter();
  const role = useGlossaryRole();
  const domainsQ = useGlossaryDomains();
  const existing = useGlossaryTerm(mode === "edit" ? termId : undefined);

  const createM = useCreateTerm();
  const updateM = useUpdateTerm();
  const submitM = useSubmitTerm();

  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = role.data?.is_org_admin ?? false;
  const editingApproved = mode === "edit" && existing.data?.status === "approved";

  // Domains the user may author in.
  const authorDomains = useMemo(() => {
    const all = (domainsQ.data ?? []).filter((d) => d.status === "active");
    if (isAdmin) return all;
    const allowed = new Set([
      ...(role.data?.owned_domain_ids ?? []),
      ...(role.data?.steward_domain_ids ?? []),
    ]);
    return all.filter((d) => allowed.has(d.id));
  }, [domainsQ.data, isAdmin, role.data]);

  const noDomains = !isAdmin && authorDomains.length === 0;

  useEffect(() => {
    if (mode === "edit" && existing.data) {
      const t = existing.data;
      setForm({
        name_en: t.name_en ?? "", name_ar: t.name_ar ?? "", acronym: t.acronym ?? "",
        domain_id: t.domain_id ?? "", term_type: t.term_type,
        definition_en: t.definition_en ?? "", definition_ar: t.definition_ar ?? "",
        examples: t.examples ?? "", business_rule: t.business_rule ?? "",
      });
    }
  }, [mode, existing.data]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const requiredOk =
    form.name_en.trim() &&
    form.definition_en.trim() &&
    (form.term_type === "enterprise" || form.domain_id);

  const busy = createM.isPending || updateM.isPending || submitM.isPending;

  const body = () => ({
    name_en: form.name_en.trim(),
    name_ar: form.name_ar.trim() || null,
    acronym: form.acronym.trim() || null,
    domain_id: form.term_type === "enterprise" ? null : form.domain_id,
    term_type: form.term_type,
    definition_en: form.definition_en.trim() || null,
    definition_ar: form.definition_ar.trim() || null,
    examples: form.examples.trim() || null,
    business_rule: form.business_rule.trim() || null,
  });

  async function persist(): Promise<string | null> {
    setError(null);
    try {
      if (mode === "new") {
        const t = await createM.mutateAsync(body());
        return t.id;
      }
      await updateM.mutateAsync({ id: termId!, body: body() });
      return termId!;
    } catch (e: unknown) {
      setError(extractError(e));
      return null;
    }
  }

  async function onSaveDraft() {
    const id = await persist();
    if (id) router.push(`/ndmo-compliance/glossary/terms/${id}`);
  }

  async function onSubmitForReview() {
    const id = await persist();
    if (!id) return;
    // Editing an approved term forks to under_review on PUT already; a draft
    // needs an explicit submit.
    if (!editingApproved) {
      try {
        await submitM.mutateAsync(id);
      } catch (e: unknown) {
        setError(extractError(e));
        router.push(`/ndmo-compliance/glossary/terms/${id}`);
        return;
      }
    }
    router.push(`/ndmo-compliance/glossary/terms/${id}`);
  }

  const nextVersion = (existing.data?.version ?? 1) + 1;

  return (
    <div>
      <PageHeader
        breadcrumb={
          <>
            <BreadcrumbLink href="/ndmo-compliance/glossary">Glossary</BreadcrumbLink>
            {" / "}
            {mode === "new" ? "New Term" : "Edit Term"}
          </>
        }
        title={mode === "new" ? "New Term" : `Edit Term${editingApproved ? ` — Creating v${nextVersion}` : ""}`}
        actions={
          <>
            <Button variant="ghost" onClick={() => router.back()}>Cancel</Button>
            {!editingApproved && (
              <Button variant="outline" onClick={onSaveDraft} disabled={busy || !form.name_en.trim() || noDomains}>
                Save as Draft
              </Button>
            )}
            <Button variant="brand" onClick={onSubmitForReview} disabled={busy || !requiredOk || noDomains}>
              {editingApproved ? "Submit Edit for Review" : "Submit for Review"}
            </Button>
          </>
        }
      />

      {noDomains && (
        <Banner tone="danger">
          You have no domains assigned. Contact your Org Admin before authoring a term.
        </Banner>
      )}
      {error && <Banner tone="danger">{error}</Banner>}

      <div className="grid grid-cols-[1fr_360px] gap-5">
        <div className="space-y-5">
          {editingApproved && existing.data && (
            <Card className="p-5" style={{ backgroundColor: T.mutedBg }}>
              <p className="mb-2 text-[11px] font-bold uppercase tracking-wide" style={{ color: T.muted }}>
                Published Version (v{existing.data.version}) — read only
              </p>
              <p className="text-[15px] font-semibold" style={{ color: T.primary }}>{existing.data.name_en}</p>
              <p className="mt-1 text-[13.5px]" style={{ color: T.muted }}>{existing.data.definition_en}</p>
            </Card>
          )}

          <Card className="p-5">
            {editingApproved && (
              <p className="mb-3 text-[11px] font-bold uppercase tracking-wide" style={{ color: T.ai }}>
                New draft — v{nextVersion}
              </p>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label required>Term Name (EN)</Label>
                <Input value={form.name_en} onChange={(e) => set("name_en", e.target.value)} placeholder="e.g. Premium" />
              </div>
              <div>
                <Label>Term Name (AR)</Label>
                <Input dir="rtl" value={form.name_ar} onChange={(e) => set("name_ar", e.target.value)} placeholder="القسط" />
              </div>
              <div>
                <Label>Acronym</Label>
                <Input value={form.acronym} onChange={(e) => set("acronym", e.target.value)} placeholder="e.g. NBO" />
              </div>
              <div>
                <Label>Term Type</Label>
                <div className="flex gap-2">
                  <SegBtn active={form.term_type === "domain"} onClick={() => set("term_type", "domain")}>Domain</SegBtn>
                  <SegBtn
                    active={form.term_type === "enterprise"}
                    disabled={!isAdmin}
                    onClick={() => isAdmin && set("term_type", "enterprise")}
                  >
                    Enterprise{!isAdmin && " (Admin)"}
                  </SegBtn>
                </div>
              </div>
              {form.term_type === "domain" && (
                <div className="col-span-2">
                  <Label required>Domain</Label>
                  <Select value={form.domain_id} onChange={(e) => set("domain_id", e.target.value)}>
                    <option value="">Select a domain…</option>
                    {authorDomains.map((d) => (
                      <option key={d.id} value={d.id}>{d.name_en}</option>
                    ))}
                  </Select>
                </div>
              )}
              <div className="col-span-2">
                <Label required>Definition (EN)</Label>
                <Textarea value={form.definition_en} onChange={(e) => set("definition_en", e.target.value)} placeholder="A clear, governed definition…" />
              </div>
              <div className="col-span-2">
                <Label>Definition (AR)</Label>
                <Textarea dir="rtl" value={form.definition_ar} onChange={(e) => set("definition_ar", e.target.value)} />
              </div>
              <div className="col-span-2">
                <Label>Usage Examples</Label>
                <Textarea value={form.examples} onChange={(e) => set("examples", e.target.value)} style={{ minHeight: 64 }} />
              </div>
              <div className="col-span-2">
                <Label>Business Rule <span style={{ color: T.muted }}>(optional — informs Phase-2 DQ linkage)</span></Label>
                <Textarea value={form.business_rule} onChange={(e) => set("business_rule", e.target.value)} style={{ minHeight: 64 }} />
              </div>
            </div>
          </Card>
        </div>

        {/* AI Assist */}
        <AiAssistPanel
          termName={form.name_en}
          currentDefinition={form.definition_en}
          termId={termId}
          onApplyDefinition={(text) => set("definition_en", text)}
        />
      </div>
    </div>
  );
}

function SegBtn({ active, disabled, onClick, children }: { active: boolean; disabled?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="h-[38px] flex-1 rounded-[8px] border text-[13px] font-semibold disabled:opacity-50"
      style={{
        color: active ? "#fff" : T.primary,
        backgroundColor: active ? T.brand : "#fff",
        borderColor: active ? T.brand : T.border,
      }}
    >
      {children}
    </button>
  );
}

function extractError(e: unknown): string {
  const anyE = e as { response?: { data?: { detail?: string } }; message?: string };
  return anyE?.response?.data?.detail ?? anyE?.message ?? "Something went wrong.";
}
