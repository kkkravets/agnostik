"""Registry access for citation checking — PubMed, ClinicalTrials.gov, UniProt.

Every fetch is cached on disk. Records are returned whole (title, abstract,
publication types) because the check that matters is not "does this id exist"
but "does the record say what the dossier claims it says".
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Record", "Registry", "RegistryError"]

_UA = {"User-Agent": "agnostik-citecheck/0.1 (research triage)"}
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"
UNIPROT = "https://rest.uniprot.org/uniprotkb"

RETRACTION_TYPES = {
    "Retracted Publication",
    "Retraction of Publication",
    "Expression of Concern",
}


class RegistryError(RuntimeError):
    pass


@dataclass
class Record:
    """What a registry says about one identifier."""

    source_type: str
    source_id: str
    exists: bool | None = None  # None = could not be determined
    title: str = ""
    abstract: str = ""
    journal: str = ""
    year: str = ""
    publication_types: list[str] = field(default_factory=list)
    status: str = ""  # trials: recruitment status
    phases: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def retracted(self) -> bool:
        return any(t in RETRACTION_TYPES for t in self.publication_types)

    @property
    def searchable_text(self) -> str:
        return " ".join(
            [self.title, self.abstract, " ".join(self.conditions), self.journal]
        ).lower()

    def to_json(self) -> dict:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "exists": self.exists,
            "title": self.title,
            "abstract": self.abstract,
            "journal": self.journal,
            "year": self.year,
            "publication_types": self.publication_types,
            "status": self.status,
            "phases": self.phases,
            "conditions": self.conditions,
            "note": self.note,
        }

    @classmethod
    def from_json(cls, raw: dict) -> Record:
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


class Registry:
    """Cached read-only access to the three registries this pipeline cites."""

    def __init__(self, cache_path: Path | None = None, offline: bool = False, timeout: int = 45) -> None:
        self.cache_path = cache_path
        self.offline = offline
        self.timeout = timeout
        self.cache: dict[str, dict] = {}
        self.fetches = 0
        if cache_path and cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.cache = {}

    # ---------------------------------------------------------------- cache

    def _cached(self, key: str) -> Record | None:
        raw = self.cache.get(key)
        return Record.from_json(raw) if raw else None

    def _store(self, key: str, record: Record) -> None:
        if record.exists is not None:
            self.cache[key] = record.to_json()

    def flush(self) -> None:
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, indent=1), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------- fetching

    def _open(self, url: str) -> tuple[int, bytes | None]:
        req = urllib.request.Request(url, headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except (urllib.error.URLError, TimeoutError):
            return 0, None

    def pubmed(self, pmids: list[str]) -> dict[str, Record]:
        """Full PubMed records, batched. Abstracts included — the check needs them."""
        out: dict[str, Record] = {}
        todo: list[str] = []
        for pmid in pmids:
            hit = self._cached(f"pmid:{pmid}")
            if hit is not None:
                out[pmid] = hit
            else:
                todo.append(pmid)

        if self.offline:
            for pmid in todo:
                out[pmid] = Record("pmid", pmid, exists=None, note="offline: not checked")
            return out

        for i in range(0, len(todo), 40):
            batch = todo[i : i + 40]
            query = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(batch), "retmode": "xml"})
            code, body = self._open(f"{EFETCH}?{query}")
            self.fetches += 1
            if code != 200 or body is None:
                for pmid in batch:
                    out[pmid] = Record("pmid", pmid, exists=None, note=f"PubMed unreachable (HTTP {code})")
                continue
            try:
                root = ET.fromstring(body)
            except ET.ParseError as exc:
                for pmid in batch:
                    out[pmid] = Record("pmid", pmid, exists=None, note=f"malformed PubMed XML: {exc}")
                continue

            found: set[str] = set()
            for article in root.findall(".//PubmedArticle"):
                pmid = _text(article.find(".//PMID"))
                if not pmid:
                    continue
                found.add(pmid)
                abstract = " ".join(
                    _text(part) for part in article.findall(".//Abstract/AbstractText")
                ).strip()
                record = Record(
                    source_type="pmid",
                    source_id=pmid,
                    exists=True,
                    title=_text(article.find(".//ArticleTitle")),
                    abstract=abstract,
                    journal=_text(article.find(".//Journal/Title")),
                    year=_text(article.find(".//JournalIssue/PubDate/Year")),
                    publication_types=[
                        _text(t) for t in article.findall(".//PublicationTypeList/PublicationType")
                    ],
                )
                out[pmid] = record
                self._store(f"pmid:{pmid}", record)
            for pmid in batch:
                if pmid not in found:
                    record = Record("pmid", pmid, exists=False, note="no record returned by PubMed")
                    out[pmid] = record
                    self._store(f"pmid:{pmid}", record)
            time.sleep(0.34)  # NCBI allows 3 requests/second without a key
        return out

    def trial(self, nct: str) -> Record:
        hit = self._cached(f"nct:{nct}")
        if hit is not None:
            return hit
        if self.offline:
            return Record("nct", nct, exists=None, note="offline: not checked")

        fields = "NCTId|BriefTitle|OverallStatus|Phase|Condition|BriefSummary"
        code, body = self._open(f"{CTGOV}/{nct}?fields={urllib.parse.quote(fields)}")
        self.fetches += 1
        if code == 404:
            record = Record("nct", nct, exists=False, note="not found on ClinicalTrials.gov")
        elif code != 200 or body is None:
            return Record("nct", nct, exists=None, note=f"registry unreachable (HTTP {code})")
        else:
            data = json.loads(body.decode())
            proto = data.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            record = Record(
                source_type="nct",
                source_id=nct,
                exists=bool(ident.get("nctId")),
                title=ident.get("briefTitle", ""),
                abstract=(proto.get("descriptionModule", {}) or {}).get("briefSummary", ""),
                status=proto.get("statusModule", {}).get("overallStatus", ""),
                phases=proto.get("designModule", {}).get("phases", []),
                conditions=proto.get("conditionsModule", {}).get("conditions", []),
            )
        self._store(f"nct:{nct}", record)
        return record

    def protein(self, accession: str) -> Record:
        hit = self._cached(f"uniprot:{accession}")
        if hit is not None:
            return hit
        if self.offline:
            return Record("uniprot", accession, exists=None, note="offline: not checked")

        code, body = self._open(f"{UNIPROT}/{accession}.json?fields=id,protein_name,gene_names,ft_binding")
        self.fetches += 1
        if code == 404:
            record = Record("uniprot", accession, exists=False, note="not found in UniProt")
        elif code != 200 or body is None:
            return Record("uniprot", accession, exists=None, note=f"registry unreachable (HTTP {code})")
        else:
            data = json.loads(body.decode())
            genes = [
                g.get("geneName", {}).get("value", "")
                for g in data.get("genes", [])
                if g.get("geneName")
            ]
            binding = sum(1 for f in data.get("features", []) if f.get("type") == "Binding site")
            record = Record(
                source_type="uniprot",
                source_id=accession,
                exists=True,
                title=(
                    data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}) or {}
                ).get("value", ""),
                abstract=" ".join(genes),
                note=f"binding_sites={binding}",
                conditions=genes,
            )
        self._store(f"uniprot:{accession}", record)
        return record


def normalise_title(title: str) -> str:
    """Lowercase, strip punctuation and trailing periods — titles drift in transcription."""
    return re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower()).strip()


# Fallback aliases, used only when UniProt cannot be reached. Everything else
# is resolved from the reviewed UniProt entry so the alias set is data, not lore.
FALLBACK_ALIASES: dict[str, tuple[str, ...]] = {
    "EGFR": ("HER1", "ERBB1", "epidermal growth factor receptor"),
    "ERBB2": ("HER2", "HER-2", "NEU", "CD340", "human epidermal growth factor receptor 2"),
    "KRAS": ("KRAS2", "RASK2", "K-Ras", "Ki-Ras"),
    "MYC": ("c-Myc", "MYCC", "bHLHe39"),
    "WRN": ("RECQ3", "RECQL2", "Werner syndrome", "Werner helicase"),
    "PRMT5": ("JBP1", "HRMT1L5", "SKB1", "IBP72", "protein arginine methyltransferase 5"),
}


def _alias_strings(data: dict) -> list[str]:
    """Gene names, synonyms and every protein name UniProt lists for an entry."""
    out: list[str] = []
    for gene in data.get("genes", []):
        name = gene.get("geneName", {}).get("value")
        if name:
            out.append(name)
        out += [s.get("value", "") for s in gene.get("synonyms", []) if s.get("value")]
    desc = data.get("proteinDescription", {}) or {}
    blocks = [desc.get("recommendedName") or {}, *(desc.get("alternativeNames") or [])]
    for block in blocks:
        full = (block.get("fullName") or {}).get("value")
        if full:
            out.append(full)
        out += [s.get("value", "") for s in block.get("shortNames", []) if s.get("value")]
    return [o for o in out if o]


def _aliases_impl(self: Registry, symbol: str) -> list[str]:
    """Every name the reviewed human entry for ``symbol`` is known by."""
    key = f"alias:{symbol.upper()}"
    cached = self.cache.get(key)
    if cached is not None:
        return list(cached.get("aliases", []))

    aliases = {symbol}
    if not self.offline:
        query = urllib.parse.urlencode(
            {
                "query": f"gene_exact:{symbol} AND organism_id:9606 AND reviewed:true",
                "fields": "accession,gene_names,protein_name",
                "format": "json",
                "size": "1",
            }
        )
        code, body = self._open(f"https://rest.uniprot.org/uniprotkb/search?{query}")
        self.fetches += 1
        if code == 200 and body:
            try:
                results = json.loads(body.decode()).get("results", [])
            except json.JSONDecodeError:
                results = []
            if results:
                aliases.update(_alias_strings(results[0]))
                self.cache[key] = {"aliases": sorted(aliases)}
                return sorted(aliases)

    aliases.update(FALLBACK_ALIASES.get(symbol.upper(), ()))
    return sorted(aliases)


Registry.aliases = _aliases_impl  # type: ignore[attr-defined]
