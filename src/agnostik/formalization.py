"""Build the formal Parseltongue export consumed by objections.

A target is judged one document at a time. For every selected article or trial
record the model extracts quoted facts from that document alone, then answers
the criteria questions from those facts with their values hidden. The counting
and the verdict are statements this module writes from the criteria file, so no
model call reads more than one document's facts. A final fact-check and report
see a summary built rule by rule.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
import threading
from typing import Any

from parseltongue import System
from parseltongue.core.atoms import Evidence, Symbol
from parseltongue.core.inspect.probe_core_to_consequence import probe
from parseltongue.core.inspect.perspectives.visualisation.items import enrich_items, items_from_structure
from parseltongue.core.lang import to_sexp
from parseltongue.llm.prompts import pass1_messages, pass2_messages, pass3_messages, pass4_messages
from parseltongue.llm.resolve import resolve_references
from parseltongue.llm.tools import ANSWER_TOOL, DERIVE_TOOL, EXTRACT_TOOL, FACTCHECK_TOOL

from agnostik.candidates import PRESELECTED_ALIASES, PRESELECTED_CANDIDATES
from agnostik.criteria import Criteria, combination_source, count_name, load_criteria, met_name
from agnostik.evidence import TRIAL_TARGET_LINE
from agnostik.nebius import create_nebius_provider
from agnostik.objections.bundle import load_export
from agnostik.objections.targets import discover
from agnostik.pmc_full_text import REFERENCES_OMITTED_NOTE
from agnostik.statements import known_names, load_statements

DEFAULT_MAX_DOCUMENT_CHARS = 120_000
DEFAULT_ATTEMPTS = 2
DEFAULT_CRITERIA = Path(__file__).resolve().parents[2] / "criteria" / "target-shortlist.md"
# Bump when the prompts change: cached per-document answers are reused only under the same wording.
PROMPT_VERSION = "1"
# Lines the pipeline adds to a source file. They are not the record's own text, so the
# model never sees them and they can never be quoted as evidence.
PIPELINE_LINES = (TRIAL_TARGET_LINE, REFERENCES_OMITTED_NOTE)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FormalizationConfig:
    tumour_type: str
    cancer_term: str
    corpus_manifest: Path
    output_dir: Path
    targets: tuple[str, ...] = PRESELECTED_CANDIDATES
    target_aliases: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: dict(PRESELECTED_ALIASES))
    max_documents_per_target: int | None = None
    max_document_chars: int = DEFAULT_MAX_DOCUMENT_CHARS
    model: str | None = None
    base_url: str | None = None
    reasoning: bool | int | None = None
    criteria: Path = DEFAULT_CRITERIA
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        tumour_type = self.tumour_type.strip().upper()
        cancer_term = " ".join(self.cancer_term.split())
        targets = tuple(dict.fromkeys(target.strip().upper() for target in self.targets))
        corpus_manifest = Path(self.corpus_manifest).resolve()
        output_dir = Path(self.output_dir).resolve()
        if not tumour_type or not cancer_term:
            raise ValueError("tumour_type and cancer_term must not be empty")
        if not targets:
            raise ValueError("at least one target candidate is required")
        if self.max_documents_per_target is not None and self.max_documents_per_target < 1:
            raise ValueError("max_documents_per_target must be at least 1")
        if self.max_document_chars < 1:
            raise ValueError("max_document_chars must be at least 1")
        if self.max_output_tokens is not None and self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")
        # --overwrite rmtree's output_dir, which must therefore not contain the corpus.
        if output_dir in corpus_manifest.parents:
            raise ValueError("corpus_manifest must live outside output_dir")
        criteria = Path(self.criteria).resolve()
        if not criteria.is_file():
            raise FileNotFoundError(f"criteria file not found: {criteria}")
        load_criteria(criteria)  # fail on a malformed rule before any model call
        aliases = {
            symbol.strip().upper(): tuple(dict.fromkeys(name.strip() for name in names if name.strip() and name.strip().upper() != symbol.strip().upper()))
            for symbol, names in self.target_aliases.items()
        }
        object.__setattr__(self, "tumour_type", tumour_type)
        object.__setattr__(self, "cancer_term", cancer_term)
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "corpus_manifest", corpus_manifest)
        object.__setattr__(self, "output_dir", output_dir)
        object.__setattr__(self, "criteria", criteria)
        object.__setattr__(self, "target_aliases", {symbol: names for symbol, names in aliases.items() if names})


@dataclass(frozen=True, slots=True)
class TargetResult:
    target: str
    system: System
    verdict_name: str
    source_names: tuple[str, ...]
    output_dir: Path
    criteria: str = ""  # file name of the review-criteria document


@dataclass(frozen=True, slots=True)
class FormalizationRun:
    source_count: int
    target_count: int
    output_dir: Path
    export_path: Path
    reused_targets: int = 0
    model_calls: int = 0


@dataclass(frozen=True, slots=True)
class DocumentPlan:
    source: Path
    key: str  # the name the document is registered and cited under: the file stem
    kind: str  # "article" or "trial"
    text: str
    prompt_text: str
    extract_query: str
    judge_query: str
    fingerprint: str

    @property
    def prefix(self) -> str:
        return document_prefix(self.key)


@dataclass(frozen=True, slots=True)
class TargetPlan:
    target: str
    aliases: tuple[str, ...]
    documents: tuple[DocumentPlan, ...]
    excluded: tuple[dict, ...]
    query: str
    fingerprint: str

    @property
    def model_calls(self) -> int:
        """An extraction and a judgement per document, then one fact-check and one report."""
        return 2 * len(self.documents) + 2


class DocumentFailures(RuntimeError):
    """Some documents of a target failed after every attempt; the others are cached for --resume."""


def discover_sources(corpus_manifest: Path) -> list[Path]:
    """Resolve the article paths recorded in a corpus manifest."""

    corpus_manifest = Path(corpus_manifest)
    if not corpus_manifest.is_file():
        raise FileNotFoundError(f"corpus manifest not found: {corpus_manifest}")
    entries = json.loads(corpus_manifest.read_text(encoding="utf-8"))["articles"]
    sources = [(corpus_manifest.parent / entry["path"]).resolve() for entry in entries]
    if not sources:
        raise FileNotFoundError(f"corpus manifest lists no articles: {corpus_manifest}")
    missing = [path for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"{corpus_manifest} references {len(missing)} missing article(s), "
            f"starting with: {missing[0]}"
        )
    return sources


def _is_trial(source: Path) -> bool:
    return source.name.startswith("trial-")


def _kind(source: Path) -> str:
    return "trial" if _is_trial(source) else "article"


def select_target_documents(
    sources: Sequence[Path],
    target: str,
    *,
    aliases: Sequence[str] = (),
    max_documents: int | None = None,
) -> tuple[list[Path], list[dict]]:
    """Every source naming the target or an alias, most mentions first.

    With ``max_documents`` at most that many articles and that many trial records
    are kept. Every source left out is returned with the reason.
    """
    names = [target, *aliases]
    pattern = re.compile(r"\b(?:" + "|".join(re.escape(name) for name in names) + r")\b", re.IGNORECASE)
    ranked: dict[str, list] = {"article": [], "trial": []}
    excluded, keys = [], set()
    for source in sources:
        if source.stem in keys:
            excluded.append({"file": source.name, "reason": "another source has the same document key"})
            continue
        keys.add(source.stem)
        mentions = len(pattern.findall(source.read_text(encoding="utf-8", errors="replace")))
        if mentions:
            ranked[_kind(source)].append((-mentions, source.name, source))
        else:
            excluded.append({"file": source.name, "reason": f"does not mention {' or '.join(names)}"})
    selected = []
    for kind, rows in ranked.items():
        ordered = [source for _, _, source in sorted(rows)]
        kept = ordered if max_documents is None else ordered[:max_documents]
        selected += kept
        excluded += [
            {"file": source.name, "reason": f"over --max-documents-per-target ({max_documents} {kind}s)"}
            for source in ordered[len(kept):]
        ]
    if not selected:
        raise ValueError(f"no source mentions target {target}")
    return selected, excluded


def document_text(source: Path) -> str:
    """The source as Parseltongue sees it: its own text, without the lines the pipeline added."""
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    return "".join(line for line in lines if not line.strip().startswith(PIPELINE_LINES))


def _prompt_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text.rfind("\n\n", 0, limit)
    return text[: cut if cut > limit // 2 else limit]


def document_prefix(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-") + "."


def verdict_name(target: str) -> str:
    return f"{target.lower()}-verdict"


def _also(aliases: Sequence[str]) -> str:
    return f" (also written {', '.join(aliases)})" if aliases else ""


def _described(kind: str) -> str:
    return "a clinical-trial record" if kind == "trial" else "a published article"


def extract_query(key: str, kind: str, target: str, aliases: Sequence[str], config: FormalizationConfig, criteria: Criteria) -> str:
    questions = "\n".join(f"- {rule.ask}" for rule in criteria.for_kind(kind))
    return (
        f'Document "{key}" is {_described(kind)} collected for {target}{_also(aliases)} in {config.cancer_term} '
        f"({config.tumour_type}). Extract, as facts quoting this document verbatim, every finding in it that bears on "
        f"these questions about {target}:\n{questions}\n"
        f"Extract findings that count against {target} as carefully as findings for it. Quote only this document. "
        "Do not answer the questions and derive no verdict: a later step answers the questions from your facts."
        + (f"\nFrom the review criteria: {criteria.scope}" if criteria.scope else "")
    )


def judge_query(key: str, kind: str, target: str, aliases: Sequence[str], config: FormalizationConfig, criteria: Criteria) -> str:
    prefix = document_prefix(key)
    questions = "\n".join(f"- {prefix}{rule.key}: {rule.ask}" for rule in criteria.for_kind(kind))
    return (
        f'The facts above come from document "{key}", {_described(kind)} about {target}{_also(aliases)} in '
        f"{config.cancer_term}. Answer each question below for this document alone. Where its facts show that the answer "
        "is yes, write one derivation with exactly the name given, whose :using lists the facts that show it. Where they "
        f"do not, write nothing for that question. Write nothing else.\n{questions}"
    )


def review_query(target: str, aliases: Sequence[str], config: FormalizationConfig, criteria: Criteria) -> str:
    recorded = "".join(
        f"\nThe answer must also address {rule.id} {rule.title}: {' '.join(rule.text)}"
        for rule in criteria.rules
        if rule.threshold is None
    )
    return (
        f"Is {target}{_also(aliases)} a promising therapeutic target in {config.cancer_term} ({config.tumour_type}) under "
        f'the review criteria in "{criteria.name}"? {verdict_name(target)} was computed by the quoted rules from each '
        "document's answers, summarised below; the facts of documents that do not decide a rule on their own are not listed."
        + recorded
    )


def _digest(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def plan_target(config: FormalizationConfig, sources: Sequence[Path], criteria: Criteria, target: str) -> TargetPlan:
    aliases = config.target_aliases.get(target, ())
    selected, excluded = select_target_documents(sources, target, aliases=aliases, max_documents=config.max_documents_per_target)
    documents = []
    for source in selected:
        kind, key, text = _kind(source), source.stem, document_text(source)
        prompt = _prompt_text(text, config.max_document_chars)
        extract = extract_query(key, kind, target, aliases, config, criteria)
        judge = judge_query(key, kind, target, aliases, config, criteria)
        fingerprint = _digest(PROMPT_VERSION, config.model or "", text, prompt, extract, judge)
        documents.append(DocumentPlan(source, key, kind, text, prompt, extract, judge, fingerprint))
    query = review_query(target, aliases, config, criteria)
    fingerprint = _digest(
        PROMPT_VERSION, config.model or "", criteria.text, query, *(f"{doc.key}:{doc.fingerprint}" for doc in documents)
    )
    return TargetPlan(target, aliases, tuple(documents), tuple(excluded), query, fingerprint)


def _json_write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _find_verdict(system: System, target: str) -> str:
    wanted = verdict_name(target)
    names = [*system.engine.theorems, *system.engine.terms, *system.engine.facts]
    if wanted in names:
        return wanted
    matches = [name for name in names if name.lower() == wanted or name.lower().endswith(f".{wanted}")]
    if len(matches) != 1:
        raise ValueError(f"Parseltongue must derive exactly one {wanted} node; found {matches or 'none'}")
    return matches[0]


def _value(system: System, name: str) -> Any:
    try:
        return system.evaluate(Symbol(name))
    except Exception:
        return None


def _process_document(doc: DocumentPlan, folder: Path, resume: bool, complete: Callable[[list, dict, str], str]) -> tuple[str, dict]:
    """Extract and judge one document in a system of its own; returns its statements and record.

    Raw model outputs are cached next to the record, so ``--resume`` repeats no call
    whose prompt is unchanged.
    """
    record_path = folder / "record.json"
    if resume and record_path.is_file() and (folder / "module.pltg").is_file():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("fingerprint") == doc.fingerprint:
            return (folder / "module.pltg").read_text(encoding="utf-8"), {**record, "reused": True}
    folder.mkdir(parents=True, exist_ok=True)
    system = System(overridable=False)
    system.register_document(doc.key, doc.text)
    extract_cache = folder / "extract.json"
    if resume and extract_cache.is_file() and json.loads(extract_cache.read_text(encoding="utf-8")).get("fingerprint") == doc.fingerprint:
        extract_output = (folder / "extract.pltg").read_text(encoding="utf-8")
    else:
        extract_output = complete(pass1_messages(system.doc(), {doc.key: doc.prompt_text}, doc.extract_query), EXTRACT_TOOL, "dsl_output")
        (folder / "extract.pltg").write_text(extract_output, encoding="utf-8")
        _json_write(extract_cache, {"fingerprint": doc.fingerprint})
    extracted = load_statements(system, extract_output, prefix=doc.prefix)
    judge_output = complete(pass2_messages(system.doc(), system, doc.judge_query), DERIVE_TOOL, "dsl_output")
    (folder / "judge.pltg").write_text(judge_output, encoding="utf-8")
    judged = load_statements(system, judge_output, prefix=doc.prefix)
    module = extracted.source + judged.source
    (folder / "module.pltg").write_text(module, encoding="utf-8")
    record = {
        "document": doc.key,
        "file": doc.source.name,
        "kind": doc.kind,
        "fingerprint": doc.fingerprint,
        "chars": len(doc.text),
        "prompt_chars": len(doc.prompt_text),
        "truncated": len(doc.prompt_text) < len(doc.text),
        "facts": sum(name in system.engine.facts for name in extracted.names),
        "extract": extracted.summary(),
        "judge": judged.summary(),
    }
    _json_write(record_path, record)
    return module, {**record, "reused": False}


def _rule_answers(system: System, criteria: Criteria, plan: TargetPlan) -> tuple[dict[str, list[str]], dict[str, dict]]:
    """Per rule: the per-document results that answer it, and who answered yes, no or nothing."""
    taken = known_names(system)
    answers, rows = {}, {}
    for rule in criteria.rules:
        row = {"title": rule.title, "threshold": rule.threshold, "yes": [], "no": [], "unanswered": [], "not_boolean": []}
        names = []
        for doc in plan.documents:
            if doc.kind not in rule.kinds:
                continue
            name = doc.prefix + rule.key
            if name not in taken:
                row["unanswered"].append(doc.key)
                continue
            value = _value(system, name)
            if isinstance(value, bool):
                names.append(name)
                row["yes" if value else "no"].append(name)
            else:
                row["not_boolean"].append(name)
        answers[rule.id], rows[rule.id] = names, row
    return answers, rows


def _quoted_inputs(system: System, name: str) -> list[str]:
    engine = system.engine
    if name in engine.theorems:
        theorem = engine.theorems[name]
        inputs, shown = theorem.derivation, to_sexp(theorem.wff)
    elif name in engine.terms and engine.terms[name].definition is not None:
        shown = to_sexp(engine.terms[name].definition)
        inputs = sorted(dep for dep in engine.facts if re.search(rf"(?<![\w.-]){re.escape(dep)}(?![\w.-])", shown))
    else:
        return [f"    {name} = {_value(system, name)}"]
    lines = [f"    {name} := {shown}  (from: {', '.join(inputs) or '-'})"]
    for dep in inputs:
        fact = engine.facts.get(dep)
        if fact is None:
            continue
        origin = fact.origin
        if isinstance(origin, Evidence):
            quotes = " / ".join(f'"{quote}"' for quote in origin.quotes)
            unverified = "" if origin.is_grounded else "  (quote NOT verified)"
            lines.append(f"      {dep} = {fact.wff}  [fact] {quotes} ({origin.document}){unverified}")
        else:
            lines.append(f"      {dep} = {fact.wff}  [fact] origin: {origin}")
    return lines


def _short(value: Any, limit: int = 160) -> str:
    text = to_sexp(value) if isinstance(value, (list, tuple)) else repr(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _issue_names(items: Sequence) -> list[str]:
    return [str(item[0]) if isinstance(item, (list, tuple)) else str(getattr(item, "name", item)) for item in items]


def _review_state(system: System, criteria: Criteria, plan: TargetPlan, rows: Mapping[str, dict]) -> str:
    """What the fact-check and the report read instead of the full system state.

    Facts are quoted only where a document's answer decides a rule on its own (the
    rule holds at or below its threshold) and for every rule that is recorded and
    weighed rather than counted, so the summary grows with the rules, not the corpus.
    """
    engine, verdict = system.engine, verdict_name(plan.target)
    definition = engine.terms[verdict].definition if verdict in engine.terms else None
    lines = [
        "Verdict",
        f"  {verdict} = {_value(system, verdict)}  [term] := {to_sexp(definition) if definition is not None else '?'}",
        f'  rule {criteria.verdict_id}, quoted from "{criteria.name}": {" ".join(criteria.verdict_text)}',
        "",
    ]
    for heading, deciding in (("Rules the verdict counts", True), ("Rules recorded and weighed, not counted", False)):
        chosen = [rule for rule in criteria.rules if (rule.threshold is not None) == deciding]
        if not chosen:
            continue
        lines.append(heading)
        for rule in chosen:
            row, count = rows[rule.id], _value(system, count_name(rule))
            if deciding:
                lines.append(
                    f"  {met_name(rule)} = {_value(system, met_name(rule))}  [term]: {count_name(rule)} = {count}, "
                    f"needs at least {rule.threshold}  ({rule.id} {rule.title}: {' '.join(rule.text)})"
                )
            else:
                lines.append(f"  {count_name(rule)} = {count}  [term]  ({rule.id} {rule.title}: {' '.join(rule.text)})")
            lines.append(f"    yes ({len(row['yes'])}): {', '.join(row['yes']) or '-'}")
            if row["no"]:
                lines.append(f"    no ({len(row['no'])}): {', '.join(row['no'])}")
            if row["unanswered"]:
                lines.append(f"    not answered by {len(row['unanswered'])} document(s): {', '.join(row['unanswered'])}")
            if row["not_boolean"]:
                lines.append(f"    answers that are not true/false, not counted: {', '.join(row['not_boolean'])}")
            if not deciding or len(row["yes"]) <= rule.threshold:
                for name in row["yes"]:
                    lines += _quoted_inputs(system, name)
        lines.append("")
    if engine.diffs:
        lines.append("Diffs")
        for name in engine.diffs:
            try:
                result = system.eval_diff(name)
                lines.append(
                    f"  {name}: {result.replace} = {_short(result.value_a)} vs {result.with_} = {_short(result.value_b)}; "
                    f"{len(result.divergences)} dependent value(s) change"
                )
            except Exception as exc:
                lines.append(f"  {name}: could not be evaluated ({type(exc).__name__}: {exc})")
        lines.append("")
    report = system.consistency()
    lines.append("Consistency: " + ("consistent" if report.consistent else "issues found"))
    for entry in [*report.issues, *report.warnings]:
        names = _issue_names(entry.items)
        kind = getattr(entry.type, "value", entry.type)
        lines.append(f"  {kind} ({len(names)}): {', '.join(names)}")
    return "\n".join(lines)


def _review_messages(instructions: list[dict], state: str, query: str, closing: str) -> list[dict]:
    return [instructions[0], {"role": "user", "content": f"Evaluated system state (summary):\n\n{state}\n\nUser query: {query}\n\n{closing}"}]


def _run_target(
    plan: TargetPlan,
    config: FormalizationConfig,
    criteria: Criteria,
    *,
    resume: bool,
    attempts: int,
    document_workers: int,
    provider_factory: Callable[..., Any],
) -> tuple[TargetResult, dict, bool, int]:
    target_dir = config.output_dir / "targets" / plan.target.lower()
    manifest_path = target_dir / "manifest.json"
    sources = tuple(doc.source.name for doc in plan.documents)
    if resume and manifest_path.is_file() and (target_dir / "system.json").is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("status") == "complete" and previous.get("fingerprint") == plan.fingerprint:
            system = System.from_dict(json.loads((target_dir / "system.json").read_text(encoding="utf-8")), overridable=False)
            return TargetResult(plan.target, system, _find_verdict(system, plan.target), sources, target_dir, config.criteria.name), previous, True, 0
    target_dir.mkdir(parents=True, exist_ok=True)
    for stale in target_dir.iterdir():
        if stale.name != "documents":  # the per-document cache survives for --resume
            shutil.rmtree(stale) if stale.is_dir() else stale.unlink()

    local, lock, providers, calls = threading.local(), threading.Lock(), [], [0]

    def complete(messages: list, tool: dict, key: str) -> str:
        provider = getattr(local, "provider", None)
        if provider is None:
            provider = local.provider = provider_factory(
                model=config.model, base_url=config.base_url, reasoning=config.reasoning, max_output_tokens=config.max_output_tokens
            )
            with lock:
                providers.append(provider)
        for attempt in range(1, attempts + 1):
            with lock:
                calls[0] += 1
            try:
                return str(provider.complete(messages, [tool])[key])
            except InterruptedError:
                raise
            except Exception as exc:
                if attempt >= attempts:
                    raise
                log.warning("%s: %s call attempt %d/%d failed (%s: %s); retrying", plan.target, tool["function"]["name"], attempt, attempts, type(exc).__name__, exc)
        raise AssertionError("unreachable")

    try:
        outcomes, failures = {}, []

        def work(doc: DocumentPlan) -> None:
            try:
                outcomes[doc.key] = _process_document(doc, target_dir / "documents" / doc.key, resume, complete)
            except InterruptedError:
                raise
            except Exception as exc:
                failures.append(f"{doc.key} ({type(exc).__name__}: {exc})")

        if document_workers == 1:
            for doc in plan.documents:
                work(doc)
        else:
            with ThreadPoolExecutor(max_workers=document_workers, thread_name_prefix=f"{plan.target.lower()}-document") as executor:
                list(executor.map(work, plan.documents))
        if failures:
            raise DocumentFailures(
                f"{plan.target}: {len(failures)} of {len(plan.documents)} document(s) failed after {attempts} attempt(s): "
                + "; ".join(failures)
                + ". Finished documents are cached; rerun with --resume to retry the rest."
            )

        system = System(overridable=False)
        system.register_document(criteria.name, criteria.text)
        for doc in plan.documents:
            system.register_document(doc.key, doc.text)
        records = []
        for doc in plan.documents:
            module, record = outcomes[doc.key]
            if module.strip():
                replayed = load_statements(system, module)
                if replayed.failed or replayed.renamed:
                    record["replay"] = replayed.summary()
            records.append(record)

        answers, rows = _rule_answers(system, criteria, plan)
        combination = combination_source(criteria, verdict_name(plan.target), answers)
        combined = load_statements(system, combination)
        if combined.failed or combined.renamed:
            raise ValueError(f"{plan.target}: the criteria statements did not load cleanly: {combined.summary()}")
        verdict = _find_verdict(system, plan.target)
        for rule in criteria.rules:
            rows[rule.id]["count"] = _value(system, count_name(rule))
            if rule.threshold is not None:
                rows[rule.id]["met"] = _value(system, met_name(rule))

        check_output = complete(
            _review_messages(
                pass3_messages(system.doc(), System(), plan.query),
                _review_state(system, criteria, plan, rows),
                plan.query,
                "Cross-validate the system state. Introduce alternative computation paths, facts from other angles, and diffs. Call the factcheck tool.",
            ),
            FACTCHECK_TOOL,
            "dsl_output",
        )
        checked = load_statements(system, check_output)
        answer_output = complete(
            _review_messages(
                pass4_messages(System(), plan.query),
                _review_state(system, criteria, plan, rows),
                plan.query,
                "Write a clear report answering the query. Use [[type:name]] references for evidence. Call the answer tool.",
            ),
            ANSWER_TOOL,
            "markdown",
        )
        output = resolve_references(answer_output, system)
    finally:
        for provider in providers:
            close = getattr(provider, "close", None)
            if callable(close):
                close()

    passes = target_dir / "passes"
    passes.mkdir(exist_ok=True)
    (passes / "combine.pltg").write_text(combination, encoding="utf-8")
    (passes / "factcheck.pltg").write_text(check_output, encoding="utf-8")
    (passes / "answer.md").write_text(answer_output, encoding="utf-8")
    (target_dir / "answer.md").write_text(output.markdown, encoding="utf-8")
    _json_write(target_dir / "system.json", system.to_dict())
    _json_write(target_dir / "references.json", [asdict(ref) for ref in output.references])
    _json_write(target_dir / "consistency.json", output.consistency)
    record = {
        "target": plan.target,
        "status": "complete",
        "fingerprint": plan.fingerprint,
        "criteria": str(config.criteria),
        "aliases": list(plan.aliases),
        "query": plan.query,
        "verdict_node": verdict,
        "verdict": _value(system, verdict),
        "rules": rows,
        "sources": list(sources),
        "documents": records,
        "excluded": list(plan.excluded),
        "model_calls": calls[0],
        "factcheck": checked.summary(),
    }
    _json_write(manifest_path, record)
    return TargetResult(plan.target, system, verdict, sources, target_dir, config.criteria.name), record, False, calls[0]


def _prefixed_structure(result: TargetResult) -> tuple[list[dict], list[dict], list[dict]]:
    structure = probe(result.verdict_name, result.system.engine)
    items = items_from_structure(structure)
    enrich_items(items, structure)
    prefix = f"formal.{result.target.lower()}."
    names = {item["id"] for item in items}
    mapped = lambda name: prefix + name
    exported = []
    for item in items:
        inputs = []
        for raw in item.get("inputs") or []:
            name = raw if isinstance(raw, str) else raw.get("name", "")
            if name:
                inputs.append({"name": mapped(name), "inProbe": name in names})
        record = {**item, "id": mapped(item["id"]), "module": f"formal.{result.target.lower()}"}
        record["inputs"] = inputs
        exported.append(record)
    layers, edges = [], []
    for layer in structure.layers:
        nodes = []
        for consumer in layer.consumers:
            if consumer.name == "__output__":
                continue
            nodes.append({"name": mapped(consumer.name), "kind": str(consumer.kind), "value": str(consumer.value)})
            for group, edge_type in ((consumer.uses, "uses"), (consumer.declares, "declares"), (consumer.pulls, "pulls")):
                edges.extend({"source": mapped(source.name), "target": mapped(consumer.name), "type": edge_type} for source in group)
        if nodes:
            layers.append({"depth": layer.depth, "nodes": nodes})
    return exported, layers, edges


def build_objections_export(results: Sequence[TargetResult]) -> dict[str, Any]:
    data, layers, edges = [], [], []
    for result in results:
        target_data, target_layers, target_edges = _prefixed_structure(result)
        data.extend(target_data)
        layers.extend(target_layers)
        edges.extend(target_edges)
    # Documents are registered under their file stem; this maps each back to the real file name.
    sources = {
        Path(name).stem: name
        for result in results
        for name in (*result.source_names, *([result.criteria] if result.criteria else []))
    }
    return {
        "DATA": data,
        "STRUCTURE_DATA": data,
        "SOURCES": sources,
        "LAYERS": {"layers": layers, "edges": edges},
        "TAINT_DATA": {"sources": [], "tainted": [], "reasons": {}},
    }


def validate_objections_export(export_path: Path, targets: Sequence[str]) -> None:
    views = discover(load_export(export_path), list(targets))
    problems = []
    for view in views:
        if view.missing or view.verdict_node is None:
            problems.append(f"{view.symbol}: verdict missing")
        elif view.verdict is None:
            problems.append(f"{view.symbol}: verdict is not Boolean")
        if not any(fact.is_grounded for fact in view.facts):
            problems.append(f"{view.symbol}: no verified quoted fact")
    if problems:
        raise ValueError("Objections export contract failed: " + "; ".join(problems))


def export_completed_targets(
    output_dir: Path,
    targets: Sequence[str],
    *,
    filename: str = "formal-system.partial.json",
) -> tuple[Path, tuple[str, ...]]:
    """Build an objections-compatible export from successfully completed targets."""

    output_dir = Path(output_dir).resolve()
    results = []
    for target in targets:
        target = target.strip().upper()
        target_dir = output_dir / "targets" / target.lower()
        manifest_path = target_dir / "manifest.json"
        system_path = target_dir / "system.json"
        if not (manifest_path.is_file() and system_path.is_file()):
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete":
            continue
        system = System.from_dict(
            json.loads(system_path.read_text(encoding="utf-8")),
            overridable=True,
        )
        verdict = _find_verdict(system, target)
        results.append(
            TargetResult(
                target,
                system,
                verdict,
                tuple(manifest.get("sources") or ()),
                target_dir,
                Path(manifest["criteria"]).name if manifest.get("criteria") else "",
            )
        )
    if not results:
        raise ValueError(f"no completed Formalization targets found in: {output_dir}")
    export_path = output_dir / filename
    _json_write(export_path, build_objections_export(results))
    completed_targets = tuple(result.target for result in results)
    validate_objections_export(export_path, completed_targets)
    return export_path, completed_targets


def run_formalization(
    config: FormalizationConfig,
    *,
    overwrite: bool = False,
    resume: bool = False,
    max_workers: int = 1,
    document_workers: int = 1,
    max_attempts: int = DEFAULT_ATTEMPTS,
    provider_factory: Callable[..., Any] = create_nebius_provider,
) -> FormalizationRun:
    if max_workers < 1 or document_workers < 1:
        raise ValueError("max_workers and document_workers must be at least 1")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    sources = discover_sources(config.corpus_manifest)
    criteria = load_criteria(config.criteria)
    if config.output_dir.exists() and not (overwrite or resume):
        raise FileExistsError(f"output already exists: {config.output_dir}; use --resume or --overwrite")
    if overwrite and config.output_dir.exists():
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    plans = [plan_target(config, sources, criteria, target) for target in config.targets]

    def run_target(plan: TargetPlan) -> tuple[TargetResult, dict, bool, int]:
        return _run_target(
            plan,
            config,
            criteria,
            resume=resume,
            attempts=max_attempts,
            document_workers=document_workers,
            provider_factory=provider_factory,
        )

    if max_workers == 1:
        completed = [run_target(plan) for plan in plans]
    else:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(plans)), thread_name_prefix="formalization") as executor:
            completed = list(executor.map(run_target, plans))

    results = [result for result, _, _, _ in completed]
    records = [record for _, record, _, _ in completed]
    reused = sum(was_reused for _, _, was_reused, _ in completed)
    calls = sum(count for _, _, _, count in completed)
    export_path = config.output_dir / "formal-system.json"
    _json_write(export_path, build_objections_export(results))
    validate_objections_export(export_path, config.targets)
    _json_write(
        config.output_dir / "manifest.json",
        {
            "status": "complete",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tumour_type": config.tumour_type,
            "cancer_term": config.cancer_term,
            "corpus_manifest": str(config.corpus_manifest),
            "criteria": str(config.criteria),
            "source_count": len(sources),
            "model_calls": calls,
            "targets": records,
            "export": export_path.name,
        },
    )
    return FormalizationRun(len(sources), len(results), config.output_dir, export_path, reused, calls)
