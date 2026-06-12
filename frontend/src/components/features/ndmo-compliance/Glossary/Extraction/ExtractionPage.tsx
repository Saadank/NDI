"use client";

/**
 * G — DB Extraction.
 *
 * Left: connections panel (status badges + Run Extraction).  Main: candidate
 * queue — inferred term (+ schema.table sub-label), AI-draft definition, a
 * domain selector, and per-row Accept / Dismiss.  A bulk-action bar appears
 * when rows are selected.  Reads metadata only — never data values.
 */
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Database, Loader2, Play, Sparkles, Trash2 } from "lucide-react";

import { useGlossaryDomains } from "@/lib/hooks/ndmo-compliance/useGlossaryDomains";
import {
  useAcceptCandidate,
  useCandidates,
  useClearCandidates,
  useDismissCandidate,
  useDraftStatus,
  useExtractionConnections,
  useRunScan,
  useStartDrafting,
} from "@/lib/hooks/ndmo-compliance/useExtraction";
import type {
  ExtractionConnection,
  GlossaryCandidate,
} from "@/lib/types/ndmo-compliance/glossary";
import {
  Banner,
  Button,
  Card,
  Input,
  Label,
  Modal,
  Mono,
  PageHeader,
  Select,
  T,
} from "../shared/ui";

export function ExtractionPage() {
  const router = useRouter();
  const connectionsQ = useExtractionConnections();
  const domainsQ = useGlossaryDomains();
  const [tableFilter, setTableFilter] = useState("");
  const draftStatusQ = useDraftStatus(true);
  const draft = draftStatusQ.data;
  const candidatesQ = useCandidates(
    { status: "pending", table: tableFilter || undefined },
    { poll: draft?.active ?? false },
  );

  const runScan = useRunScan();
  const accept = useAcceptCandidate();
  const dismiss = useDismissCandidate();
  const startDrafting = useStartDrafting();
  const clear = useClearCandidates();
  const [clearOpen, setClearOpen] = useState(false);

  const [runOpen, setRunOpen] = useState(false);
  const [rowDomain, setRowDomain] = useState<Record<string, string>>({});
  const [dup, setDup] = useState<{ candidateId: string; existingId?: string; name?: string; domainId: string } | null>(null);
  const [dismissId, setDismissId] = useState<string | null>(null);
  const [dismissReason, setDismissReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const connections = connectionsQ.data ?? [];
  const domains = (domainsQ.data ?? []).filter((d) => d.status === "active");
  const candidates = candidatesQ.data ?? [];
  const tables = useMemo(
    () => Array.from(new Set(candidates.map((c) => c.table_name).filter(Boolean))) as string[],
    [candidates],
  );

  async function doAccept(c: GlossaryCandidate, force = false) {
    const domainId = rowDomain[c.id] || c.assigned_domain_id || "";
    if (!domainId) { setErr("Select a domain for this candidate first."); return; }
    setErr(null);
    try {
      const res = await accept.mutateAsync({ id: c.id, domainId, force });
      if (!res.accepted && res.duplicate) {
        setDup({ candidateId: c.id, existingId: res.existing_term_id, name: res.existing_name_en, domainId });
      } else {
        setDup(null);
      }
    } catch (e: unknown) {
      setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Accept failed.");
    }
  }

  return (
    <div>
      <PageHeader
        title="DB Extraction"
        subtitle="Bootstrap the glossary from a connected database. Reads schema/table/column metadata only — never data values."
        actions={<Button variant="brand" onClick={() => setRunOpen(true)} disabled={connections.length === 0}><Play className="h-4 w-4" /> Run Extraction</Button>}
      />

      {err && <Banner tone="danger">{err}</Banner>}

      <div className="grid grid-cols-[320px_1fr] gap-5">
        {/* Connections panel */}
        <Card className="h-fit p-4">
          <p className="mb-3 text-[11px] font-bold uppercase tracking-wide" style={{ color: T.muted }}>Connections</p>
          {connections.length === 0 ? (
            <p className="text-[13px]" style={{ color: T.muted }}>No database connections configured.</p>
          ) : (
            <div className="space-y-2">
              {connections.map((c) => <ConnectionRow key={c.id} conn={c} />)}
            </div>
          )}
        </Card>

        {/* Candidate queue */}
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: T.border }}>
            <div className="flex items-center gap-2">
              <p className="text-[14px] font-semibold" style={{ color: T.primary }}>Candidate Queue</p>
              <span className="rounded-full px-2 py-0.5 text-[12px]" style={{ backgroundColor: T.mutedBg, color: T.muted }}>{candidates.length}</span>
              {draft && draft.active && (
                <span className="inline-flex items-center gap-1 text-[12px]" style={{ color: T.ai }}>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> AI drafting… {draft.drafted}/{draft.total}
                </span>
              )}
              {draft && !draft.active && draft.remaining > 0 && draft.llm_available && (
                <button
                  onClick={() => startDrafting.mutate()}
                  className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[12px] font-semibold"
                  style={{ color: T.ai, backgroundColor: T.aiTint }}
                >
                  <Sparkles className="h-3.5 w-3.5" /> Generate AI drafts ({draft.remaining})
                </button>
              )}
              {draft && !draft.active && draft.remaining > 0 && !draft.llm_available && (
                <span className="text-[12px]" style={{ color: T.muted }}>AI not configured</span>
              )}
              {draft && draft.total > 0 && draft.remaining === 0 && (
                <span className="text-[12px]" style={{ color: T.success }}>All drafted</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {tables.length > 0 && (
                <Select value={tableFilter} onChange={(e) => setTableFilter(e.target.value)} style={{ width: 200, height: 32 }}>
                  <option value="">All tables</option>
                  {tables.map((t) => <option key={t} value={t}>{t}</option>)}
                </Select>
              )}
              {candidates.length > 0 && (
                <Button size="sm" variant="danger-outline" onClick={() => setClearOpen(true)}>
                  <Trash2 className="h-3.5 w-3.5" /> {tableFilter ? "Clear table" : "Clear all"}
                </Button>
              )}
            </div>
          </div>

          {candidatesQ.isLoading ? (
            <p className="p-8 text-center text-[13.5px]" style={{ color: T.muted }}>Loading…</p>
          ) : candidates.length === 0 ? (
            <EmptyQueue hasConnections={connections.length > 0} onRun={() => setRunOpen(true)} />
          ) : (
            <div className="max-h-[620px] overflow-y-auto">
              <table className="w-full text-left">
                <thead className="sticky top-0 bg-white">
                  <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                    <Th>Inferred Term</Th>
                    <Th>AI Draft Definition</Th>
                    <Th>Domain</Th>
                    <Th> </Th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.slice(0, 150).map((c) => (
                    <tr key={c.id} style={{ borderBottom: `1px solid ${T.border}` }}>
                      <Td>
                        <div className="font-semibold" style={{ color: T.primary }}>{c.inferred_name_en}</div>
                        <Mono>{c.schema_name}.{c.table_name}.{c.column_name}</Mono>
                      </Td>
                      <Td>
                        {c.ai_draft_definition ? (
                          <span className="inline-flex items-start gap-1.5">
                            <span className="mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold" style={{ backgroundColor: T.aiTint, color: T.ai }}>AI</span>
                            <span className="text-[13px]" style={{ color: T.muted }}>{truncate(c.ai_draft_definition, 110)}</span>
                          </span>
                        ) : (
                          <span className="text-[12.5px]" style={{ color: T.placeholder }}>—</span>
                        )}
                      </Td>
                      <Td>
                        <Select
                          value={rowDomain[c.id] ?? c.assigned_domain_id ?? ""}
                          onChange={(e) => setRowDomain((m) => ({ ...m, [c.id]: e.target.value }))}
                          style={{ width: 160, height: 32 }}
                        >
                          <option value="">— unassigned</option>
                          {domains.map((d) => <option key={d.id} value={d.id}>{d.name_en}</option>)}
                        </Select>
                      </Td>
                      <Td>
                        <div className="flex items-center justify-end gap-1.5">
                          <Button size="sm" variant="success" onClick={() => doAccept(c)} disabled={accept.isPending}>Accept</Button>
                          <Button size="sm" variant="outline" onClick={() => { setDismissId(c.id); setDismissReason(""); }}>Dismiss</Button>
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {candidates.length > 150 && (
                <p className="px-4 py-3 text-center text-[12.5px]" style={{ color: T.muted }}>
                  Showing 150 of {candidates.length}. Filter by table to narrow the queue.
                </p>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Run modal */}
      {runOpen && (
        <RunModal
          connections={connections}
          busy={runScan.isPending}
          onClose={() => setRunOpen(false)}
          onRun={async (connectionId, aiDraft) => {
            setErr(null);
            try {
              await runScan.mutateAsync({ connection_id: connectionId, ai_draft: aiDraft });
              setRunOpen(false);
            } catch (e: unknown) {
              setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Scan failed.");
              setRunOpen(false);
            }
          }}
        />
      )}

      {/* Duplicate modal */}
      {dup && (
        <Modal
          title="Duplicate term detected"
          onClose={() => setDup(null)}
          footer={
            <>
              {dup.existingId && (
                <Button variant="outline" onClick={() => router.push(`/ndmo-compliance/glossary/terms/${dup.existingId}`)}>View existing</Button>
              )}
              <Button variant="ghost" onClick={() => setDup(null)}>Cancel</Button>
              <Button variant="warn" onClick={() => { const c = candidates.find((x) => x.id === dup.candidateId); if (c) doAccept(c, true); }}>Accept anyway</Button>
            </>
          }
        >
          A term named <strong>{dup.name}</strong> already exists in this domain. Accept anyway to create a separate term, or view the existing one.
        </Modal>
      )}

      {/* Dismiss modal */}
      {dismissId && (
        <Modal
          title="Dismiss candidate"
          onClose={() => setDismissId(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setDismissId(null)}>Cancel</Button>
              <Button variant="danger" onClick={async () => { await dismiss.mutateAsync({ id: dismissId, reason: dismissReason || undefined }); setDismissId(null); }}>Dismiss</Button>
            </>
          }
        >
          <Label>Reason (optional, for audit)</Label>
          <Input value={dismissReason} onChange={(e) => setDismissReason(e.target.value)} placeholder="e.g. Not a business term" />
        </Modal>
      )}

      {/* Clear-all confirm modal */}
      {clearOpen && (
        <Modal
          title={tableFilter ? `Clear "${tableFilter}" candidates?` : "Clear all candidates?"}
          onClose={() => setClearOpen(false)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setClearOpen(false)}>Cancel</Button>
              <Button
                variant="danger"
                disabled={clear.isPending}
                onClick={async () => {
                  await clear.mutateAsync(tableFilter || undefined);
                  setClearOpen(false);
                }}
              >
                {clear.isPending ? "Clearing…" : `Clear ${candidates.length}`}
              </Button>
            </>
          }
        >
          This dismisses {candidates.length} pending candidate{candidates.length === 1 ? "" : "s"}
          {tableFilter ? ` from "${tableFilter}"` : ""}. They&apos;re removed from the queue (kept as
          dismissed for audit) and can be re-mined by running the extraction again.
        </Modal>
      )}
    </div>
  );
}

function ConnectionRow({ conn }: { conn: ExtractionConnection }) {
  const ok = (conn.status ?? "active") === "active";
  return (
    <div className="flex items-center gap-2.5 rounded-[8px] border px-3 py-2.5" style={{ borderColor: T.border }}>
      <Database className="h-4 w-4 shrink-0" style={{ color: T.muted }} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-semibold" style={{ color: T.primary }}>
          {conn.description || conn.database || conn.host}
        </div>
        <div className="truncate text-[11.5px]" style={{ color: T.muted }}>{conn.db_type} · {conn.host}</div>
      </div>
      <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ color: ok ? T.success : T.muted, backgroundColor: ok ? T.successBg : T.mutedBg }}>
        {ok ? "active" : conn.status}
      </span>
    </div>
  );
}

function RunModal({
  connections,
  busy,
  onClose,
  onRun,
}: {
  connections: ExtractionConnection[];
  busy: boolean;
  onClose: () => void;
  onRun: (connectionId: string, aiDraft: boolean) => void;
}) {
  const [connId, setConnId] = useState(connections[0]?.id ?? "");
  const [aiDraft, setAiDraft] = useState(true);
  return (
    <Modal
      title="Run Extraction"
      width={520}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="brand" disabled={busy || !connId} onClick={() => onRun(connId, aiDraft)}>
            {busy ? <><Loader2 className="h-4 w-4 animate-spin" /> Scanning…</> : <><Play className="h-4 w-4" /> Run</>}
          </Button>
        </>
      }
    >
      <Label required>Connection</Label>
      <Select value={connId} onChange={(e) => setConnId(e.target.value)}>
        {connections.map((c) => <option key={c.id} value={c.id}>{c.description || c.database || c.host} ({c.db_type})</option>)}
      </Select>
      <button
        onClick={() => setAiDraft((v) => !v)}
        className="mt-4 flex w-full items-center gap-3 rounded-[10px] border p-3 text-left"
        style={{ borderColor: aiDraft ? T.ai : T.border, backgroundColor: aiDraft ? T.aiTint : "#fff" }}
      >
        <span className="flex h-5 w-9 items-center rounded-full p-0.5 transition-colors" style={{ backgroundColor: aiDraft ? T.ai : T.border }}>
          <span className="h-4 w-4 rounded-full bg-white transition-transform" style={{ transform: aiDraft ? "translateX(16px)" : "none" }} />
        </span>
        <span>
          <span className="flex items-center gap-1.5 text-[13.5px] font-semibold" style={{ color: aiDraft ? T.ai : T.primary }}>
            <Sparkles className="h-4 w-4" /> Draft definitions with AI
          </span>
          <span className="text-[12px]" style={{ color: T.muted }}>Review every AI draft before accepting.</span>
        </span>
      </button>
      <p className="mt-3 text-[12.5px]" style={{ color: T.muted }}>
        Extraction reads metadata only and runs in the background — you can navigate away. New candidates appear in the queue as they&apos;re found.
      </p>
    </Modal>
  );
}

function EmptyQueue({ hasConnections, onRun }: { hasConnections: boolean; onRun: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full" style={{ backgroundColor: T.mutedBg }}>
        <Database className="h-6 w-6" style={{ color: T.muted }} />
      </div>
      <h3 className="text-[16px] font-bold" style={{ color: T.primary }}>No candidates yet</h3>
      <p className="mb-4 mt-1 max-w-sm text-[13.5px]" style={{ color: T.muted }}>
        Run an extraction on a connection to mine candidate terms from its columns.
      </p>
      {hasConnections && <Button variant="brand" onClick={onRun}><Play className="h-4 w-4" /> Run Extraction</Button>}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-2.5 text-[10.5px] font-bold uppercase tracking-wide" style={{ color: T.muted }}>{children}</th>;
}
function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 align-top text-[13.5px]">{children}</td>;
}
function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}
