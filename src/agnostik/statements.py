"""Load model-written Parseltongue statements into a System without losing any silently.

Two library behaviours make this necessary. A statement that reuses an existing
name replaces it: terms, axioms, theorems and diffs always, facts too under
``overridable=True``. And the parser stops at the first unmatched ``)`` without
an error, dropping every statement after it.

Here every statement is parsed on its own, names are namespaced per document,
and a name that is already taken is loaded under a new one next to a diff
against the original, so a disagreement shows up in the consistency report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parseltongue import System
from parseltongue.core.atoms import Symbol
from parseltongue.core.lang import PGStringParser, to_sexp

DIRECTIVES = frozenset({"fact", "defterm", "axiom", "derive", "diff"})


@dataclass
class LoadReport:
    statements: list[str] = field(default_factory=list)  # as loaded, replayable with load_statements
    names: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    renamed: list[dict] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)

    @property
    def source(self) -> str:
        return "".join(statement + "\n\n" for statement in self.statements)

    def summary(self) -> dict:
        return {"loaded": len(self.names), "failed": self.failed, "renamed": self.renamed, "repairs": self.repairs}


def dsl_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_statements(source: str) -> tuple[list[tuple[int, str]], list[str]]:
    """Top-level statements with their first line, plus notes on what was skipped."""
    pieces: list[tuple[int, str]] = []
    stray, outside = [], []
    depth = start = start_line = 0
    line, index, end = 1, 0, len(source)
    unterminated = False
    while index < end:
        char = source[index]
        if char == "\n":
            line += 1
        elif char == ";":
            newline = source.find("\n", index)
            index = end if newline < 0 else newline
            continue
        elif char == '"':
            index += 1
            while index < end and source[index] != '"':
                if source[index] == "\\":
                    index += 1
                elif source[index] == "\n":
                    line += 1
                index += 1
            if index >= end:
                unterminated = True
                break
            if depth == 0:
                outside.append(line)
        elif char == "(":
            if depth == 0:
                start, start_line = index, line
            depth += 1
        elif char == ")":
            if depth == 0:
                stray.append(line)
            else:
                depth -= 1
                if depth == 0:
                    pieces.append((start_line, source[start : index + 1]))
        elif depth == 0 and not char.isspace():
            outside.append(line)
        index += 1
    notes = []
    if stray:
        notes.append(f"ignored {len(stray)} unmatched ')' on line {_lines(stray)}")
    if outside:
        notes.append(f"ignored text outside any statement on line {_lines(outside)}")
    if depth or unterminated:
        notes.append(f"dropped an unfinished statement starting on line {start_line if depth else line}")
    return pieces, notes


def _lines(numbers: list[int]) -> str:
    return ", ".join(str(number) for number in dict.fromkeys(numbers))


def _is_directive(form) -> bool:
    return isinstance(form, (list, tuple)) and len(form) > 1 and str(form[0]) in DIRECTIVES


def _rename(form, qualify):
    if isinstance(form, Symbol):
        return form if str(form).startswith("?") else Symbol(qualify(str(form)))
    if isinstance(form, (list, tuple)):
        return type(form)(_rename(part, qualify) for part in form)
    return form


def known_names(system: System) -> set[str]:
    engine = system.engine
    return {*engine.facts, *engine.terms, *engine.axioms, *engine.theorems, *engine.diffs}


def load_statements(system: System, source: str, *, prefix: str = "") -> LoadReport:
    """Load each statement of ``source`` into ``system``, recording everything not loaded as written.

    With a ``prefix`` every name the source defines is namespaced under it, and a
    reference the model wrote without the prefix is resolved to the prefixed name.
    """
    report = LoadReport()
    pieces, report.repairs = split_statements(source or "")
    if not pieces:
        report.repairs.append("no statements in the output")
    forms = []
    for line, text in pieces:
        try:
            forms.append((line, PGStringParser.translate(text)))
        except Exception as exc:
            report.failed.append({"line": line, "statement": text[:120], "error": f"{type(exc).__name__}: {exc}"})
    defined = {str(form[1]) for _, form in forms if _is_directive(form)}
    engine = system.engine
    taken = known_names(system)

    def qualify(name: str) -> str:
        if not prefix or name.startswith(prefix):
            return name
        if name in defined or (name not in taken and prefix + name in taken):
            return prefix + name
        return name

    for line, form in forms:
        if not _is_directive(form):
            report.failed.append({"line": line, "statement": to_sexp(form)[:120], "error": "not a fact, defterm, axiom, derive or diff statement"})
            continue
        form = _rename(form, qualify)
        name = loaded_as = str(form[1])
        if name in taken:
            loaded_as = _unused(name, taken)
            form = type(form)((form[0], Symbol(loaded_as), *form[2:]))
        try:
            engine.execute(form)
        except Exception as exc:
            report.failed.append({"line": line, "statement": f"{form[0]} {loaded_as}", "error": f"{type(exc).__name__}: {exc}"})
            continue
        taken.add(loaded_as)
        report.statements.append(to_sexp(form))
        report.names.append(loaded_as)
        if loaded_as != name:
            diff = _unused(f"{name}.clash", taken)
            engine.register_diff(diff, name, loaded_as)
            taken.add(diff)
            report.statements.append(f"(diff {diff} :replace {name} :with {loaded_as})")
            report.renamed.append({"line": line, "name": name, "loaded_as": loaded_as, "diff": diff})
    return report


def _unused(name: str, taken: set[str]) -> str:
    if name not in taken:
        return name
    number = 2
    while f"{name}.{number}" in taken:
        number += 1
    return f"{name}.{number}"
