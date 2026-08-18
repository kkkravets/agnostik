"""Stage 5 CLI — citation resolving check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..objections.backtrace import ledger
from ..objections.bundle import ExportError, load_exports
from ..objections.targets import DEFAULT_SHORTLIST, VERDICT_PATTERN, discover
from .check import check_citations
from .emit import write_pltg, write_snapshots
from .registry import Registry
from .report import write_json, write_markdown

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agnostik-citecheck",
        description="Check that every cited record says what the dossier claims it says.",
    )
    ap.add_argument("--export", action="append", required=True, metavar="PATH",
                    help="pg-bench JSON export (.html / .js / .json); repeat to merge views")
    ap.add_argument("--targets", default=",".join(DEFAULT_SHORTLIST))
    ap.add_argument("--verdict-pattern", default=VERDICT_PATTERN)
    ap.add_argument("--out", default="results/stage5")
    ap.add_argument("--ledger-limit", type=int, default=80,
                    help="max citations pulled per target (default: 80)")
    ap.add_argument("--max-hops", type=int, default=12)
    ap.add_argument("--offline", action="store_true",
                    help="use only cached registry responses; do not call out")
    ap.add_argument("--no-pltg", action="store_true",
                    help="skip the Parseltongue emission that stage 6 consumes")
    ap.add_argument("--fail-on", default="off-target,retracted,unresolved",
                    help="comma-separated statuses that make the run exit non-zero "
                         "(default: off-target,retracted,unresolved)")
    return ap


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = load_exports(args.export)
    symbols = [s.strip() for s in args.targets.split(",") if s.strip()]
    views = discover(bundle, symbols, verdict_pattern=args.verdict_pattern)

    registry = Registry(cache_path=out_dir / ".registry-cache.json", offline=args.offline)
    by_target: dict[str, list] = {}

    for view in views:
        if view.missing:
            print(f"{view.symbol:6} skipped — not present in the export", file=sys.stderr)
            continue
        roots = [view.verdict_node.id] if view.verdict_node else []
        secondary = [c.id for c in view.claims]
        if not roots:
            roots, secondary = secondary[:1], secondary[1:]
        if not roots:
            print(f"{view.symbol:6} skipped — no verdict or claim node", file=sys.stderr)
            continue

        led = ledger(bundle, roots, secondary, max_hops=args.max_hops, limit=args.ledger_limit)
        checks = check_citations(led.citations, symbols, registry)
        by_target[view.symbol] = checks

        flagged = [c for c in checks if c.status not in ("sound", "not-checked")]
        print(
            f"{view.symbol:6} {len(checks):3} citations · "
            f"{sum(1 for c in checks if c.gene_role == 'title'):2} subject-level · "
            f"{len(flagged):2} flagged"
            + (f" ({', '.join(sorted({c.status for c in flagged}))})" if flagged else "")
        )

    registry.flush()

    if not by_target:
        print("nothing checked — no target matched the export", file=sys.stderr)
        return 1

    counters = write_snapshots(by_target, out_dir / "docs")
    meta = {
        "export": [str(p) for p in args.export],
        "targets": list(by_target),
        "offline": args.offline,
        "registry_fetches": registry.fetches,
    }
    write_json(by_target, counters, meta, out_dir / "citations.json")
    write_markdown(by_target, counters, meta, out_dir / "citations.md")

    if not args.no_pltg:
        modules = write_pltg(by_target, counters, out_dir / "src")
        print(f"\nwrote {out_dir}/citations.json, citations.md, "
              f"docs/registry-*.txt and {len(modules)} .pltg modules for stage 6")
    else:
        print(f"\nwrote {out_dir}/citations.json, citations.md, docs/registry-*.txt")

    fail_on = {s.strip() for s in args.fail_on.split(",") if s.strip()}
    offenders = [
        c for checks in by_target.values() for c in checks if c.status in fail_on
    ]
    if offenders:
        print(
            f"{len(offenders)} citation(s) in a failing state: "
            f"{', '.join(sorted({c.status for c in offenders}))}",
            file=sys.stderr,
        )
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ExportError as exc:
        print(f"export error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
