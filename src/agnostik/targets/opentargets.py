"""Open Targets Platform lookups: disease search and ranked associated targets."""

from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import urllib.error
import urllib.request

API_URL = "https://api.platform.opentargets.org/api/v4/graphql"
PAGE_SIZE = 200

# (url, JSON payload or None for a GET) -> decoded JSON body. Tests pass a stub.
HttpJson = Callable[[str, dict | None], dict]

SEARCH_QUERY = """
query SearchDisease($queryString: String!, $size: Int!) {
    search(queryString: $queryString, entityNames: ["disease"], page: {index: 0, size: $size}) {
        hits { id name score }
    }
}
"""

CONTEXT_QUERY = """
query DiseaseContext($diseaseId: String!) {
    disease(efoId: $diseaseId) {
        name
        therapeuticAreas { id }
        parents { id name therapeuticAreas { id } }
    }
}
"""

# Therapeutic areas every cancer has; sharing only these says nothing about the organ.
GENERIC_AREAS = {"MONDO_0045024", "EFO_0000651"}  # cancer or benign tumor, phenotype

TARGETS_QUERY = """
query DiseaseTargets($diseaseId: String!, $pageIndex: Int!, $pageSize: Int!, $enableIndirect: Boolean!) {
    disease(efoId: $diseaseId) {
        name
        associatedTargets(enableIndirect: $enableIndirect, page: {index: $pageIndex, size: $pageSize}) {
            count
            rows {
                score
                target { id approvedSymbol approvedName biotype }
            }
        }
    }
}
"""

SHORTLIST_FIELDS = [
    "opentargets_rank",
    "ensembl_id",
    "gene_symbol",
    "gene_name",
    "biotype",
    "opentargets_association_score",
    "disease_id",
]


@dataclass(frozen=True, slots=True)
class DiseaseRef:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class DiseaseHit:
    id: str
    name: str
    score: float


def http_json(url: str, payload: dict | None = None, *, timeout: int = 120) -> dict:
    """GET, or POST when a payload is given, and decode the JSON reply.

    An error status still returns its JSON body, so callers can report the
    service's own message.
    """

    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        body = error.read()
    try:
        return json.loads(body)
    except ValueError as error:
        raise ValueError(f"{url} did not return JSON") from error


def _graphql(query: str, variables: dict, http: HttpJson) -> dict:
    payload = http(API_URL, {"query": query, "variables": variables})
    if "errors" in payload:
        raise RuntimeError(f"Open Targets GraphQL error:\n{payload['errors']}")
    return payload.get("data") or {}


def search_diseases(query: str, *, size: int = 5, http: HttpJson = http_json) -> list[DiseaseHit]:
    """Diseases matching a free-text name, best match first."""

    data = _graphql(SEARCH_QUERY, {"queryString": query, "size": size}, http)
    hits = (data.get("search") or {}).get("hits") or []
    return [DiseaseHit(hit["id"], hit["name"], float(hit["score"])) for hit in hits]


def disease_context(disease_id: str, *, http: HttpJson = http_json) -> tuple[str, list[DiseaseRef]]:
    """A disease's name and its organ-specific parents.

    Parents that share no therapeutic area beyond "cancer" are dropped, so
    "pancreatic adenocarcinoma" keeps "exocrine pancreatic carcinoma" but not the
    generic "adenocarcinoma".
    """

    disease = _graphql(CONTEXT_QUERY, {"diseaseId": disease_id}, http).get("disease")
    if disease is None:
        raise RuntimeError(f"Disease '{disease_id}' was not found in Open Targets.")
    areas = {area["id"] for area in disease["therapeuticAreas"]} - GENERIC_AREAS
    parents = [
        DiseaseRef(parent["id"], parent["name"])
        for parent in disease["parents"]
        if areas & {area["id"] for area in parent["therapeuticAreas"]}
    ]
    return disease["name"], parents


def fetch_targets(
    disease_id: str,
    n_targets: int,
    *,
    enable_indirect: bool = True,
    http: HttpJson = http_json,
) -> tuple[str, list[dict]]:
    """The disease's top protein-coding targets, ranked by association score.

    ``enable_indirect`` includes evidence propagated from descendant disease terms.
    """

    targets: list[dict] = []
    seen_ids: set[str] = set()
    page_index = 0

    while len(targets) < n_targets:
        variables = {
            "diseaseId": disease_id,
            "pageIndex": page_index,
            "pageSize": PAGE_SIZE,
            "enableIndirect": enable_indirect,
        }
        disease = _graphql(TARGETS_QUERY, variables, http).get("disease")
        if disease is None:
            raise RuntimeError(f"Disease '{disease_id}' was not found in Open Targets.")

        associations = disease["associatedTargets"]
        rows = associations["rows"]
        if not rows:
            break

        for row in rows:
            target = row["target"]
            if target["biotype"] != "protein_coding":  # skip ncRNAs, pseudogenes, etc.
                continue
            if target["id"] in seen_ids:
                continue
            seen_ids.add(target["id"])
            targets.append(
                {
                    "ensembl_id": target["id"],
                    "gene_symbol": target["approvedSymbol"],
                    "gene_name": target["approvedName"],
                    "biotype": target["biotype"],
                    "opentargets_association_score": row["score"],
                    "disease_id": disease_id,
                }
            )
            if len(targets) >= n_targets:
                break

        if (page_index + 1) * PAGE_SIZE >= associations["count"]:
            break
        page_index += 1

    if not targets:
        raise RuntimeError("No protein-coding targets were returned.")

    for rank, target in enumerate(targets, start=1):
        target["opentargets_rank"] = rank
    return disease["name"], targets


def merge_targets(per_disease: list[list[dict]], n_targets: int) -> list[dict]:
    """Union of ranked lists: each gene keeps its best score, then the top n are re-ranked."""

    best: dict[str, dict] = {}
    for targets in per_disease:
        for target in targets:
            held = best.get(target["ensembl_id"])
            if held is None or target["opentargets_association_score"] > held["opentargets_association_score"]:
                best[target["ensembl_id"]] = target
    ranked = sorted(best.values(), key=lambda t: -t["opentargets_association_score"])[:n_targets]
    return [{**target, "opentargets_rank": rank} for rank, target in enumerate(ranked, start=1)]


def write_shortlist(targets: list[dict], out_dir: Path) -> tuple[Path, Path]:
    """Write ``candidates.csv`` (for review) and ``symbols.txt`` (one gene per line)."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "candidates.csv"
    symbols_path = out_dir / "symbols.txt"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHORTLIST_FIELDS)
        writer.writeheader()
        writer.writerows({key: target[key] for key in SHORTLIST_FIELDS} for target in targets)

    with symbols_path.open("w", encoding="utf-8") as handle:
        for target in targets:
            if target["gene_symbol"]:
                handle.write(target["gene_symbol"] + "\n")
    return csv_path, symbols_path
