"""Resolving check: does the cited record actually exist?

A citation that names PMID 12345678 is worthless if that PMID does not
resolve, or resolves to something unrelated. Every citation carrying an
external id is checked against the issuing registry — PubMed via NCBI
E-utilities, trials via ClinicalTrials.gov v2, proteins via UniProt — and
the answer is cached on disk so repeat runs cost nothing.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .backtrace import Citation

__all__ = ["resolve_citations", "ResolveCache"]

_UA = {"User-Agent": "objection-forge/0.1 (research triage)"}
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"
UNIPROT = "https://rest.uniprot.org/uniprotkb"


class ResolveCache:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.data: dict[str, dict] = {}
        if path and path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.data = {}

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def put(self, key: str, value: dict) -> None:
        self.data[key] = value

    def flush(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        except OSError:
            pass


def _get_json(url: str, timeout: int = 30) -> dict | None:
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"__status__": 404}
        return {"__status__": exc.code}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def _resolve_pmids(pmids: list[str], cache: ResolveCache) -> dict[str, dict]:
    out: dict[str, dict] = {}
    todo = []
    for pmid in pmids:
        hit = cache.get(f"pmid:{pmid}")
        if hit is not None:
            out[pmid] = hit
        else:
            todo.append(pmid)

    for i in range(0, len(todo), 50):
        batch = todo[i : i + 50]
        url = f"{ESUMMARY}?{urllib.parse.urlencode({'db': 'pubmed', 'id': ','.join(batch), 'retmode': 'json'})}"
        data = _get_json(url)
        if data is None or "__status__" in data:
            note = "registry unreachable" if data is None else f"HTTP {data['__status__']}"
            for pmid in batch:
                out[pmid] = {"resolves": None, "title": "", "note": note}
            continue
        result = data.get("result", {})
        for pmid in batch:
            rec = result.get(pmid)
            if not rec or rec.get("error"):
                entry = {"resolves": False, "title": "", "note": "not found in PubMed"}
            else:
                entry = {
                    "resolves": True,
                    "title": rec.get("title", ""),
                    "note": f"{rec.get('source', '')} {rec.get('pubdate', '')}".strip(),
                }
            out[pmid] = entry
            cache.put(f"pmid:{pmid}", entry)
        time.sleep(0.34)  # NCBI: 3 req/s without a key
    return out


def _resolve_nct(nct: str, cache: ResolveCache) -> dict:
    hit = cache.get(f"nct:{nct}")
    if hit is not None:
        return hit
    data = _get_json(f"{CTGOV}/{nct}?fields=NCTId|BriefTitle|OverallStatus|Phase")
    if data is None:
        return {"resolves": None, "title": "", "note": "registry unreachable"}
    if "__status__" in data:
        entry = (
            {"resolves": False, "title": "", "note": "not found on ClinicalTrials.gov"}
            if data["__status__"] == 404
            else {"resolves": None, "title": "", "note": f"HTTP {data['__status__']}"}
        )
    else:
        proto = data.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status = proto.get("statusModule", {}).get("overallStatus", "")
        entry = {
            "resolves": bool(ident.get("nctId")),
            "title": ident.get("briefTitle", ""),
            "note": status,
        }
    if entry["resolves"] is not None:
        cache.put(f"nct:{nct}", entry)
    return entry


def _resolve_uniprot(acc: str, cache: ResolveCache) -> dict:
    hit = cache.get(f"uniprot:{acc}")
    if hit is not None:
        return hit
    data = _get_json(f"{UNIPROT}/{acc}.json?fields=id,protein_name")
    if data is None:
        return {"resolves": None, "title": "", "note": "registry unreachable"}
    if "__status__" in data:
        entry = {"resolves": False, "title": "", "note": f"HTTP {data['__status__']}"}
    else:
        name = (
            data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}) or {}
        ).get("value", "")
        entry = {"resolves": True, "title": name, "note": data.get("uniProtkbId", "")}
    if entry["resolves"] is not None:
        cache.put(f"uniprot:{acc}", entry)
    return entry


def resolve_citations(citations: list[Citation], cache_path: Path | None = None, offline: bool = False) -> dict:
    """Check every external id in place. Returns a summary dict."""
    summary = {"checked": 0, "resolved": 0, "unresolved": 0, "unknown": 0, "skipped": 0}
    if offline:
        summary["skipped"] = sum(1 for c in citations if c.source_id)
        for c in citations:
            if c.source_id:
                c.resolve_note = "not checked (offline)"
        return summary

    cache = ResolveCache(cache_path)
    pmids = sorted({c.source_id for c in citations if c.source_type == "pmid" and c.source_id})
    pmid_results = _resolve_pmids(pmids, cache) if pmids else {}

    for c in citations:
        if not c.source_id:
            continue
        if c.source_type == "pmid":
            entry = pmid_results.get(c.source_id, {"resolves": None, "title": "", "note": "not queried"})
        elif c.source_type == "nct":
            entry = _resolve_nct(c.source_id, cache)
        elif c.source_type == "uniprot":
            entry = _resolve_uniprot(c.source_id, cache)
        else:
            continue
        c.resolved = entry.get("resolves")
        c.resolved_title = entry.get("title", "")
        c.resolve_note = entry.get("note", "")
        summary["checked"] += 1
        if c.resolved is True:
            summary["resolved"] += 1
        elif c.resolved is False:
            summary["unresolved"] += 1
        else:
            summary["unknown"] += 1

    cache.flush()
    return summary
