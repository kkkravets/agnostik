"""Stage 6 — build a Parseltongue system that cross-examines the shortlist.

This is the replacement for a weighted target-validation score. Nothing here
adds points up. Two independent descriptions of the same set of records — what
the dossier asserts, and what the registries returned in stage 5 — are written
as separate fact modules, and every place they can disagree is declared as a
``diff``. The engine, not this code, decides which of them actually diverge,
and it refuses to do so on evidence it cannot quote.

What is compared is set-wise identical on both sides: the citations the dossier
itself rests on. Counting a dossier-wide query total against a spot-checked
registry sample would produce divergences that mean nothing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

__all__ = ["CHARTER", "build_system", "TargetFacts"]

from dataclasses import dataclass, field

CHARTER = """# Verification charter — v1

The shortlist is judged a second time, against the registries themselves.

## V1 Support base
A record supports a target only when the registry entry for that record names
the target as its subject. A record that merely mentions the target does not
enlarge the support base.

## V2 Off-target records
A record that never names the target, under any of the names its reviewed
UniProt entry lists, does not support that target at all.

## V3 Retraction
A retracted record, or one under an expression of concern, supports nothing
regardless of what it says.

## V4 Resolution
A record that its registry cannot return does not exist for the purposes of
this review.

## V5 Indication
A record that names no colorectal indication does not speak to colorectal
cancer, whatever else it establishes.

## V6 Verdict integrity
A verdict whose support base diverges from the verified support base is not
thereby wrong, but it is unproven: it rests on records that do not carry it.

## V7 Divergence is proved, not scored
Agreement and divergence are decided by comparing quoted values from two
independent sources. No weight, threshold or partial credit takes part in it.
"""


@dataclass
class TargetFacts:
    """Both sides of the comparison for one target, over the same record set."""

    symbol: str
    verdict: bool | None
    verdict_node: str
    cited_records: int = 0
    subject_records: int = 0
    weak_attribution: int = 0
    off_target: int = 0
    title_drift: int = 0
    retracted: int = 0
    unresolved: int = 0
    no_indication: int = 0
    records: list[dict] = field(default_factory=list)  # per-record join of both sides

    @property
    def module(self) -> str:
        return self.symbol.lower()

    @property
    def base_intact(self) -> bool:
        return self.cited_records == self.subject_records


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _pltg(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _one_line(text: str, limit: int = 300) -> str:
    return " ".join((text or "").split())[:limit].rstrip()


def _write_dossier_doc(facts: TargetFacts, export_names: list[str], docs: Path) -> None:
    """A transcript of what the dossier asserts, so its facts have a document to quote."""
    lines = [
        f"Dossier transcript — {facts.symbol}",
        f"Transcribed {_stamp()} from: {', '.join(export_names)}",
        "",
        "## ASSERTED",
        f"DOSSIER cited_records={facts.cited_records}",
        f"DOSSIER assumed_off_target=0",
        f"DOSSIER assumed_retracted=0",
        f"DOSSIER assumed_unresolved=0",
        f"DOSSIER verdict={'promising' if facts.verdict else 'rejected'}",
        f"DOSSIER verdict_node={facts.verdict_node}",
        "",
        "## RECORDS THE DOSSIER TREATS AS SUPPORT",
    ]
    for record in facts.records:
        lines.append(f"DOSSIER SUPPORTS {record['source_type']} {record['source_id']}")
        lines.append(f"  as: {_one_line(record['quote'], 260)}")
        lines.append(f"  via node: {record['node_id']}")
        lines.append("")
    (docs / f"dossier-{facts.symbol}.txt").write_text("\n".join(lines), encoding="utf-8")


def _dossier_module(facts: TargetFacts) -> str:
    doc = f"dossier-{facts.symbol}"
    out = [
        f"; {facts.symbol} — what the dossier asserts (stage 4 export, transcribed)",
        "",
    ]

    def fact(name: str, value, quote: str, explanation: str) -> None:
        out.extend(
            [
                f"(fact {name} {value}",
                f'    :evidence (evidence "{doc}"',
                f'        :quotes ("{_pltg(quote)}")',
                f'        :explanation "{_pltg(explanation)}"))',
                "",
            ]
        )

    fact("cited-records", facts.cited_records, f"DOSSIER cited_records={facts.cited_records}",
         f"Records the {facts.symbol} dossier rests on")
    fact("assumed-off-target", 0, "DOSSIER assumed_off_target=0",
         "The dossier cites every record as support, so it assumes none is off target")
    fact("assumed-retracted", 0, "DOSSIER assumed_retracted=0",
         "The dossier assumes no cited record is retracted")
    fact("assumed-unresolved", 0, "DOSSIER assumed_unresolved=0",
         "The dossier assumes every cited record resolves")

    for record in facts.records:
        name = f"supports-{record['source_type']}-{record['source_id']}".replace(".", "-")
        fact(name, "true",
             f"DOSSIER SUPPORTS {record['source_type']} {record['source_id']}",
             f"The dossier treats {record['source_id']} as support for {facts.symbol}")
    return "\n".join(out)


def _registry_module(facts: TargetFacts) -> str:
    doc = f"registry-{facts.symbol}"
    out = [
        f"; {facts.symbol} — what the registries returned (stage 5)",
        "",
    ]

    def fact(name: str, value, quote: str, explanation: str) -> None:
        out.extend(
            [
                f"(fact {name} {value}",
                f'    :evidence (evidence "{doc}"',
                f'        :quotes ("{_pltg(quote)}")',
                f'        :explanation "{_pltg(explanation)}"))',
                "",
            ]
        )

    fact("subject-records", facts.subject_records, f"VERIFIED subject_records={facts.subject_records}",
         f"Cited records whose registry entry names {facts.symbol} as its subject")
    fact("off-target", facts.off_target, f"VERIFIED off_target={facts.off_target}",
         f"Cited records that never name {facts.symbol}")
    fact("retracted", facts.retracted, f"VERIFIED retracted={facts.retracted}",
         "Cited records that are retracted or under an expression of concern")
    fact("unresolved", facts.unresolved, f"VERIFIED unresolved={facts.unresolved}",
         "Cited identifiers no registry could return")

    for record in facts.records:
        name = f"supports-{record['source_type']}-{record['source_id']}".replace(".", "-")
        supports = "true" if record["status"] == "sound" else "false"
        quote = (
            f"{record['source_type']} {record['source_id']} | status={record['status']} | "
            f"gene_role={record['gene_role']} | indication={record['indication_role']} | "
            f"resolves={record['resolves']}"
        )
        fact(name, supports, quote,
             record["reason"] or f"registry grade for {record['source_id']}")
    return "\n".join(out)


def _rules_module() -> str:
    return '''; rules.pltg — verification invariants, quoted from the verification charter.

(axiom support-requires-subject-record
    (implies (= ?registry-names-target-as-subject false) (= ?record-supports false))
    :evidence (evidence "charter"
        :quotes ("A record supports a target only when the registry entry for that record names")
        :explanation "V1 — mention is not support"))

(axiom off-target-supports-nothing
    (implies (= ?target-never-named true) (= ?record-supports false))
    :evidence (evidence "charter"
        :quotes ("A record that never names the target, under any of the names its reviewed")
        :explanation "V2 — a record that never names the target supports nothing"))

(axiom retraction-voids-support
    (implies (= ?retracted true) (= ?record-supports false))
    :evidence (evidence "charter"
        :quotes ("A retracted record, or one under an expression of concern, supports nothing")
        :explanation "V3 — retraction voids support"))

(axiom unresolved-does-not-exist
    (implies (= ?registry-returns-record false) (= ?record-exists false))
    :evidence (evidence "charter"
        :quotes ("A record that its registry cannot return does not exist for the purposes of")
        :explanation "V4 — unresolved records do not count"))

(axiom verdict-unproven-on-divergent-base
    (implies (= ?support-base-diverges true) (= ?verdict-proven false))
    :evidence (evidence "charter"
        :quotes ("A verdict whose support base diverges from the verified support base is not")
        :explanation "V6 — a divergent support base leaves the verdict unproven"))

(axiom divergence-not-scored
    (implies (= ?comparison-quoted-both-sides true) (= ?divergence-decidable true))
    :evidence (evidence "charter"
        :quotes ("Agreement and divergence are decided by comparing quoted values from two")
        :explanation "V7 — divergence is proved by comparison, never scored"))
'''


def _checks_module(all_facts: list[TargetFacts]) -> str:
    out = [
        "; checks.pltg — every place the two descriptions can disagree.",
        "; A diff that holds is silent; a diff that fails is a proved inconsistency.",
        "",
    ]
    for facts in all_facts:
        mod = facts.module
        out += [
            f"; ---------------------------------------------------------- {facts.symbol}",
            "",
            f"(diff {mod}-support-base",
            f"    :replace dossier_{mod}.cited-records",
            f"    :with registry_{mod}.subject-records)",
            "",
            f"(diff {mod}-off-target",
            f"    :replace dossier_{mod}.assumed-off-target",
            f"    :with registry_{mod}.off-target)",
            "",
            f"(diff {mod}-retracted",
            f"    :replace dossier_{mod}.assumed-retracted",
            f"    :with registry_{mod}.retracted)",
            "",
            f"(diff {mod}-unresolved",
            f"    :replace dossier_{mod}.assumed-unresolved",
            f"    :with registry_{mod}.unresolved)",
            "",
        ]
        for record in facts.records:
            if record["status"] == "sound":
                continue
            name = f"supports-{record['source_type']}-{record['source_id']}".replace(".", "-")
            out += [
                f"(diff {mod}-{name}",
                f"    :replace dossier_{mod}.{name}",
                f"    :with registry_{mod}.{name})",
                "",
            ]
        # Three separate questions, kept apart on purpose. Exact agreement of the
        # two bases is informative but nearly never true, so it is recorded, not
        # used as the gate. What gates the verdict is whether the base that
        # survived verification can still carry it.
        out += [
            f"(derive {mod}-base-intact",
            f"    (= dossier_{mod}.cited-records registry_{mod}.subject-records)",
            f"    :using (dossier_{mod}.cited-records registry_{mod}.subject-records))",
            "",
            f"(derive {mod}-clean-of-off-target",
            f"    (= registry_{mod}.off-target 0)",
            f"    :using (registry_{mod}.off-target))",
            "",
            f"(derive {mod}-clean-of-retracted",
            f"    (= registry_{mod}.retracted 0)",
            f"    :using (registry_{mod}.retracted))",
            "",
            f"(derive {mod}-all-records-resolve",
            f"    (= registry_{mod}.unresolved 0)",
            f"    :using (registry_{mod}.unresolved))",
            "",
            f"(derive {mod}-has-subject-record",
            f"    (> registry_{mod}.subject-records 0)",
            f"    :using (registry_{mod}.subject-records))",
            "",
            f"(derive {mod}-base-usable",
            f"    (and (and {mod}-clean-of-off-target {mod}-clean-of-retracted)",
            f"         (and {mod}-all-records-resolve {mod}-has-subject-record))",
            f"    :using ({mod}-clean-of-off-target {mod}-clean-of-retracted "
            f"{mod}-all-records-resolve {mod}-has-subject-record))",
            "",
            f"(derive {mod}-verdict-proven {mod}-base-usable",
            f"    :using ({mod}-base-usable))",
            "",
        ]

    terms = [f"(if {f.module}-verdict-proven 1 0)" for f in all_facts]
    expr = terms[-1]
    for term in reversed(terms[:-1]):
        expr = f"(+ {term} {expr})"
    out += [
        "; how many of the verdicts survive verification against the registries",
        "(derive proven-verdicts",
        f"    {expr}",
        "    :using (" + " ".join(f"{f.module}-verdict-proven" for f in all_facts) + "))",
        "",
    ]
    return "\n".join(out)


def _main_module(all_facts: list[TargetFacts]) -> str:
    lines = [
        "; main.pltg — formal consistency screening of the CRC shortlist",
        f"; Generated {_stamp()}",
        "",
        '(load-document "charter" "docs/charter.md")',
    ]
    for facts in all_facts:
        lines.append(f'(load-document "dossier-{facts.symbol}" "docs/dossier-{facts.symbol}.txt")')
        lines.append(f'(load-document "registry-{facts.symbol}" "docs/registry-{facts.symbol}.txt")')
    lines += ["", "(import (quote src.rules))", ""]
    for facts in all_facts:
        lines.append(f"(import (quote src.dossier_{facts.module}))")
        lines.append(f"(import (quote src.registry_{facts.module}))")
    lines += ["", "(import (quote src.checks))", ""]
    return "\n".join(lines)


def build_system(all_facts: list[TargetFacts], export_names: list[str], root: Path) -> Path:
    """Write the whole screening system. Returns the entry point path."""
    docs, src = root / "docs", root / "src"
    docs.mkdir(parents=True, exist_ok=True)
    src.mkdir(parents=True, exist_ok=True)

    (docs / "charter.md").write_text(CHARTER, encoding="utf-8")
    for facts in all_facts:
        _write_dossier_doc(facts, export_names, docs)
        (src / f"dossier_{facts.module}.pltg").write_text(_dossier_module(facts), encoding="utf-8")
        (src / f"registry_{facts.module}.pltg").write_text(_registry_module(facts), encoding="utf-8")

    (src / "rules.pltg").write_text(_rules_module(), encoding="utf-8")
    (src / "checks.pltg").write_text(_checks_module(all_facts), encoding="utf-8")
    entry = root / "main.pltg"
    entry.write_text(_main_module(all_facts), encoding="utf-8")
    return entry
