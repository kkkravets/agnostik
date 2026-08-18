"""Build the formal Stage-3 Parseltongue export consumed by Stage 4."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
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


@dataclass(frozen=True, slots=True)
class Stage3Config:
    tumour_type: str
    cancer_term: str
    source_dir: Path
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
        source_dir, output_dir = Path(self.source_dir).resolve(), Path(self.output_dir).resolve()
        if not tumour_type or not cancer_term:
            raise ValueError("tumour_type and cancer_term must not be empty")
        if not targets:
            raise ValueError("at least one target candidate is required")
        if self.max_documents_per_target < 1 or self.max_target_chars < 1:
            raise ValueError("document and character limits must be at least 1")
        if output_dir == source_dir or output_dir in source_dir.parents or source_dir in output_dir.parents:
            raise ValueError("output_dir must be separate from the source directory tree")
        object.__setattr__(self, "tumour_type", tumour_type)
        object.__setattr__(self, "cancer_term", cancer_term)
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "source_dir", source_dir)
        object.__setattr__(self, "output_dir", output_dir)


@dataclass(frozen=True, slots=True)
class TargetResult:
    target: str
    system: System
    verdict_name: str
    source_names: tuple[str, ...]
    output_dir: Path


@dataclass(frozen=True, slots=True)
class Stage3Run:
    source_count: int
    target_count: int
    output_dir: Path
    export_path: Path
    reused_targets: int = 0


def discover_sources(source_dir: Path) -> list[Path]:
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise FileNotFoundError(f"full-text source directory not found: {source_dir}")
    sources = sorted(path for path in source_dir.glob("*.txt") if path.is_file())
    if not sources:
        raise FileNotFoundError(f"no .txt articles found in: {source_dir}")
    return sources


def select_target_sources(sources: Sequence[Path], target: str, *, max_documents: int, max_chars: int) -> list[Path]:
    """Select the most target-specific articles within one model context budget."""
    pattern = re.compile(rf"\b{re.escape(target)}\b", re.IGNORECASE)
    scored = []
    for source in sources:
        text = source.read_text(encoding="utf-8", errors="replace")
        score = len(pattern.findall(text))
        if score:
            scored.append((-score, source.name, source, len(text)))
    selected, used_chars = [], 0
    for _, _, source, size in sorted(scored):
        if selected and used_chars + size > max_chars:
            continue
        selected.append(source)
        used_chars += size
        if len(selected) >= max_documents:
            break
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
    prefix = f"stage3.{result.target.lower()}."
    names = {item["id"] for item in items}
    mapped = lambda name: prefix + name
    exported = []
    for item in items:
        inputs = []
        for raw in item.get("inputs") or []:
            name = raw if isinstance(raw, str) else raw.get("name", "")
            if name:
                inputs.append({"name": mapped(name), "inProbe": name in names})
        record = {**item, "id": mapped(item["id"]), "module": f"stage3.{result.target.lower()}"}
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


def build_stage4_export(results: Sequence[TargetResult]) -> dict[str, Any]:
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


def validate_stage4_export(export_path: Path, targets: Sequence[str]) -> None:
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
        raise ValueError("Stage-4 export contract failed: " + "; ".join(problems))


def run_stage3(
    config: Stage3Config,
    *,
    overwrite: bool = False,
    resume: bool = False,
    provider_factory: Callable[..., Any] = create_nebius_provider,
    pipeline_runner: Callable[[Sequence[tuple[str, str]], str, Any], PipelineResult] = _run_pipeline,
) -> Stage3Run:
    sources = discover_sources(config.source_dir)
    if config.output_dir.exists() and not (overwrite or resume):
        raise FileExistsError(f"output already exists: {config.output_dir}; use --resume or --overwrite")
    if overwrite and config.output_dir.exists():
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    provider, results, records, reused = None, [], [], 0
    for target in config.targets:
        selected = select_target_sources(sources, target, max_documents=config.max_documents_per_target, max_chars=config.max_target_chars)
        query = target_query(target, config.cancer_term, config.tumour_type)
        fingerprint = _fingerprint(selected, query, config.model)
        target_dir = config.output_dir / "targets" / target.lower()
        target_manifest = target_dir / "manifest.json"
        if resume and target_manifest.is_file() and (target_dir / "system.json").is_file():
            previous = json.loads(target_manifest.read_text(encoding="utf-8"))
            if previous.get("status") == "complete" and previous.get("fingerprint") == fingerprint:
                system = System.from_dict(json.loads((target_dir / "system.json").read_text(encoding="utf-8")), overridable=True)
                verdict = _find_verdict(system, target)
                results.append(TargetResult(target, system, verdict, tuple(path.name for path in selected), target_dir))
                records.append(previous)
                reused += 1
                continue
        if target_dir.exists():
            shutil.rmtree(target_dir)
        if provider is None:
            provider = provider_factory(model=config.model, base_url=config.base_url, reasoning=config.reasoning)
        documents = [(path.stem, path.read_text(encoding="utf-8", errors="replace")) for path in selected]
        pipeline_result = pipeline_runner(documents, query, provider)
        verdict = _find_verdict(pipeline_result.system, target)
        _write_pipeline_result(pipeline_result, target_dir)
        record = {"target": target, "status": "complete", "fingerprint": fingerprint, "query": query, "verdict_node": verdict, "sources": [path.name for path in selected]}
        _json_write(target_manifest, record)
        records.append(record)
        results.append(TargetResult(target, pipeline_result.system, verdict, tuple(record["sources"]), target_dir))
    export_path = config.output_dir / "stage3-export.json"
    _json_write(export_path, build_stage4_export(results))
    validate_stage4_export(export_path, config.targets)
    _json_write(config.output_dir / "manifest.json", {"status": "complete", "generated_at": datetime.now(timezone.utc).isoformat(), "tumour_type": config.tumour_type, "cancer_term": config.cancer_term, "source_dir": str(config.source_dir), "source_count": len(sources), "targets": records, "stage4_export": export_path.name})
    return Stage3Run(len(sources), len(results), config.output_dir, export_path, reused)
