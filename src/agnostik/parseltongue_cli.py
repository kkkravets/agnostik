"""Console entrypoint for the formal Parseltongue Formalization pipeline."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from agnostik.candidates import PRESELECTED_CANDIDATES
from agnostik.evidence_cli import DEFAULT_CANCER_TERMS
from agnostik.formalization import (
    DEFAULT_MAX_DOCUMENTS_PER_TARGET,
    DEFAULT_MAX_TARGET_CHARS,
    DEFAULT_TARGET_ATTEMPTS,
    FormalizationConfig,
    discover_sources,
    export_completed_targets,
    run_formalization,
    select_target_sources,
    target_query,
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
    parser.add_argument("--target", action="append", dest="targets")
    parser.add_argument("--max-documents-per-target", type=int, default=DEFAULT_MAX_DOCUMENTS_PER_TARGET)
    parser.add_argument("--max-target-chars", type=int, default=DEFAULT_MAX_TARGET_CHARS)
    parser.add_argument(
        "--criteria",
        type=Path,
        help="markdown file of review criteria the model must encode as axioms and apply to every target "
        "(for example criteria/target-shortlist.md); without it the model invents its own decision rule",
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
        help="targets to process concurrently (default: 1; passes within a target remain sequential)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=DEFAULT_TARGET_ATTEMPTS,
        help="maximum complete pipeline attempts per target (default: 2)",
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
    targets = tuple(args.targets or PRESELECTED_CANDIDATES)
    try:
        config = FormalizationConfig(
            tumour_type=tumour_type,
            cancer_term=cancer_term,
            corpus_manifest=args.corpus_manifest
            or Path("results/evidence") / tumour_type.lower() / "corpus.json",
            output_dir=args.output_dir or tumour_root / "formalization",
            targets=targets,
            max_documents_per_target=args.max_documents_per_target,
            max_target_chars=args.max_target_chars,
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
            plans = []
            for target in config.targets:
                selected = select_target_sources(sources, target, max_documents=config.max_documents_per_target, max_chars=config.max_target_chars)
                plans.append({
                    "target": target,
                    "source_count": len(selected),
                    "sources": [path.name for path in selected],
                    "required_verdict": f"{target.lower()}-verdict",
                    "query": target_query(target, cancer_term, tumour_type, criteria=config.criteria.name if config.criteria else None),
                })
            payload = {
                "corpus_manifest": str(config.corpus_manifest),
                "output_dir": str(config.output_dir),
                "corpus_source_count": len(sources),
                "criteria": str(config.criteria) if config.criteria else None,
                "targets": plans,
                "export": str(config.output_dir / "formal-system.json"),
            }
        else:
            run = run_formalization(
                config,
                overwrite=args.overwrite,
                resume=args.resume,
                max_workers=args.workers,
                max_attempts=args.attempts,
            )
            payload = {
                "source_count": run.source_count,
                "target_count": run.target_count,
                "reused_targets": run.reused_targets,
                "output_dir": str(run.output_dir),
                "export": str(run.export_path),
            }
    except (FileNotFoundError, FileExistsError, ValueError, EmptyToolCallError) as exc:
        parser.error(str(exc))
    if args.as_json:
        print(json.dumps(payload))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
