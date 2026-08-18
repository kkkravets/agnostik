"""Turn citation checks into Parseltongue input.

Stage 6 does not trust a JSON file it cannot quote. So stage 5 writes two
things: a registry snapshot document per target, and a .pltg whose facts quote
that document verbatim. The engine verifies those quotes itself, which is what
makes the stage-6 divergences provable rather than asserted.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .check import CitationCheck

__all__ = ["counters_for", "write_snapshots", "write_pltg", "module_name"]

COUNTER_KEYS = (
    "subject_records",
    "weak_attribution",
    "off_target",
    "title_drift",
    "retracted",
    "unresolved",
    "not_checked",
    "checked_total",
)


def module_name(symbol: str) -> str:
    return symbol.lower().replace("-", "_")


def _one_line(text: str, limit: int = 300) -> str:
    return " ".join((text or "").split())[:limit].rstrip()


def counters_for(checks: list[CitationCheck]) -> dict[str, int]:
    """The counters stage 6 diffs the dossier against."""
    by_status = Counter(c.status for c in checks)
    return {
        "subject_records": sum(1 for c in checks if c.gene_role == "title" and c.status == "sound"),
        "weak_attribution": by_status["weak-attribution"],
        "off_target": by_status["off-target"],
        "title_drift": by_status["title-drift"],
        "retracted": by_status["retracted"],
        "unresolved": by_status["unresolved"],
        "not_checked": by_status["not-checked"],
        "checked_total": len(checks),
    }


def write_snapshots(by_target: dict[str, list[CitationCheck]], docs_dir: Path) -> dict[str, dict[str, int]]:
    """One registry snapshot per target. Returns the counters keyed by target."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    all_counters: dict[str, dict[str, int]] = {}

    for symbol, checks in by_target.items():
        counters = counters_for(checks)
        all_counters[symbol] = counters
        lines = [
            f"Registry snapshot — {symbol}",
            f"Checked {stamp} against PubMed, ClinicalTrials.gov and UniProt",
            "",
            "## COUNTERS",
        ]
        lines += [f"VERIFIED {key}={counters[key]}" for key in COUNTER_KEYS]
        lines += ["", "## RECORDS"]
        for check in checks:
            lines.append(
                f"{check.source_type} {check.source_id} | status={check.status} | "
                f"gene_role={check.gene_role} | indication={check.indication_role} | "
                f"resolves={check.resolves}"
            )
            lines.append(f"REGISTRY TITLE: {_one_line(check.registry_title, 320)}")
            lines.append(f"DOSSIER QUOTE: {_one_line(check.quote, 320)}")
            if check.publication_types:
                lines.append(f"PUBLICATION TYPES: {', '.join(check.publication_types)}")
            for reason in check.reasons:
                lines.append(f"REASON: {_one_line(reason, 320)}")
            lines.append("")
        (docs_dir / f"registry-{symbol}.txt").write_text("\n".join(lines), encoding="utf-8")

    return all_counters


def _pltg_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def write_pltg(
    by_target: dict[str, list[CitationCheck]],
    counters: dict[str, dict[str, int]],
    src_dir: Path,
) -> list[str]:
    """One module per target, facts quoting that target's registry snapshot."""
    src_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    for symbol, checks in by_target.items():
        mod = module_name(symbol)
        doc = f"registry-{symbol}"
        out = [
            f"; {symbol} — registry verification results (stage 5)",
            f"; Every fact quotes docs/{doc}.txt, which is the recorded registry response.",
            "",
        ]
        for key in COUNTER_KEYS:
            value = counters[symbol][key]
            out += [
                f"(fact {key.replace('_', '-')} {value}",
                f'    :evidence (evidence "{doc}"',
                f'        :quotes ("VERIFIED {key}={value}")',
                f'        :explanation "Citations graded {key.replace("_", " ")} for {symbol}"))',
                "",
            ]

        for check in checks:
            if check.status in ("sound", "not-checked"):
                continue
            name = f"finding-{check.source_type}-{check.source_id}".replace(".", "-")
            quote = (
                f"{check.source_type} {check.source_id} | status={check.status} | "
                f"gene_role={check.gene_role} | indication={check.indication_role} | "
                f"resolves={check.resolves}"
            )
            explanation = check.reasons[0] if check.reasons else check.status
            out += [
                f"(fact {name} true",
                f'    :evidence (evidence "{doc}"',
                f'        :quotes ("{_pltg_str(quote)}")',
                f'        :explanation "{_pltg_str(_one_line(explanation, 240))}"))',
                "",
            ]

        out += [
            "; --- derived: how much of this dossier's citation base is subject-level ---",
            "(derive citations-all-sound (= weak-attribution 0) :using (weak-attribution))",
            "",
            "(derive citations-none-off-target (= off-target 0) :using (off-target))",
            "",
            "(derive citations-none-retracted (= retracted 0) :using (retracted))",
            "",
            "(derive citations-all-resolve (= unresolved 0) :using (unresolved))",
            "",
        ]
        path = src_dir / f"{mod}.pltg"
        path.write_text("\n".join(out), encoding="utf-8")
        written.append(mod)

    return written
