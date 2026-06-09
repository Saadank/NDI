"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

import type { RequiredDocument } from "@/lib/types/data-sharing/request.types";

// Preset documents a reviewer commonly needs, plus a free-text "other" entry
// (issue 5: "both — he could choose Other and write").
const PRESETS = [
  "Signed contract / DPA",
  "DPIA",
  "Consent evidence",
  "Data flow diagram",
  "Legal basis memo",
];

interface Props {
  value: RequiredDocument[];
  onChange: (docs: RequiredDocument[]) => void;
}

/**
 * Lets a DPO / Data Owner build a checklist of documents the requester must
 * attach before resubmitting. The requester sees this checklist on the edit
 * screen and ticks items off as they upload.
 */
export function RequiredDocsPicker({ value, onChange }: Props) {
  const [custom, setCustom] = useState("");

  const has = (label: string) => value.some((d) => d.label === label);
  const toggle = (label: string) =>
    has(label)
      ? onChange(value.filter((d) => d.label !== label))
      : onChange([...value, { label, satisfied: false }]);
  const addCustom = () => {
    const v = custom.trim();
    if (!v || has(v)) { setCustom(""); return; }
    onChange([...value, { label: v, satisfied: false }]);
    setCustom("");
  };

  return (
    <div className="flex flex-col gap-2">
      <span className="text-[13px] font-semibold" style={{ color: "#374151" }}>
        Documents required before resubmission{" "}
        <span className="font-normal" style={{ color: "#9CA3AF" }}>(optional)</span>
      </span>

      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => {
          const active = has(p);
          return (
            <button
              key={p}
              type="button"
              onClick={() => toggle(p)}
              className="rounded-full px-2.5 py-1 text-[11px]"
              style={
                active
                  ? { backgroundColor: "#FFF5F0", color: "#D76736", border: "1px solid #FFCDB8" }
                  : { backgroundColor: "#F3F4F6", color: "#374151", border: "1px solid #E5E7EB" }
              }
            >
              {active ? "✓ " : "+ "}{p}
            </button>
          );
        })}
      </div>

      {/* Custom "Other" entry */}
      <div className="flex items-center gap-2">
        <input
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustom(); } }}
          placeholder="Other — type a document name…"
          className="h-9 flex-1 rounded-md border px-3 text-[12px] outline-none"
          style={{ borderColor: "#E5E7EB" }}
        />
        <button
          type="button"
          onClick={addCustom}
          className="flex h-9 w-9 items-center justify-center rounded-md text-white"
          style={{ backgroundColor: "#D76736" }}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Selected list (incl. any custom ones not in PRESETS) */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value
            .filter((d) => !PRESETS.includes(d.label))
            .map((d) => (
              <span
                key={d.label}
                className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px]"
                style={{ backgroundColor: "#FFF5F0", color: "#D76736", border: "1px solid #FFCDB8" }}
              >
                {d.label}
                <button type="button" onClick={() => onChange(value.filter((x) => x.label !== d.label))}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
        </div>
      )}
    </div>
  );
}
