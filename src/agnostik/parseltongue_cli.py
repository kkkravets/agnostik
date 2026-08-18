"""Console entrypoint for the formal Parseltongue Stage-3 pipeline."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from agnostik.candidates import PRESELECTED_CANDIDATES
from agnostik.evidence_cli import DEFAULT_CANCER_TERMS
from agnostik.parseltongue_corpus import (
    DEFAULT_MAX_DOCUMENTS_PER_TARGET,
    DEFAULT_MAX_TARGET_CHARS,
    Stage3Config,
    discover_sources,
    run_stage3,
    select_target_sources,
    target_query,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agnostik-parseltongue",
        description="Derive per-candidate verdicts and emit the pg-bench JSON consumed by Stage 4.",
    )
    parser.add_argument("tumour_type", help="TCGA tumour code, for example COAD")
    parser.add_argument("--input", type=Path, dest="source_dir")
    parser.add_argument("--output", type=Path, dest="output_dir")
    parser.add_argument("--cancer-term", help="human-readable cancer term")
    parser.add_argument("--target", action="append", dest="targets")
    parser.add_argument("--max-documents-per-target", type=int, default=DEFAULT_MAX_DOCUMENTS_PER_TARGET)
    parser.add_argument("--max-target-chars", type=int, default=DEFAULT_MAX_TARGET_CHARS)
    parser.add_argument("--model", help="Nebius model; defaults to NEBIUS_MODEL")
    parser.add_argument("--base-url", help="defaults to NEBIUS_BASE_URL")
    parser.add_argument("--reasoning-tokens", type=int)
    rerun = parser.add_mutually_exclusive_group()
    rerun.add_argument("--resume", action="store_true")
    rerun.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
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
        config = Stage3Config(
            tumour_type=tumour_type,
            cancer_term=cancer_term,
            source_dir=args.source_dir or tumour_root / "full_text_articles",
            output_dir=args.output_dir or tumour_root / "parseltongue_stage3",
            targets=targets,
            max_documents_per_target=args.max_documents_per_target,
            max_target_chars=args.max_target_chars,
            model=args.model,
            base_url=args.base_url,
            reasoning=args.reasoning_tokens,
        )
        if args.dry_run:
            sources = discover_sources(config.source_dir)
            plans = []
            for target in config.targets:
                selected = select_target_sources(sources, target, max_documents=config.max_documents_per_target, max_chars=config.max_target_chars)
                plans.append({
                    "target": target,
                    "source_count": len(selected),
                    "sources": [path.name for path in selected],
                    "required_verdict": f"{target.lower()}-verdict",
                    "query": target_query(target, cancer_term, tumour_type),
                })
            payload = {
                "source_dir": str(config.source_dir),
                "output_dir": str(config.output_dir),
                "corpus_source_count": len(sources),
                "targets": plans,
                "stage4_export": str(config.output_dir / "stage3-export.json"),
            }
        else:
            run = run_stage3(config, overwrite=args.overwrite, resume=args.resume)
            payload = {
                "source_count": run.source_count,
                "target_count": run.target_count,
                "reused_targets": run.reused_targets,
                "output_dir": str(run.output_dir),
                "stage4_export": str(run.export_path),
            }
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        parser.error(str(exc))
    if args.as_json:
        print(json.dumps(payload))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
