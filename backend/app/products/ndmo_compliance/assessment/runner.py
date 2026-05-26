"""Batch CLI for the assessment engine.

Usage::

    python -m app.products.ndmo_compliance.assessment.runner \\
        --tenant-id 42 \\
        [--cycle-id 7] \\
        [--dry-run] \\
        [--spec-limit 3] \\
        [--model claude-sonnet-4-6]

Recommended first run (per the Phase-3 acceptance plan):

    --dry-run --spec-limit 1     # 1 spec, no DB write — proves the path end-to-end
    --dry-run                    # all 190 specs, no DB write — confirms cost + latency
    (without --dry-run)          # write results

The runner prints a per-spec summary table and an aggregate row count.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from app.products.ndmo_compliance.assessment.engine import AssessmentEngine, BatchResult


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NDMO assessment engine runner")
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--cycle-id", type=int, default=None,
                        help="If omitted, the tenant's active cycle is used.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip DB write; print results to stdout only.")
    parser.add_argument("--spec-limit", type=int, default=None,
                        help="Cap the number of specs assessed (canary mode).")
    parser.add_argument("--model", default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    return asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> int:
    engine = AssessmentEngine(
        model=args.model, top_k=args.top_k, concurrency=args.concurrency,
    )
    result = await engine.run_cycle(
        tenant_id=args.tenant_id,
        cycle_id=args.cycle_id,
        dry_run=args.dry_run,
        spec_limit=args.spec_limit,
    )
    _print_summary(result, dry_run=args.dry_run)
    return 0 if result.errors == 0 else 2


def _print_summary(result: BatchResult, *, dry_run: bool) -> None:
    elapsed = result.ended_at - result.started_at
    print("=" * 80)
    print(f"NDMO assessment — {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"  tenant_id : {result.tenant_id}")
    print(f"  cycle_id  : {result.cycle_id}")
    print(f"  total     : {result.total}")
    print(f"  ok        : {result.ok}")
    print(f"  no_ev     : {result.skipped}")
    print(f"  errors    : {result.errors}")
    print(f"  elapsed   : {elapsed:.1f}s")
    print("-" * 80)
    print(f"{'spec_code':<14} {'status':<22} {'lvl':>4} {'conf':>6} "
          f"{'chunks':>7} {'lat_ms':>7}")
    for r in result.per_spec:
        lvl = r.output.maturity_level if r.output else "-"
        conf = f"{r.output.confidence:.2f}" if r.output else "-"
        print(
            f"{r.spec_code:<14} {r.status:<22} "
            f"{str(lvl):>4} {str(conf):>6} {r.retrieved_chunks:>7} {r.latency_ms:>7}"
        )
    print("=" * 80)


if __name__ == "__main__":
    sys.exit(main())
