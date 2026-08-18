"""Backtrace: from a claim, down its derivation, out to the source documents.

Two products:

* :func:`closure` — every node a claim rests on, transitively.
* :func:`ledger` — the citable evidence under those nodes, each entry keyed
  ``E1``, ``E2``, … The keys are what the model is allowed to cite, and what
  the verifier checks its sentences against.

An entry keeps the whole chain: sentence -> key -> parseltongue node ->
document + verbatim quote -> external record (PMID / NCT / UniProt).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .bundle import Bundle, Node

__all__ = ["Citation", "Ledger", "closure", "ledger"]

_PMID_RX = re.compile(r"\bPMID[:\s]*([0-9]{5,9})\b", re.IGNORECASE)
_PMID_LOOSE_RX = re.compile(r"\bpaper[-_]([0-9]{5,9})\b", re.IGNORECASE)
_NCT_RX = re.compile(r"\b(NCT[0-9]{8})\b", re.IGNORECASE)
_UNIPROT_RX = re.compile(r"\b([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\b")
_DOI_RX = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE)
# An aggregate counter line, e.g. "TRIALS recruiting=1" or "PUBMED_HITS crc=5".
_COUNTER_RX = re.compile(r"^[A-Z][A-Z_]+\s+[a-z_]+=")


@dataclass
class Citation:
    """One citable piece of evidence under a claim."""

    key: str
    node_id: str
    node_kind: str
    node_value: str
    doc: str
    quote: str
    explanation: str = ""
    status: str = "unverified"
    verified: bool | None = None
    context_before: str = ""
    context_after: str = ""
    source_type: str = "document"  # pmid | nct | uniprot | doi | document
    source_id: str = ""
    url: str = ""
    hops: int = 0  # derivation distance from the claim being defended
    resolved: bool | None = None  # filled in by resolve.py
    resolved_title: str = ""
    resolve_note: str = ""

    @property
    def citation_line(self) -> str:
        where = f"{self.source_type}:{self.source_id}" if self.source_id else f"doc:{self.doc}"
        return f"[{self.key}] {where} — {self.quote}"

    def to_json(self) -> dict:
        return {
            "key": self.key,
            "node": self.node_id,
            "node_kind": self.node_kind,
            "node_value": self.node_value,
            "doc": self.doc,
            "quote": self.quote,
            "explanation": self.explanation,
            "evidence_status": self.status,
            "quote_verified": self.verified,
            "context": {"before": self.context_before, "after": self.context_after},
            "source": {"type": self.source_type, "id": self.source_id, "url": self.url},
            "derivation_hops": self.hops,
            "resolution": {
                "checked": self.resolved is not None,
                "resolves": self.resolved,
                "title": self.resolved_title,
                "note": self.resolve_note,
            },
        }


@dataclass
class Ledger:
    citations: list[Citation] = field(default_factory=list)
    chain: list[tuple[str, int]] = field(default_factory=list)  # node id, hops

    def __len__(self) -> int:
        return len(self.citations)

    def __iter__(self):
        return iter(self.citations)

    def by_key(self, key: str) -> Citation | None:
        for c in self.citations:
            if c.key.lower() == key.lower():
                return c
        return None

    @property
    def keys(self) -> list[str]:
        return [c.key for c in self.citations]

    def rendered(self) -> str:
        return "\n".join(c.citation_line for c in self.citations)


def closure(bundle: Bundle, roots: list[str], max_hops: int = 12) -> list[tuple[Node, int]]:
    """Every node reachable upstream from ``roots``, with its hop distance."""
    seen: dict[str, int] = {}
    frontier = [(r, 0) for r in roots if r in bundle.nodes]
    while frontier:
        node_id, hops = frontier.pop(0)
        if node_id in seen and seen[node_id] <= hops:
            continue
        seen[node_id] = hops
        if hops >= max_hops:
            continue
        node = bundle.nodes.get(node_id)
        if node is None:
            continue
        for parent in node.inputs:
            if parent in bundle.nodes:
                frontier.append((parent, hops + 1))
    return sorted(
        ((bundle.nodes[nid], h) for nid, h in seen.items()),
        key=lambda pair: (pair[1], pair[0].id),
    )


def _classify(quote: str, node: Node, doc: str, explanation: str, before: str, after: str) -> tuple[str, str, str]:
    """Work out which external record a quote belongs to.

    Order matters. The explanation and the node name are authored per fact,
    so they identify the record exactly. The surrounding document context is
    only consulted for quotes that are themselves record lines — an
    aggregate counter such as ``TRIALS recruiting=1`` sits next to arbitrary
    trial records in the dossier and must not inherit one of their ids.
    """
    primary = [explanation, node.id, quote]
    is_counter = bool(_COUNTER_RX.match((quote or "").strip()))
    haystacks = primary if is_counter else [*primary, before, after]

    for text in haystacks:
        m = _NCT_RX.search(text or "")
        if m:
            nct = m.group(1).upper()
            return "nct", nct, f"https://clinicaltrials.gov/study/{nct}"

    for text in haystacks:
        m = _PMID_RX.search(text or "") or _PMID_LOOSE_RX.search(text or "")
        if m:
            pmid = m.group(1)
            return "pmid", pmid, f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    for text in haystacks:
        m = _DOI_RX.search(text or "")
        if m:
            doi = m.group(1).rstrip(".")
            return "doi", doi, f"https://doi.org/{doi}"

    if "uniprot" in (doc or "").lower() or "uniprot" in (explanation or "").lower():
        for text in [*primary, before, after]:
            m = _UNIPROT_RX.search(text or "")
            if m:
                return "uniprot", m.group(1), f"https://www.uniprot.org/uniprotkb/{m.group(1)}"
        return "uniprot", "", ""

    return "document", "", ""


def ledger(
    bundle: Bundle,
    roots: list[str],
    secondary_roots: list[str] | None = None,
    max_hops: int = 12,
    limit: int = 40,
    prefix: str = "E",
    secondary_offset: int = 50,
) -> Ledger:
    """Build the citable evidence ledger under ``roots``.

    Ordering is derivation-proximal first: evidence closest to the claim
    gets the lowest key, so a model that cites early keys cites the
    evidence the verdict actually turned on.
    """
    chain = closure(bundle, roots, max_hops=max_hops)
    if secondary_roots:
        primary_ids = {n.id for n, _ in chain}
        extra = [
            (n, h + secondary_offset)
            for n, h in closure(bundle, secondary_roots, max_hops=max_hops)
            if n.id not in primary_ids
        ]
        chain = sorted([*chain, *extra], key=lambda pair: (pair[1], pair[0].id))
    out = Ledger(chain=[(n.id, h) for n, h in chain])
    seen_quotes: set[tuple[str, str]] = set()
    index = 0

    for node, hops in chain:
        for ev in node.evidence:
            if not ev.quotes:
                continue
            for quote in ev.quotes:
                dedup = (ev.doc, quote)
                if dedup in seen_quotes:
                    continue
                seen_quotes.add(dedup)
                ctx = ev.quote_contexts.get(quote, {})
                before, after = ctx.get("before", ""), ctx.get("after", "")
                src_type, src_id, url = _classify(quote, node, ev.doc, ev.explanation, before, after)
                index += 1
                out.citations.append(
                    Citation(
                        key=f"{prefix}{index}",
                        node_id=node.id,
                        node_kind=node.kind,
                        node_value=node.value,
                        doc=ev.doc,
                        quote=quote,
                        explanation=ev.explanation,
                        status=ev.status,
                        verified=ev.verified,
                        context_before=before,
                        context_after=after,
                        source_type=src_type,
                        source_id=src_id,
                        url=url,
                        hops=hops,
                    )
                )
                if len(out.citations) >= limit:
                    return out
    return out


def derivation_path(bundle: Bundle, claim_id: str, evidence_node_id: str, max_hops: int = 12) -> list[str]:
    """Shortest input-chain from a claim down to the node carrying evidence."""
    if claim_id not in bundle.nodes:
        return []
    queue: list[list[str]] = [[claim_id]]
    seen = {claim_id}
    while queue:
        path = queue.pop(0)
        if path[-1] == evidence_node_id:
            return path
        if len(path) > max_hops:
            continue
        node = bundle.nodes.get(path[-1])
        if node is None:
            continue
        for parent in node.inputs:
            if parent in seen or parent not in bundle.nodes:
                continue
            seen.add(parent)
            queue.append([*path, parent])
    return []
