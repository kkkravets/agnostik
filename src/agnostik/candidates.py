"""Candidate selection for the v1 workflow."""

from dataclasses import dataclass
import re

PRESELECTED_CANDIDATES: tuple[str, ...] = (
    "EGFR",
    "ERBB2",
    "KRAS",
    "MYC",
    "WRN",
    "PRMT5",
)

_TCGA_CODE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


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

