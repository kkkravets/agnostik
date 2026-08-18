#!/usr/bin/env python3
"""Turn collected raw evidence into a Parseltongue system (.pltg).

STAND-IN for pipeline stage 3. Emits source documents whose lines the
facts quote verbatim, one module per target, a shared rules module whose
axioms quote the review charter, and a main entry point.

    fixtures/docs/*.txt|md      source documents (quote targets)
    fixtures/src/<gene>.pltg    facts + derived claims for one target
    fixtures/src/rules.pltg     charter-grounded axioms
    fixtures/main.pltg          entry point
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
DOCS = HERE / "docs"
SRC = HERE / "src"

TARGETS = ["EGFR", "ERBB2", "KRAS", "MYC", "WRN", "PRMT5"]
DISEASE = "colorectal cancer"
LATE_PHASES = {"PHASE3", "PHASE4"}

CHARTER = """# CRC Target Shortlist Charter — v1

Scope: colorectal cancer (MONDO_0005575). Six pre-selected targets are
judged; nothing else is in scope for this round.

## C1 Structural druggability
A target is structurally druggable when UniProt annotates at least one
binding site on the reviewed human entry.

## C2 Chemical matter
A target has chemical matter when at least three indexed publications
describe an inhibitor, degrader, small molecule or antibody against it.

## C3 Druggability
A target is druggable only when it satisfies both C1 and C2. Chemical
matter alone does not establish druggability.

## C4 In vitro support
A target has in vitro support when at least one indexed publication
reports colorectal cell line or organoid work.

## C5 In vivo support
A target has in vivo support when at least one indexed publication
reports a xenograft, mouse model or other in vivo colorectal experiment.

## C6 Clinical traction
A target has clinical traction when at least one registered colorectal
cancer trial that names it is late phase, or is currently recruiting.

## C7 Verdict
A target is promising when it is druggable, has in vivo support, and has
clinical traction. Every other target is rejected for this round.

## C8 Provenance
Every fact must quote the document it came from. A verdict that cannot be
traced to quoted evidence is void.
"""


def pltg_str(s: str) -> str:
    """Escape a Python string for a .pltg double-quoted literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def one_line(s: str, limit: int = 240) -> str:
    """Collapse to a single line — quotes must match the document exactly."""
    flat = " ".join((s or "").split())
    return flat[:limit].rstrip()


def write_documents(rec: dict) -> dict:
    """Write the evidence documents and return the derived counters."""
    gene = rec["gene"]
    pm = rec["pubmed"]
    trials = rec["trials"]
    uni = rec["uniprot"]

    counts = {k: len(pm.get(k, [])) for k in ("crc", "in_vitro", "in_vivo", "druggability")}
    late = [t for t in trials if any(p in LATE_PHASES for p in t.get("phases", []))]
    recruiting = [t for t in trials if t.get("status") == "RECRUITING"]

    # ---- PubMed dossier -------------------------------------------------
    lines = [
        f"PubMed evidence dossier — {gene} / {DISEASE}",
        "Source: NCBI E-utilities via ClawBio pubmed-summariser",
        "",
        "## COUNTERS",
        f"PUBMED_HITS crc={counts['crc']}",
        f"PUBMED_HITS in_vitro={counts['in_vitro']}",
        f"PUBMED_HITS in_vivo={counts['in_vivo']}",
        f"PUBMED_HITS druggability={counts['druggability']}",
        "",
    ]
    for key in ("crc", "in_vitro", "in_vivo", "druggability"):
        lines.append(f"## SECTION {key} — query: {pm.get(key + '_query', '')}")
        lines.append("")
        for p in pm.get(key, []):
            lines.append(f"PMID {p['pmid']} | {p.get('journal', '')} | {p.get('date', '')}")
            lines.append(f"TITLE: {one_line(p['title'], 400)}")
            lines.append(f"ABSTRACT: {one_line(p.get('abstract', '') or '(no abstract available)', 1200)}")
            lines.append(f"URL: {p.get('url', '')}")
            lines.append("")
    (DOCS / f"pubmed-{gene}.txt").write_text("\n".join(lines), encoding="utf-8")

    # ---- Trials dossier -------------------------------------------------
    lines = [
        f"ClinicalTrials.gov dossier — {gene} / {DISEASE}",
        "Source: clinicaltrials.gov/api/v2, condition-scoped to colorectal cancer",
        "",
        "## COUNTERS",
        f"TRIALS total={len(trials)}",
        f"TRIALS late_phase={len(late)}",
        f"TRIALS recruiting={len(recruiting)}",
        "",
    ]
    for t in trials:
        lines.append(
            f"{t['nct_id']} | {t.get('status', '')} | phases: {', '.join(t.get('phases', [])) or 'NA'} | {t.get('study_type', '')}"
        )
        lines.append(f"TITLE: {one_line(t.get('title', ''), 400)}")
        lines.append(f"CONDITIONS: {one_line(', '.join(t.get('conditions', [])), 300)}")
        lines.append(f"INTERVENTIONS: {one_line(', '.join(t.get('interventions', [])), 300)}")
        lines.append(f"SUMMARY: {one_line(t.get('summary', ''), 700)}")
        lines.append("")
    (DOCS / f"trials-{gene}.txt").write_text("\n".join(lines), encoding="utf-8")

    # ---- UniProt record -------------------------------------------------
    lines = [
        f"UniProt reviewed record — {gene}",
        "Source: rest.uniprot.org, organism 9606, reviewed only",
        "",
        "## COUNTERS",
        f"UNIPROT binding_sites={uni.get('binding_sites', 0)}",
        "",
        f"ACCESSION: {uni.get('accession', 'NA')}",
        f"ENTRY: {uni.get('uniprot_id', 'NA')}",
        f"PROTEIN: {uni.get('protein_name', 'NA')}",
        f"FUNCTION: {one_line(uni.get('function', 'NA'), 900)}",
        "",
    ]
    (DOCS / f"uniprot-{gene}.txt").write_text("\n".join(lines), encoding="utf-8")

    return {
        "counts": counts,
        "trials_total": len(trials),
        "trials_late": len(late),
        "trials_recruiting": len(recruiting),
        "binding_sites": uni.get("binding_sites", 0),
        "late_examples": late[:2],
        "recruiting_examples": recruiting[:2],
        "uniprot": uni,
    }


def module_name(gene: str) -> str:
    return gene.lower()


def build_target_module(rec: dict, stats: dict) -> str:
    gene = rec["gene"]
    pm = rec["pubmed"]
    c = stats["counts"]
    pmdoc, trdoc, updoc = f"pubmed-{gene}", f"trials-{gene}", f"uniprot-{gene}"

    out: list[str] = [
        f"; {gene} — {DISEASE} target dossier",
        f"; Facts quote docs/{pmdoc}.txt, docs/{trdoc}.txt, docs/{updoc}.txt verbatim.",
        "; Claims conjoin the charter criterion that licenses them, so every verdict",
        "; backtraces to both the data and the rule text.",
        "",
        "; ---------------------------------------------------------------- facts",
        "",
    ]

    def fact(name: str, value, doc: str, quote: str, explanation: str) -> None:
        out.append(f"(fact {name} {value}")
        out.append(f'    :evidence (evidence "{doc}"')
        out.append(f'        :quotes ("{pltg_str(quote)}")')
        out.append(f'        :explanation "{pltg_str(explanation)}"))')
        out.append("")

    fact("crc-literature-hits", c["crc"], pmdoc, f"PUBMED_HITS crc={c['crc']}",
         f"Indexed PubMed records for {gene} in colorectal cancer")
    fact("in-vitro-hits", c["in_vitro"], pmdoc, f"PUBMED_HITS in_vitro={c['in_vitro']}",
         f"Indexed records reporting colorectal cell line or organoid work on {gene}")
    fact("in-vivo-hits", c["in_vivo"], pmdoc, f"PUBMED_HITS in_vivo={c['in_vivo']}",
         f"Indexed records reporting xenograft or mouse model work on {gene}")
    fact("druggability-hits", c["druggability"], pmdoc, f"PUBMED_HITS druggability={c['druggability']}",
         f"Indexed records describing an inhibitor, degrader or antibody against {gene}")
    fact("trials-total", stats["trials_total"], trdoc, f"TRIALS total={stats['trials_total']}",
         f"Registered colorectal cancer trials naming {gene}")
    fact("trials-late-phase", stats["trials_late"], trdoc, f"TRIALS late_phase={stats['trials_late']}",
         "Trials in phase 3 or phase 4")
    fact("trials-recruiting", stats["trials_recruiting"], trdoc, f"TRIALS recruiting={stats['trials_recruiting']}",
         "Trials currently recruiting")
    fact("binding-sites", stats["binding_sites"], updoc, f"UNIPROT binding_sites={stats['binding_sites']}",
         f"Binding sites annotated on the reviewed human {gene} entry")

    # Per-document anchors: one fact per cited paper / trial, so the objection
    # layer can backtrace a sentence to a single PMID or NCT id.
    out.append("; ------------------------------------------------ document anchors")
    out.append("")
    anchors: list[str] = []
    seen: set[str] = set()
    for key in ("in_vivo", "in_vitro", "druggability", "crc"):
        for p in pm.get(key, [])[:2]:
            pmid = p["pmid"]
            if pmid in seen:
                continue
            seen.add(pmid)
            name = f"paper-{pmid}"
            anchors.append(name)
            fact(name, "true", pmdoc, f"TITLE: {one_line(p['title'], 400)}",
                 f"PMID {pmid} ({key} query, {p.get('journal', '')} {p.get('date', '')})")
    for t in (stats["late_examples"] + stats["recruiting_examples"])[:3]:
        nct = t["nct_id"]
        if nct in seen:
            continue
        seen.add(nct)
        name = f"trial-{nct}"
        anchors.append(name)
        fact(name, "true", trdoc, f"TITLE: {one_line(t.get('title', ''), 400)}",
             f"{nct} — status {t.get('status', '')}, phases {', '.join(t.get('phases', [])) or 'NA'}")

    out.append("; -------------------------------------------------------- claims")
    out.append("")
    out.append("(derive structurally-druggable (and (> binding-sites 0) src.rules.c1-in-force)")
    out.append("    :using (binding-sites src.rules.c1-in-force))")
    out.append("")
    out.append("(derive has-chemical-matter (and (>= druggability-hits 3) src.rules.c2-in-force)")
    out.append("    :using (druggability-hits src.rules.c2-in-force))")
    out.append("")
    out.append("(derive druggable (and (and structurally-druggable has-chemical-matter) src.rules.c3-in-force)")
    out.append("    :using (structurally-druggable has-chemical-matter src.rules.c3-in-force))")
    out.append("")
    out.append("(derive in-vitro-supported (and (> in-vitro-hits 0) src.rules.c4-in-force)")
    out.append("    :using (in-vitro-hits src.rules.c4-in-force))")
    out.append("")
    out.append("(derive in-vivo-supported (and (> in-vivo-hits 0) src.rules.c5-in-force)")
    out.append("    :using (in-vivo-hits src.rules.c5-in-force))")
    out.append("")
    out.append("(derive clinical-traction")
    out.append("    (and (or (> trials-late-phase 0) (> trials-recruiting 0)) src.rules.c6-in-force)")
    out.append("    :using (trials-late-phase trials-recruiting src.rules.c6-in-force))")
    out.append("")
    if anchors:
        expr = anchors[-1]
        for a in reversed(anchors[:-1]):
            expr = f"(and {a} {expr})"
        out.append("; charter C8 — the dossier is anchored to quoted documents")
        out.append(f"(derive dossier-anchored (and {expr} src.rules.c8-in-force)")
        out.append(f"    :using ({' '.join(anchors)} src.rules.c8-in-force))")
        out.append("")
    return "\n".join(out)


def build_rules() -> str:
    return '''; rules.pltg — CRC shortlist criteria, quoted from the review charter.
; Universally quantified rules: each target module derives its own verdict
; from its own facts, under these rules.

(axiom structural-site-required
    (implies (= ?has-binding-site true) (= ?structurally-druggable true))
    :evidence (evidence "charter"
        :quotes ("A target is structurally druggable when UniProt annotates at least one")
        :explanation "C1 — UniProt binding-site annotation is the structural criterion"))

(axiom chemical-matter-threshold
    (implies (= ?inhibitor-papers-at-least-three true) (= ?chemical-matter true))
    :evidence (evidence "charter"
        :quotes ("matter when at least three indexed publications")
        :explanation "C2 — three indexed inhibitor/degrader/antibody papers"))

(axiom druggability-needs-both
    (implies (and (= ?structurally-druggable true) (= ?chemical-matter true))
             (= ?druggable true))
    :evidence (evidence "charter"
        :quotes ("A target is druggable only when it satisfies both C1 and C2. Chemical")
        :explanation "C3 — structural site and chemical matter are both required"))

(axiom clinical-traction-rule
    (implies (or (= ?late-phase-trial true) (= ?recruiting-trial true))
             (= ?clinical-traction true))
    :evidence (evidence "charter"
        :quotes ("cancer trial that names it is late phase, or is currently recruiting.")
        :explanation "C6 — late phase or actively recruiting counts as traction"))

(axiom verdict-rule
    (implies (and (= ?druggable true)
                  (and (= ?in-vivo-support true) (= ?clinical-traction true)))
             (= ?promising true))
    :evidence (evidence "charter"
        :quotes ("A target is promising when it is druggable, has in vivo support, and has")
        :explanation "C7 — the conjunction that defines a promising target"))

(axiom provenance-rule
    (implies (= ?verdict-quoted false) (= ?verdict-void true))
    :evidence (evidence "charter"
        :quotes ("Every fact must quote the document it came from. A verdict that cannot be")
        :explanation "C8 — a verdict without quoted evidence is void"))

; ---------------------------------------------------------------------------
; Criterion facts — the rule text itself, quoted. Every claim conjoins the
; criterion that licenses it, so a verdict backtraces to the charter as well
; as to the data.
; ---------------------------------------------------------------------------

(fact c1-in-force true
    :evidence (evidence "charter"
        :quotes ("A target is structurally druggable when UniProt annotates at least one")
        :explanation "C1 structural druggability criterion is in force"))

(fact c2-in-force true
    :evidence (evidence "charter"
        :quotes ("A target has chemical matter when at least three indexed publications")
        :explanation "C2 chemical matter criterion is in force"))

(fact c3-in-force true
    :evidence (evidence "charter"
        :quotes ("A target is druggable only when it satisfies both C1 and C2. Chemical")
        :explanation "C3 druggability criterion is in force"))

(fact c4-in-force true
    :evidence (evidence "charter"
        :quotes ("A target has in vitro support when at least one indexed publication")
        :explanation "C4 in vitro criterion is in force"))

(fact c5-in-force true
    :evidence (evidence "charter"
        :quotes ("A target has in vivo support when at least one indexed publication")
        :explanation "C5 in vivo criterion is in force"))

(fact c6-in-force true
    :evidence (evidence "charter"
        :quotes ("A target has clinical traction when at least one registered colorectal")
        :explanation "C6 clinical traction criterion is in force"))

(fact c7-in-force true
    :evidence (evidence "charter"
        :quotes ("A target is promising when it is druggable, has in vivo support, and has")
        :explanation "C7 verdict criterion is in force"))

(fact c8-in-force true
    :evidence (evidence "charter"
        :quotes ("Every fact must quote the document it came from. A verdict that cannot be")
        :explanation "C8 provenance criterion is in force"))
'''


def build_main(genes: list[str]) -> str:
    """Entry point: documents, rules, dossiers, then the cross-module verdicts.

    The verdicts live here rather than inside each dossier because pg-bench
    probes core-to-consequence from the entry file — derivations reachable
    from here are what land in the export.
    """
    lines = [
        "; shortlist.pltg — CRC target shortlist system (entry point)",
        f"; Targets: {', '.join(genes)} | Disease: {DISEASE}",
        "; Stand-in for pipeline stages 1-3; stage 4 (objections) consumes the",
        "; pg-bench export of this system.",
        "",
        "; --- source documents ---",
        '(load-document "charter" "docs/charter.md")',
    ]
    for g in genes:
        lines.append(f'(load-document "pubmed-{g}" "docs/pubmed-{g}.txt")')
        lines.append(f'(load-document "trials-{g}" "docs/trials-{g}.txt")')
        lines.append(f'(load-document "uniprot-{g}" "docs/uniprot-{g}.txt")')
    lines += ["", "; --- decision rules (charter-grounded axioms) ---", "(import (quote src.rules))", ""]
    lines.append("; --- target dossiers (facts + per-target claims) ---")
    for g in genes:
        lines.append(f"(import (quote src.{module_name(g)}))")
    lines += ["", "; --- verdicts: charter C7 applied to each dossier ---", ""]
    for g in genes:
        m = f"src.{module_name(g)}"
        lines.append(f"(derive {module_name(g)}-promising")
        lines.append(f"    (and (and {m}.druggable (and {m}.in-vivo-supported {m}.clinical-traction))")
        lines.append("         src.rules.c7-in-force)")
        lines.append(f"    :using ({m}.druggable {m}.in-vivo-supported {m}.clinical-traction src.rules.c7-in-force))")
        lines.append("")
        lines.append(f"(derive {module_name(g)}-traceable {m}.dossier-anchored")
        lines.append(f"    :using ({m}.dossier-anchored))")
        lines.append("")
    lines.append("; --- shortlist size: how many of the six survive C7 ---")
    lines.append("(derive shortlist-size")
    terms = [f"(if {module_name(g)}-promising 1 0)" for g in genes]
    expr = terms[-1]
    for t in reversed(terms[:-1]):
        expr = f"(+ {t} {expr})"
    lines.append(f"    {expr}")
    lines.append("    :using (" + " ".join(f"{module_name(g)}-promising" for g in genes) + "))")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    (DOCS / "charter.md").write_text(CHARTER, encoding="utf-8")

    verdicts = {}
    genes = []
    for gene in TARGETS:
        raw_path = RAW / f"{gene}.json"
        if not raw_path.exists():
            print(f"skip {gene}: no raw data — run collect.py first")
            continue
        rec = json.loads(raw_path.read_text(encoding="utf-8"))
        stats = write_documents(rec)
        (SRC / f"{module_name(gene)}.pltg").write_text(build_target_module(rec, stats), encoding="utf-8")
        genes.append(gene)

        druggable = stats["binding_sites"] > 0 and stats["counts"]["druggability"] >= 3
        traction = stats["trials_late"] > 0 or stats["trials_recruiting"] > 0
        promising = druggable and stats["counts"]["in_vivo"] > 0 and traction
        verdicts[gene] = "promising" if promising else "rejected"

    (SRC / "rules.pltg").write_text(build_rules(), encoding="utf-8")
    (HERE / "shortlist.pltg").write_text(build_main(genes), encoding="utf-8")

    print(f"wrote {len(genes)} target modules + rules + main")
    for gene, v in verdicts.items():
        print(f"  {gene:6} -> {v}")
    n_prom = sum(1 for v in verdicts.values() if v == "promising")
    print(f"expected split: {n_prom} promising / {len(verdicts) - n_prom} rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
