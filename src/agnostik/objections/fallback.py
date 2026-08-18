"""Offline objection composer — used by --dry-run, and when no key is present.

It writes the same shape the model is asked for: five cited sentences built
only from the ledger and the audit flags. It is deliberately mechanical —
its job is to exercise verification, backtrace and reporting without spend,
not to sound like a reviewer.
"""

from __future__ import annotations

from .backtrace import Ledger
from .targets import TargetView

__all__ = ["compose"]


def _key_for(led: Ledger, predicate, default_index: int = 0) -> str:
    for c in led:
        if predicate(c):
            return c.key
    return led.citations[default_index].key if led.citations else "E1"


def compose(view: TargetView, led: Ledger, flags: list[str]) -> str:
    if not led.citations:
        return "No ledger entries were available for this target."

    counter_key = _key_for(led, lambda c: "=" in c.quote)
    rule_key = _key_for(led, lambda c: c.doc == "charter" or "criterion" in (c.explanation or "").lower())
    record_key = _key_for(led, lambda c: c.source_type in ("pmid", "nct"))
    unresolved = [c for c in led if c.resolved is False]
    unchecked = [c for c in led if c.source_id and c.resolved is None]
    zero_flags = [f for f in flags if f.startswith("counter at zero")]

    verdict_word = "promising" if view.verdict else "rejected"
    sentences = [
        f"The {verdict_word} verdict on {view.symbol} rests on aggregate query counters rather than on "
        f"any single study result [{counter_key}].",
        f"The criterion that does the deciding is stated in the charter, not derived from the data, so the "
        f"verdict moves whenever that threshold moves [{rule_key}].",
        (
            f"The zero counter in this dossier is a property of the query as issued, not established absence "
            f"of evidence [{counter_key}]."
            if zero_flags
            else f"The literature support reduces to a small number of indexed records, which is thin ground "
            f"for a {verdict_word} call [{record_key}]."
        ),
        (
            f"At least one cited record does not resolve in its registry, so part of the chain cannot be read "
            f"back to a source [{unresolved[0].key}]."
            if unresolved
            else f"Resolution of {len(unchecked)} cited identifiers was not checked in this run, so their "
            f"backing is asserted rather than confirmed [{record_key}]."
            if unchecked
            else f"Every cited identifier resolves, but resolution only proves the record exists, not that it "
            f"supports the claim made from it [{record_key}]."
        ),
        f"Nothing in the derivation tests {view.symbol} against a colorectal-specific outcome, so the verdict "
        f"should be read as a triage signal only [{rule_key}].",
    ]
    return " ".join(sentences)
