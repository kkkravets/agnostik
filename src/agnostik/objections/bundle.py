"""Loader for pg-bench JSON export.

pg-bench emits its graph as JSON globals embedded in the viz HTML
(``pg eval '(fmt "viz" ...)' > out.html``):

    const DATA = [...]             primary nodes in the view
    const STRUCTURE_DATA = [...]   full probe structure (richer evidence)
    const LAYERS = {layers, edges} depth layout + typed edges
    const TAINT_DATA = {sources, tainted, reasons}

``extract_viz_data.sh`` pulls those four into a ``*-data.js``. This module
accepts any of the three containers — .html, .js, or plain .json holding
either the DATA array or an object with those keys — and normalises them
into a :class:`Bundle`.

Node schema (see parseltongue/core/inspect/perspectives/visualisation/items.py):
    id, kind, value, depth, inputs[{name,inProbe}], module, external,
    definition, evidence[{doc, quotes, quote_contexts, explanation,
                          verified, status, signature, quote_details}]
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

__all__ = ["Bundle", "Node", "Evidence", "load_export", "ExportError"]


class ExportError(RuntimeError):
    """The file is not a recognisable pg-bench export."""


@dataclass
class Evidence:
    doc: str = ""
    quotes: list[str] = field(default_factory=list)
    quote_contexts: dict[str, dict[str, str]] = field(default_factory=dict)
    quote_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    explanation: str = ""
    verified: bool | None = None
    status: str = "unverified"
    signature: str = ""

    @property
    def is_derived(self) -> bool:
        return self.status == "derived"

    @classmethod
    def from_json(cls, raw: dict) -> Evidence:
        return cls(
            doc=raw.get("doc") or "",
            quotes=list(raw.get("quotes") or []),
            quote_contexts=dict(raw.get("quote_contexts") or {}),
            quote_details=dict(raw.get("quote_details") or {}),
            explanation=raw.get("explanation") or "",
            verified=raw.get("verified"),
            status=raw.get("status") or "unverified",
            signature=raw.get("signature") or "",
        )


@dataclass
class Node:
    id: str
    kind: str = ""
    value: str = ""
    depth: int = 0
    inputs: list[str] = field(default_factory=list)
    module: str = ""
    external: bool = False
    definition: str = ""
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def local_name(self) -> str:
        return self.id.split(".", 1)[1] if "." in self.id else self.id

    @property
    def is_derived(self) -> bool:
        return self.kind in ("theorem", "derived") or any(e.is_derived for e in self.evidence)

    @property
    def is_grounded(self) -> bool:
        """Carries at least one document-backed, verified quote."""
        return any(e.quotes and e.verified for e in self.evidence)

    @property
    def evidence_status(self) -> str:
        if not self.evidence:
            return "none"
        for wanted in ("unverified", "manual", "verified", "derived"):
            for e in self.evidence:
                if e.status == wanted:
                    return wanted
        return self.evidence[0].status

    @classmethod
    def from_json(cls, raw: dict) -> Node:
        inputs = []
        for inp in raw.get("inputs") or []:
            inputs.append(inp if isinstance(inp, str) else str(inp.get("name", "")))
        node_id = str(raw.get("id", ""))
        return cls(
            id=node_id,
            kind=str(raw.get("kind") or ""),
            value=str(raw.get("value") if raw.get("value") is not None else ""),
            depth=int(raw.get("depth") or 0),
            inputs=[i for i in inputs if i],
            module=str(raw.get("module") or (node_id.split(".")[0] if "." in node_id else "")),
            external=bool(raw.get("external")),
            definition=str(raw.get("definition") or ""),
            evidence=[Evidence.from_json(e) for e in (raw.get("evidence") or []) if isinstance(e, dict)],
        )


@dataclass
class Bundle:
    """A parsed pg-bench export."""

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)
    taint_sources: set[str] = field(default_factory=set)
    tainted: set[str] = field(default_factory=set)
    taint_reasons: dict[str, str] = field(default_factory=dict)
    source_path: Path | None = None
    globals_found: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.nodes)

    def get(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def modules(self) -> list[str]:
        return sorted({n.module for n in self.nodes.values() if n.module})

    def in_module(self, module: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.module == module]

    def find(self, pattern: str, module: str | None = None) -> list[Node]:
        rx = re.compile(pattern, re.IGNORECASE)
        return sorted(
            (
                n
                for n in self.nodes.values()
                if rx.search(n.id) and (module is None or n.module == module)
            ),
            key=lambda n: n.id,
        )

    def consumers(self, node_id: str) -> list[str]:
        return sorted(n.id for n in self.nodes.values() if node_id in n.inputs)

    def is_tainted(self, node_id: str) -> bool:
        return node_id in self.tainted


# ---------------------------------------------------------------- parsing


def _scan_literal(text: str, start: int) -> str:
    """Return the JSON literal beginning at ``start`` ('[' or '{').

    String-aware bracket matcher — more robust than a lazy regex when a
    quote inside the data contains brackets or a ``];`` sequence.
    """
    opener = text[start]
    closer = {"[": "]", "{": "}"}[opener]
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ExportError(f"unterminated JSON literal starting at offset {start}")


def _extract_global(text: str, name: str) -> Any | None:
    """Pull ``const NAME = <json>;`` out of a viz HTML / data.js blob."""
    m = re.search(rf"(?:const|var|let)\s+{re.escape(name)}\s*=\s*", text)
    if not m:
        return None
    idx = m.end()
    while idx < len(text) and text[idx] in " \t\r\n":
        idx += 1
    if idx >= len(text) or text[idx] not in "[{":
        return None
    literal = _scan_literal(text, idx)
    try:
        return json.loads(literal)
    except json.JSONDecodeError as exc:  # pragma: no cover - malformed export
        raise ExportError(f"{name} is not valid JSON: {exc}") from exc


def _normalise(payload: dict[str, Any], path: Path | None) -> Bundle:
    data = payload.get("DATA") or []
    structure = payload.get("STRUCTURE_DATA") or []
    layers = payload.get("LAYERS") or {}
    taint = payload.get("TAINT_DATA") or {}

    if not isinstance(data, list):
        raise ExportError("DATA is not a list")

    nodes: dict[str, Node] = {}
    # STRUCTURE_DATA first: it carries the richer evidence for nodes that
    # appear in both. DATA then overrides/adds view-level nodes, but never
    # downgrades evidence we already have.
    for raw in structure:
        if isinstance(raw, dict) and raw.get("id"):
            node = Node.from_json(raw)
            nodes[node.id] = node
    for raw in data:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        node = Node.from_json(raw)
        existing = nodes.get(node.id)
        if existing is not None:
            if not node.evidence and existing.evidence:
                node.evidence = existing.evidence
            if not node.definition and existing.definition:
                node.definition = existing.definition
            if not node.inputs and existing.inputs:
                node.inputs = existing.inputs
        nodes[node.id] = node

    if not nodes:
        raise ExportError("export contains no nodes (DATA and STRUCTURE_DATA are empty)")

    edges = [e for e in (layers.get("edges") or []) if isinstance(e, dict)]
    # Layer edges can reveal inputs the node dicts omitted.
    for edge in edges:
        src, tgt = edge.get("source"), edge.get("target")
        if src and tgt and tgt in nodes and src not in nodes[tgt].inputs:
            if edge.get("type") in (None, "", "uses", "pulls", "declares", "input"):
                nodes[tgt].inputs.append(str(src))

    found = [k for k in ("DATA", "STRUCTURE_DATA", "LAYERS", "TAINT_DATA") if payload.get(k)]
    return Bundle(
        nodes=nodes,
        edges=edges,
        taint_sources=set(taint.get("sources") or []),
        tainted=set(taint.get("tainted") or []),
        taint_reasons=dict(taint.get("reasons") or {}),
        source_path=path,
        globals_found=found,
    )


def load_export(path: str | Path) -> Bundle:
    """Load a pg-bench export from .html, .js or .json."""
    p = Path(path)
    if not p.exists():
        raise ExportError(f"export not found: {p}")
    text = p.read_text(encoding="utf-8", errors="replace")

    if p.suffix.lower() == ".json":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExportError(f"{p} is not valid JSON: {exc}") from exc
        if isinstance(raw, list):
            return _normalise({"DATA": raw}, p)
        if isinstance(raw, dict):
            # Accept both the SCREAMING and lower-case spellings.
            payload = {
                key: raw.get(key, raw.get(key.lower()))
                for key in ("DATA", "STRUCTURE_DATA", "LAYERS", "TAINT_DATA")
            }
            if not any(payload.values()):
                raise ExportError(
                    "JSON has none of DATA / STRUCTURE_DATA / LAYERS / TAINT_DATA — "
                    "is this a pg-bench export?"
                )
            return _normalise(payload, p)
        raise ExportError("JSON root must be a list of nodes or an object of globals")

    payload = {name: _extract_global(text, name) for name in ("DATA", "STRUCTURE_DATA", "LAYERS", "TAINT_DATA")}
    if not any(v for v in payload.values()):
        raise ExportError(
            f"no pg-bench globals found in {p}. Expected `const DATA = [...]` — "
            "produce one with: pg eval '(fmt \"viz\" ...)' > export.html"
        )
    return _normalise(payload, p)


def iter_evidence(nodes: Iterable[Node]):
    """Yield (node, evidence, quote) for every quote carried by the nodes."""
    for node in nodes:
        for ev in node.evidence:
            for quote in ev.quotes:
                yield node, ev, quote


def load_exports(paths: list[str | Path]) -> Bundle:
    """Load and merge several pg-bench exports into one bundle.

    Stage 3 usually hands over more than one view — one per lens, or a
    dossier export plus a verdict export. Later files add nodes and fill in
    gaps; they never blank out evidence an earlier file supplied.
    """
    if not paths:
        raise ExportError("no export files given")
    merged: Bundle | None = None
    for p in paths:
        bundle = load_export(p)
        if merged is None:
            merged = bundle
            continue
        for node_id, node in bundle.nodes.items():
            existing = merged.nodes.get(node_id)
            if existing is None:
                merged.nodes[node_id] = node
                continue
            if not existing.evidence and node.evidence:
                existing.evidence = node.evidence
            if not existing.definition and node.definition:
                existing.definition = node.definition
            for inp in node.inputs:
                if inp not in existing.inputs:
                    existing.inputs.append(inp)
        merged.edges.extend(bundle.edges)
        merged.taint_sources |= bundle.taint_sources
        merged.tainted |= bundle.tainted
        merged.taint_reasons.update(bundle.taint_reasons)
        for g in bundle.globals_found:
            if g not in merged.globals_found:
                merged.globals_found.append(g)
    assert merged is not None
    return merged
