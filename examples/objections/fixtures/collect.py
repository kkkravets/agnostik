#!/usr/bin/env python3
"""Collect raw ClawBio evidence for the 6 hardcoded CRC targets.

STAND-IN for pipeline stages 1-3. Stage 4 (objection generation) is the
deliverable in this repo; this script only exists so stage 4 has a real,
network-derived input to develop against. Replace with the team's own
stage 1-3 output when it lands.

Writes:
  fixtures/raw/<GENE>.json   raw records (pubmed / trials / target summary)
  fixtures/docs/*.txt        source documents that .pltg quotes verbatim
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAWBIO = HERE.parent.parent / "clawbio-src" / "skills"
sys.path.insert(0, str(CLAWBIO / "pubmed-summariser"))
sys.path.insert(0, str(CLAWBIO / "clinical-trial-finder"))

from pubmed_api import fetch_papers  # noqa: E402

TARGETS = ["EGFR", "ERBB2", "KRAS", "MYC", "WRN", "PRMT5"]
DISEASE = "colorectal cancer"

QUERIES = {
    "crc": '{gene} AND "colorectal cancer"',
    "in_vitro": '{gene} AND "colorectal" AND (in vitro OR "cell line" OR organoid)',
    "in_vivo": '{gene} AND "colorectal" AND (xenograft OR "mouse model" OR in vivo)',
    "druggability": '{gene} AND (inhibitor OR "small molecule" OR degrader OR antibody)',
}

CTGOV = "https://clinicaltrials.gov/api/v2/studies"


def fetch_trials(gene: str, max_results: int = 10) -> list[dict]:
    """ClinicalTrials.gov API v2 — CRC-scoped trials mentioning the gene."""
    params = {
        "query.cond": DISEASE,
        "query.term": gene,
        "pageSize": str(max_results),
        "fields": "NCTId|BriefTitle|OverallStatus|Phase|StudyType|Condition|InterventionName|BriefSummary|StartDate",
    }
    url = f"{CTGOV}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "objection-forge/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    out = []
    for study in data.get("studies", []):
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        arms = proto.get("armsInterventionsModule", {})
        cond = proto.get("conditionsModule", {})
        out.append(
            {
                "nct_id": ident.get("nctId", ""),
                "title": ident.get("briefTitle", ""),
                "status": status.get("overallStatus", ""),
                "start_date": (status.get("startDateStruct") or {}).get("date", ""),
                "phases": design.get("phases", []),
                "study_type": design.get("studyType", ""),
                "conditions": cond.get("conditions", []),
                "interventions": [i.get("name", "") for i in arms.get("interventions", [])],
                "summary": (proto.get("descriptionModule", {}) or {}).get("briefSummary", "")[:600],
            }
        )
    return out


def fetch_uniprot(gene: str) -> dict:
    """UniProt REST — canonical target record."""
    params = {
        "query": f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true",
        "fields": "accession,id,protein_name,cc_function,ft_binding,cc_subcellular_location",
        "format": "json",
        "size": "1",
    }
    url = f"https://rest.uniprot.org/uniprotkb/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "objection-forge/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    results = data.get("results", [])
    if not results:
        return {}
    r = results[0]
    function = ""
    for c in r.get("comments", []):
        if c.get("commentType") == "FUNCTION":
            texts = c.get("texts", [])
            if texts:
                function = texts[0].get("value", "")
            break
    return {
        "accession": r.get("primaryAccession", ""),
        "uniprot_id": r.get("uniProtkbId", ""),
        "protein_name": (r.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}) or {}).get("value", ""),
        "function": function,
        "binding_sites": sum(1 for f in r.get("features", []) if f.get("type") == "Binding site"),
    }


def collect(gene: str) -> dict:
    print(f"[{gene}] uniprot...", flush=True)
    rec: dict = {"gene": gene, "disease": DISEASE, "uniprot": fetch_uniprot(gene)}
    rec["pubmed"] = {}
    for key, tmpl in QUERIES.items():
        q = tmpl.format(gene=gene)
        print(f"[{gene}] pubmed {key}...", flush=True)
        n = 5 if key == "crc" else 3
        try:
            rec["pubmed"][key] = fetch_papers(q, max_results=n)
        except Exception as exc:  # noqa: BLE001
            print(f"[{gene}] pubmed {key} FAILED: {exc}", file=sys.stderr)
            rec["pubmed"][key] = []
        rec["pubmed"][key + "_query"] = q
        time.sleep(0.4)
    print(f"[{gene}] trials...", flush=True)
    try:
        rec["trials"] = fetch_trials(gene, max_results=10)
    except Exception as exc:  # noqa: BLE001
        print(f"[{gene}] trials FAILED: {exc}", file=sys.stderr)
        rec["trials"] = []
    return rec


def write_documents(rec: dict) -> None:
    """Emit the plain-text source documents that .pltg facts quote verbatim."""
    gene = rec["gene"]
    docs = HERE / "docs"

    lines = [f"PubMed evidence dossier — {gene} / {DISEASE}", ""]
    for key in ("crc", "in_vitro", "in_vivo", "druggability"):
        papers = rec["pubmed"].get(key, [])
        lines.append(f"## {key} — query: {rec['pubmed'].get(key + '_query', '')}")
        lines.append(f"hits returned: {len(papers)}")
        lines.append("")
        for p in papers:
            lines.append(f"PMID {p['pmid']} | {p.get('journal', '')} | {p.get('date', '')}")
            lines.append(f"TITLE: {p['title']}")
            lines.append(f"ABSTRACT: {p.get('abstract', '') or '(no abstract available)'}")
            lines.append(f"URL: {p.get('url', '')}")
            lines.append("")
    (docs / f"pubmed-{gene}.txt").write_text("\n".join(lines), encoding="utf-8")

    lines = [f"ClinicalTrials.gov dossier — {gene} / {DISEASE}", ""]
    lines.append(f"trials returned: {len(rec['trials'])}")
    lines.append("")
    for t in rec["trials"]:
        lines.append(f"{t['nct_id']} | {t['status']} | phases: {', '.join(t['phases']) or 'NA'} | {t['study_type']}")
        lines.append(f"TITLE: {t['title']}")
        lines.append(f"CONDITIONS: {', '.join(t['conditions'])}")
        lines.append(f"INTERVENTIONS: {', '.join(t['interventions'])}")
        lines.append(f"SUMMARY: {t['summary']}")
        lines.append("")
    (docs / f"trials-{gene}.txt").write_text("\n".join(lines), encoding="utf-8")

    u = rec["uniprot"]
    lines = [
        f"UniProt target record — {gene}",
        "",
        f"ACCESSION: {u.get('accession', 'NA')}",
        f"ENTRY: {u.get('uniprot_id', 'NA')}",
        f"PROTEIN: {u.get('protein_name', 'NA')}",
        f"ANNOTATED BINDING SITES: {u.get('binding_sites', 0)}",
        f"FUNCTION: {u.get('function', 'NA')}",
        "",
    ]
    (docs / f"uniprot-{gene}.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    (HERE / "raw").mkdir(exist_ok=True)
    (HERE / "docs").mkdir(exist_ok=True)
    genes = sys.argv[1:] or TARGETS
    for gene in genes:
        rec = collect(gene)
        (HERE / "raw" / f"{gene}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        write_documents(rec)
        n_pm = sum(len(v) for k, v in rec["pubmed"].items() if isinstance(v, list))
        print(f"[{gene}] done: {n_pm} papers, {len(rec['trials'])} trials", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
