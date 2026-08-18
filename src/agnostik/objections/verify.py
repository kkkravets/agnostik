"""Grounding gate for a generated objection.

The model is asked for five sentences, each carrying citation keys. This
module checks that it delivered exactly that, that every key exists, that
no external id or number was invented, and it attaches the resolved
backtrace to each sentence so a reader can walk from any claim in the
objection down to the quote and the source record it came from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .backtrace import Citation, Ledger

__all__ = ["SentenceCheck", "VerifiedObjection", "verify", "split_sentences"]

_KEY_RX = re.compile(r"\[([A-Za-z]+\d+)\]")
_PMID_RX = re.compile(r"\bPMID[:\s]*([0-9]{5,9})\b", re.IGNORECASE)
_NCT_RX = re.compile(r"\b(NCT[0-9]{8})\b", re.IGNORECASE)
_NUMBER_RX = re.compile(r"(?<![\w./-])(\d+(?:\.\d+)?)\s?%?(?![\w/-])")
_ABBREV = r"(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bcf)(?<!\bFig)(?<!\bNo)(?<!\bph)(?<!\bDr)(?<!\bal)"
_SENT_SPLIT_RX = re.compile(rf"{_ABBREV}(?<=[.!?])[\)\]\"']*\s+(?=[A-Z0-9(\[])")

# Numbers a sentence may use without the ledger stating them: ordinals and
# criterion labels that name the charter itself (C1..C9, phase 1..4).
_STRUCTURAL_NUMBER_CONTEXT = re.compile(r"\b(C\d|phase\s*\d|Phase\s*\d|stage\s*\d)\b")


def split_sentences(text: str) -> list[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    parts = [p.strip() for p in _SENT_SPLIT_RX.split(cleaned) if p.strip()]
    return parts


@dataclass
class SentenceCheck:
    index: int
    text: str
    keys: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def grounded(self) -> bool:
        return not self.problems

    def to_json(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "keys": self.keys,
            "grounded": self.grounded,
            "problems": self.problems,
            "warnings": self.warnings,
            "backtrace": [
                {
                    "key": c.key,
                    "node": c.node_id,
                    "doc": c.doc,
                    "quote": c.quote,
                    "source": {"type": c.source_type, "id": c.source_id, "url": c.url},
                    "resolves": c.resolved,
                    "resolved_title": c.resolved_title,
                    "quote_verified": c.verified,
                }
                for c in self.citations
            ],
        }


@dataclass
class VerifiedObjection:
    text: str
    sentences: list[SentenceCheck] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and all(s.grounded for s in self.sentences)

    @property
    def cited_keys(self) -> list[str]:
        seen: list[str] = []
        for s in self.sentences:
            for k in s.keys:
                if k not in seen:
                    seen.append(k)
        return seen

    def failure_report(self) -> str:
        lines = list(self.problems)
        for s in self.sentences:
            for p in s.problems:
                lines.append(f"sentence {s.index}: {p}")
        return "\n".join(f"- {line}" for line in lines) or "- (no findings)"

    def to_json(self) -> dict:
        return {
            "text": self.text,
            "verified": self.ok,
            "sentence_count": len(self.sentences),
            "problems": self.problems,
            "warnings": self.warnings,
            "cited_keys": self.cited_keys,
            "sentences": [s.to_json() for s in self.sentences],
        }


def _ledger_numbers(led: Ledger) -> set[str]:
    numbers: set[str] = set()
    for c in led:
        for blob in (c.quote, c.explanation, c.node_value, c.resolved_title, c.node_id):
            for m in _NUMBER_RX.finditer(blob or ""):
                numbers.add(m.group(1))
        if c.source_id:
            numbers.add(c.source_id)
    return numbers


def verify(text: str, led: Ledger, expected_sentences: int = 5) -> VerifiedObjection:
    result = VerifiedObjection(text=(text or "").strip())
    sentences = split_sentences(text)

    if not sentences:
        result.problems.append("the model returned no text")
        return result
    if len(sentences) != expected_sentences:
        result.problems.append(
            f"expected {expected_sentences} sentences, got {len(sentences)}"
        )

    ledger_numbers = _ledger_numbers(led)
    ledger_pmids = {c.source_id for c in led if c.source_type == "pmid"}
    ledger_ncts = {c.source_id.upper() for c in led if c.source_type == "nct"}

    for i, sentence in enumerate(sentences, start=1):
        check = SentenceCheck(index=i, text=sentence)
        raw_keys = _KEY_RX.findall(sentence)

        for key in raw_keys:
            cit = led.by_key(key)
            if cit is None:
                check.problems.append(f"cites unknown key [{key}] — not in the ledger")
                continue
            if key not in check.keys:
                check.keys.append(key)
                check.citations.append(cit)

        if not check.keys and not check.problems:
            check.problems.append("no citation — every sentence must cite at least one ledger key")

        for pmid in _PMID_RX.findall(sentence):
            if pmid not in ledger_pmids:
                check.problems.append(f"names PMID {pmid}, which is not in the ledger")
        for nct in _NCT_RX.findall(sentence):
            if nct.upper() not in ledger_ncts:
                check.problems.append(f"names {nct.upper()}, which is not in the ledger")

        bare = _KEY_RX.sub(" ", sentence)
        for m in _NUMBER_RX.finditer(bare):
            number = m.group(1)
            if number in ledger_numbers:
                continue
            window = bare[max(0, m.start() - 12) : m.end() + 12]
            if _STRUCTURAL_NUMBER_CONTEXT.search(window):
                continue
            check.warnings.append(f"number {number} does not appear in any cited quote")

        for cit in check.citations:
            if cit.resolved is False:
                check.warnings.append(
                    f"[{cit.key}] cites {cit.source_type}:{cit.source_id}, which does not resolve"
                )
            if cit.verified is False:
                check.warnings.append(f"[{cit.key}] rests on a quote the engine could not verify")

        result.sentences.append(check)

    if result.sentences and not any(s.keys for s in result.sentences):
        result.problems.append("the objection cites nothing at all")

    return result
