"use client";

/**
 * B — Term Detail (and E2 — Review Mode).
 *
 * Header (breadcrumb, name + status/type badges, meta line, actions) over a
 * two-column grid: left = definition cards; right = governance, version
 * history, review history.  When the term is under_review and the viewer can
 * approve it, a review-action card (Approve / Request Changes / Reject) is
 * shown with mandatory-note modals.
 */
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";

import { useGlossaryDomains } from "@/lib/hooks/ndmo-compliance/useGlossaryDomains";
import { useGlossaryRole } from "@/lib/hooks/ndmo-compliance/useGlossary";
import {
  useCancelReview,
  useDeleteTerm,
  useDeprecateTerm,
  useGlossaryTerm,
  useReinstateTerm,
  useReviewTerm,
  useSubmitTerm,
} from "@/lib/hooks/ndmo-compliance/useGlossaryTerms";
import type { GlossaryReviewDecision } from "@/lib/types/ndmo-compliance/glossary";
import {
  Banner,
  BreadcrumbLink,
  Button,
  Card,
  DomainBadge,
  Label,
  Modal,
  Mono,
  PageHeader,
  StatusBadge,
  Textarea,
  T,
  TypeBadge,
} from "../shared/ui";
import { useUserNameMap, userLabel } from "../shared/UserPicker";

export function TermDetailPage({ termId }: { termId: string }) {
  const router = useRouter();
  const q = useGlossaryTerm(termId);
  const role = useGlossaryRole();
  const domainsQ = useGlossaryDomains();

  const submitM = useSubmitTerm();
  const cancelM = useCancelReview();
  const reviewM = useReviewTerm();
  const deprecateM = useDeprecateTerm();
  const reinstateM = useReinstateTerm();
  const deleteM = useDeleteTerm();

  const [modal, setModal] = useState<null | GlossaryReviewDecision | "deprecate">(null);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const nameMap = useUserNameMap();
  const domainName = useMemo(() => {
    const m = new Map<string, string>();
    (domainsQ.data ?? []).forEach((d) => m.set(d.id, d.name_en));
    return m;
  }, [domainsQ.data]);

  if (q.isLoading) return <p className="text-[13.5px]" style={{ color: T.muted }}>Loading…</p>;
  if (q.isError || !q.data) return <Banner tone="danger">Term not found.</Banner>;

  const term = q.data;
  const changesNote = term.reviews.find((r) => r.decision === "request_changes")?.note ?? null;
  const isAdmin = role.data?.is_org_admin ?? false;
  const owns = term.domain_id ? (role.data?.owned_domain_ids ?? []).includes(term.domain_id) : false;
  const stewards = term.domain_id ? (role.data?.steward_domain_ids ?? []).includes(term.domain_id) : false;

  const canReview =
    term.term_type === "enterprise" ? isAdmin : isAdmin || owns;
  const canEdit = isAdmin || owns || stewards;
  const canDeprecate = canReview;

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try {
      await fn();
      setModal(null);
      setNote("");
    } catch (e: unknown) {
      const anyE = e as { response?: { data?: { detail?: string } } };
      setErr(anyE?.response?.data?.detail ?? "Action failed.");
    }
  }

  const reviewDecision = (decision: GlossaryReviewDecision) =>
    run(() => reviewM.mutateAsync({ id: termId, body: { decision, note: note || null } }));

  return (
    <div>
      <PageHeader
        breadcrumb={
          <>
            <BreadcrumbLink href="/ndmo-compliance/glossary">Glossary</BreadcrumbLink>
            {" / "}
            {term.name_en}
          </>
        }
        title={term.name_en}
        actions={
          <div className="flex items-center gap-2">
            {(term.status === "draft" || term.status === "changes_requested") && canEdit && (
              <>
                <Button variant="outline" onClick={() => router.push(`/ndmo-compliance/glossary/terms/${termId}/edit`)}>
                  <Pencil className="h-4 w-4" /> Edit
                </Button>
                <Button variant="brand" onClick={() => run(() => submitM.mutateAsync(termId))}>
                  {term.status === "changes_requested" ? "Resubmit for Review" : "Submit for Review"}
                </Button>
                <Button variant="danger-outline" onClick={() => run(() => deleteM.mutateAsync(termId).then(() => router.push("/ndmo-compliance/glossary")))}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </>
            )}
            {term.status === "under_review" && canEdit && (
              <Button variant="outline" onClick={() => run(() => cancelM.mutateAsync(termId))}>Cancel Review</Button>
            )}
            {term.status === "approved" && canEdit && (
              <Button variant="outline" onClick={() => router.push(`/ndmo-compliance/glossary/terms/${termId}/edit`)}>
                <Pencil className="h-4 w-4" /> Edit
              </Button>
            )}
            {term.status === "approved" && canDeprecate && (
              <Button variant="danger-outline" onClick={() => setModal("deprecate")}>Deprecate</Button>
            )}
            {term.status === "deprecated" && canDeprecate && (
              <Button variant="outline" onClick={() => run(() => reinstateM.mutateAsync(termId))}>Reinstate</Button>
            )}
          </div>
        }
      />

      <div className="mb-4 flex items-center gap-2">
        <StatusBadge status={term.status} />
        {term.domain_id ? <DomainBadge name={domainName.get(term.domain_id) ?? "Domain"} /> : <TypeBadge type="enterprise" />}
        <span className="text-[12.5px]" style={{ color: T.muted }}>
          {term.acronym && <>· {term.acronym} </>}· <Mono>v{term.version}</Mono> · updated <Mono>{term.updated_at.slice(0, 10)}</Mono>
        </span>
      </div>

      {err && <Banner tone="danger">{err}</Banner>}
      {term.status === "changes_requested" && (
        <Banner tone="danger">
          <strong>Changes requested</strong>
          {changesNote ? `: ${changesNote}` : "."} Edit the term and resubmit it for review.
        </Banner>
      )}
      {term.status === "under_review" && (
        <Banner tone="warn">This term is awaiting Data Owner approval. It is locked until the review completes.</Banner>
      )}
      {term.status === "deprecated" && (
        <Banner tone="info">
          This term was deprecated{term.deprecated_at ? ` on ${term.deprecated_at.slice(0, 10)}` : ""}.
          {term.deprecation_reason ? ` Reason: ${term.deprecation_reason}` : ""}
        </Banner>
      )}

      <div className="grid grid-cols-[1fr_332px] gap-5">
        {/* Left: definitions */}
        <div className="space-y-5">
          <Card className="p-5">
            <SectionTitle>Definition</SectionTitle>
            <p className="text-[14px] leading-relaxed" style={{ color: T.primary }}>
              {term.definition_en || <span style={{ color: T.muted }}>No English definition.</span>}
            </p>
            {term.definition_ar && (
              <>
                <div className="my-4 h-px" style={{ backgroundColor: T.border }} />
                <p dir="rtl" className="text-[14px] leading-relaxed" style={{ color: T.primary }}>{term.definition_ar}</p>
              </>
            )}
          </Card>

          {term.examples && (
            <Card className="p-5">
              <SectionTitle>Usage Examples</SectionTitle>
              <p className="whitespace-pre-wrap text-[13.5px]" style={{ color: T.primary }}>{term.examples}</p>
            </Card>
          )}

          {term.relations.length > 0 && (
            <Card className="p-5">
              <SectionTitle>Related Terms</SectionTitle>
              <div className="flex flex-wrap gap-2">
                {term.relations.map((r) => (
                  <span key={r.id} className="rounded-full border px-3 py-1 text-[12.5px]" style={{ borderColor: T.border, color: T.primary }}>
                    {r.target_name_en} <span style={{ color: T.muted }}>· {r.relation_type.replace("_", " ")}</span>
                  </span>
                ))}
              </div>
            </Card>
          )}

          {term.business_rule && (
            <Card className="p-5">
              <SectionTitle>Business Rule</SectionTitle>
              <p className="text-[13.5px]" style={{ color: T.primary }}>{term.business_rule}</p>
            </Card>
          )}
        </div>

        {/* Right: governance + history (+ review actions) */}
        <div className="space-y-5">
          {term.status === "under_review" && canReview && (
            <Card className="p-5" style={{ backgroundColor: T.warnBg, borderColor: "#EAD9B0" }}>
              <SectionTitle>Review</SectionTitle>
              <div className="space-y-2">
                <Button variant="success" className="w-full" onClick={() => setModal("approve")}>Approve &amp; Publish</Button>
                <Button variant="warn" className="w-full" onClick={() => setModal("request_changes")}>Request Changes</Button>
                <Button variant="danger-outline" className="w-full" onClick={() => setModal("reject")}>Reject</Button>
              </div>
            </Card>
          )}

          <Card className="p-5">
            <SectionTitle>Governance</SectionTitle>
            <KV label="Term Type" value={term.term_type === "enterprise" ? "Enterprise" : "Domain"} />
            <KV label="Domain" value={term.domain_id ? domainName.get(term.domain_id) ?? "—" : "Enterprise (cross-domain)"} />
            <KV label="Source" value={term.source.replace("_", " ")} />
            <KV label="Created by" value={userLabel(nameMap, term.created_by)} />
            <KV label="Last updated" value={term.updated_at.slice(0, 10)} mono />
            {term.approved_at && <KV label="Approved" value={term.approved_at.slice(0, 10)} mono />}
          </Card>

          <Card className="p-5">
            <SectionTitle>Version History</SectionTitle>
            {term.versions.length === 0 ? (
              <p className="text-[13px]" style={{ color: T.muted }}>No published versions yet.</p>
            ) : (
              <ul className="space-y-2">
                {term.versions.map((v) => (
                  <li key={v.id} className="flex items-center gap-2 text-[13px]">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: T.brand }} />
                    <Mono>v{v.version}</Mono>
                    <span style={{ color: T.muted }}>· {v.changed_at.slice(0, 10)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="p-5">
            <SectionTitle>Review History</SectionTitle>
            {term.reviews.length === 0 ? (
              <p className="text-[13px]" style={{ color: T.muted }}>No reviews yet.</p>
            ) : (
              <ul className="space-y-2.5">
                {term.reviews.map((r) => (
                  <li key={r.id} className="text-[13px]">
                    <span className="font-semibold" style={{ color: decisionColor(r.decision) }}>
                      {labelFor(r.decision)}
                    </span>{" "}
                    <span style={{ color: T.muted }}>· {userLabel(nameMap, r.reviewer_id)} · {r.reviewed_at.slice(0, 10)}</span>
                    {r.note && <p className="mt-0.5" style={{ color: T.muted }}>{r.note}</p>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {/* ---- modals ---- */}
      {modal === "approve" && (
        <Modal
          title={`Approve "${term.name_en}"?`}
          onClose={() => setModal(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setModal(null)}>Cancel</Button>
              <Button variant="success" onClick={() => reviewDecision("approve")} disabled={reviewM.isPending}>Approve &amp; Publish</Button>
            </>
          }
        >
          This will publish the term to the glossary and notify the author.
        </Modal>
      )}
      {(modal === "request_changes" || modal === "reject") && (
        <Modal
          title={modal === "reject" ? `Reject "${term.name_en}"` : `Request changes on "${term.name_en}"`}
          onClose={() => setModal(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setModal(null)}>Cancel</Button>
              <Button
                variant={modal === "reject" ? "danger" : "warn"}
                disabled={!note.trim() || reviewM.isPending}
                onClick={() => reviewDecision(modal)}
              >
                {modal === "reject" ? "Reject" : "Send"}
              </Button>
            </>
          }
        >
          <Label required>{modal === "reject" ? "Reason for rejection" : "Describe the required changes"}</Label>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
        </Modal>
      )}
      {modal === "deprecate" && (
        <Modal
          title={`Deprecate "${term.name_en}"?`}
          onClose={() => setModal(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setModal(null)}>Cancel</Button>
              <Button variant="danger" disabled={!note.trim() || deprecateM.isPending} onClick={() => run(() => deprecateM.mutateAsync({ id: termId, body: { reason: note } }))}>
                Deprecate
              </Button>
            </>
          }
        >
          <Label required>Reason for deprecation</Label>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
          <p className="mt-2 text-[12.5px]" style={{ color: T.muted }}>
            The term is kept for audit and excluded from default search, and can be reinstated later.
          </p>
        </Modal>
      )}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <p className="mb-3 text-[11px] font-bold uppercase tracking-wide" style={{ color: T.muted }}>{children}</p>;
}

function KV({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3 border-b py-1.5 text-[13px] last:border-0" style={{ borderColor: T.border }}>
      <span style={{ color: T.muted }}>{label}</span>
      <span className="text-right font-medium" style={{ color: T.primary, fontFamily: mono ? "ui-monospace, monospace" : undefined }}>{value}</span>
    </div>
  );
}

function labelFor(d: GlossaryReviewDecision) {
  return d === "approve" ? "Approved" : d === "reject" ? "Rejected" : "Changes requested";
}
function decisionColor(d: GlossaryReviewDecision) {
  return d === "approve" ? T.success : d === "reject" ? T.danger : T.warn;
}
