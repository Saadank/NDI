"use client";

import { ClipboardList, Plus, Search, Trash2, X } from "lucide-react";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { get, post, del } from "@/lib/api/client";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { RoleBadge } from "@/components/shared/RoleBadge";

interface ExternalRecipient {
  id: string;
  name: string;
  organisation: string;
  email: string;
  country: string | null;
  safeguard: string | null;
  is_active: boolean;
  created_at: string;
}

const BASE = "/api/v1/products/data-sharing/dpo/external-recipients";

function AddModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    organisation: "",
    email: "",
    country: "",
    safeguard: "",
  });

  const addMutation = useMutation({
    mutationFn: () => post<ExternalRecipient>(BASE, form),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["dpo", "external-recipients"] });
      onClose();
    },
  });

  const set = <K extends keyof typeof form>(k: K, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.4)" }}>
      <div
        className="flex w-[480px] flex-col gap-4 rounded-lg p-6"
        style={{ backgroundColor: "#FFFFFF" }}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-auth-text">Add External Recipient</h2>
          <button type="button" onClick={onClose} className="rounded p-1 hover:bg-gray-100">
            <X className="h-4 w-4" style={{ color: "#9E9E9E" }} />
          </button>
        </div>

        <div className="flex flex-col gap-3">
          {[
            { key: "name" as const, label: "Full Name", placeholder: "Recipient full name", required: true },
            { key: "organisation" as const, label: "Organisation", placeholder: "Company or entity name", required: true },
            { key: "email" as const, label: "Email Address", placeholder: "recipient@company.com", required: true },
            { key: "country" as const, label: "Country", placeholder: "e.g. Saudi Arabia" },
            { key: "safeguard" as const, label: "Transfer Safeguard", placeholder: "e.g. Standard Contractual Clauses" },
          ].map(({ key, label, placeholder, required }) => (
            <div key={key} className="flex flex-col gap-1">
              <label className="text-[13px] font-medium text-auth-text">
                {label}{required && <span className="ml-0.5 text-red-500">*</span>}
              </label>
              <input
                type={key === "email" ? "email" : "text"}
                value={form[key]}
                onChange={(e) => set(key, e.target.value)}
                placeholder={placeholder}
                className="h-9 rounded-md border px-3 text-[13px] outline-none"
                style={{ borderColor: "#EEEEEE" }}
              />
            </div>
          ))}
        </div>

        <div className="flex items-center justify-end gap-2">
          <button type="button" onClick={onClose}
            className="h-9 rounded-md border px-4 text-[13px]"
            style={{ borderColor: "#EEEEEE", color: "#515157" }}>
            Cancel
          </button>
          <button
            type="button"
            onClick={() => addMutation.mutate()}
            disabled={!form.name || !form.organisation || !form.email || addMutation.isPending}
            className="h-9 rounded-md px-4 text-[13px] font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: "#D76736" }}
          >
            {addMutation.isPending ? "Adding…" : "Add Recipient"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ExternalRecipientsPage() {
  const { isReady } = useRoleGuard({ allow: ["dpo", "org_admin"] });
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  const recipientsQuery = useQuery({
    queryKey: ["dpo", "external-recipients"],
    queryFn: () => get<ExternalRecipient[]>(BASE),
    enabled: isReady,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => del(`${BASE}/${id}`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["dpo", "external-recipients"] }),
  });

  if (!isReady) return null;

  const recipients = recipientsQuery.data ?? [];
  const filtered = search
    ? recipients.filter((r) =>
        `${r.name} ${r.organisation} ${r.email}`.toLowerCase().includes(search.toLowerCase()),
      )
    : recipients;

  return (
    <>
      {showAdd && <AddModal onClose={() => setShowAdd(false)} />}

      <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
        <div
          className="flex h-16 shrink-0 items-center justify-between px-8"
          style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
        >
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-auth-text">External Recipients Directory</h1>
            <RoleBadge label="DPO" />
          </div>
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-medium text-white"
            style={{ backgroundColor: "#D76736" }}
          >
            <Plus className="h-3.5 w-3.5" />
            Add Recipient
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
          <div
            className="flex h-9 w-72 items-center gap-2 rounded-md px-3"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "#9E9E9E" }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search recipients…"
              className="h-full flex-1 bg-transparent text-[13px] outline-none placeholder:text-[#BABABA]"
            />
          </div>

          <div
            className="flex flex-col overflow-hidden rounded-lg"
            style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
          >
            <div
              className="flex h-10 shrink-0 items-center px-5"
              style={{ backgroundColor: "#FAFAFA", borderBottom: "1px solid #EEEEEE" }}
            >
              <span className="w-[180px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>NAME</span>
              <span className="flex-1 text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>ORGANISATION</span>
              <span className="w-[200px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>EMAIL</span>
              <span className="w-[120px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>COUNTRY</span>
              <span className="w-[160px] text-[11px] font-semibold tracking-[0.6px]" style={{ color: "#9E9E9E" }}>SAFEGUARD</span>
              <span className="w-[40px]" />
            </div>

            {recipientsQuery.isLoading ? (
              <div className="py-20 text-center text-sm text-auth-text-subtle">Loading…</div>
            ) : recipientsQuery.isError ? (
              <div className="py-20 text-center text-sm text-red-600">Failed to load recipients.</div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-20">
                <ClipboardList className="h-10 w-10" style={{ color: "#EEEEEE" }} />
                <p className="text-sm font-medium text-auth-text">No external recipients yet</p>
                <p className="text-xs" style={{ color: "#9E9E9E" }}>
                  External recipients must be pre-approved before data can be shared externally.
                </p>
                <button
                  type="button"
                  onClick={() => setShowAdd(true)}
                  className="flex h-8 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium text-white"
                  style={{ backgroundColor: "#D76736" }}
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add First Recipient
                </button>
              </div>
            ) : (
              filtered.map((r, i) => (
                <div
                  key={r.id}
                  className="flex h-14 items-center px-5 hover:bg-[#FFFBF9]"
                  style={{ borderBottom: i < filtered.length - 1 ? "1px solid #F5F5F5" : undefined }}
                >
                  <span className="w-[180px] text-[13px] font-medium text-auth-text truncate">{r.name}</span>
                  <span className="flex-1 text-xs truncate" style={{ color: "#515157" }}>{r.organisation}</span>
                  <span className="w-[200px] text-xs truncate" style={{ color: "#9E9E9E" }}>{r.email}</span>
                  <span className="w-[120px] text-xs" style={{ color: "#9E9E9E" }}>{r.country ?? "—"}</span>
                  <span className="w-[160px] text-xs truncate" style={{ color: "#9E9E9E" }}>{r.safeguard ?? "—"}</span>
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate(r.id)}
                    className="flex w-[40px] justify-center rounded p-1.5 transition-colors hover:bg-red-50"
                    style={{ color: "#CCCCCC" }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}
