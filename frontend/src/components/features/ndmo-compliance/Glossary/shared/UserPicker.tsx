"use client";

/**
 * Searchable user pickers for owner/steward assignment — by name, not id.
 * Backed by GET /glossary/users (id + display name); the full tenant list is
 * small, so we fetch once and filter client-side.
 */
import { useMemo, useState } from "react";
import { Check, Search, X } from "lucide-react";

import { useGlossaryUsers } from "@/lib/hooks/ndmo-compliance/useGlossary";
import type { GlossaryUser } from "@/lib/types/ndmo-compliance/glossary";

import { Input, Label, T } from "./ui";

/** Map of user id → display name, for resolving ids elsewhere in the UI. */
export function useUserNameMap(): Map<number, string> {
  const { data } = useGlossaryUsers();
  return useMemo(() => {
    const m = new Map<number, string>();
    (data ?? []).forEach((u) => m.set(u.id, u.name));
    return m;
  }, [data]);
}

export function userLabel(map: Map<number, string>, id: number | null | undefined): string {
  if (!id) return "—";
  return map.get(id) ?? `User #${id}`;
}

/** Single-select owner picker. */
export function UserPicker({
  label,
  required,
  value,
  onChange,
  placeholder = "Search by name…",
}: {
  label: string;
  required?: boolean;
  value: number | null;
  onChange: (id: number | null) => void;
  placeholder?: string;
}) {
  const { data } = useGlossaryUsers();
  const users = data ?? [];
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  const selected = users.find((u) => u.id === value) ?? null;
  const filtered = filterUsers(users, q);

  return (
    <div>
      <Label required={required}>{label}</Label>
      {selected ? (
        <div className="flex items-center justify-between rounded-[8px] border px-3 py-2" style={{ borderColor: T.border }}>
          <span className="text-[13.5px] font-medium" style={{ color: T.primary }}>{selected.name}</span>
          <button onClick={() => onChange(null)} style={{ color: T.muted }}><X className="h-4 w-4" /></button>
        </div>
      ) : (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: T.placeholder }} />
          <Input
            value={q}
            placeholder={placeholder}
            onChange={(e) => { setQ(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            style={{ paddingLeft: 36 }}
          />
          {open && filtered.length > 0 && (
            <Dropdown users={filtered} onPick={(u) => { onChange(u.id); setOpen(false); setQ(""); }} />
          )}
        </div>
      )}
    </div>
  );
}

/** Multi-select steward picker (chips). */
export function UserMultiPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number[];
  onChange: (ids: number[]) => void;
}) {
  const { data } = useGlossaryUsers();
  const users = data ?? [];
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = filterUsers(users, q).filter((u) => !value.includes(u.id));

  return (
    <div>
      <Label>{label}</Label>
      {value.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {value.map((id) => {
            const u = users.find((x) => x.id === id);
            return (
              <span key={id} className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[12.5px]" style={{ backgroundColor: T.mutedBg, color: T.primary }}>
                {u?.name ?? `User #${id}`}
                <button onClick={() => onChange(value.filter((v) => v !== id))} style={{ color: T.muted }}><X className="h-3 w-3" /></button>
              </span>
            );
          })}
        </div>
      )}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: T.placeholder }} />
        <Input
          value={q}
          placeholder="Add stewards by name…"
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          style={{ paddingLeft: 36 }}
        />
        {open && filtered.length > 0 && (
          <Dropdown users={filtered} onPick={(u) => { onChange([...value, u.id]); setQ(""); }} />
        )}
      </div>
    </div>
  );
}

function Dropdown({ users, onPick }: { users: GlossaryUser[]; onPick: (u: GlossaryUser) => void }) {
  return (
    <div className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-[8px] border bg-white py-1" style={{ borderColor: T.border, boxShadow: "0 12px 32px rgba(0,0,0,.12)" }}>
      {users.slice(0, 30).map((u) => (
        <button
          key={u.id}
          onClick={() => onPick(u)}
          className="flex w-full items-center justify-between px-3 py-1.5 text-left text-[13.5px] hover:bg-[#FAFAF8]"
          style={{ color: T.primary }}
        >
          <span>
            {u.name}
            <span className="ml-2 text-[12px]" style={{ color: T.muted }}>{u.email}</span>
          </span>
          <Check className="h-3.5 w-3.5 opacity-0" />
        </button>
      ))}
    </div>
  );
}

function filterUsers(users: GlossaryUser[], q: string): GlossaryUser[] {
  const s = q.trim().toLowerCase();
  if (!s) return users;
  return users.filter((u) => u.name.toLowerCase().includes(s) || u.email.toLowerCase().includes(s));
}
