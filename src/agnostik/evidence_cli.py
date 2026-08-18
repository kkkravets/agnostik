"""CLI for reproducible literature and clinical-trial collection."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from agnostik.candidates import PRESELECTED_CANDIDATES, select_candidates
from agnostik.evidence import EvidenceConfig, collect_evidence_batch


DEFAULT_CANCER_TERMS = {
    "BRCA": "breast cancer",
    "COAD": "colon adenocarcinoma",
    "LUAD": "lung adenocarcinoma",
    "LUSC": "lung squamous cell carcinoma",
    "PAAD": "pancreatic adenocarcinoma",
    "PRAD": "prostate adenocarcinoma",
    "SKCM": "cutaneous melanoma",
}

DEFAULT_ARTICLE_QUERIES = {
    "COAD": (
        '(COAD[Title/Abstract] OR "colon adenocarcinoma"[Title/Abstract] '
        'OR colorectal[Title/Abstract])'
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agnostik-evidence",
        description=(
            "Collect reproducible ClawBio PubMed, PMC full-text, and "
            "ClinicalTrials.gov evidence for target candidates."
        ),
    )
    parser.add_argument("tumour_type", help="TCGA code, for example BRCA")
    parser.add_argument(
        "--cancer-term",
        help="Registry/literature disease term; required when no default exists",
    )
    parser.add_argument(
        "--gene",
        action="append",
        dest="genes",
        help="candidate gene; repeat for multiple genes (default: fixed v1 panel)",
    )
    parser.add_argument(
        "--article-query",
        help=(
            "base PubMed/PMC expression; each gene is appended as "
            "'AND GENE[Title/Abstract]'"
        ),
    )
    parser.add_argument(
        "--max-articles",
        "--max-articles-per-gene",
        dest="max_articles",
        type=int,
        default=5,
        help="maximum complete PMC articles per gene (default: 5)",
    )
    parser.add_argument("--max-trials", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("results/evidence"))
    parser.add_argument("--ncbi-email", default="agnostik@example.com")
    rerun = parser.add_mutually_exclusive_group()
    rerun.add_argument("--overwrite", action="store_true")
    rerun.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        selection = select_candidates(args.tumour_type)
        cancer_term = args.cancer_term or DEFAULT_CANCER_TERMS.get(selection.tumour_type)
        if not cancer_term:
            parser.error(
                f"--cancer-term is required for TCGA-{selection.tumour_type}"
            )
        genes = tuple(args.genes or PRESELECTED_CANDIDATES)
        article_query = args.article_query or DEFAULT_ARTICLE_QUERIES.get(
            selection.tumour_type
        )
        config = EvidenceConfig(
            tumour_type=selection.tumour_type,
            cancer_term=cancer_term,
            genes=genes,
            article_query=article_query,
            max_articles=args.max_articles,
            max_trials=args.max_trials,
            output_root=args.output,
            ncbi_email=args.ncbi_email,
        )
    except ValueError as exc:
        parser.error(str(exc))

    runs = collect_evidence_batch(
        config,
        overwrite=args.overwrite,
        skip_existing=args.skip_existing,
    )
    if args.as_json:
        print(
            json.dumps(
                [
                    {
                        "gene": run.gene,
                        "run_id": run.run_id,
                        "run_dir": str(run.run_dir),
                        "status": run.status,
                        "article_count": run.article_count,
                        "trial_count": run.trial_count,
                        "recruiting_trial_count": run.recruiting_trial_count,
                        "error": run.error,
                    }
                    for run in runs
                ]
            )
        )
    else:
        for run in runs:
            print(
                f"{run.gene}: {run.status} | articles={run.article_count} "
                f"trials={run.trial_count} recruiting={run.recruiting_trial_count} "
                f"| {run.run_dir}"
            )
            if run.error:
                print(f"  error: {run.error}")
    return 1 if any(run.status == "failed" for run in runs) else 0
