"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .backtrace import ledger
from .bundle import ExportError, load_exports
from .fallback import compose
from .prompt import REPAIR_TEMPLATE, SYSTEM_PROMPT, audit_flags, build_user_prompt
from .report import write_html, write_json, write_markdown
from .resolve import resolve_citations
from .targets import DEFAULT_SHORTLIST, VERDICT_PATTERN, discover, shared_axioms
from .tokenfactory import TokenFactory, TokenFactoryError, env_model
from .verify import verify


def _add_common(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--export",
        action="append",
        required=True,
        metavar="PATH",
        help="pg-bench JSON export (.html / .js / .json). Repeat to merge several views.",
    )
    ap.add_argument(
        "--targets",
        default=",".join(DEFAULT_SHORTLIST),
        help="comma-separated target symbols (default: the six-target CRC shortlist)",
    )
    ap.add_argument("--verdict-pattern", default=VERDICT_PATTERN, help="regex identifying verdict nodes")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="objection-forge",
        description="Five-sentence objections to Parseltongue target verdicts, cited and backtraceable.",
    )
    ap.add_argument("--version", action="version", version=f"objection-forge {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="generate objections")
    _add_common(run)
    run.add_argument("--out", default="out", help="output directory (default: out)")
    run.add_argument("--disease", default="colorectal cancer")
    run.add_argument("--model", default=None, help="model id (default: $NEBIUS_MODEL, else the verified default)")
    run.add_argument("--base-url", default=None, help="OpenAI-compatible endpoint (default: $NEBIUS_BASE_URL)")
    run.add_argument("--temperature", type=float, default=0.2)
    run.add_argument(
        "--max-tokens",
        type=int,
        default=2500,
        help="per-response cap; reasoning models spend most of it thinking before they answer",
    )
    run.add_argument("--sentences", type=int, default=5, help="required sentence count (default: 5)")
    run.add_argument("--ledger-limit", type=int, default=40, help="max citable items per target")
    run.add_argument("--max-hops", type=int, default=12, help="derivation depth walked for the ledger")
    run.add_argument("--attempts", type=int, default=2, help="generation attempts before giving up on a target")
    run.add_argument("--dry-run", action="store_true", help="compose objections offline, no API call, no spend")
    run.add_argument("--no-resolve", action="store_true", help="skip the PMID/NCT/UniProt resolving check")
    run.add_argument("--print-prompt", action="store_true", help="also write each prompt next to the reports")

    ins = sub.add_parser("inspect", help="show what was parsed out of the export")
    _add_common(ins)
    ins.add_argument("--ledger", action="store_true", help="also print the evidence ledger per target")
    ins.add_argument("--ledger-limit", type=int, default=40)
    ins.add_argument("--max-hops", type=int, default=12)

    mod = sub.add_parser("models", help="list the live Token Factory catalogue")
    mod.add_argument("--base-url", default=None)
    return ap


def _roots_for(view) -> tuple[list[str], list[str]]:
    """Primary roots decide ordering; secondary roots pull in the document anchors."""
    primary = [view.verdict_node.id] if view.verdict_node else []
    secondary = [c.id for c in view.claims if not primary or c.id != view.verdict_node.id]
    if not primary and secondary:
        primary, secondary = secondary[:1], secondary[1:]
    return primary, secondary


def cmd_inspect(args: argparse.Namespace) -> int:
    bundle = load_exports(args.export)
    symbols = [s.strip() for s in args.targets.split(",") if s.strip()]
    views = discover(bundle, symbols, verdict_pattern=args.verdict_pattern)

    print(f"export: {', '.join(str(p) for p in args.export)}")
    print(f"globals: {', '.join(bundle.globals_found)}")
    print(f"nodes: {len(bundle)} | tainted: {len(bundle.tainted)} | axioms: {len(shared_axioms(bundle, views))}")
    print()
    for view in views:
        if view.missing:
            print(f"{view.symbol:6} NOT FOUND in export")
            continue
        node = view.verdict_node.id if view.verdict_node else "-"
        print(
            f"{view.symbol:6} {view.label:10} verdict={node:24} "
            f"claims={len(view.claims):3} facts={len(view.facts):3} module={view.module}"
        )
        if args.ledger:
            primary, secondary = _roots_for(view)
            led = ledger(bundle, primary, secondary, max_hops=args.max_hops, limit=args.ledger_limit)
            for c in led:
                src = f"{c.source_type}:{c.source_id}" if c.source_id else f"doc:{c.doc}"
                print(f"        [{c.key:>4}] {src:24} {c.node_id}")
                print(f"               {c.quote[:100]}")
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    client = TokenFactory(base_url=args.base_url or "")
    if not client.available:
        print("no API key: set TOKENFACTORY_TOKEN (or NEBIUS_API_KEY)", file=sys.stderr)
        return 2
    try:
        for model_id in client.list_models():
            print(model_id)
    except TokenFactoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = load_exports(args.export)
    symbols = [s.strip() for s in args.targets.split(",") if s.strip()]
    views = discover(bundle, symbols, verdict_pattern=args.verdict_pattern)

    model_id = args.model or env_model()
    client = TokenFactory(model=model_id, base_url=args.base_url or "")
    offline = args.dry_run or not client.available
    if offline and not args.dry_run:
        print(
            "no Token Factory key found (TOKENFACTORY_TOKEN / NEBIUS_API_KEY) — "
            "composing offline objections instead; set the key for model-written ones",
            file=sys.stderr,
        )

    results: list[dict] = []
    for view in views:
        if view.missing:
            print(f"{view.symbol:6} skipped — not present in the export", file=sys.stderr)
            continue

        primary, secondary = _roots_for(view)
        if not primary:
            print(f"{view.symbol:6} skipped — no verdict or claim node found", file=sys.stderr)
            continue

        led = ledger(bundle, primary, secondary, max_hops=args.max_hops, limit=args.ledger_limit)
        resolution = resolve_citations(
            led.citations,
            cache_path=out_dir / ".resolve-cache.json",
            offline=args.no_resolve,
        )
        flags = audit_flags(view, led, bundle)
        user_prompt = build_user_prompt(view, led, bundle, disease=args.disease, flags=flags)

        attempts_log: list[dict] = []
        text = ""
        checked = None
        model_used = "offline-composer" if offline else model_id

        if offline:
            text = compose(view, led, flags)
            checked = verify(text, led, expected_sentences=args.sentences)
            attempts_log.append({"attempt": 1, "mode": "offline", "verified": checked.ok})
        else:
            prompt = user_prompt
            for attempt in range(1, args.attempts + 1):
                try:
                    completion = client.complete(
                        SYSTEM_PROMPT,
                        prompt,
                        temperature=args.temperature,
                        max_tokens=args.max_tokens,
                    )
                except TokenFactoryError as exc:
                    print(f"{view.symbol:6} model error: {exc}", file=sys.stderr)
                    attempts_log.append({"attempt": attempt, "error": str(exc)})
                    break
                text = completion.text
                checked = verify(text, led, expected_sentences=args.sentences)
                attempts_log.append(
                    {"attempt": attempt, "verified": checked.ok, **completion.to_json()}
                )
                model_used = completion.model
                if checked.ok:
                    break
                prompt = (
                    user_prompt
                    + "\n\n"
                    + REPAIR_TEMPLATE.format(
                        previous=text,
                        problems=checked.failure_report(),
                        keys=", ".join(led.keys),
                    )
                )

        if checked is None:
            text = compose(view, led, flags)
            checked = verify(text, led, expected_sentences=args.sentences)
            model_used = "offline-composer (model unavailable)"

        status = "ok " if checked.ok else "FAIL"
        print(
            f"{view.symbol:6} {view.label:10} {status} "
            f"{len(checked.sentences)} sentences · {len(led)} ledger items · "
            f"{resolution['resolved']}/{resolution['checked']} ids resolve"
        )

        results.append(
            {
                "target": view.symbol,
                "disease": args.disease,
                "verdict": view.label,
                "verdict_node": view.verdict_node.id if view.verdict_node else "",
                "verdict_value": view.verdict_node.value if view.verdict_node else "",
                "model": model_used,
                "claims": [
                    {"id": c.id, "value": c.value, "rule": c.definition, "inputs": c.inputs}
                    for c in sorted(view.claims, key=lambda n: (n.depth, n.id))
                ],
                "flags": flags,
                "resolution": resolution,
                "ledger_size": len(led),
                "ledger": [c.to_json() for c in led],
                "derivation_chain": [{"node": nid, "hops": h} for nid, h in led.chain],
                "attempts": attempts_log,
                "verification": checked.to_json(),
            }
        )

        if args.print_prompt:
            (out_dir / f"prompt-{view.symbol}.txt").write_text(
                SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt, encoding="utf-8"
            )

    if not results:
        print("nothing to report — no target matched the export", file=sys.stderr)
        return 1

    meta = {
        "version": __version__,
        "export": [str(p) for p in args.export],
        "model": results[0]["model"] if results else model_id,
        "disease": args.disease,
        "sentences_required": args.sentences,
        "offline": offline,
        "resolution_checked": not args.no_resolve,
        "targets": [r["target"] for r in results],
    }
    write_json(results, meta, out_dir / "objections.json")
    write_markdown(results, meta, out_dir / "objections.md")
    write_html(results, meta, out_dir / "objections.html")

    failed = [r["target"] for r in results if not r["verification"]["verified"]]
    print()
    print(f"wrote {out_dir}/objections.json, objections.md, objections.html")
    if failed:
        print(f"verification failed for: {', '.join(failed)}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return cmd_run(args)
        if args.command == "inspect":
            return cmd_inspect(args)
        if args.command == "models":
            return cmd_models(args)
    except ExportError as exc:
        print(f"export error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    return 1
