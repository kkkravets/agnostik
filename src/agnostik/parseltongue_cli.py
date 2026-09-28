"""Console entrypoint for the formal Parseltongue Formalization pipeline."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
import json
from pathlib import Path

from agnostik.candidates import PRESELECTED_ALIASES, PRESELECTED_CANDIDATES, load_gene_aliases, load_gene_list
from agnostik.criteria import load_criteria
from agnostik.evidence_cli import DEFAULT_CANCER_TERMS
from agnostik.formalization import (
    DEFAULT_ATTEMPTS,
    DEFAULT_CRITERIA,
    DEFAULT_MAX_DOCUMENT_CHARS,
    DocumentFailures,
    FormalizationConfig,
    discover_sources,
    export_completed_targets,
    plan_target,
    run_formalization,
    verdict_name,
)
from agnostik.nebius import EmptyToolCallError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agnostik-parseltongue",
        description="Derive per-candidate verdicts and emit the pg-bench JSON consumed by objections.",
    )
    parser.add_argument("tumour_type", help="TCGA tumour code, for example COAD")
    parser.add_argument(
        "--input",
        type=Path,
        dest="corpus_manifest",
        help="corpus.json written by agnostik-collect-evidence "
        "(default: results/evidence/<tumour>/corpus.json)",
    )
    parser.add_argument("--output", type=Path, dest="output_dir")
    parser.add_argument("--cancer-term", help="human-readable cancer term")
    targets_group = parser.add_mutually_exclusive_group()
    targets_group.add_argument("--target", action="append", dest="targets")
    targets_group.add_argument(
        "--targets-file",
        type=Path,
        help=(
            "shortlist of candidate genes to use instead of the fixed v1 panel: "
            "a plain text file with one gene symbol per line, or a CSV with a "
            "'gene_symbol' column and an optional 'aliases' column (names separated by ';'), "
            "such as the output of scripts/open_targets_crc_candidates.py"
        ),
    )
    parser.add_argument(
        "--top-n",
        type=int,
        help="with --targets-file, use only the first N genes from the file",
    )
    parser.add_argument(
        "--max-documents-per-target",
        type=int,
        help="use at most N articles and N trial records per target, the most target-specific first "
        "(default: all that mention the target; the rest are listed in the target manifest)",
    )
    parser.add_argument(
        "--max-document-chars",
        type=int,
        default=DEFAULT_MAX_DOCUMENT_CHARS,
        help="characters of one document shown to the model (default: %(default)s); a longer document is cut "
        "for the prompt, recorded as truncated, and still verified against its full text",
    )
    parser.add_argument(
        "--criteria",
        type=Path,
        default=DEFAULT_CRITERIA,
        help="Markdown file of review criteria every target is judged by (default: criteria/target-shortlist.md); "
        "see the README for its format",
    )
    parser.add_argument("--model", help="Nebius model; defaults to NEBIUS_MODEL")
    parser.add_argument("--base-url", help="defaults to NEBIUS_BASE_URL")
    parser.add_argument("--reasoning-tokens", type=int)
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        help="output-token limit per model reply; without it the provider's default applies, which a reasoning "
        "model can use up before writing its answer (finish_reason=length)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="targets to process concurrently (default: 1)",
    )
    parser.add_argument(
        "--document-workers",
        type=int,
        default=1,
        help="documents of one target to process concurrently, each with its own connection (default: 1)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=DEFAULT_ATTEMPTS,
        help="maximum attempts per model call (default: 2)",
    )
    rerun = parser.add_mutually_exclusive_group()
    rerun.add_argument("--resume", action="store_true")
    rerun.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--export-completed",
        action="store_true",
        help="build formal-system.partial.json from completed targets without model calls",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    tumour_type = args.tumour_type.strip().upper()
    cancer_term = args.cancer_term or DEFAULT_CANCER_TERMS.get(tumour_type)
    if not cancer_term:
        parser.error("--cancer-term is required when no default exists")
    tumour_root = Path("results/clawbio_skill_trial") / f"tcga-{tumour_type.lower()}"
    try:
        if args.top_n is not None and not args.targets_file:
            parser.error("--top-n requires --targets-file")
        aliases = dict(PRESELECTED_ALIASES)
        if args.targets_file:
            targets = load_gene_list(args.targets_file, limit=args.top_n)
            aliases.update(load_gene_aliases(args.targets_file))
        else:
            targets = tuple(args.targets or PRESELECTED_CANDIDATES)
        config = FormalizationConfig(
            tumour_type=tumour_type,
            cancer_term=cancer_term,
            corpus_manifest=args.corpus_manifest
            or Path("results/evidence") / tumour_type.lower() / "corpus.json",
            output_dir=args.output_dir or tumour_root / "formalization",
            targets=targets,
            target_aliases=aliases,
            max_documents_per_target=args.max_documents_per_target,
            max_document_chars=args.max_document_chars,
            model=args.model,
            base_url=args.base_url,
            reasoning=args.reasoning_tokens,
            criteria=args.criteria,
            max_output_tokens=args.max_output_tokens,
        )
        if args.export_completed:
            export_path, completed_targets = export_completed_targets(
                config.output_dir,
                config.targets,
            )
            payload = {
                "completed_targets": list(completed_targets),
                "target_count": len(completed_targets),
                "export": str(export_path),
            }
        elif args.dry_run:
            sources = discover_sources(config.corpus_manifest)
            criteria = load_criteria(config.criteria)
            plans = [plan_target(config, sources, criteria, target) for target in config.targets]
            payload = {
                "corpus_manifest": str(config.corpus_manifest),
                "output_dir": str(config.output_dir),
                "corpus_source_count": len(sources),
                "criteria": str(config.criteria),
                # Each rule's prose next to what the pipeline read from it, to check they agree.
                "rules": criteria.describe(),
                "model_calls": sum(plan.model_calls for plan in plans),
                "targets": [
                    {
                        "target": plan.target,
                        "aliases": list(plan.aliases),
                        "required_verdict": verdict_name(plan.target),
                        "model_calls": plan.model_calls,
                        "documents": [
                            {
                                "file": doc.source.name,
                                "kind": doc.kind,
                                "chars": len(doc.text),
                                "truncated_to": len(doc.prompt_text) if len(doc.prompt_text) < len(doc.text) else None,
                            }
                            for doc in plan.documents
                        ],
                        "excluded": dict(Counter(entry["reason"] for entry in plan.excluded)),
                        "excluded_over_cap": [entry["file"] for entry in plan.excluded if entry["reason"].startswith("over ")],
                    }
                    for plan in plans
                ],
                "export": str(config.output_dir / "formal-system.json"),
            }
        else:
            run = run_formalization(
                config,
                overwrite=args.overwrite,
                resume=args.resume,
                max_workers=args.workers,
                document_workers=args.document_workers,
                max_attempts=args.attempts,
            )
            payload = {
                "source_count": run.source_count,
                "target_count": run.target_count,
                "reused_targets": run.reused_targets,
                "model_calls": run.model_calls,
                "output_dir": str(run.output_dir),
                "export": str(run.export_path),
            }
    except (FileNotFoundError, FileExistsError, ValueError, EmptyToolCallError, DocumentFailures) as exc:
        parser.error(str(exc))
    if args.as_json:
        print(json.dumps(payload))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
