"""Stage 5 — citation resolving check.

Grades every external identifier the shortlist rests on: does it resolve, does
the quoted title still match, is the attributed gene the subject of the record
or only mentioned in passing, and has the paper been retracted.
"""

from .check import CitationCheck, check_citations
from .registry import Record, Registry

__all__ = ["CitationCheck", "check_citations", "Registry", "Record"]
