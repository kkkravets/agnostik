#!/usr/bin/env python3
"""Rank colorectal-cancer (CRC) gene targets via the Open Targets GraphQL API.

Writes two files with the same ranked list, both usable as a target
shortlist for the agnostik pipeline in place of the fixed v1 panel
(EGFR, ERBB2, KRAS, MYC, WRN, PRMT5):

- crc_opentargets_100_symbols.txt: one gene symbol per line, rank order.
  This is the minimal shortlist format `agnostik-collect-evidence
  --genes-file` and `agnostik-parseltongue --targets-file` expect.
- crc_opentargets_100_genes.csv: the same symbols plus ensembl_id,
  gene_name, biotype, and association score, for reviewing candidates
  before committing to a cutoff. `--genes-file`/`--targets-file` accept
  this too (they read the gene_symbol column) — but each extra target
  costs real evidence-collection and model time downstream, so trim the
  shortlist with `--top-n` or a smaller N_TARGETS below rather than
  running the full 100.
"""

import csv
import sys
from pathlib import Path

import requests

API_URL = "https://api.platform.opentargets.org/api/v4/graphql"
DISEASE_ID = "MONDO_0005575"  # colorectal cancer
N_TARGETS = 100
ENABLE_INDIRECT = True  # include evidence propagated from descendant disease terms, not just CRC directly
PAGE_SIZE = 200

OUTPUT_CSV = Path("crc_opentargets_100_genes.csv")
OUTPUT_SYMBOLS = Path("crc_opentargets_100_symbols.txt")

QUERY = """
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


def fetch_targets() -> tuple[str, list[dict]]:
    session = requests.Session()
    targets: list[dict] = []
    seen_ids: set[str] = set()
    page_index = 0

    while len(targets) < N_TARGETS:
        variables = {
            "diseaseId": DISEASE_ID,
            "pageIndex": page_index,
            "pageSize": PAGE_SIZE,
            "enableIndirect": ENABLE_INDIRECT,
        }
        print(f"Querying Open Targets page {page_index}...", file=sys.stderr)

        response = session.post(API_URL, json={"query": QUERY, "variables": variables}, timeout=120)
        response.raise_for_status()
        payload = response.json()
        if "errors" in payload:
            raise RuntimeError(f"Open Targets GraphQL error:\n{payload['errors']}")

        disease = payload.get("data", {}).get("disease")
        if disease is None:
            raise RuntimeError(f"Disease '{DISEASE_ID}' was not found in Open Targets.")

        associations = disease["associatedTargets"]
        rows = associations["rows"]
        if not rows:
            break

        for row in rows:
            target = row["target"]
            if target["biotype"] != "protein_coding":  # skip ncRNAs, pseudogenes, etc.
                continue
            ensembl_id = target["id"]
            if ensembl_id in seen_ids:
                continue
            seen_ids.add(ensembl_id)
            targets.append(
                {
                    "ensembl_id": ensembl_id,
                    "gene_symbol": target["approvedSymbol"],
                    "gene_name": target["approvedName"],
                    "biotype": target["biotype"],
                    "opentargets_association_score": row["score"],
                }
            )
            if len(targets) >= N_TARGETS:
                break

        print(f"  collected {len(targets)}/{N_TARGETS} protein-coding targets", file=sys.stderr)
        if (page_index + 1) * PAGE_SIZE >= associations["count"]:
            break
        page_index += 1

    if not targets:
        raise RuntimeError("No protein-coding targets were returned.")
    if len(targets) < N_TARGETS:
        print(f"WARNING: only {len(targets)} protein-coding targets were available.", file=sys.stderr)

    for rank, target in enumerate(targets, start=1):
        target["opentargets_rank"] = rank

    return disease["name"], targets


def write_outputs(targets: list[dict]) -> None:
    # Full ranked shortlist for review; see module docstring for how the
    # agnostik pipeline consumes it.
    fieldnames = ["opentargets_rank", "ensembl_id", "gene_symbol", "gene_name", "biotype", "opentargets_association_score"]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: target[key] for key in fieldnames} for target in targets)

    # One gene symbol per line, rank order, nothing else — the bare
    # shortlist format `--genes-file`/`--targets-file` reads directly.
    with OUTPUT_SYMBOLS.open("w", encoding="utf-8") as handle:
        for target in targets:
            if target["gene_symbol"]:
                handle.write(target["gene_symbol"] + "\n")


def main() -> None:
    disease_name, targets = fetch_targets()
    write_outputs(targets)

    print()
    print(f"Disease:           {disease_name} ({DISEASE_ID}) | indirect evidence: {ENABLE_INDIRECT}")
    print(f"Targets retrieved: {len(targets)}")
    print(f"CSV:               {OUTPUT_CSV.resolve()}")
    print(f"Symbols:           {OUTPUT_SYMBOLS.resolve()}")
    print()
    print("Top 20:")
    for target in targets[:20]:
        print(f"{target['opentargets_rank']:3d}  {target['gene_symbol']:<12} {target['ensembl_id']}  {target['opentargets_association_score']:.4f}")


if __name__ == "__main__":
    main()
