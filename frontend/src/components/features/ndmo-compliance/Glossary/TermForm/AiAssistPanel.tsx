"use client";

/**
 * C/D — AI Assist panel (BRD §6.3 / WF-06).
 *
 * Purple-accented, clearly separated from the brand orange.  Three modes —
 * Draft / Rephrase / Advise.  Suggestions only: "Apply" copies the output
 * into the definition field locally; it never saves and never changes status.
 * Handles loading and a graceful "AI unavailable" fallback (the form stays
 * fully usable).
 */
import { useState } from "react";
import { Check, Copy, Loader2, Sparkles, X } from "lucide-react";

import {
  assistAdvise,
  assistDraft,
  assistRephrase,
} from "@/lib/api/products/ndmo-compliance/glossary.api";
import type { AssistMode } from "@/lib/types/ndmo-compliance/glossary";

import { Button, T, Textarea } from "../shared/ui";

type Status = "idle" | "loading" | "output" | "unavailable";

const TABS: { key: AssistMode; label: string; blurb: string }[] = [
  { key: "draft", label: "Draft", blurb: "Generate a definition from the term name + context." },
  { key: "rephrase", label: "Rephrase", blurb: "Improve the current definition for clarity & tone." },
  { key: "advise", label: "Advise", blurb: "Get suggestions: missing fields, synonyms, inconsistencies." },
];

export function AiAssistPanel({
  termName,
  currentDefinition,
  relatedTerms,
  termId,
  onApplyDefinition,
}: {
  termName: string;
  currentDefinition: string;
  relatedTerms?: string;
  termId?: string;
  onApplyDefinition: (text: string) => void;
}) {
  const [tab, setTab] = useState<AssistMode>("draft");
  const [context, setContext] = useState("");
  const [instruction, setInstruction] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [output, setOutput] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const canGenerate =
    tab === "rephrase" ? currentDefinition.trim().length > 0 : termName.trim().length > 0;

  async function generate() {
    setStatus("loading");
    setOutput(null);
    setMessage(null);
    try {
      const res =
        tab === "draft"
          ? await assistDraft({ term_name: termName, context, term_id: termId })
          : tab === "rephrase"
            ? await assistRephrase({ current_definition: currentDefinition, instruction, term_id: termId })
            : await assistAdvise({ term_name: termName, definition_draft: currentDefinition, related_terms: relatedTerms, term_id: termId });

      if (res.available && res.output) {
        setOutput(res.output);
        setStatus("output");
      } else {
        setMessage(res.message ?? "AI Assist is temporarily unavailable. You can continue authoring manually.");
        setStatus("unavailable");
      }
    } catch {
      setMessage("AI Assist is temporarily unavailable. You can continue authoring manually.");
      setStatus("unavailable");
    }
  }

  function dismiss() {
    setOutput(null);
    setMessage(null);
    setStatus("idle");
  }

  async function copy() {
    if (!output) return;
    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — no-op */
    }
  }

  return (
    <div className="h-fit rounded-[14px] border p-5" style={{ backgroundColor: T.aiTint, borderColor: "#E3D4F7" }}>
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4" style={{ color: T.ai }} />
        <p className="text-[14px] font-bold" style={{ color: T.ai }}>AI Assist</p>
      </div>
      <p className="mt-1 text-[12px]" style={{ color: T.ai }}>Suggestions only · never auto-saves</p>

      {/* Tabs */}
      <div className="mt-4 flex gap-1 rounded-[8px] p-1" style={{ backgroundColor: "#FFFFFF80" }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); dismiss(); }}
            className="flex-1 rounded-[6px] py-1.5 text-[12.5px] font-semibold"
            style={{
              color: tab === t.key ? "#fff" : T.ai,
              backgroundColor: tab === t.key ? T.ai : "transparent",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <p className="mt-3 text-[12px]" style={{ color: T.muted }}>{TABS.find((x) => x.key === tab)!.blurb}</p>

      {/* Inputs per tab */}
      {tab === "draft" && (
        <div className="mt-3">
          <PanelLabel>Context (optional)</PanelLabel>
          <Textarea value={context} onChange={(e) => setContext(e.target.value)} placeholder="e.g. domain, typical use cases…" style={{ minHeight: 64, backgroundColor: "#fff" }} />
        </div>
      )}
      {tab === "rephrase" && (
        <div className="mt-3">
          <PanelLabel>Current definition</PanelLabel>
          <div className="mb-2 rounded-[8px] border bg-white px-3 py-2 text-[12.5px]" style={{ borderColor: "#E3D4F7", color: T.muted }}>
            {currentDefinition.trim() || "Write a definition in the form first."}
          </div>
          <PanelLabel>Instruction (optional)</PanelLabel>
          <Textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="e.g. make it more formal / simpler" style={{ minHeight: 48, backgroundColor: "#fff" }} />
        </div>
      )}
      {tab === "advise" && (
        <div className="mt-3 rounded-[8px] border bg-white px-3 py-2 text-[12.5px]" style={{ borderColor: "#E3D4F7", color: T.muted }}>
          Reviews <strong style={{ color: T.primary }}>{termName || "this term"}</strong> and its draft definition, then suggests improvements.
        </div>
      )}

      <button
        onClick={generate}
        disabled={!canGenerate || status === "loading"}
        className="mt-3 flex h-[38px] w-full items-center justify-center gap-1.5 rounded-[8px] text-[13.5px] font-semibold text-white disabled:opacity-50"
        style={{ backgroundColor: T.ai }}
      >
        {status === "loading" ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</> : <><Sparkles className="h-4 w-4" /> Generate</>}
      </button>

      {/* Output / fallback */}
      {status === "output" && output && (
        <div className="mt-3 rounded-[10px] border bg-white p-3" style={{ borderColor: "#E3D4F7" }}>
          <span className="inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ backgroundColor: T.aiTint, color: T.ai }}>
            AI-generated — review before submitting
          </span>
          <p className="mt-2 whitespace-pre-wrap text-[13px]" style={{ color: T.primary }}>{output}</p>
          <div className="mt-3 flex items-center gap-2">
            {tab !== "advise" && (
              <Button size="sm" variant="brand" onClick={() => onApplyDefinition(output)} className="!bg-[#8A4FD8] !border-[#8A4FD8]">
                Apply
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={copy}>
              {copied ? <><Check className="h-3.5 w-3.5" /> Copied</> : <><Copy className="h-3.5 w-3.5" /> Copy</>}
            </Button>
            <Button size="sm" variant="ghost" onClick={dismiss}><X className="h-3.5 w-3.5" /> Dismiss</Button>
          </div>
        </div>
      )}
      {status === "unavailable" && (
        <div className="mt-3 rounded-[10px] px-3 py-2.5 text-[12.5px]" style={{ backgroundColor: T.warnBg, color: T.warn }}>
          {message}
        </div>
      )}
    </div>
  );
}

function PanelLabel({ children }: { children: React.ReactNode }) {
  return <p className="mb-1.5 text-[12px] font-semibold" style={{ color: T.ai }}>{children}</p>;
}
