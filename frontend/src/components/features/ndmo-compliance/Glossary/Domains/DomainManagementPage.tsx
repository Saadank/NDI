"use client";

/**
 * F — Domain Management.
 *
 * Tree of the (unlimited-depth) domain hierarchy with per-node actions
 * (edit / add sub-domain / archive).  New-domain + sub-domain use a slide-over
 * drawer; archive uses a confirm modal.  Org Admin manages top-level domains;
 * a Data Owner sees their subtree and the "Add Top-Level Domain" action is
 * disabled (Admin-only).
 *
 * Owner/steward assignment uses a numeric user id for Slice 1 — a searchable
 * user picker is a follow-up polish item.
 */
import { useMemo, useState } from "react";
import { Archive, ChevronDown, ChevronRight, Pencil, Plus } from "lucide-react";

import { useGlossaryRole } from "@/lib/hooks/ndmo-compliance/useGlossary";
import {
  buildDomainTree,
  useArchiveDomain,
  useCreateDomain,
  useCreateSubdomain,
  useGlossaryDomains,
  useUpdateDomain,
} from "@/lib/hooks/ndmo-compliance/useGlossaryDomains";
import type { GlossaryDomainNode } from "@/lib/types/ndmo-compliance/glossary";
import {
  Banner,
  Button,
  Card,
  Drawer,
  Input,
  Label,
  Modal,
  PageHeader,
  Textarea,
  T,
} from "../shared/ui";
import { UserMultiPicker, UserPicker, useUserNameMap, userLabel } from "../shared/UserPicker";

interface DrawerState {
  mode: "new" | "sub" | "edit";
  parent?: GlossaryDomainNode;
  target?: GlossaryDomainNode;
}

export function DomainManagementPage() {
  const role = useGlossaryRole();
  const domainsQ = useGlossaryDomains();
  const createM = useCreateDomain();
  const subM = useCreateSubdomain();
  const updateM = useUpdateDomain();
  const archiveM = useArchiveDomain();

  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<GlossaryDomainNode | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const nameMap = useUserNameMap();
  const tree = useMemo(() => buildDomainTree(domainsQ.data ?? []), [domainsQ.data]);
  const isAdmin = role.data?.is_org_admin ?? false;
  const ownedIds = new Set(role.data?.owned_domain_ids ?? []);
  const stewardIds = new Set(role.data?.steward_domain_ids ?? []);

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try {
      await fn();
      setDrawer(null);
      setArchiveTarget(null);
    } catch (e: unknown) {
      const anyE = e as { response?: { data?: { detail?: string } } };
      setErr(anyE?.response?.data?.detail ?? "Action failed.");
    }
  }

  return (
    <div>
      <PageHeader
        title="Domain Management"
        subtitle="Organise your business domains and assign owners and stewards."
        actions={
          <Button variant="brand" disabled={!isAdmin} onClick={() => setDrawer({ mode: "new" })}>
            <Plus className="h-4 w-4" /> Add Top-Level Domain
          </Button>
        }
      />

      {!isAdmin && (
        <Banner tone="info">You see the domains you own. Only an Org Admin can create top-level domains.</Banner>
      )}
      {err && <Banner tone="danger">{err}</Banner>}

      <Card className="p-3">
        {domainsQ.isLoading ? (
          <p className="p-6 text-center text-[13.5px]" style={{ color: T.muted }}>Loading…</p>
        ) : tree.length === 0 ? (
          <p className="p-8 text-center text-[13.5px]" style={{ color: T.muted }}>No domains yet. Add a top-level domain to begin.</p>
        ) : (
          tree.map((node) => (
            <DomainNode
              key={node.id}
              node={node}
              depth={0}
              isAdmin={isAdmin}
              ownedIds={ownedIds}
              stewardIds={stewardIds}
              nameMap={nameMap}
              onAddSub={(n) => setDrawer({ mode: "sub", parent: n })}
              onEdit={(n) => setDrawer({ mode: "edit", target: n })}
              onArchive={(n) => setArchiveTarget(n)}
            />
          ))
        )}
      </Card>

      {drawer && (
        <DomainDrawer
          state={drawer}
          busy={createM.isPending || subM.isPending || updateM.isPending}
          onClose={() => setDrawer(null)}
          onSubmit={(payload) => {
            if (drawer.mode === "new") return run(() => createM.mutateAsync(payload));
            if (drawer.mode === "sub") return run(() => subM.mutateAsync({ parentId: drawer.parent!.id, body: payload }));
            return run(() => updateM.mutateAsync({ id: drawer.target!.id, body: payload }));
          }}
        />
      )}

      {archiveTarget && (
        <Modal
          title={`Archive "${archiveTarget.name_en}"?`}
          onClose={() => setArchiveTarget(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setArchiveTarget(null)}>Cancel</Button>
              <Button variant="danger" disabled={archiveM.isPending} onClick={() => run(() => archiveM.mutateAsync(archiveTarget.id))}>Archive</Button>
            </>
          }
        >
          Archiving hides this domain from new-term creation but preserves all existing terms and audit
          history. It can be restored later — this is never a hard delete.
        </Modal>
      )}
    </div>
  );
}

function DomainNode({
  node,
  depth,
  isAdmin,
  ownedIds,
  stewardIds,
  nameMap,
  onAddSub,
  onEdit,
  onArchive,
}: {
  node: GlossaryDomainNode;
  depth: number;
  isAdmin: boolean;
  ownedIds: Set<string>;
  stewardIds: Set<string>;
  nameMap: Map<number, string>;
  onAddSub: (n: GlossaryDomainNode) => void;
  onEdit: (n: GlossaryDomainNode) => void;
  onArchive: (n: GlossaryDomainNode) => void;
}) {
  const [open, setOpen] = useState(true);
  const owns = ownedIds.has(node.id);
  const stewards = stewardIds.has(node.id);
  // Edit/Archive: Org Admin or the domain owner.  Add sub-domain: also a
  // steward of this domain (stewards can create sub-domains).
  const canEditOrArchive = isAdmin || owns;
  const canAddSub = isAdmin || owns || stewards;
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div className="group flex items-center gap-2 rounded-[8px] px-2 py-2 hover:bg-[#FAFAF8]" style={{ paddingLeft: 8 + depth * 20 }}>
        {hasChildren ? (
          <button onClick={() => setOpen((o) => !o)} style={{ color: T.muted }}>
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[14px] font-semibold" style={{ color: T.primary }}>{node.name_en}</span>
            {node.name_ar && <span dir="rtl" className="text-[12.5px]" style={{ color: T.muted }}>{node.name_ar}</span>}
            <span className="rounded-full px-2 py-0.5 text-[11px]" style={{ color: T.muted, backgroundColor: T.mutedBg }}>
              {node.term_count} terms
            </span>
          </div>
          <div className="mt-0.5 text-[12px]" style={{ color: T.muted }}>
            {node.owner_user_id ? `Owner: ${userLabel(nameMap, node.owner_user_id)}` : "No owner assigned"}
            {node.steward_ids.length > 0 && ` · Stewards: ${node.steward_ids.map((id) => userLabel(nameMap, id)).join(", ")}`}
          </div>
        </div>
        {(canEditOrArchive || canAddSub) && (
          <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            {canEditOrArchive && <IconBtn onClick={() => onEdit(node)} title="Edit"><Pencil className="h-4 w-4" /></IconBtn>}
            {canAddSub && <IconBtn onClick={() => onAddSub(node)} title="Add sub-domain"><Plus className="h-4 w-4" /></IconBtn>}
            {canEditOrArchive && <IconBtn onClick={() => onArchive(node)} title="Archive"><Archive className="h-4 w-4" /></IconBtn>}
          </div>
        )}
      </div>
      {open && node.children.map((c) => (
        <DomainNode key={c.id} node={c} depth={depth + 1} isAdmin={isAdmin} ownedIds={ownedIds} stewardIds={stewardIds} nameMap={nameMap} onAddSub={onAddSub} onEdit={onEdit} onArchive={onArchive} />
      ))}
    </div>
  );
}

function IconBtn({ children, onClick, title }: { children: React.ReactNode; onClick: () => void; title: string }) {
  return (
    <button onClick={onClick} title={title} className="flex h-7 w-7 items-center justify-center rounded-[6px] border" style={{ borderColor: T.border, color: T.muted }}>
      {children}
    </button>
  );
}

function DomainDrawer({
  state,
  busy,
  onClose,
  onSubmit,
}: {
  state: DrawerState;
  busy: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    name_en: string;
    name_ar: string | null;
    description_en: string | null;
    description_ar: string | null;
    owner_user_id: number | null;
    steward_user_ids?: number[];
  }) => void;
}) {
  const seed = state.mode === "edit" ? state.target : undefined;
  const [nameEn, setNameEn] = useState(seed?.name_en ?? "");
  const [nameAr, setNameAr] = useState(seed?.name_ar ?? "");
  const [descEn, setDescEn] = useState(seed?.description_en ?? "");
  const [ownerId, setOwnerId] = useState<number | null>(
    seed?.owner_user_id ?? (state.mode === "sub" ? state.parent?.owner_user_id ?? null : null),
  );
  const [stewards, setStewards] = useState<number[]>([]);

  const title =
    state.mode === "new" ? "New Top-Level Domain" : state.mode === "sub" ? "Add Sub-domain" : "Edit Domain";

  function submit() {
    onSubmit({
      name_en: nameEn.trim(),
      name_ar: nameAr.trim() || null,
      description_en: descEn.trim() || null,
      description_ar: null,
      owner_user_id: ownerId,
      steward_user_ids: state.mode === "sub" ? stewards : undefined,
    });
  }

  return (
    <Drawer
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="brand" disabled={busy || !nameEn.trim()} onClick={submit}>Save</Button>
        </>
      }
    >
      {state.mode === "sub" && (
        <div>
          <Label>Parent Domain</Label>
          <Input value={state.parent?.name_en ?? ""} disabled />
        </div>
      )}
      <div>
        <Label required>Name (EN)</Label>
        <Input value={nameEn} onChange={(e) => setNameEn(e.target.value)} placeholder="e.g. Health" />
      </div>
      <div>
        <Label>Name (AR)</Label>
        <Input dir="rtl" value={nameAr} onChange={(e) => setNameAr(e.target.value)} placeholder="الصحة" />
      </div>
      <div>
        <Label>Description</Label>
        <Textarea value={descEn} onChange={(e) => setDescEn(e.target.value)} style={{ minHeight: 72 }} />
      </div>
      <UserPicker label="Assign Data Owner" value={ownerId} onChange={setOwnerId} />
      {state.mode === "sub" && (
        <UserMultiPicker label="Assign Data Stewards" value={stewards} onChange={setStewards} />
      )}
    </Drawer>
  );
}
