"""Build the formal Formalization Parseltongue export consumed by objections."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
from typing import Any

from parseltongue import System
from parseltongue.llm import Pipeline, PipelineResult
from parseltongue.core.inspect.probe_core_to_consequence import probe
from parseltongue.core.inspect.perspectives.visualisation.items import enrich_items, items_from_structure

from agnostik.candidates import PRESELECTED_CANDIDATES
from agnostik.nebius import create_nebius_provider
from agnostik.objections.bundle import load_export
from agnostik.objections.targets import discover

DEFAULT_MAX_DOCUMENTS_PER_TARGET = 10
DEFAULT_MAX_TARGET_CHARS = 250_000
# Trial records are short; without a reserved share the few long articles use the whole budget.
TRIAL_CHAR_SHARE = 0.2
DEFAULT_TARGET_ATTEMPTS = 2

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FormalizationConfig:
    tumour_type: str
    cancer_term: str
    corpus_manifest: Path
    output_dir: Path
    targets: tuple[str, ...] = PRESELECTED_CANDIDATES
    max_documents_per_target: int = DEFAULT_MAX_DOCUMENTS_PER_TARGET
    max_target_chars: int = DEFAULT_MAX_TARGET_CHARS
    model: str | None = None
    base_url: str | None = None
    reasoning: bool | int | None = None

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
        if self.max_documents_per_target < 1 or self.max_target_chars < 1:
            raise ValueError("document and character limits must be at least 1")
        # --overwrite rmtree's output_dir, which must therefore not contain the corpus.
        if output_dir in corpus_manifest.parents:
            raise ValueError("corpus_manifest must live outside output_dir")
        object.__setattr__(self, "tumour_type", tumour_type)
        object.__setattr__(self, "cancer_term", cancer_term)
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "corpus_manifest", corpus_manifest)
        object.__setattr__(self, "output_dir", output_dir)


@dataclass(frozen=True, slots=True)
class TargetResult:
    target: str
    system: System
    verdict_name: str
    source_names: tuple[str, ...]
    output_dir: Path


@dataclass(frozen=True, slots=True)
class FormalizationRun:
    source_count: int
    target_count: int
    output_dir: Path
    export_path: Path
    reused_targets: int = 0


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


def select_target_sources(sources: Sequence[Path], target: str, *, max_documents: int, max_chars: int) -> list[Path]:
    """Select the most target-specific sources within one model context budget.

    Articles and clinical-trial records are ranked separately: trials may use at
    most ``TRIAL_CHAR_SHARE`` of the character budget and articles the rest.
    """
    pattern = re.compile(rf"\b{re.escape(target)}\b", re.IGNORECASE)
    scored = {True: [], False: []}
    for source in sources:
        text = source.read_text(encoding="utf-8", errors="replace")
        score = len(pattern.findall(text))
        if score:
            scored[_is_trial(source)].append((-score, source.name, source, len(text)))
    trial_budget = int(max_chars * TRIAL_CHAR_SHARE)
    selected, used_chars = [], 0
    for is_trial, budget in ((False, max_chars - trial_budget), (True, trial_budget)):
        group, used_chars = [], 0
        for _, _, source, size in sorted(scored[is_trial]):
            if len(selected) + len(group) >= max_documents:
                break
            if used_chars + size > budget and (group or is_trial):
                continue
            group.append(source)
            used_chars += size
        selected += group
    if not selected:
        raise ValueError(f"no source article mentions target {target}")
    return selected


def target_query(target: str, cancer_term: str, tumour_type: str) -> str:
    verdict = f"{target.lower()}-verdict"
    return (
        f"Build a formal evidence dossier for therapeutic targeting of {target} in {cancer_term} ({tumour_type}). "
        "Extract balanced supporting and opposing facts only from the supplied documents, and attach exact verbatim "
        "document quotes to every fact. Derive intermediate claims with explicit :using dependencies. "
        f"Finally derive exactly one Boolean node named {verdict}; true means the target is promising and false means "
        "it is rejected. The verdict's complete :using chain must terminate in the quoted facts. Do not leave it unknown."
    )


def _fingerprint(paths: Sequence[Path], query: str, model: str | None) -> str:
    digest = hashlib.sha256(query.encode() + (model or "").encode())
    for path in paths:
        digest.update(path.name.encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _json_write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _run_pipeline(documents: Sequence[tuple[str, str]], query: str, provider: Any) -> PipelineResult:
    system = System(overridable=True)
    pipeline = Pipeline(system, provider)
    for name, text in documents:
        # text=, never path=: the path branch opens the file with the locale
        # encoding, which mangles or rejects most PMC articles on Windows.
        pipeline.add_document(name, text=text)
    return pipeline.run(query)


def _find_verdict(system: System, target: str) -> str:
    wanted = f"{target.lower()}-verdict"
    names = [*system.engine.theorems, *system.engine.terms, *system.engine.facts]
    matches = [name for name in names if name.lower() == wanted or name.lower().endswith(f".{wanted}")]
    if len(matches) != 1:
        raise ValueError(f"Parseltongue must derive exactly one {wanted} node; found {matches or 'none'}")
    return matches[0]


def _write_pipeline_result(result: PipelineResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    passes = output_dir / "passes"
    passes.mkdir(exist_ok=True)
    (output_dir / "answer.md").write_text(result.output.markdown, encoding="utf-8")
    _json_write(output_dir / "system.json", result.system.to_dict())
    _json_write(output_dir / "references.json", [asdict(ref) for ref in result.output.references])
    _json_write(output_dir / "consistency.json", result.output.consistency)
    (passes / "pass1_extract.pltg").write_text(result.pass1_source, encoding="utf-8")
    (passes / "pass2_derive.pltg").write_text(result.pass2_source, encoding="utf-8")
    (passes / "pass3_factcheck.pltg").write_text(result.pass3_source, encoding="utf-8")
    (passes / "pass4_answer.md").write_text(result.pass4_raw, encoding="utf-8")


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
    return {
        "DATA": data,
        "STRUCTURE_DATA": data,
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
    max_attempts: int = DEFAULT_TARGET_ATTEMPTS,
    provider_factory: Callable[..., Any] = create_nebius_provider,
    pipeline_runner: Callable[[Sequence[tuple[str, str]], str, Any], PipelineResult] = _run_pipeline,
) -> FormalizationRun:
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    sources = discover_sources(config.corpus_manifest)
    if config.output_dir.exists() and not (overwrite or resume):
        raise FileExistsError(f"output already exists: {config.output_dir}; use --resume or --overwrite")
    if overwrite and config.output_dir.exists():
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    plans = []
    for target in config.targets:
        selected = select_target_sources(sources, target, max_documents=config.max_documents_per_target, max_chars=config.max_target_chars)
        query = target_query(target, config.cancer_term, config.tumour_type)
        fingerprint = _fingerprint(selected, query, config.model)
        plans.append((target, selected, query, fingerprint))

    def run_target(plan: tuple[str, list[Path], str, str]) -> tuple[TargetResult, dict[str, Any], bool]:
        target, selected, query, fingerprint = plan
        target_dir = config.output_dir / "targets" / target.lower()
        target_manifest = target_dir / "manifest.json"
        if resume and target_manifest.is_file() and (target_dir / "system.json").is_file():
            previous = json.loads(target_manifest.read_text(encoding="utf-8"))
            if previous.get("status") == "complete" and previous.get("fingerprint") == fingerprint:
                system = System.from_dict(json.loads((target_dir / "system.json").read_text(encoding="utf-8")), overridable=True)
                verdict = _find_verdict(system, target)
                return TargetResult(target, system, verdict, tuple(path.name for path in selected), target_dir), previous, True
        if target_dir.exists():
            shutil.rmtree(target_dir)
        documents = [(path.stem, path.read_text(encoding="utf-8", errors="replace")) for path in selected]
        for attempt in range(1, max_attempts + 1):
            provider = provider_factory(model=config.model, base_url=config.base_url, reasoning=config.reasoning)
            try:
                pipeline_result = pipeline_runner(documents, query, provider)
                break
            except InterruptedError:
                raise
            except Exception as exc:
                if attempt >= max_attempts:
                    raise
                log.warning(
                    "%s attempt %d/%d failed (%s: %s); retrying target",
                    target,
                    attempt,
                    max_attempts,
                    type(exc).__name__,
                    exc,
                )
            finally:
                close_provider = getattr(provider, "close", None)
                if callable(close_provider):
                    close_provider()
        verdict = _find_verdict(pipeline_result.system, target)
        _write_pipeline_result(pipeline_result, target_dir)
        record = {"target": target, "status": "complete", "fingerprint": fingerprint, "query": query, "verdict_node": verdict, "sources": [path.name for path in selected]}
        _json_write(target_manifest, record)
        return TargetResult(target, pipeline_result.system, verdict, tuple(record["sources"]), target_dir), record, False

    if max_workers == 1:
        completed = [run_target(plan) for plan in plans]
    else:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(plans)), thread_name_prefix="formalization") as executor:
            completed = list(executor.map(run_target, plans))

    results = [result for result, _, _ in completed]
    records = [record for _, record, _ in completed]
    reused = sum(was_reused for _, _, was_reused in completed)
    export_path = config.output_dir / "formal-system.json"
    _json_write(export_path, build_objections_export(results))
    validate_objections_export(export_path, config.targets)
    _json_write(config.output_dir / "manifest.json", {"status": "complete", "generated_at": datetime.now(timezone.utc).isoformat(), "tumour_type": config.tumour_type, "cancer_term": config.cancer_term, "corpus_manifest": str(config.corpus_manifest), "source_count": len(sources), "targets": records, "export": export_path.name})
    return FormalizationRun(len(sources), len(results), config.output_dir, export_path, reused)
