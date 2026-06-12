"use client";

/**
 * A — Glossary Home / Browse.
 *
 * Page header (Export + New Term) → tab row (All / My Domains / Enterprise)
 * → split panel (280px domain tree | fluid term list) inside a bordered card.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronRight,
  Folder,
  Plus,
  Search,
  Tag,
} from "lucide-react";

import { useGlossaryDomains, buildDomainTree } from "@/lib/hooks/ndmo-compliance/useGlossaryDomains";
import { useGlossaryTerms } from "@/lib/hooks/ndmo-compliance/useGlossaryTerms";
import { useGlossaryRole } from "@/lib/hooks/ndmo-compliance/useGlossary";
import type {
  GlossaryDomain,
  GlossaryDomainNode,
  GlossaryTerm,
} from "@/lib/types/ndmo-compliance/glossary";
import {
  Banner,
  Button,
  Card,
  DomainBadge,
  Input,
  PageHeader,
  Select,
  StatusBadge,
  T,
  TypeBadge,
} from "../shared/ui";

type Tab = "all" | "my" | "enterprise";

export function GlossaryBrowse() {
  const role = useGlossaryRole();
  const domainsQ = useGlossaryDomains();
  const [tab, setTab] = useState<Tab>("all");
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");

  const isSteward = role.data?.effective_role === "glossary_data_steward";
  const canAuthor =
    role.data && role.data.effective_role !== "glossary_viewer";

  const termsQ = useGlossaryTerms({
    scope: tab === "my" ? "my" : "all",
    domain_id: selectedDomain ?? undefined,
    term_type: tab === "enterprise" ? "enterprise" : type || undefined,
    status: status || undefined,
    search: search || undefined,
  });

  const domains = domainsQ.data ?? [];
  const tree = useMemo(() => buildDomainTree(domains), [domains]);
  const domainName = useMemo(() => {
    const m = new Map<string, string>();
    domains.forEach((d) => m.set(d.id, d.name_en));
    return m;
  }, [domains]);

  const terms = termsQ.data ?? [];
  const totalApproved = domains.reduce((n, d) => n + d.term_count, 0);

  return (
    <div>
      <PageHeader
        title="Business Glossary"
        subtitle="A governed vocabulary of business terms, organised by domain."
        actions={
          <>
            <Button variant="outline">Export</Button>
            {canAuthor && (
              <Link href="/ndmo-compliance/glossary/terms/new">
                <Button variant="brand">
                  <Plus className="h-4 w-4" /> New Term
                </Button>
              </Link>
            )}
          </>
        }
      />

      {/* Tabs */}
      <div className="mb-4 flex items-center gap-1 border-b" style={{ borderColor: T.border }}>
        <TabButton active={tab === "all"} onClick={() => { setTab("all"); setSelectedDomain(null); }}>
          All Terms
        </TabButton>
        <TabButton active={tab === "my"} onClick={() => { setTab("my"); setSelectedDomain(null); }}>
          My Domains
        </TabButton>
        <TabButton active={tab === "enterprise"} onClick={() => { setTab("enterprise"); setSelectedDomain(null); }}>
          Enterprise
        </TabButton>
      </div>

      {isSteward && (
        <Banner tone="info">
          As a Data Steward you can draft and edit terms in your assigned domains.
          Every change is reviewed by the domain&apos;s Data Owner before it is published.
        </Banner>
      )}

      <Card className="flex min-h-[520px] overflow-hidden">
        {/* Domain tree */}
        <aside className="w-[280px] shrink-0 border-r p-3" style={{ borderColor: T.border }}>
          <TreeRow
            label="All Terms"
            count={totalApproved}
            icon={<Tag className="h-4 w-4" />}
            active={tab === "all" && !selectedDomain}
            onClick={() => { setTab("all"); setSelectedDomain(null); }}
          />
          <div className="my-2 h-px" style={{ backgroundColor: T.border }} />
          {tree
            .filter((n) => n.parent_id === null)
            .map((node) => (
              <DomainTreeNode
                key={node.id}
                node={node}
                depth={0}
                selected={selectedDomain}
                onSelect={(id) => { setSelectedDomain(id); setTab("all"); }}
              />
            ))}
          <div className="my-2 h-px" style={{ backgroundColor: T.border }} />
          <TreeRow
            label="Enterprise"
            icon={<Tag className="h-4 w-4" />}
            active={tab === "enterprise"}
            onClick={() => { setTab("enterprise"); setSelectedDomain(null); }}
          />
        </aside>

        {/* Term list */}
        <div className="flex-1 p-4">
          {/* Filter bar */}
          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: T.placeholder }} />
              <Input
                placeholder="Search terms, acronyms, definitions…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: 36 }}
              />
            </div>
            <Select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 160 }}>
              <option value="">Any status</option>
              <option value="approved">Approved</option>
              <option value="under_review">Under Review</option>
              <option value="changes_requested">Changes Requested</option>
              <option value="draft">Draft</option>
              <option value="deprecated">Deprecated</option>
            </Select>
            {tab !== "enterprise" && (
              <Select value={type} onChange={(e) => setType(e.target.value)} style={{ width: 150 }}>
                <option value="">Any type</option>
                <option value="domain">Domain</option>
                <option value="enterprise">Enterprise</option>
              </Select>
            )}
          </div>

          {termsQ.isLoading ? (
            <p className="py-10 text-center text-[13.5px]" style={{ color: T.muted }}>Loading…</p>
          ) : terms.length === 0 ? (
            <EmptyState canAuthor={!!canAuthor} />
          ) : (
            <div className="space-y-2">
              {terms.map((term) => (
                <TermRow key={term.id} term={term} domainName={term.domain_id ? domainName.get(term.domain_id) : undefined} />
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="relative px-3 pb-2.5 pt-1 text-[14px] font-semibold"
      style={{ color: active ? T.brand : T.muted }}
    >
      {children}
      {active && <span className="absolute inset-x-2 -bottom-px h-[2.5px] rounded-full" style={{ backgroundColor: T.brand }} />}
    </button>
  );
}

function TreeRow({
  label,
  count,
  icon,
  active,
  onClick,
  depth = 0,
}: {
  label: string;
  count?: number;
  icon: React.ReactNode;
  active?: boolean;
  onClick?: () => void;
  depth?: number;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-2 rounded-[8px] px-2.5 py-1.5 text-left text-[13.5px] font-medium"
      style={{
        paddingLeft: 10 + depth * 16,
        color: active ? T.brand : T.primary,
        backgroundColor: active ? T.brandTint : "transparent",
      }}
    >
      <span style={{ color: active ? T.brand : T.muted }}>{icon}</span>
      <span className="flex-1 truncate">{label}</span>
      {count !== undefined && (
        <span className="text-[12px]" style={{ color: T.muted }}>{count}</span>
      )}
    </button>
  );
}

function DomainTreeNode({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: GlossaryDomainNode;
  depth: number;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const hasChildren = node.children.length > 0;
  return (
    <div>
      <div className="flex items-center">
        {hasChildren ? (
          <button onClick={() => setOpen((o) => !o)} style={{ color: T.muted, paddingLeft: depth * 16 }}>
            {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        ) : (
          <span style={{ paddingLeft: depth * 16 + 14 }} />
        )}
        <TreeRow
          label={node.name_en}
          count={node.term_count}
          icon={<Folder className="h-4 w-4" />}
          active={selected === node.id}
          onClick={() => onSelect(node.id)}
        />
      </div>
      {open &&
        node.children.map((child) => (
          <DomainTreeNode key={child.id} node={child} depth={depth + 1} selected={selected} onSelect={onSelect} />
        ))}
    </div>
  );
}

function TermRow({ term, domainName }: { term: GlossaryTerm; domainName?: string }) {
  return (
    <Link href={`/ndmo-compliance/glossary/terms/${term.id}`}>
      <div
        className="flex items-center gap-3 rounded-[10px] border px-4 py-3 transition-colors hover:bg-[#FAFAF8]"
        style={{ borderColor: T.border }}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-semibold" style={{ color: T.primary }}>
              {term.name_en}
            </span>
            {term.acronym && (
              <span className="rounded px-1.5 py-0.5 text-[11px] font-semibold" style={{ color: T.muted, backgroundColor: T.mutedBg }}>
                {term.acronym}
              </span>
            )}
          </div>
          <p className="mt-0.5 truncate text-[13px]" style={{ color: T.muted }}>
            {term.definition_en || "No definition yet."}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {domainName ? <DomainBadge name={domainName} /> : <TypeBadge type={term.term_type} />}
          <StatusBadge status={term.status} />
        </div>
      </div>
    </Link>
  );
}

function EmptyState({ canAuthor }: { canAuthor: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full" style={{ backgroundColor: T.brandTint }}>
        <Tag className="h-6 w-6" style={{ color: T.brand }} />
      </div>
      <h3 className="text-[16px] font-bold" style={{ color: T.primary }}>No terms yet</h3>
      <p className="mb-4 mt-1 max-w-sm text-[13.5px]" style={{ color: T.muted }}>
        Start building your glossary by creating a term, or bootstrap it from a connected database.
      </p>
      {canAuthor && (
        <Link href="/ndmo-compliance/glossary/terms/new">
          <Button variant="brand"><Plus className="h-4 w-4" /> Create First Term</Button>
        </Link>
      )}
    </div>
  );
}
