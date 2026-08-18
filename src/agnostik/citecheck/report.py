"""Stage 5 reports."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .check import STATUS_ORDER, CitationCheck

__all__ = ["write_json", "write_markdown"]

_BAD = {"unresolved", "retracted", "off-target", "title-drift"}


def write_json(by_target: dict[str, list[CitationCheck]], counters: dict, meta: dict, path: Path) -> None:
    payload = {
        "meta": meta,
        "targets": {
            symbol: {
                "counters": counters.get(symbol, {}),
                "citations": [c.to_json() for c in checks],
            }
            for symbol, checks in by_target.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(by_target: dict[str, list[CitationCheck]], counters: dict, meta: dict, path: Path) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    every = [c for checks in by_target.values() for c in checks]
    overall = Counter(c.status for c in every)

    lines = [
        "# Citation resolving check",
        "",
        f"Generated {stamp} · {len(every)} citations across {len(by_target)} targets · "
        f"export `{meta.get('export', 'n/a')}`",
        "",
        "Resolution alone proves a record exists. These grades ask the harder question: "
        "does the record say what the dossier claims it says.",
        "",
        "| status | count | meaning |",
        "|---|---|---|",
    ]
    meanings = {
        "sound": "resolves, title matches, the attributed gene is the subject of the record",
        "weak-attribution": "resolves, but the gene appears only in the abstract — it is not what the record is about",
        "title-drift": "resolves, but the quoted title no longer matches the registry title",
        "off-target": "resolves, and the attributed gene appears nowhere in the record",
        "retracted": "resolves to a retracted paper or an expression of concern",
        "unresolved": "the registry returns no record for this identifier",
        "not-checked": "registry not consulted in this run",
    }
    for status in STATUS_ORDER:
        if overall.get(status):
            lines.append(f"| `{status}` | {overall[status]} | {meanings[status]} |")
    lines.append("")

    for symbol, checks in by_target.items():
        counts = counters.get(symbol, {})
        lines += [
            f"## {symbol}",
            "",
            f"{counts.get('checked_total', 0)} citations checked — "
            f"{counts.get('subject_records', 0)} subject-level, "
            f"{counts.get('weak_attribution', 0)} weak attribution, "
            f"{counts.get('off_target', 0)} off target, "
            f"{counts.get('unresolved', 0)} unresolved, "
            f"{counts.get('retracted', 0)} retracted",
            "",
        ]
        flagged = [c for c in checks if c.status != "sound"]
        if not flagged:
            lines += ["Every citation is subject-level and resolves.", ""]
            continue
        lines += ["| key | id | status | gene | indication | registry title |", "|---|---|---|---|---|---|"]
        for c in flagged:
            title = (c.registry_title or "—").replace("|", "\\|")[:70]
            link = f"[{c.source_id}]({c.url})" if c.url else c.source_id
            mark = f"**{c.status}**" if c.status in _BAD else c.status
            lines.append(
                f"| {c.key} | {link} | {mark} | {c.gene_role} | {c.indication_role} | {title} |"
            )
        lines.append("")
        for c in flagged:
            for reason in c.reasons:
                lines.append(f"- `{c.source_id}` — {reason}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
