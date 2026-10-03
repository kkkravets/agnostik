"""Candidate selection for the v1 workflow."""

import csv
from dataclasses import dataclass
from pathlib import Path
import re

PRESELECTED_CANDIDATES: tuple[str, ...] = (
    "EGFR",
    "ERBB2",
    "KRAS",
    "MYC",
    "WRN",
    "PRMT5",
)

# Other names a panel target goes by in articles and trial records. A document naming
# an alias counts as naming the target, for selection and for the criteria questions.
PRESELECTED_ALIASES: dict[str, tuple[str, ...]] = {
    "EGFR": ("ERBB1", "HER1"),
    "ERBB2": ("HER2", "HER-2"),
    "KRAS": ("K-RAS",),
}

TARGETS_ROOT = Path("results/targets")

_TCGA_CODE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
_GENE_SYMBOL = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    """A normalized tumour type paired with the fixed v1 candidate panel."""

    tumour_type: str
    candidates: tuple[str, ...]


def select_candidates(tumour_type: str) -> CandidateSelection:
    """Return the fixed v1 panel for a TCGA tumour-type code.

    This step intentionally performs no candidate discovery, evidence lookup,
    or ranking. Semantic validation against Xena happens when the live-query
    stage is implemented.
    """

    normalized = tumour_type.strip().upper()
    if not _TCGA_CODE.fullmatch(normalized):
        raise ValueError(
            "tumour type must be a 2-10 character TCGA code, for example BRCA or LUAD"
        )

    return CandidateSelection(
        tumour_type=normalized,
        candidates=PRESELECTED_CANDIDATES,
    )


def load_gene_list(path: Path, limit: int | None = None) -> tuple[str, ...]:
    """Read a ranked gene shortlist, such as the CSV or symbol list written by
    ``scripts/open_targets_candidates.py``, into a target panel.

    Accepts either a plain text file with one gene symbol per line, or a CSV
    with a ``gene_symbol`` column (rows are kept in file order, so an
    ``opentargets_rank``-sorted CSV yields a rank-ordered panel). Blank lines,
    a leading ``#`` comment marker, and duplicate symbols are ignored.
    """

    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "gene_symbol" not in reader.fieldnames:
                raise ValueError(f"{path}: CSV must have a 'gene_symbol' column")
            raw_symbols = [row["gene_symbol"] for row in reader]
    else:
        raw_symbols = path.read_text(encoding="utf-8").splitlines()

    genes: list[str] = []
    seen: set[str] = set()
    for raw in raw_symbols:
        symbol = raw.strip()
        if not symbol or symbol.startswith("#"):
            continue
        symbol = symbol.upper()
        if not _GENE_SYMBOL.fullmatch(symbol):
            raise ValueError(f"{path}: invalid gene symbol {raw!r}")
        if symbol in seen:
            continue
        seen.add(symbol)
        genes.append(symbol)
        if limit is not None and len(genes) >= limit:
            break

    if not genes:
        raise ValueError(f"{path}: no gene symbols found")

    return tuple(genes)


def load_gene_aliases(path: Path) -> dict[str, tuple[str, ...]]:
    """Read the optional ``aliases`` column of a gene-list CSV (names separated by ``;``).

    Plain text lists and CSVs without the column carry no aliases.
    """

    path = Path(path)
    if path.suffix.lower() != ".csv":
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "aliases" not in reader.fieldnames:
            return {}
        aliases: dict[str, tuple[str, ...]] = {}
        for row in reader:
            symbol = (row.get("gene_symbol") or "").strip().upper()
            names = tuple(dict.fromkeys(name.strip() for name in (row.get("aliases") or "").split(";") if name.strip()))
            if symbol and names:
                aliases[symbol] = names
    return aliases



def default_targets_file(tumour_code: str) -> Path:
    """Where `agnostik` writes a tumour's ranked symbol shortlist."""

    return TARGETS_ROOT / tumour_code.strip().lower() / "symbols.txt"


def resolution_file(tumour_code: str) -> Path:
    """The disease resolution saved beside the shortlist."""

    return default_targets_file(tumour_code).with_name("resolution.json")
