"""Stage 5 — does the cited record say what the dossier claims it says?

Resolving an identifier is the weakest possible check: it proves the record
exists, not that it supports the claim built on it. This stage grades four
things per citation, and every grade is mechanical:

* **resolution** — the registry returns a record for the id;
* **title fidelity** — the quoted title still matches the registry title;
* **subject role** — where the attributed gene appears: title, abstract, or
  nowhere. Appearing in the title is subject-level evidence; appearing only in
  the abstract is a mention, which is a much weaker claim than the dossier
  usually makes of it;
* **indication role** — the same, for the disease.

Plus a retraction check, because a retracted paper resolves perfectly well.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from ..objections.backtrace import Citation
from .registry import Record, Registry, normalise_title

__all__ = ["CitationCheck", "check_citations", "STATUS_ORDER", "DISEASE_TERMS"]

STATUS_ORDER = [
    "unresolved",
    "retracted",
    "off-target",
    "title-drift",
    "weak-attribution",
    "sound",
    "not-checked",
]

DISEASE_TERMS = ("colorectal", "colon cancer", "colonic", "rectal", "rectum", "crc", "bowel cancer")

_TITLE_PREFIX = re.compile(r"^\s*TITLE:\s*", re.IGNORECASE)


def _role(terms: list[str], record: Record) -> str:
    """Where any of a gene's names appears in the record: title, abstract, nowhere.

    Symbols are not how papers refer to targets — ERBB2 shows up as HER2 or as
    "human epidermal growth factor receptor 2". The alias set comes from the
    reviewed UniProt entry, so this is resolution, not a keyword guess.
    """
    needles = [t.lower() for t in terms if t and len(t) > 2]
    if not needles:
        return "unknown"
    title = (record.title or "").lower()
    if any(re.search(rf"\b{re.escape(n)}\b", title) for n in needles):
        return "title"
    haystack = " ".join([record.abstract or "", " ".join(record.conditions), record.note or ""]).lower()
    if any(re.search(rf"\b{re.escape(n)}\b", haystack) for n in needles):
        return "abstract"
    return "absent"


def _indication_role(record: Record) -> str:
    title = (record.title or "").lower()
    body = " ".join([record.abstract or "", " ".join(record.conditions)]).lower()
    for term in DISEASE_TERMS:
        if term in title:
            return "title"
    for term in DISEASE_TERMS:
        if term in body:
            return "abstract"
    return "absent"


@dataclass
class CitationCheck:
    """One citation, graded against its registry record."""

    key: str
    node_id: str
    target: str
    source_type: str
    source_id: str
    url: str
    quote: str
    doc: str
    resolves: bool | None = None
    registry_title: str = ""
    title_similarity: float | None = None
    title_verdict: str = "not-applicable"  # match | drift | not-applicable
    gene_role: str = "unknown"  # title | abstract | absent | unknown
    indication_role: str = "unknown"
    retracted: bool = False
    publication_types: list[str] = field(default_factory=list)
    status: str = "not-checked"
    reasons: list[str] = field(default_factory=list)

    @property
    def sound(self) -> bool:
        return self.status == "sound"

    def to_json(self) -> dict:
        return {
            "key": self.key,
            "node": self.node_id,
            "target": self.target,
            "source": {"type": self.source_type, "id": self.source_id, "url": self.url},
            "quote": self.quote,
            "doc": self.doc,
            "resolves": self.resolves,
            "registry_title": self.registry_title,
            "title": {"verdict": self.title_verdict, "similarity": self.title_similarity},
            "gene_role": self.gene_role,
            "indication_role": self.indication_role,
            "retracted": self.retracted,
            "publication_types": self.publication_types,
            "status": self.status,
            "reasons": self.reasons,
        }


def _quoted_title(quote: str) -> str | None:
    """The dossier quotes a record title as ``TITLE: …``; anything else is a counter."""
    if not _TITLE_PREFIX.match(quote or ""):
        return None
    return _TITLE_PREFIX.sub("", quote).strip()


def _grade(check: CitationCheck, record: Record, gene: str, aliases: list[str] | None = None) -> None:
    if record.exists is None:
        check.status = "not-checked"
        check.reasons.append(record.note or "registry not consulted")
        return

    check.resolves = record.exists
    check.registry_title = record.title
    check.publication_types = record.publication_types
    check.retracted = record.retracted

    if not record.exists:
        check.status = "unresolved"
        check.reasons.append(record.note or "no record for this identifier")
        return

    quoted = _quoted_title(check.quote)
    if quoted and record.title:
        ratio = difflib.SequenceMatcher(
            None, normalise_title(quoted), normalise_title(record.title)
        ).ratio()
        check.title_similarity = round(ratio, 3)
        # The dossier truncates long titles, so a prefix match counts as fidelity.
        prefix_ok = normalise_title(record.title).startswith(normalise_title(quoted)[:60])
        check.title_verdict = "match" if (ratio >= 0.88 or prefix_ok) else "drift"

    check.gene_role = _role(aliases or ([gene] if gene else []), record) if gene else "unknown"
    # A protein entry is not indexed to a disease and is not expected to be:
    # asking a UniProt record about colorectal cancer is a category error.
    check.indication_role = (
        "not-applicable" if check.source_type == "uniprot" else _indication_role(record)
    )

    if check.retracted:
        check.status = "retracted"
        check.reasons.append(f"publication types include {', '.join(record.publication_types)}")
        return
    if check.gene_role == "absent":
        if check.source_type == "nct" and check.indication_role in ("title", "abstract"):
            check.status = "weak-attribution"
            check.reasons.append(
                f"trial record names no {gene} under any of its UniProt names — it was matched "
                "to this target by free-text search, and only the indication lines up"
            )
            return
        check.status = "off-target"
        check.reasons.append(f"{gene} appears nowhere in the registry record, under any of its names")
        return
    if check.title_verdict == "drift":
        check.status = "title-drift"
        check.reasons.append(
            f"quoted title and registry title agree only {check.title_similarity:.0%}"
        )
        return
    if check.gene_role == "abstract":
        # The record mentions the gene without being about it. The dossier
        # counts this as support for the gene; that is a weaker claim than the
        # record licenses, and stage 6 turns the difference into a diff.
        tail = (
            "and the record names no colorectal indication either"
            if check.indication_role in ("absent", "unknown")
            else "the record is indexed to a colorectal indication, but about something else"
        )
        check.status = "weak-attribution"
        check.reasons.append(
            f"{gene} appears only in the abstract, not in the title, so it is not the "
            f"subject of this record — {tail}"
        )
        return
    if check.indication_role == "absent":
        check.status = "weak-attribution"
        check.reasons.append(
            "record names no colorectal indication, so it does not speak to this disease"
        )
        return
    if check.gene_role == "unknown" and check.source_type != "uniprot":
        check.status = "weak-attribution"
        check.reasons.append("citation is not attributed to any target in the panel")
        return

    check.status = "sound"
    return


def target_of(node_id: str, known: list[str]) -> str:
    """Which target a node belongs to, by namespace segment."""
    parts = [p.lower() for p in node_id.split(".")]
    for symbol in known:
        if symbol.lower() in parts:
            return symbol
    return ""


def check_citations(
    citations: list[Citation],
    targets: list[str],
    registry: Registry,
) -> list[CitationCheck]:
    """Grade every citation that carries an external identifier."""
    checks: list[CitationCheck] = []
    with_ids = [c for c in citations if c.source_id]

    alias_cache: dict[str, list[str]] = {}
    pmids = sorted({c.source_id for c in with_ids if c.source_type == "pmid"})
    pubmed_records = registry.pubmed(pmids) if pmids else {}

    for citation in with_ids:
        gene = target_of(citation.node_id, targets)
        check = CitationCheck(
            key=citation.key,
            node_id=citation.node_id,
            target=gene,
            source_type=citation.source_type,
            source_id=citation.source_id,
            url=citation.url,
            quote=citation.quote,
            doc=citation.doc,
        )
        aliases = alias_cache.setdefault(gene, registry.aliases(gene) if gene else [])
        if citation.source_type == "pmid":
            record = pubmed_records.get(citation.source_id, Record("pmid", citation.source_id))
        elif citation.source_type == "nct":
            record = registry.trial(citation.source_id)
        elif citation.source_type == "uniprot":
            record = registry.protein(citation.source_id)
        else:
            record = Record(citation.source_type, citation.source_id, exists=None, note="no registry adapter")
        _grade(check, record, gene, aliases)
        checks.append(check)

    return checks
