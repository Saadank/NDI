"use client";

/**
 * E1 — Review Queue.
 *
 * Terms in under_review status for the Data Owner's domain(s) (Org Admin also
 * sees enterprise terms).  Each row links to the Term Detail in review mode,
 * where Approve / Request Changes / Reject live.
 */
import { useMemo } from "react";
import Link from "next/link";
import { ArrowRight, Inbox } from "lucide-react";

import { useGlossaryDomains } from "@/lib/hooks/ndmo-compliance/useGlossaryDomains";
import { useReviewQueue } from "@/lib/hooks/ndmo-compliance/useGlossaryTerms";
import {
  Card,
  DomainBadge,
  Mono,
  PageHeader,
  T,
  TypeBadge,
} from "../shared/ui";
import { useUserNameMap, userLabel } from "../shared/UserPicker";

export function ReviewQueuePage() {
  const q = useReviewQueue();
  const domainsQ = useGlossaryDomains();
  const nameMap = useUserNameMap();

  const domainName = useMemo(() => {
    const m = new Map<string, string>();
    (domainsQ.data ?? []).forEach((d) => m.set(d.id, d.name_en));
    return m;
  }, [domainsQ.data]);

  const rows = q.data ?? [];

  return (
    <div>
      <PageHeader
        title="Review Queue"
        subtitle="Terms submitted for your approval. Open a term to approve, request changes, or reject."
      />

      <Card className="overflow-hidden">
        {q.isLoading ? (
          <p className="p-8 text-center text-[13.5px]" style={{ color: T.muted }}>Loading…</p>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full" style={{ backgroundColor: T.successBg }}>
              <Inbox className="h-6 w-6" style={{ color: T.success }} />
            </div>
            <h3 className="text-[16px] font-bold" style={{ color: T.primary }}>All caught up</h3>
            <p className="mt-1 text-[13.5px]" style={{ color: T.muted }}>No terms are awaiting your review.</p>
          </div>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                <Th>Term</Th>
                <Th>Domain</Th>
                <Th>Submitted</Th>
                <Th>Status</Th>
                <Th> </Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} className="hover:bg-[#FAFAF8]" style={{ borderBottom: `1px solid ${T.border}` }}>
                  <Td>
                    <div className="font-semibold" style={{ color: T.primary }}>{t.name_en}</div>
                    <div className="text-[12px]" style={{ color: T.muted }}>{t.term_type === "enterprise" ? "Enterprise term" : "Domain term"}</div>
                  </Td>
                  <Td>
                    {t.domain_id ? <DomainBadge name={domainName.get(t.domain_id) ?? "Domain"} /> : <TypeBadge type="enterprise" />}
                  </Td>
                  <Td><Mono>{t.updated_at.slice(0, 10)}</Mono> <span className="text-[12px]" style={{ color: T.muted }}>· {userLabel(nameMap, t.created_by)}</span></Td>
                  <Td>
                    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-semibold" style={{ color: T.warn, backgroundColor: T.warnBg }}>
                      Under Review
                    </span>
                  </Td>
                  <Td>
                    <Link href={`/ndmo-compliance/glossary/terms/${t.id}`} className="inline-flex items-center gap-1 text-[13px] font-semibold" style={{ color: T.brand }}>
                      Review <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-2.5 text-[10.5px] font-bold uppercase tracking-wide" style={{ color: T.muted }}>{children}</th>;
}
function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 align-middle text-[13.5px]">{children}</td>;
}
