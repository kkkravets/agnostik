#!/usr/bin/env python3

import csv
import sys
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

API_URL = "https://api.platform.opentargets.org/api/v4/graphql"

# Colorectal cancer
DISEASE_ID = "MONDO_0005575"

N_TARGETS = 100

# Open Targets disease -> target associations normally include
# evidence propagated from more specific descendant disease terms.
# Set to False if you want ONLY evidence directly assigned to CRC.
ENABLE_INDIRECT = True

PAGE_SIZE = 200

OUTPUT_CSV = Path("crc_opentargets_100_genes.csv")
OUTPUT_SYMBOLS = Path("crc_opentargets_100_symbols.txt")


# ============================================================
# GRAPHQL QUERY
# ============================================================

QUERY = """
query DiseaseTargets(
    $diseaseId: String!,
    $pageIndex: Int!,
    $pageSize: Int!,
    $enableIndirect: Boolean!
) {
    disease(efoId: $diseaseId) {
        id
        name

        associatedTargets(
            enableIndirect: $enableIndirect
            page: {
                index: $pageIndex
                size: $pageSize
            }
        ) {
            count

            rows {
                score

                target {
                    id
                    approvedSymbol
                    approvedName
                    biotype
                }
            }
        }
    }
}
"""


# ============================================================
# QUERY OPEN TARGETS
# ============================================================

session = requests.Session()

protein_coding_targets = []
seen_ensembl_ids = set()

page_index = 0
total_associations = None
disease_name = None


while len(protein_coding_targets) < N_TARGETS:

    variables = {
        "diseaseId": DISEASE_ID,
        "pageIndex": page_index,
        "pageSize": PAGE_SIZE,
        "enableIndirect": ENABLE_INDIRECT,
    }

    print(
        f"Querying Open Targets page {page_index}...",
        file=sys.stderr,
    )

    response = session.post(
        API_URL,
        json={
            "query": QUERY,
            "variables": variables,
        },
        timeout=120,
    )

    response.raise_for_status()

    payload = response.json()

    if "errors" in payload:
        raise RuntimeError(
            f"Open Targets GraphQL error:\n{payload['errors']}"
        )

    disease = payload.get("data", {}).get("disease")

    if disease is None:
        raise RuntimeError(
            f"Disease '{DISEASE_ID}' was not found in Open Targets."
        )

    disease_name = disease["name"]

    associations = disease["associatedTargets"]

    total_associations = associations["count"]
    rows = associations["rows"]

    if not rows:
        break

    for row in rows:

        target = row["target"]

        # We want genes encoding proteins, rather than ncRNAs,
        # pseudogenes, etc.
        if target["biotype"] != "protein_coding":
            continue

        ensembl_id = target["id"]

        # Defensive deduplication
        if ensembl_id in seen_ensembl_ids:
            continue

        seen_ensembl_ids.add(ensembl_id)

        protein_coding_targets.append(
            {
                "ensembl_id": ensembl_id,
                "gene_symbol": target["approvedSymbol"],
                "gene_name": target["approvedName"],
                "biotype": target["biotype"],
                "opentargets_association_score": row["score"],
            }
        )

        if len(protein_coding_targets) >= N_TARGETS:
            break

    print(
        f"  collected {len(protein_coding_targets)}/{N_TARGETS} "
        f"protein-coding targets",
        file=sys.stderr,
    )

    # Stop if we have exhausted the association list
    if (page_index + 1) * PAGE_SIZE >= total_associations:
        break

    page_index += 1


# ============================================================
# CHECK RESULT
# ============================================================

if not protein_coding_targets:
    raise RuntimeError(
        "No protein-coding targets were returned."
    )

if len(protein_coding_targets) < N_TARGETS:
    print(
        f"WARNING: only {len(protein_coding_targets)} protein-coding "
        f"targets were available.",
        file=sys.stderr,
    )


# ============================================================
# ADD OPEN TARGETS RANK
# ============================================================

for rank, target in enumerate(protein_coding_targets, start=1):
    target["opentargets_rank"] = rank


# ============================================================
# WRITE CSV
# ============================================================

fieldnames = [
    "opentargets_rank",
    "ensembl_id",
    "gene_symbol",
    "gene_name",
    "biotype",
    "opentargets_association_score",
]

with OUTPUT_CSV.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    for target in protein_coding_targets:
        writer.writerow(
            {
                key: target[key]
                for key in fieldnames
            }
        )


# ============================================================
# WRITE SIMPLE GENE SYMBOL LIST
# ============================================================

with OUTPUT_SYMBOLS.open(
    "w",
    encoding="utf-8",
) as handle:

    for target in protein_coding_targets:
        symbol = target["gene_symbol"]

        if symbol:
            handle.write(symbol + "\n")


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 60)
print("Open Targets CRC target extraction complete")
print("=" * 60)

print(f"Disease:             {disease_name}")
print(f"Disease ID:          {DISEASE_ID}")
print(f"Indirect evidence:   {ENABLE_INDIRECT}")
print(f"Targets retrieved:   {len(protein_coding_targets)}")
print()

print(f"CSV:                 {OUTPUT_CSV.resolve()}")
print(f"Gene symbol list:    {OUTPUT_SYMBOLS.resolve()}")
print()

print("First 20 targets:")
print()

for target in protein_coding_targets[:20]:
    print(
        f"{target['opentargets_rank']:3d}  "
        f"{target['gene_symbol']:<12} "
        f"{target['ensembl_id']}  "
        f"{target['opentargets_association_score']:.4f}"
    )