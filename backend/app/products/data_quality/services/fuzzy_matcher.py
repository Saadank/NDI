"""Fuzzy column-name → concept matcher.

Pure function module — no DB, no I/O. The orchestrator (concept_matcher_service)
calls this for each column to get a fast, free first pass; columns that don't
get a confident-enough fuzzy hit are escalated to the LLM matcher.

Matching tiers:
  1. Exact match against (normalized) synonym                → score 1.00, HIGH
  2. Synonym appears as a token in the column name (or vice) → score 0.95, HIGH
  3. SequenceMatcher ratio across synonyms                   → score 0.0–1.0
                                                               HIGH  >= 0.90
                                                               MEDIUM >= 0.78
                                                               LOW    >= 0.65
                                                               (below — escalate to LLM)
"""
from __future__ import annotations

from difflib import SequenceMatcher

# Confidence thresholds — tuned conservatively. Below LOW we hand the column
# to the LLM matcher (which can spot semantic similarity the string ratio misses).
_HIGH_THRESHOLD   = 0.90
_MEDIUM_THRESHOLD = 0.78
_LOW_THRESHOLD    = 0.65

# Common column-name suffixes/prefixes worth stripping for the second-pass
# fuzzy ratio. We keep the original name for tier 1/2; only the stripped
# variant is used to widen tier 3's reach.
_STRIPPABLE_SUFFIXES = ("_id", "_key", "_pk", "_at", "_on", "_date", "_ts",
                        "_code", "_value", "_name")
_STRIPPABLE_PREFIXES = ("tbl_", "col_")


def normalize(name: str) -> str:
    """Lowercase, replace separators with underscore, collapse repeats."""
    if not name:
        return ""
    out = name.strip().lower()
    for ch in (" ", "-", ".", "/"):
        out = out.replace(ch, "_")
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def _strip_affixes(name: str) -> str:
    for p in _STRIPPABLE_PREFIXES:
        if name.startswith(p):
            name = name[len(p):]
    for s in _STRIPPABLE_SUFFIXES:
        if name.endswith(s) and len(name) > len(s) + 1:
            name = name[:-len(s)]
    return name


def _tokens(name: str) -> set[str]:
    return {t for t in name.split("_") if t}


def _confidence_for(score: float) -> str | None:
    if score >= _HIGH_THRESHOLD:
        return "high"
    if score >= _MEDIUM_THRESHOLD:
        return "medium"
    if score >= _LOW_THRESHOLD:
        return "low"
    return None  # below LOW: escalate to LLM


def match_column_against_synonyms(
    column_name: str, synonyms: list[str],
) -> tuple[float, str | None]:
    """Return the best (score, confidence) for one column against one
    concept's synonym list. Confidence is None when the score isn't high
    enough to warrant a fuzzy match — caller should consult the LLM."""
    if not synonyms:
        return 0.0, None

    norm_col = normalize(column_name)
    if not norm_col:
        return 0.0, None

    # Synonyms come pre-normalized from the dictionary, but we re-normalize
    # defensively in case a manual edit slipped through.
    syn_norms = [normalize(s) for s in synonyms if s]
    if not syn_norms:
        return 0.0, None

    # Tier 1: exact match.
    if norm_col in syn_norms:
        return 1.0, "high"

    col_tokens = _tokens(norm_col)

    # Tier 2: any synonym is a full token in the column (e.g. "id" in
    # "user_id"), or vice-versa — treat as high-confidence equivalence.
    for syn in syn_norms:
        if syn in col_tokens:
            return 0.95, "high"
        if "_" not in syn and syn in norm_col:
            # Single-token synonym appearing as a substring (e.g. "email"
            # within "useremailaddress"). Slightly lower confidence than a
            # clean token boundary but still a clear hit.
            return 0.92, "high"
        syn_tokens = _tokens(syn)
        if syn_tokens and syn_tokens.issubset(col_tokens):
            # Multi-token synonym whose every token appears in the column
            # (e.g. synonym "email_addr" vs column "user_email_addr_2").
            return 0.93, "high"

    # Tier 3: ratio against the original column AND a stripped variant.
    stripped = _strip_affixes(norm_col)
    candidates = {norm_col}
    if stripped and stripped != norm_col:
        candidates.add(stripped)

    best = 0.0
    for cand in candidates:
        for syn in syn_norms:
            r = SequenceMatcher(None, cand, syn).ratio()
            if r > best:
                best = r
    return round(best, 4), _confidence_for(best)


def match_column_against_concepts(
    column_name: str, concepts: list[dict],
) -> list[dict]:
    """For one column, evaluate every concept and return the (potentially
    multi-concept) fuzzy matches."""
    matches: list[dict] = []
    for c in concepts:
        if not c.get("enabled", True):
            continue
        score, conf = match_column_against_synonyms(column_name, c.get("synonyms") or [])
        if conf is None:
            continue
        matches.append({
            "concept_id": c["id"],
            "dimension": c["dimension"],
            "concept": c["concept"],
            "matched_by": "fuzzy",
            "confidence": conf,
            "matcher_score": score,
            "matcher_reasoning": _reason_for(column_name, c, score),
        })
    return matches


def _reason_for(column_name: str, concept: dict, score: float) -> str:
    if score >= 1.0:
        return f"Column name exactly matches synonym in '{concept['concept']}'."
    if score >= 0.92:
        return f"Synonym of '{concept['concept']}' appears as a token in '{column_name}'."
    return (f"Column '{column_name}' is {int(score*100)}% similar to a synonym "
            f"of '{concept['concept']}'.")


def needs_llm_review(column_name: str, concepts: list[dict]) -> bool:
    """True if no concept fuzzy-matched the column — caller should escalate
    this column to the LLM matcher for semantic comparison."""
    fuzzy = match_column_against_concepts(column_name, concepts)
    return not fuzzy
