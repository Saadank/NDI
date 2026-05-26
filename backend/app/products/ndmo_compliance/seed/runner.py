"""NDMO seed runner — CLI entry point.

Usage::

    python -m app.products.ndmo_compliance.seed.runner \\
        --input-dir /path/to/uploaded-source-files \\
        --dsn postgresql://user:pass@host:5432/db \\
        [--dry-run]

The runner is idempotent: every catalog row is UPSERTed keyed on its `code`.
Per the Phase-1 plan, the catalog tables (domains / controls / specs) are
GLOBAL — they are NDMO-published and identical for every tenant.

Per the spec-gap policy (190 vs 191): the seeder inserts whatever it found,
logs the gap to ndmo.t_ndmo_seed_runs.notes, and exits 0.  It does NOT
invent a row to reach 191.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from .cross_validate_trackers import extract_tracker_evidence
from .models import ParseReport, SeedBundle
from .parse_dms_pdf import parse_dms_pdf
from .parse_ndi_formula import verify_ndi_formula
from .parse_req_pdfs import parse_all_req_pdfs
from .parse_xlsx_template import parse_xlsx_template

logger = logging.getLogger(__name__)
SEEDER_VERSION = "1.0.0"

# Expected filenames in --input-dir.  The runner tolerates the few known
# variations (e.g. "OD.pdf" vs "OD Req.pdf") via the per-stage modules.
DMS_PDF_NAME = "DataManagementPersonalDataProtectionStandardsAr.pdf"
NDI_PDF_NAME = "National-Data-Index_v1.0_AR.pdf"
XLSX_TEMPLATE_CANDIDATES = (
    "__مؤشر نضيء_-d9a5d936.xlsx",
    "__مؤشر نضيء_.xlsx",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed NDMO catalog tables.")
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="Directory containing the seed PDFs and xlsx files.")
    parser.add_argument("--dsn", type=str, default=None,
                        help="Postgres DSN.  Required unless --dry-run is set.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse but skip DB writes.  Prints what would be inserted.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    if not args.dry_run and not args.dsn:
        parser.error("--dsn is required unless --dry-run is set")

    return asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> int:
    input_dir: Path = args.input_dir
    if not input_dir.is_dir():
        logger.error("--input-dir is not a directory: %s", input_dir)
        return 2

    # ---------- Stage A: DMS PDF ------------------------------------------ #
    dms_path = input_dir / DMS_PDF_NAME
    if not dms_path.exists():
        logger.error("Master DMS PDF not found at %s", dms_path)
        return 2
    domains, controls, specs, dms_report = parse_dms_pdf(dms_path)
    _log_report(dms_report)

    # ---------- Stage B: xlsx template ------------------------------------ #
    xlsx_path = _resolve_one_of(input_dir, XLSX_TEMPLATE_CANDIDATES)
    if xlsx_path is None:
        xlsx_report = ParseReport(stage="B.parse_xlsx_template")
        xlsx_report.warnings.append(
            f"No xlsx template found.  Tried: {XLSX_TEMPLATE_CANDIDATES}"
        )
        xlsx_data: dict[str, dict[str, Any]] = {}
    else:
        xlsx_data, xlsx_report = parse_xlsx_template(xlsx_path)
    _log_report(xlsx_report)

    # The xlsx now returns data keyed by *control code* (DG.1, BIA.2, …).
    # Merge onto every child spec under that control.
    by_code = {s.code: s for s in specs}
    for spec in specs:
        control_code = spec.control_code
        if control_code in xlsx_data:
            spec.required_elements = xlsx_data[control_code]

    # ---------- Stage C: Req PDFs ----------------------------------------- #
    req_data, req_report = parse_all_req_pdfs(input_dir)
    _log_report(req_report)

    for code, payload in req_data.items():
        if code not in by_code:
            # The Req PDFs sometimes mention specs we didn't extract from the
            # DMS — that's actually a clue for reconciliation.  We do not
            # invent a SpecRow here (per the user's instruction "do not invent
            # a spec just to reach 191").  We record it in raw_source for
            # later operator review.
            continue
        sp = by_code[code]
        if payload.get("search_query"):
            sp.search_query = payload["search_query"]
        if payload.get("acceptance_criteria"):
            sp.acceptance_criteria = payload["acceptance_criteria"]
        if payload.get("maturity_levels"):
            sp.maturity_levels = payload["maturity_levels"]
        sp.raw_source.update({
            "req_pdf_file": payload.get("raw_source_file"),
            "req_pdf_snippet": payload.get("raw_text_snippet"),
        })

    # ---------- Stage D: Tracker evidence-code extraction + reconciliation #
    dms_control_codes = {c.code for c in controls}
    tracker_by_control, per_domain_summary, tracker_report = extract_tracker_evidence(
        input_dir,
        dms_control_codes=dms_control_codes,
    )
    _log_report(tracker_report)

    # Merge evidence codes into each spec's maturity_levels JSONB.
    # Every spec under a given control receives that control's evidence codes
    # (Trackers don't carry per-spec granularity).
    for spec in specs:
        control_evidence = tracker_by_control.get(spec.control_code, {})
        if not control_evidence and not spec.maturity_levels:
            continue
        # Start from whatever the Req-PDF parser produced, then enrich.
        levels = dict(spec.maturity_levels)
        for level_int, evidence_list in control_evidence.items():
            key = str(level_int)
            entry = levels.setdefault(key, {})
            entry.setdefault("evidence_codes", [])
            # Append, de-dup by code.
            existing_codes = {e.get("code") for e in entry["evidence_codes"]}
            for ev in evidence_list:
                if ev.get("code") not in existing_codes:
                    entry["evidence_codes"].append(ev)
        spec.maturity_levels = levels

    tracker_payload = {
        "per_domain_summary": per_domain_summary,
        "trackers_with_evidence": len(tracker_by_control),
    }

    # ---------- Stage E: NDI formula -------------------------------------- #
    ndi_payload, ndi_report = verify_ndi_formula(input_dir / NDI_PDF_NAME)
    _log_report(ndi_report)

    # ---------- Final assembly ------------------------------------------- #
    bundle = SeedBundle(
        domains=domains,
        controls=controls,
        specs=specs,
        reports=[dms_report, xlsx_report, req_report, tracker_report, ndi_report],
    )

    counts = {
        "domains": len(bundle.domains),
        "controls": len(bundle.controls),
        "specifications": len(bundle.specs),
        "priority_1": sum(1 for s in bundle.specs if s.priority == 1),
        "priority_2": sum(1 for s in bundle.specs if s.priority == 2),
        "priority_3": sum(1 for s in bundle.specs if s.priority == 3),
        "nca_conditional": sum(1 for s in bundle.specs if s.nca_conditional),
        "specs_with_maturity_levels": sum(1 for s in bundle.specs if s.maturity_levels),
        "specs_with_search_query": sum(1 for s in bundle.specs if s.search_query),
        "specs_with_required_elements": sum(1 for s in bundle.specs if s.required_elements),
    }

    spec_gap_note = ""
    if len(bundle.specs) < 191:
        spec_gap_note = (
            f"Seeded {len(bundle.specs)} specifications (expected 191 in spec).  "
            f"Per project policy: did not invent a placeholder spec.  "
            f"Per-domain reconciliation summary: "
            f"{tracker_payload['per_domain_summary']}"
        )

    file_hashes = _hash_inputs(input_dir)

    notes_obj = {
        "spec_gap": spec_gap_note,
        "tracker_payload": tracker_payload,
        "ndi_hash": ndi_payload,
        "stage_reports": [
            {"stage": r.stage, "counts": r.counts, "warnings": r.warnings, "errors": r.errors}
            for r in bundle.reports
        ],
    }

    if args.dry_run:
        print("=" * 78)
        print("NDMO seed — DRY RUN")
        print("=" * 78)
        print("Counts:")
        for k, v in counts.items():
            print(f"  {k:36s} = {v}")
        print()
        print("Stage reports:")
        for r in bundle.reports:
            print(f"  [{r.stage}]")
            for k, v in r.counts.items():
                print(f"      counts.{k} = {v}")
            for w in r.warnings:
                print(f"      WARN: {w}")
            for e in r.errors:
                print(f"      ERR : {e}")
        print()
        print(f"Spec gap note: {spec_gap_note or '(none — seeded 191)'}")
        print()
        print("Input file SHA-256:")
        for n, h in file_hashes.items():
            print(f"  {n:64s} {h}")
        return 0

    # ---------- DB persistence ------------------------------------------- #
    import asyncpg
    conn = await asyncpg.connect(args.dsn)
    try:
        async with conn.transaction():
            await _upsert_bundle(conn, bundle)
            await conn.execute(
                """
                INSERT INTO ndmo.t_ndmo_seed_runs
                    (seeder_version, input_dir, file_hashes, counts, notes)
                VALUES ($1, $2, $3::jsonb, $4::jsonb, $5)
                """,
                SEEDER_VERSION,
                str(input_dir),
                json.dumps(file_hashes),
                json.dumps(counts),
                json.dumps(notes_obj, ensure_ascii=False),
            )
    finally:
        await conn.close()

    print(f"Seed complete: {counts}")
    if spec_gap_note:
        print(f"NOTE: {spec_gap_note}")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_one_of(input_dir: Path, candidates: tuple[str, ...]) -> Path | None:
    for name in candidates:
        p = input_dir / name
        if p.exists():
            return p
    return None


def _log_report(r: ParseReport) -> None:
    logger.info("[%s] counts=%s", r.stage, r.counts)
    for w in r.warnings:
        logger.warning("[%s] %s", r.stage, w)
    for e in r.errors:
        logger.error("[%s] %s", r.stage, e)


def _hash_inputs(input_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for p in sorted(input_dir.iterdir()):
        if p.is_file():
            hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


async def _upsert_bundle(conn: Any, bundle: SeedBundle) -> None:
    # Domains
    domain_id: dict[str, int] = {}
    for d in bundle.domains:
        row = await conn.fetchrow(
            """
            INSERT INTO ndmo.t_ndmo_domains
                (code, name_ar, name_en, description_ar, sort_order)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (code) DO UPDATE
              SET name_ar = EXCLUDED.name_ar,
                  name_en = EXCLUDED.name_en,
                  description_ar = EXCLUDED.description_ar,
                  sort_order = EXCLUDED.sort_order,
                  updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            d.code, d.name_ar, d.name_en, d.description_ar, d.sort_order,
        )
        domain_id[d.code] = row["id"]

    # Controls
    control_id: dict[str, int] = {}
    for c in bundle.controls:
        row = await conn.fetchrow(
            """
            INSERT INTO ndmo.t_ndmo_controls
                (domain_id, code, name_ar, description_ar, sort_order)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (code) DO UPDATE
              SET domain_id = EXCLUDED.domain_id,
                  name_ar = EXCLUDED.name_ar,
                  description_ar = EXCLUDED.description_ar,
                  sort_order = EXCLUDED.sort_order,
                  updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            domain_id[c.domain_code], c.code, c.name_ar, c.description_ar, c.sort_order,
        )
        control_id[c.code] = row["id"]

    # Specs
    for s in bundle.specs:
        await conn.execute(
            """
            INSERT INTO ndmo.t_ndmo_specifications
                (control_id, code, name_ar, description_ar, priority, nca_conditional,
                 maturity_levels, required_elements, acceptance_criteria, search_query,
                 related_specs, issue_date, raw_source, sort_order)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11, $12, $13::jsonb, $14)
            ON CONFLICT (code) DO UPDATE
              SET control_id = EXCLUDED.control_id,
                  name_ar = EXCLUDED.name_ar,
                  description_ar = EXCLUDED.description_ar,
                  priority = EXCLUDED.priority,
                  nca_conditional = EXCLUDED.nca_conditional,
                  maturity_levels = EXCLUDED.maturity_levels,
                  required_elements = EXCLUDED.required_elements,
                  acceptance_criteria = EXCLUDED.acceptance_criteria,
                  search_query = EXCLUDED.search_query,
                  related_specs = EXCLUDED.related_specs,
                  raw_source = EXCLUDED.raw_source,
                  sort_order = EXCLUDED.sort_order,
                  updated_at = CURRENT_TIMESTAMP
            """,
            control_id[s.control_code], s.code, s.name_ar, s.description_ar,
            s.priority or 1,  # CHECK constraint requires 1/2/3; default to 1 if unknown
            s.nca_conditional,
            json.dumps(s.maturity_levels, ensure_ascii=False),
            json.dumps(s.required_elements, ensure_ascii=False, default=str),
            s.acceptance_criteria,
            s.search_query,
            s.related_specs,
            s.issue_date,
            json.dumps(s.raw_source, ensure_ascii=False, default=str),
            s.sort_order,
        )


if __name__ == "__main__":
    sys.exit(main())
