"""Find targets, their claims and their verdicts inside a pg-bench export.

The upstream naming is not ours to dictate — stage 3 belongs to another
part of the pipeline — so discovery is pattern-driven and every pattern is
overridable from the CLI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .bundle import Bundle, Node

__all__ = ["TargetView", "discover", "DEFAULT_SHORTLIST", "VERDICT_PATTERN"]

# The shortlist is fixed for this round — the six targets carried by the
# Parseltongue CRC demo. Scope for the clock, not for the idea.
DEFAULT_SHORTLIST = ["EGFR", "ERBB2", "KRAS", "MYC", "WRN", "PRMT5"]

VERDICT_PATTERN = r"(verdict|promising|rejected|shortlist|decision)"

_TRUE = {"true", "t", "yes", "1", "promising", "accept", "accepted"}
_FALSE = {"false", "f", "no", "0", "rejected", "reject", "none", "nil", "()"}


def as_bool(value: str) -> bool | None:
    v = (value or "").strip().strip("'\"").lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None


@dataclass
class TargetView:
    """Everything the objection layer needs about one target."""

    symbol: str
    module: str | None = None
    verdict_node: Node | None = None
    verdict: bool | None = None
    claims: list[Node] = field(default_factory=list)
    facts: list[Node] = field(default_factory=list)
    axioms: list[Node] = field(default_factory=list)
    missing: bool = False

    @property
    def label(self) -> str:
        if self.verdict is True:
            return "promising"
        if self.verdict is False:
            return "rejected"
        return "undecided"

    @property
    def all_nodes(self) -> list[Node]:
        seen: dict[str, Node] = {}
        for n in [*self.claims, *self.facts, *self.axioms]:
            seen[n.id] = n
        if self.verdict_node is not None:
            seen[self.verdict_node.id] = self.verdict_node
        return list(seen.values())

    def claim(self, needle: str) -> Node | None:
        for n in self.claims:
            if needle in n.id:
                return n
        return None


def _module_for(bundle: Bundle, symbol: str) -> str | None:
    """Locate the namespace segment that holds this target's dossier."""
    sym = symbol.lower()
    best: tuple[int, str] | None = None
    for node in bundle.nodes.values():
        parts = node.id.split(".")
        for i, part in enumerate(parts[:-1]):
            if part.lower() == sym:
                prefix = ".".join(parts[: i + 1])
                count = sum(1 for n in bundle.nodes if n.startswith(prefix + "."))
                if best is None or count > best[0]:
                    best = (count, prefix)
    return best[1] if best else None


def _verdict_for(bundle: Bundle, symbol: str, module: str | None, pattern: str) -> Node | None:
    """Pick the node that carries this target's accept/reject decision.

    Prefers a top-level decision node (``egfr-promising``) over a
    dossier-internal one, since the top level is where a stage-3 system
    usually applies its final rule.
    """
    rx = re.compile(pattern, re.IGNORECASE)
    sym = symbol.lower()
    candidates: list[tuple[int, Node]] = []
    for node in bundle.nodes.values():
        nid = node.id.lower()
        if not rx.search(nid):
            continue
        in_module = bool(module) and nid.startswith(module.lower() + ".")
        names_symbol = re.search(rf"(^|[.\-_]){re.escape(sym)}([.\-_]|$)", nid) is not None
        if not (in_module or names_symbol):
            continue
        depth_of_name = node.id.count(".")
        # lower score wins: top-level, symbol-named, decided
        score = depth_of_name * 10
        if not names_symbol:
            score += 5
        if as_bool(node.value) is None:
            score += 3
        candidates.append((score, node))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: (pair[0], pair[1].id))
    return candidates[0][1]


def discover(
    bundle: Bundle,
    symbols: list[str] | None = None,
    verdict_pattern: str = VERDICT_PATTERN,
) -> list[TargetView]:
    """Build a :class:`TargetView` per requested symbol."""
    symbols = symbols or DEFAULT_SHORTLIST
    views: list[TargetView] = []

    for symbol in symbols:
        module = _module_for(bundle, symbol)
        verdict_node = _verdict_for(bundle, symbol, module, verdict_pattern)
        view = TargetView(symbol=symbol, module=module, verdict_node=verdict_node)

        if verdict_node is not None:
            view.verdict = as_bool(verdict_node.value)

        if module:
            members = [n for n in bundle.nodes.values() if n.id.startswith(module + ".")]
            for node in sorted(members, key=lambda n: n.id):
                if node.kind == "axiom":
                    view.axioms.append(node)
                elif node.is_derived or node.kind in ("calc", "theorem", "term"):
                    view.claims.append(node)
                else:
                    view.facts.append(node)

        view.missing = module is None and verdict_node is None
        views.append(view)

    return views


def shared_axioms(bundle: Bundle, views: list[TargetView]) -> list[Node]:
    """Rule nodes that are not owned by any single target (the charter)."""
    owned = {n.id for v in views for n in v.all_nodes}
    return sorted(
        (n for n in bundle.nodes.values() if n.kind == "axiom" and n.id not in owned),
        key=lambda n: n.id,
    )
