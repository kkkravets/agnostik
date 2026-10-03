"""Command-line interface for the v1 workflow."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
import sys

from agnostik.candidates import TARGETS_ROOT, select_candidates
from agnostik.targets.opentargets import HttpJson, fetch_targets, http_json, merge_targets, write_shortlist
from agnostik.targets.resolve import resolve_disease, write_resolution

DEFAULT_TUMOUR = "COAD"  # colorectal cancer
DEFAULT_TOP_N = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agnostik",
        description=(
            "Find target candidates for a TCGA tumour type: the tumour is matched to an "
            "Open Targets disease and its top-ranked genes are written as a shortlist "
            "the later stages pick up. --fixed-panel prints the fixed v1 panel instead."
        ),
    )
    parser.add_argument(
        "tumour_type",
        nargs="?",
        default=DEFAULT_TUMOUR,
        help=f"TCGA tumour-type code, for example BRCA, READ or LUAD (default: {DEFAULT_TUMOUR})",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"number of protein-coding targets to keep (default: {DEFAULT_TOP_N})",
    )
    parser.add_argument(
        "--disease",
        help="disease name to search Open Targets for, instead of the GDC name of the TCGA project",
    )
    parser.add_argument(
        "--disease-id",
        help="Open Targets disease ID (MONDO_/EFO_...), skipping the search",
    )
    parser.add_argument(
        "--no-parents",
        action="store_true",
        help="rank the matched disease alone, without its organ-specific parent diseases",
    )
    parser.add_argument(
        "--direct-only",
        action="store_true",
        help="rank on evidence recorded on the disease itself, not on its descendant subtypes",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help=f"where to write the shortlist (default: {TARGETS_ROOT}/<tumour>)",
    )
    parser.add_argument(
        "--fixed-panel",
        action="store_true",
        help="print the fixed v1 panel without any lookup",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, http: HttpJson = http_json) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        selection = select_candidates(args.tumour_type)
    except ValueError as error:
        parser.error(str(error))

    if args.fixed_panel:
        if args.disease or args.disease_id:
            parser.error("--fixed-panel cannot be combined with --disease or --disease-id")
        if args.as_json:
            print(
                json.dumps(
                    {
                        "tumour_type": selection.tumour_type,
                        "candidates": list(selection.candidates),
                    }
                )
            )
        else:
            print(f"Tumour type: {selection.tumour_type}")
            print(f"Candidates: {', '.join(selection.candidates)}")
        return 0

    if args.top_n < 1:
        parser.error("--top-n must be at least 1")
    try:
        resolution = resolve_disease(
            selection.tumour_type,
            disease=args.disease,
            disease_id=args.disease_id,
            include_parents=not args.no_parents,
            http=http,
        )
        targets = merge_targets(
            [
                fetch_targets(disease_id, args.top_n, enable_indirect=not args.direct_only, http=http)[1]
                for disease_id in (resolution.disease_id, *(parent.id for parent in resolution.parents))
            ],
            args.top_n,
        )
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    except OSError as error:
        print(f"agnostik: could not reach the lookup service ({error})", file=sys.stderr)
        return 1

    out_dir = args.out_dir or TARGETS_ROOT / selection.tumour_type.lower()
    csv_path, symbols_path = write_shortlist(targets, out_dir)
    write_resolution(resolution, out_dir)
    symbols = [target["gene_symbol"] for target in targets if target["gene_symbol"]]

    for warning in resolution.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if args.as_json:
        print(
            json.dumps(
                {
                    "tumour_type": selection.tumour_type,
                    "candidates": symbols,
                    "disease": {"id": resolution.disease_id, "name": resolution.disease_name},
                    "parents": [{"id": parent.id, "name": parent.name} for parent in resolution.parents],
                    "cancer_term": resolution.cancer_term,
                    "warnings": list(resolution.warnings),
                    "shortlist": str(symbols_path),
                }
            )
        )
    else:
        print(f"Tumour type: {selection.tumour_type}")
        print(f"Disease: {resolution.disease_name} ({resolution.disease_id})")
        if resolution.parents:
            print(f"Ranked together with: {', '.join(parent.name for parent in resolution.parents)}")
        print(f"Candidates ({len(symbols)}): {', '.join(symbols)}")
        print(f"Shortlist: {symbols_path} (review scores in {csv_path.name})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
