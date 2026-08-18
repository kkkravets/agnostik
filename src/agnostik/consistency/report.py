"""Stage 6 reports — proved divergences, not scores."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .engine import EngineResult
from .generate import TargetFacts

__all__ = ["write_json", "write_markdown", "adjudicate"]


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _standing(facts: TargetFacts, proven: bool) -> str:
    if not proven:
        if facts.off_target:
            return f"unproven — {facts.off_target} cited record(s) never name {facts.symbol}"
        if facts.retracted:
            return f"unproven — {facts.retracted} cited record(s) retracted"
        if facts.unresolved:
            return f"unproven — {facts.unresolved} cited identifier(s) do not resolve"
        if facts.subject_records == 0:
            return f"unproven — no cited record has {facts.symbol} as its subject"
        return "unproven"
    if facts.base_intact:
        return "proven — every cited record is subject-level"
    return (
        f"proven on a narrowed base — {facts.subject_records} of {facts.cited_records} "
        f"cited records are subject-level, the rest only mention {facts.symbol}"
    )


def adjudicate(all_facts: list[TargetFacts], engine: EngineResult) -> list[dict]:
    """Join each target's asserted verdict with what the engine proved about it."""
    rows = []
    for facts in all_facts:
        mod = facts.module
        failed = [i for i in engine.issues if i.short_name.startswith(f"{mod}-")]
        def value(node: str) -> str:
            return engine.values.get(f"src.checks.{mod}-{node}", "").strip()

        proven = value("verdict-proven").lower() in ("true", "1")
        rows.append(
            {
                "target": facts.symbol,
                "asserted_verdict": "promising" if facts.verdict else "rejected",
                "verdict_node": facts.verdict_node,
                "cited_records": facts.cited_records,
                "subject_records": facts.subject_records,
                "weak_attribution": facts.weak_attribution,
                "off_target": facts.off_target,
                "retracted": facts.retracted,
                "unresolved": facts.unresolved,
                "support_base_intact": facts.base_intact,
                "base_narrowed_by": facts.cited_records - facts.subject_records,
                "verdict_proven": proven,
                "engine_values": {
                    node: value(node)
                    for node in ("verdict-proven", "base-intact", "base-usable", "has-subject-record")
                },
                "failed_checks": [i.to_json() for i in failed],
                "standing": _standing(facts, proven),
            }
        )
    return rows


def write_json(rows: list[dict], engine: EngineResult, meta: dict, path: Path) -> None:
    path.write_text(
        json.dumps({"meta": meta, "engine": engine.to_json(), "targets": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_markdown(rows: list[dict], engine: EngineResult, meta: dict, path: Path) -> None:
    proven = sum(1 for r in rows if r["verdict_proven"])
    engine_count = engine.values.get("src.checks.proven-verdicts", "")
    lines = [
        "# Formal consistency screening",
        "",
        f"Generated {_stamp()} · engine integrity **{engine.integrity}** · "
        f"{len(engine.issues)} proved inconsistencies · "
        f"{engine_count or proven}/{len(rows)} verdicts proven (engine-computed)",
        "",
        "Two independent descriptions of the same citation set — what the dossier asserts, "
        "and what the registries returned — are declared as Parseltongue `diff`s. What follows "
        "is what the engine proved, on evidence it verified against quoted documents. "
        "Nothing here is weighted or scored.",
        "",
        "| target | asserted | cited | subject-level | off-target | retracted | unresolved | verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        standing = "proven" if r["verdict_proven"] else "**unproven**"
        lines.append(
            f"| {r['target']} | {r['asserted_verdict']} | {r['cited_records']} | "
            f"{r['subject_records']} | {r['off_target']} | {r['retracted']} | "
            f"{r['unresolved']} | {standing} |"
        )
    lines.append("")

    if engine.load_errors:
        lines += ["## Load errors", "", *[f"- `{e}`" for e in engine.load_errors], ""]

    divergences = [i for i in engine.issues if i.is_divergence]
    taint = [i for i in engine.issues if not i.is_divergence]

    lines += ["## Proved divergences", ""]
    if not divergences:
        lines.append("None — every declared comparison holds.")
    else:
        lines += [
            "Each row is a comparison the engine evaluated on both sides. "
            "`consequence` names what the divergence changes downstream.",
            "",
            "| check | dossier says | registry says | consequence |",
            "|---|---|---|---|",
        ]
        for issue in divergences:
            compared = f"`{issue.replace.split('.')[-1]}` = {issue.value_a}" if issue.replace else "—"
            against = f"`{issue.with_.split('.')[-1]}` = {issue.value_b}" if issue.with_ else "—"
            consequence = (
                ", ".join(
                    f"`{node.split('.')[-1]}` {vals[0]} → {vals[1]}"
                    for node, vals in list(issue.consequences.items())[:3]
                )
                or "—"
            )
            lines.append(f"| `{issue.short_name}` | {compared} | {against} | {consequence} |")
    lines.append("")

    if taint:
        lines += [
            "## Nodes the engine marked unsafe",
            "",
            "Derivations the engine will not vouch for, because they descend from a "
            "value that diverges or from evidence it could not verify.",
            "",
            "| node | type | where |",
            "|---|---|---|",
        ]
        for issue in taint:
            lines.append(f"| `{issue.short_name}` | {issue.type} | `{issue.loc}` |")
        lines.append("")

    for r in rows:
        lines += [f"## {r['target']} — {r['standing']}", ""]
        lines.append(
            f"The dossier rests on {r['cited_records']} records; the registries confirm "
            f"{r['subject_records']} of them name {r['target']} as the subject "
            f"({r['weak_attribution']} mention it only in passing, {r['off_target']} never name it)."
        )
        lines.append("")
        if r["failed_checks"]:
            lines.append("Failed checks:")
            lines += [f"- `{c['name']}` — {c['type']} at `{c['location']}`" for c in r["failed_checks"]]
            lines.append("")

    if engine.stats:
        lines += [
            "## Engine screening statistics",
            "",
            "```json",
            json.dumps(engine.stats, indent=1),
            "```",
            "",
        ]

    path.write_text("\n".join(lines), encoding="utf-8")
