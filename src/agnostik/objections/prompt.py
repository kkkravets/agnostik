"""Prompt construction — the objection is written against the ledger, not against memory."""

from __future__ import annotations

from .backtrace import Ledger
from .bundle import Bundle
from .targets import TargetView

__all__ = ["SYSTEM_PROMPT", "build_user_prompt", "audit_flags", "REPAIR_TEMPLATE"]

SYSTEM_PROMPT = """You sit on a target-triage committee for colorectal cancer research. \
A formal reasoning engine (Parseltongue) has already produced a verdict for one target, \
together with the derivation chain and the quoted evidence each step rests on.

Your job is to write the OBJECTION: the strongest honest case against that verdict.

Hard rules — a violation makes the objection unusable:
1. Write EXACTLY five sentences. No preamble, no heading, no list, no closing remark.
2. Every sentence must cite at least one ledger key in square brackets, e.g. [E4] or [E4][E9].
3. Cite only keys that appear in the ledger below. Never invent a key, a PMID, an NCT id or a number.
4. Use only what the ledger and the derivation state. If something is absent, say it is absent \
rather than supplying it from your own knowledge.
5. Attack the reasoning, not the target: point at weak evidence, at counters that are zero or \
tiny, at a criterion that does the work, at a query artefact, at unresolved or unverified \
citations, at what the derivation never tested.
6. If the verdict is "promising", argue why it may not survive scrutiny. If the verdict is \
"rejected", argue why the rejection may be wrong.
7. Be concrete and quantitative. Name the counter, the criterion or the document you are \
objecting to.

Output the five sentences as one paragraph and nothing else."""

REPAIR_TEMPLATE = """Your previous objection was rejected by the verifier.

Previous attempt:
{previous}

Verifier findings:
{problems}

Rewrite it. Exactly five sentences, every sentence citing at least one valid ledger key from \
the list below, no invented keys, ids or numbers. Valid keys: {keys}"""


def audit_flags(view: TargetView, led: Ledger, bundle: Bundle) -> list[str]:
    """Mechanically detected weak spots — handed to the model as raw material.

    These are facts about the export, not opinions: zero counters, quotes the
    engine could not verify, external ids that do not resolve, claims with no
    document under them at all.
    """
    flags: list[str] = []

    for node in sorted(view.facts, key=lambda n: n.id):
        value = (node.value or "").strip()
        if value in ("0", "0.0"):
            flags.append(f"counter at zero: {node.id} = 0")

    unverified = [c for c in led if c.verified is False]
    if unverified:
        keys = ", ".join(c.key for c in unverified[:6])
        flags.append(f"quote not verified against its document: {keys}")

    unresolved = [c for c in led if c.resolved is False]
    if unresolved:
        keys = ", ".join(f"{c.key} ({c.source_type}:{c.source_id})" for c in unresolved[:6])
        flags.append(f"cited record does not resolve in its registry: {keys}")

    unchecked = [c for c in led if c.source_id and c.resolved is None]
    if unchecked:
        flags.append(f"{len(unchecked)} external ids were not resolution-checked in this run")

    doc_only = [c for c in led if c.source_type == "document"]
    if doc_only and len(doc_only) == len(led.citations):
        flags.append("no citation in this ledger reaches an external record — all evidence is internal document text")

    for claim in view.claims:
        if not any(c.node_id == claim.id for c in led) and not claim.inputs:
            flags.append(f"claim with no evidence and no inputs: {claim.id}")

    if bundle.tainted:
        tainted_here = [n.id for n in view.all_nodes if n.id in bundle.tainted]
        if tainted_here:
            reasons = {bundle.taint_reasons.get(nid, "") for nid in tainted_here}
            reason = next((r for r in reasons if r), "propagated from an unverified source")
            flags.append(f"engine marked {len(tainted_here)} node(s) tainted: {reason}")

    aggregate = [c for c in led if c.source_type == "document" and "=" in c.quote]
    if aggregate:
        flags.append(
            f"{len(aggregate)} of the decisive numbers are aggregate counters "
            "(a count of query hits), not findings from a specific study"
        )

    return flags


def _claim_lines(view: TargetView, bundle: Bundle) -> list[str]:
    lines = []
    for claim in sorted(view.claims, key=lambda n: (n.depth, n.id)):
        expr = claim.definition or claim.value
        inputs = ", ".join(claim.inputs) if claim.inputs else "-"
        lines.append(f"  {claim.id} = {claim.value}")
        if expr and expr != claim.value:
            lines.append(f"      rule: {expr}")
        lines.append(f"      from: {inputs}")
    return lines


def _fact_lines(view: TargetView) -> list[str]:
    lines = []
    for fact in sorted(view.facts, key=lambda n: n.id):
        if fact.id.split(".")[-1].startswith(("paper-", "trial-")):
            continue  # document anchors appear in the ledger, not as counters
        lines.append(f"  {fact.id} = {fact.value}")
    return lines


def build_user_prompt(
    view: TargetView,
    led: Ledger,
    bundle: Bundle,
    disease: str = "colorectal cancer",
    flags: list[str] | None = None,
) -> str:
    flags = flags if flags is not None else audit_flags(view, led, bundle)
    verdict_id = view.verdict_node.id if view.verdict_node else "(no verdict node)"

    parts = [
        f"TARGET: {view.symbol}",
        f"DISEASE: {disease}",
        f"ENGINE VERDICT: {view.label.upper()}  (node {verdict_id} = {view.verdict_node.value if view.verdict_node else '?'})",
        "",
        "DERIVATION — what the engine computed:",
        *_claim_lines(view, bundle),
        "",
        "COUNTERS the derivation consumed:",
        *_fact_lines(view),
        "",
        "EVIDENCE LEDGER — the only citable material:",
    ]

    for c in led:
        bits = [f"[{c.key}]"]
        bits.append(f"{c.source_type}:{c.source_id}" if c.source_id else f"doc:{c.doc}")
        if c.resolved is True:
            bits.append("(resolves")
            bits.append(f"— {c.resolved_title[:90]})" if c.resolved_title else "—)")
        elif c.resolved is False:
            bits.append("(DOES NOT RESOLVE)")
        elif c.source_id:
            bits.append("(resolution unchecked)")
        if c.verified is False:
            bits.append("(QUOTE UNVERIFIED)")
        head = " ".join(bits)
        parts.append(f'{head}: "{c.quote}"')
        if c.explanation:
            parts.append(f"      note: {c.explanation}")

    if flags:
        parts += ["", "AUDIT FLAGS — weak points the engine or the checker already found:"]
        parts += [f"  - {f}" for f in flags]

    parts += [
        "",
        f"Write the five-sentence objection to the {view.label.upper()} verdict on {view.symbol}.",
    ]
    return "\n".join(parts)
