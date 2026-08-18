"""Command-line interface for the v1 workflow."""

import argparse
import json
from collections.abc import Sequence

from agnostik.candidates import select_candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agnostik",
        description="Select the fixed v1 target panel for a TCGA tumour type.",
    )
    parser.add_argument(
        "tumour_type",
        help="TCGA tumour-type code, for example BRCA, LUAD, or COAD",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        selection = select_candidates(args.tumour_type)
    except ValueError as error:
        parser.error(str(error))

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

