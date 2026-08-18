"""Stage 6 CLI — formal consistency screening."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from ..objections.backtrace import ledger
from ..objections.bundle import ExportError, load_exports
from ..objections.targets import DEFAULT_SHORTLIST, VERDICT_PATTERN, discover
from .engine import EngineError, run_screening
from .generate import TargetFacts, build_system
from .report import adjudicate, write_json, write_markdown

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agnostik-consistency",
        description="Prove, rather than score, where the shortlist and the registries disagree.",
    )
    ap.add_argument("--export", action="append", required=True, metavar="PATH",
                    help="pg-bench JSON export the dossier side is transcribed from")
    ap.add_argument("--citecheck", required=True, metavar="DIR",
                    help="stage 5 output directory (citations.json + docs/registry-*.txt)")
    ap.add_argument("--targets", default=",".join(DEFAULT_SHORTLIST))
    ap.add_argument("--verdict-pattern", default=VERDICT_PATTERN)
    ap.add_argument("--out", default="results/stage6")
    ap.add_argument("--ledger-limit", type=int, default=80)
    ap.add_argument("--max-hops", type=int, default=12)
    ap.add_argument("--pg-binary", default="pg", help="pg-bench executable (default: pg)")
    ap.add_argument("--generate-only", action="store_true",
                    help="write the screening system without running the engine")
    ap.add_argument("--keep-bench", action="store_true", help="leave the bench daemon running")
    return ap


def _load_citecheck(path: Path) -> dict:
    payload = json.loads((path / "citations.json").read_text(encoding="utf-8"))
    return payload.get("targets", {})


def _facts_for(view, led, checked: dict) -> TargetFacts:
    """Join the dossier side and the registry side over the same record set."""
    counters = checked.get("counters", {})
    by_id = {c["source"]["id"]: c for c in checked.get("citations", [])}

    facts = TargetFacts(
        symbol=view.symbol,
        verdict=view.verdict,
        verdict_node=view.verdict_node.id if view.verdict_node else "",
        cited_records=counters.get("checked_total", 0),
        subject_records=counters.get("subject_records", 0),
        weak_attribution=counters.get("weak_attribution", 0),
        off_target=counters.get("off_target", 0),
        title_drift=counters.get("title_drift", 0),
        retracted=counters.get("retracted", 0),
        unresolved=counters.get("unresolved", 0),
    )
    for citation in led:
        if not citation.source_id:
            continue
        graded = by_id.get(citation.source_id)
        if graded is None:
            continue
        facts.records.append(
            {
                "source_type": citation.source_type,
                "source_id": citation.source_id,
                "node_id": citation.node_id,
                "quote": citation.quote,
                "status": graded["status"],
                "gene_role": graded["gene_role"],
                "indication_role": graded["indication_role"],
                "resolves": graded["resolves"],
                "reason": (graded["reasons"] or [""])[0],
            }
        )
    return facts


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    system_dir = out_dir / "system"
    out_dir.mkdir(parents=True, exist_ok=True)

    citecheck_dir = Path(args.citecheck)
    if not (citecheck_dir / "citations.json").exists():
        print(f"no citations.json in {citecheck_dir} — run agnostik-citecheck first", file=sys.stderr)
        return 2
    checked = _load_citecheck(citecheck_dir)

    bundle = load_exports(args.export)
    symbols = [s.strip() for s in args.targets.split(",") if s.strip()]
    views = discover(bundle, symbols, verdict_pattern=args.verdict_pattern)

    all_facts: list[TargetFacts] = []
    for view in views:
        if view.missing or view.symbol not in checked:
            print(f"{view.symbol:6} skipped — not in both the export and the citation check", file=sys.stderr)
            continue
        roots = [view.verdict_node.id] if view.verdict_node else []
        secondary = [c.id for c in view.claims]
        if not roots:
            roots, secondary = secondary[:1], secondary[1:]
        led = ledger(bundle, roots, secondary, max_hops=args.max_hops, limit=args.ledger_limit)
        all_facts.append(_facts_for(view, led, checked[view.symbol]))

    if not all_facts:
        print("nothing to screen", file=sys.stderr)
        return 1

    entry = build_system(all_facts, [str(p) for p in args.export], system_dir)

    # The registry snapshots are stage 5's own documents: copy them in rather
    # than paraphrasing, so the engine verifies the quotes against the file the
    # registry responses were written to.
    for facts in all_facts:
        source = citecheck_dir / "docs" / f"registry-{facts.symbol}.txt"
        if source.exists():
            shutil.copy2(source, system_dir / "docs" / f"registry-{facts.symbol}.txt")
        else:
            print(f"missing registry snapshot for {facts.symbol}: {source}", file=sys.stderr)
            return 2

    print(f"screening system written to {system_dir}")
    if args.generate_only:
        return 0

    # Imported modules are namespaced, so the adjudication nodes are queried by
    # their qualified names.
    value_nodes = [
        f"src.checks.{f.module}-{node}"
        for f in all_facts
        for node in ("verdict-proven", "base-intact", "base-usable", "has-subject-record")
    ] + ["src.checks.proven-verdicts"]
    try:
        engine = run_screening(entry, value_nodes, pg_binary=args.pg_binary, keep_running=args.keep_bench)
    except EngineError as exc:
        print(f"engine error: {exc}", file=sys.stderr)
        return 4

    rows = adjudicate(all_facts, engine)
    meta = {
        "export": [str(p) for p in args.export],
        "citecheck": str(citecheck_dir),
        "system": str(system_dir),
        "targets": [f.symbol for f in all_facts],
    }
    write_json(rows, engine, meta, out_dir / "consistency.json")
    write_markdown(rows, engine, meta, out_dir / "consistency.md")

    print(f"integrity: {engine.integrity} · {len(engine.issues)} proved inconsistencies")
    for row in rows:
        mark = "proven  " if row["verdict_proven"] else "UNPROVEN"
        print(
            f"{row['target']:6} {row['asserted_verdict']:10} {mark} "
            f"cited={row['cited_records']:2} subject={row['subject_records']:2} "
            f"off-target={row['off_target']} retracted={row['retracted']}"
        )
    print(f"\nwrote {out_dir}/consistency.json, consistency.md")

    if engine.load_errors or engine.integrity != "verified":
        return 5
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
