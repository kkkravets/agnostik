#!/usr/bin/env python3
"""Rank gene targets for a TCGA tumour type via Open Targets.

Kept as a thin wrapper around `agnostik` (same arguments), for running from a checkout:

    uv run python scripts/open_targets_candidates.py READ --top-n 20
"""

from agnostik.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
