"""Reproducible prior-art collection for oncology target candidates."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import clawbio

from agnostik.pmc_full_text import (
    MAX_ARTICLES,
    FullTextArticle,
    download_open_access_articles,
)


SCHEMA_VERSION = 1
CLAWBIO_PUBMED_MAX_RESULTS = 50
_GENE_SYMBOL = re.compile(r"^[A-Z][A-Z0-9-]{0,19}$")


@dataclass(frozen=True, slots=True)
class EvidenceConfig:
    tumour_type: str
    cancer_term: str
    genes: tuple[str, ...]
    article_query: str | None = None
    max_articles: int = 5
    max_trials: int = 20
    output_root: Path = Path("results/evidence")
    ncbi_email: str = "agnostik@example.com"

    def __post_init__(self) -> None:
        tumour_type = self.tumour_type.strip().upper()
        cancer_term = " ".join(self.cancer_term.split())
        genes = tuple(dict.fromkeys(gene.strip().upper() for gene in self.genes))
        article_query = (
            " ".join(self.article_query.split())
            if self.article_query
            else f'"{cancer_term}"[Title/Abstract]'
        )
        if not tumour_type:
            raise ValueError("tumour_type must not be empty")
        if not cancer_term:
            raise ValueError("cancer_term must not be empty")
        if not genes:
            raise ValueError("at least one gene is required")
        invalid = [gene for gene in genes if not _GENE_SYMBOL.fullmatch(gene)]
        if invalid:
            raise ValueError(f"invalid gene symbol(s): {', '.join(invalid)}")
        if not 1 <= self.max_articles <= MAX_ARTICLES:
            raise ValueError(f"max_articles must be between 1 and {MAX_ARTICLES}")
        if not 1 <= self.max_trials <= 1000:
            raise ValueError("max_trials must be between 1 and 1000")
        object.__setattr__(self, "tumour_type", tumour_type)
        object.__setattr__(self, "cancer_term", cancer_term)
        object.__setattr__(self, "genes", genes)
        object.__setattr__(self, "article_query", article_query)
        object.__setattr__(self, "output_root", Path(self.output_root))


@dataclass(frozen=True, slots=True)
class CandidateQueries:
    pubmed: str
    full_text: str
    clinical_trials: str


@dataclass(frozen=True, slots=True)
class CandidateRun:
    gene: str
    run_id: str
    run_dir: Path
    status: str
    article_count: int = 0
    trial_count: int = 0
    recruiting_trial_count: int = 0
    error: str = ""


def build_queries(
    gene: str,
    cancer_term: str,
    article_query: str | None = None,
) -> CandidateQueries:
    """Build explicit queries for each upstream system."""

    gene = gene.strip().upper()
    cancer_term = " ".join(cancer_term.split())
    base_query = (
        " ".join(article_query.split())
        if article_query
        else f'"{cancer_term}"[Title/Abstract]'
    )
    gene_query = f"({base_query}) AND {gene}[Title/Abstract]"
    return CandidateQueries(
        pubmed=gene_query,
        full_text=gene_query,
        clinical_trials=f"{gene} {cancer_term}",
    )


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"


def _run_payload(config: EvidenceConfig, gene: str, queries: CandidateQueries) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "tumour_type": config.tumour_type,
        "cancer_term": config.cancer_term,
        "article_query": config.article_query,
        "gene": gene,
        "max_articles": config.max_articles,
        "max_trials": config.max_trials,
        "queries": asdict(queries),
        "dependencies": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "clawbio": _package_version("clawbio"),
            "parseltongue-dsl": _package_version("parseltongue-dsl"),
            "agnostik": _package_version("agnostik"),
        },
    }


def candidate_run_id(config: EvidenceConfig, gene: str) -> str:
    normalized_gene = gene.strip().upper()
    queries = build_queries(normalized_gene, config.cancer_term, config.article_query)
    payload = _run_payload(config, normalized_gene, queries)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


def _skill_script(skill: str, script: str) -> Path:
    root = Path(clawbio.__file__).resolve().parent
    path = root / "skills" / skill / script
    if not path.is_file():
        raise FileNotFoundError(f"ClawBio skill script not found: {path}")
    return path


def _run_command(command: Sequence[str], log_path: Path) -> None:
    completed = subprocess.run(
        list(command),
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"COMMAND\n{json.dumps(list(command), ensure_ascii=False)}\n\n"
        f"STDOUT\n{completed.stdout}\n\nSTDERR\n{completed.stderr}",
        encoding="utf-8",
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed with exit code {completed.returncode}; see {log_path}"
        )


def _write_checksums(run_dir: Path) -> Path:
    checksum_path = run_dir / "checksums.sha256"
    lines = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path == checksum_path:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(run_dir).as_posix()}")
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def _trial_counts(summary_path: Path) -> tuple[int, int]:
    if not summary_path.is_file():
        return 0, 0
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return int(payload.get("total", 0)), int(payload.get("recruiting", 0))


def collect_candidate_evidence(
    config: EvidenceConfig,
    gene: str,
    *,
    overwrite: bool = False,
    skip_existing: bool = False,
    command_runner: Callable[[Sequence[str], Path], None] = _run_command,
    article_downloader: Callable[..., list[FullTextArticle]] = download_open_access_articles,
) -> CandidateRun:
    """Collect all literature and trial evidence for one candidate."""

    gene = gene.strip().upper()
    queries = build_queries(gene, config.cancer_term, config.article_query)
    run_id = candidate_run_id(config, gene)
    run_dir = config.output_root / config.tumour_type.lower() / gene.lower() / run_id
    if run_dir.exists():
        if skip_existing:
            manifest_path = run_dir / "manifest.json"
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.is_file()
                else {}
            )
            return CandidateRun(
                gene,
                run_id,
                run_dir,
                "skipped",
                int(manifest.get("article_count", 0)),
                int(manifest.get("trial_count", 0)),
                int(manifest.get("recruiting_trial_count", 0)),
            )
        if not overwrite:
            raise FileExistsError(
                f"run already exists: {run_dir}; use --skip-existing or --overwrite"
            )
        shutil.rmtree(run_dir)

    run_dir.mkdir(parents=True)
    logs_dir = run_dir / "logs"
    pubmed_dir = run_dir / "literature" / "clawbio_pubmed"
    source_dir = run_dir / "literature" / "sources"
    article_artifacts_dir = run_dir / "literature" / "artifacts"
    trials_dir = run_dir / "clinical_trials"
    payload = _run_payload(config, gene, queries)
    (run_dir / "config.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    commands: dict[str, list[str]] = {}
    status = "complete"
    error = ""
    article_count = trial_count = recruiting_count = 0
    try:
        pubmed_command = [
            sys.executable,
            str(_skill_script("pubmed-summariser", "pubmed_summariser.py")),
            "--query",
            queries.pubmed,
            "--max-results",
            str(min(config.max_articles, CLAWBIO_PUBMED_MAX_RESULTS)),
            "--output",
            str(pubmed_dir),
        ]
        commands["pubmed_summariser"] = pubmed_command
        command_runner(pubmed_command, logs_dir / "pubmed_summariser.log")

        articles = article_downloader(
            queries.full_text,
            config.max_articles,
            source_dir,
            artifacts_dir=article_artifacts_dir,
            email=config.ncbi_email,
        )
        article_count = len(articles)

        trial_command = [
            sys.executable,
            str(_skill_script("clinical-trial-finder", "clinical_trial_finder.py")),
            "--query",
            queries.clinical_trials,
            "--max-results",
            str(config.max_trials),
            "--output",
            str(trials_dir),
        ]
        commands["clinical_trial_finder"] = trial_command
        command_runner(trial_command, logs_dir / "clinical_trial_finder.log")
        trial_count, recruiting_count = _trial_counts(trials_dir / "summary.json")
    except Exception as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"

    (run_dir / "commands.json").write_text(
        json.dumps(commands, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest = {
        **payload,
        "run_id": run_id,
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "article_count": article_count,
        "trial_count": trial_count,
        "recruiting_trial_count": recruiting_count,
        "parseltongue_source_dir": "literature/sources",
        "error": error,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_checksums(run_dir)
    return CandidateRun(
        gene,
        run_id,
        run_dir,
        status,
        article_count,
        trial_count,
        recruiting_count,
        error,
    )


def collect_evidence_batch(
    config: EvidenceConfig,
    *,
    overwrite: bool = False,
    skip_existing: bool = False,
) -> list[CandidateRun]:
    """Collect evidence for all configured genes, continuing after failures."""

    runs = []
    for gene in config.genes:
        try:
            run = collect_candidate_evidence(
                config,
                gene,
                overwrite=overwrite,
                skip_existing=skip_existing,
            )
        except Exception as exc:
            queries = build_queries(gene, config.cancer_term, config.article_query)
            run_id = candidate_run_id(config, gene)
            run_dir = config.output_root / config.tumour_type.lower() / gene.lower() / run_id
            run = CandidateRun(
                gene=gene,
                run_id=run_id,
                run_dir=run_dir,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        runs.append(run)

    tumour_root = config.output_root / config.tumour_type.lower()
    tumour_root.mkdir(parents=True, exist_ok=True)
    batch_manifest = {
        "schema_version": SCHEMA_VERSION,
        "tumour_type": config.tumour_type,
        "cancer_term": config.cancer_term,
        "article_query": config.article_query,
        "max_articles_per_gene": config.max_articles,
        "max_trials_per_gene": config.max_trials,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "genes": [
            {
                "gene": run.gene,
                "query": build_queries(
                    run.gene, config.cancer_term, config.article_query
                ).full_text,
                "run_id": run.run_id,
                "run_dir": str(run.run_dir.relative_to(tumour_root)),
                "status": run.status,
                "article_count": run.article_count,
                "trial_count": run.trial_count,
                "error": run.error,
            }
            for run in runs
        ],
    }
    (tumour_root / "batch_manifest.json").write_text(
        json.dumps(batch_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return runs
