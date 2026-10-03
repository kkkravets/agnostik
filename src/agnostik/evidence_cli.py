"""CLI for reproducible literature and clinical-trial collection."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys

from agnostik.candidates import PRESELECTED_CANDIDATES, default_targets_file, load_gene_list, select_candidates
from agnostik.evidence import (
    EvidenceConfig,
    collect_evidence_batch,
    write_corpus_manifest,
)
from agnostik.targets.resolve import cancer_term_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agnostik-collect-evidence",
        description=(
            "Collect reproducible ClawBio PubMed, PMC full-text, and "
            "ClinicalTrials.gov evidence for target candidates."
        ),
    )
    parser.add_argument("tumour_type", help="TCGA code, for example BRCA")
    parser.add_argument(
        "--cancer-term",
        help="literature and trial disease term (default: the saved resolution, else the GDC project name)",
    )
    genes_group = parser.add_mutually_exclusive_group()
    genes_group.add_argument(
        "--gene",
        action="append",
        dest="genes",
        help="candidate gene; repeat for multiple genes (default: fixed v1 panel)",
    )
    genes_group.add_argument(
        "--genes-file",
        type=Path,
        help=(
            "shortlist of candidate genes to use instead of the fixed v1 panel: "
            "a plain text file with one gene symbol per line, or a CSV with a "
            "'gene_symbol' column, such as the output of "
            "scripts/open_targets_candidates.py"
            " (default: results/targets/<tumour>/symbols.txt when it exists)"
        ),
    )
    genes_group.add_argument(
        "--fixed-panel",
        action="store_true",
        help="use the fixed v1 panel even when a ranked shortlist exists for the tumour",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        help="with --genes-file, use only the first N genes from the file",
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
        try:
            cancer_term = args.cancer_term or cancer_term_for(selection.tumour_type)
        except ValueError as exc:
            parser.error(f"{exc}; pass --cancer-term")
        genes_file = args.genes_file
        if genes_file is None and not (args.genes or args.fixed_panel):
            shortlist = default_targets_file(selection.tumour_type)
            if shortlist.is_file():
                genes_file = shortlist
                print(f"Using ranked shortlist {shortlist}", file=sys.stderr)
        if args.top_n is not None and not genes_file:
            parser.error("--top-n requires --genes-file")
        if genes_file:
            genes = load_gene_list(genes_file, limit=args.top_n)
        else:
            genes = tuple(args.genes or PRESELECTED_CANDIDATES)
        article_query = args.article_query
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
    corpus_path = config.output_root / config.tumour_type.lower() / "corpus.json"
    try:
        corpus_count = write_corpus_manifest(runs, corpus_path)
    except ValueError as exc:
        parser.error(str(exc))
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
        if corpus_count:
            print(f"Corpus: {corpus_count} unique articles | {corpus_path}")
        else:
            print("Corpus: no articles collected; no manifest written")
    return 1 if any(run.status == "failed" for run in runs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
