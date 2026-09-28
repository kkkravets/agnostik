"""Review criteria: the rules every target is judged by, read from a Markdown file.

Each ``## <ID> <title>`` section states its rule as prose, which is the text
quoted as evidence, followed by indented lines the pipeline reads::

    applies to: publications | trials | publications and trials
    ask: <yes/no question put to each such document>
    met when: at least <N> documents answer yes

A rule that is recorded and weighed but never decides the verdict carries the
bare line ``record only`` instead of ``met when``. One section carries
``verdict: <rule ids joined by and, or, not and parentheses>``. Sections without
indented lines, such as a provenance rule, are prose only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from agnostik.statements import dsl_string

KINDS = {
    "publications": frozenset({"article"}),
    "trials": frozenset({"trial"}),
    "publications and trials": frozenset({"article", "trial"}),
}
_FIELDS = {"applies to", "ask", "met when", "verdict"}
_HEADING = re.compile(r"^##\s+(\S+)\s*(.*)$")
_TOKEN = re.compile(r"\(|\)|[^\s()]+")


@dataclass(frozen=True, slots=True)
class Criterion:
    id: str
    title: str
    text: tuple[str, ...]
    kinds: frozenset[str]
    ask: str
    threshold: int | None  # None: recorded and weighed, never part of the verdict

    @property
    def key(self) -> str:
        return self.id.lower()


@dataclass(frozen=True, slots=True)
class Criteria:
    name: str  # document key the file is registered under
    text: str
    scope: str
    rules: tuple[Criterion, ...]
    verdict: str | tuple
    verdict_id: str
    verdict_text: tuple[str, ...]
    verdict_expression: str

    def for_kind(self, kind: str) -> list[Criterion]:
        return [rule for rule in self.rules if kind in rule.kinds]

    def describe(self) -> list[dict]:
        rows = [
            {
                "rule": f"{rule.id} {rule.title}",
                "applies_to": sorted(rule.kinds),
                "ask": rule.ask,
                "met_when": f"at least {rule.threshold} document(s) answer yes" if rule.threshold is not None else "record only",
                "quoted": " ".join(rule.text),
            }
            for rule in self.rules
        ]
        rows.append({"rule": self.verdict_id, "verdict": self.verdict_expression, "quoted": " ".join(self.verdict_text)})
        return rows


def load_criteria(path: Path) -> Criteria:
    path = Path(path)
    return parse_criteria(path.stem, path.read_text(encoding="utf-8"))


def parse_criteria(name: str, text: str) -> Criteria:
    scope, sections, current = [], [], None
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            current = {"id": heading[1], "title": heading[2].strip(), "prose": [], "fields": {}, "flags": set()}
            sections.append(current)
        elif current is None:
            if line.strip() and not line.startswith("#"):
                scope.append(line.strip())
        elif line.startswith(("    ", "\t")) and line.strip():
            key, separator, value = line.strip().partition(":")
            if separator:
                if key.strip().lower() not in _FIELDS:
                    raise ValueError(f"{name}: rule {current['id']} has an unknown line {line.strip()!r}")
                current["fields"][key.strip().lower()] = value.strip()
            elif line.strip().lower() == "record only":
                current["flags"].add("record only")
            else:
                raise ValueError(f"{name}: rule {current['id']} has an unknown line {line.strip()!r}")
        elif line.strip():
            current["prose"].append(line.strip())

    rules, verdict = [], None
    for section in sections:
        fields, where = section["fields"], f"{name}: rule {section['id']}"
        if "verdict" in fields:
            if verdict is not None:
                raise ValueError(f"{name}: more than one rule carries a 'verdict:' line")
            verdict = section
            continue
        if not fields and not section["flags"]:
            continue
        if not section["prose"]:
            raise ValueError(f"{where} has no prose line to quote")
        kinds = KINDS.get(fields.get("applies to", "").lower())
        if kinds is None:
            raise ValueError(f"{where}: 'applies to' must be one of: {', '.join(KINDS)}")
        if not fields.get("ask"):
            raise ValueError(f"{where}: missing the 'ask' question")
        if "record only" in section["flags"]:
            threshold = None
        else:
            met = re.fullmatch(r"at least (\d+)\b.*", fields.get("met when", ""))
            if not met or int(met[1]) < 1:
                raise ValueError(f"{where}: needs 'met when: at least N documents answer yes' (N >= 1) or 'record only'")
            threshold = int(met[1])
        rules.append(Criterion(section["id"], section["title"], tuple(section["prose"]), kinds, fields["ask"], threshold))

    ids = [rule.id.upper() for rule in rules]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name}: rule ids must be unique")
    if verdict is None:
        raise ValueError(f"{name}: no rule carries a 'verdict:' line")
    if not verdict["prose"]:
        raise ValueError(f"{name}: rule {verdict['id']} has no prose line to quote")
    tree = parse_verdict(verdict["fields"]["verdict"])
    deciding = {rule.id.upper(): rule for rule in rules if rule.threshold is not None}
    unknown = sorted(rule for rule in _rule_ids(tree) if rule.upper() not in deciding)
    if unknown:
        raise ValueError(f"{name}: the verdict names {', '.join(unknown)}, which are not rules with a 'met when' line")
    tree = _canonical(tree, {rule_id: rule.id for rule_id, rule in deciding.items()})
    return Criteria(
        name, text, " ".join(scope), tuple(rules), tree, verdict["id"], tuple(verdict["prose"]), verdict["fields"]["verdict"]
    )


def parse_verdict(expression: str) -> str | tuple:
    """``R1 and (R3 or not R4)`` as a tree of ``("and", a, b)``, ``("not", a)`` and rule ids."""
    tokens, position = _TOKEN.findall(expression), 0

    def peek() -> str | None:
        return tokens[position].lower() if position < len(tokens) else None

    def take() -> str:
        nonlocal position
        position += 1
        return tokens[position - 1]

    def either():
        node = both()
        while peek() == "or":
            take()
            node = ("or", node, both())
        return node

    def both():
        node = single()
        while peek() == "and":
            take()
            node = ("and", node, single())
        return node

    def single():
        token = peek()
        if token == "not":
            take()
            return ("not", single())
        if token == "(":
            take()
            node = either()
            if peek() != ")":
                raise ValueError(f"verdict {expression!r}: missing ')'")
            take()
            return node
        if token in (None, "and", "or", ")"):
            raise ValueError(f"verdict {expression!r}: expected a rule id")
        return take()

    tree = either()
    if position != len(tokens):
        raise ValueError(f"verdict {expression!r}: unexpected {tokens[position]!r}")
    return tree


def render_verdict(tree: str | tuple, name_for) -> str:
    if isinstance(tree, str):
        return name_for(tree)
    operator, *operands = tree
    return f"({operator} {' '.join(render_verdict(operand, name_for) for operand in operands)})"


def _rule_ids(tree: str | tuple) -> set[str]:
    return {tree} if isinstance(tree, str) else set().union(*(_rule_ids(operand) for operand in tree[1:]))


def _canonical(tree: str | tuple, ids: dict[str, str]) -> str | tuple:
    if isinstance(tree, str):
        return ids[tree.upper()]
    return (tree[0], *(_canonical(operand, ids) for operand in tree[1:]))


def count_name(rule: Criterion) -> str:
    return f"criteria.{rule.key}-count"


def met_name(rule: Criterion) -> str:
    return f"criteria.{rule.key}-met"


def combination_source(criteria: Criteria, verdict_name: str, answers: dict[str, list[str]]) -> str:
    """Statements that count each rule's yes-answers and decide the verdict.

    ``answers`` maps a rule id to the names of the per-document results that
    answer it. Every statement quotes its rule from the criteria document.
    """

    def evidence(lines: tuple[str, ...], explanation: str) -> str:
        quotes = " ".join(dsl_string(line) for line in lines)
        return f"(evidence {dsl_string(criteria.name)} :quotes ({quotes}) :explanation {dsl_string(explanation)})"

    statements = []
    for rule in criteria.rules:
        names = answers.get(rule.id, [])
        # Parseltongue's + takes exactly two arguments.
        total = "0"
        for name in reversed(names):
            total = f"(if {name} 1 0)" if total == "0" else f"(+ (if {name} 1 0) {total})"
        statements.append(
            f"(defterm {count_name(rule)} {total}\n  :evidence {evidence(rule.text, f'{rule.id} {rule.title}: documents answering yes')})"
        )
        if rule.threshold is not None:
            statements.append(
                f"(defterm {met_name(rule)} (>= {count_name(rule)} {rule.threshold})\n"
                f"  :evidence {evidence(rule.text, f'{rule.id} {rule.title}: met when at least {rule.threshold} documents answer yes')})"
            )
    by_id = {rule.id: rule for rule in criteria.rules}
    decision = render_verdict(criteria.verdict, lambda rule_id: met_name(by_id[rule_id]))
    statements.append(f"(defterm {verdict_name} {decision}\n  :evidence {evidence(criteria.verdict_text, f'{criteria.verdict_id}: the verdict rule')})")
    return "\n\n".join(statements) + "\n"
