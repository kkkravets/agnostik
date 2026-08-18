"""objection-forge — stage 4 of the CRC target triage pipeline.

Takes a pg-bench JSON export of the Parseltongue shortlist system, and for
each target produces a five-sentence objection written by a Token Factory
model, where every sentence is cited into the derivation and every citation
backtraces to a source document and an external record.
"""

__version__ = "0.1.0"

from .bundle import Bundle, ExportError, Node, load_export, load_exports
from .targets import DEFAULT_SHORTLIST, TargetView, discover

__all__ = [
    "Bundle",
    "Node",
    "ExportError",
    "load_export",
    "load_exports",
    "discover",
    "TargetView",
    "DEFAULT_SHORTLIST",
    "__version__",
]
