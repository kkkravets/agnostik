"""Stage 6 — formal consistency screening.

Replaces a weighted target-validation score with proved divergence: the
dossier's assertions and the registries' answers are written as two independent
Parseltongue fact modules over the same record set, every possible disagreement
is declared as a ``diff``, and the engine decides which of them actually hold.
"""

from .engine import EngineResult, ScreenItem, run_screening
from .generate import TargetFacts, build_system

__all__ = ["run_screening", "EngineResult", "ScreenItem", "build_system", "TargetFacts"]
