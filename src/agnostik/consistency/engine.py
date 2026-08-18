"""Drive pg-bench over the generated screening system and read back its verdict.

Everything reported by stage 6 comes from the engine: integrity of the quotes,
the diffs that failed, the taint it propagated. This module runs it and parses
it; it never decides anything itself.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["ScreenItem", "EngineResult", "EngineError", "run_screening", "parse_items"]

# pg-bench prints ScreenItem reprs. `kind` is an enum repr, and `detail` holds a
# nested DiffResult repr with both sides of the comparison, so the fields are
# pulled out individually rather than with one all-or-nothing pattern.
_ITEM_SPLIT = "ScreenItem("
_FIELD_RX = {
    "name": re.compile(r"name='([^']*)'"),
    "category": re.compile(r"category='([^']*)'"),
    "type": re.compile(r"type='([^']*)'"),
    "loc": re.compile(r"loc='([^']*)'"),
}
_KIND_RX = re.compile(r"kind=(?:'([^']*)'|<\w+\.\w+:\s*'([^']*)'>)")
_DIFF_RX = re.compile(
    r"replace='(?P<replace>[^']*)',\s*with_='(?P<with_>[^']*)',\s*"
    r"value_a=(?P<value_a>.*?),\s*value_b=(?P<value_b>.*?),\s*divergences=(?P<divergences>\{.*?\})",
    re.DOTALL,
)
_CONSEQUENCE_RX = re.compile(r"'([^']+)':\s*\[([^\]]*)\]")

_INTEGRITY_RX = re.compile(r"integrity=Integrity\([^:]*:\s*(?P<state>\w+)\)")
_NOT_READY = "Still initializing"


class EngineError(RuntimeError):
    pass


@dataclass
class ScreenItem:
    name: str
    category: str
    type: str
    kind: str
    loc: str
    detail: str = ""
    replace: str = ""
    with_: str = ""
    value_a: str = ""
    value_b: str = ""
    consequences: dict[str, list[str]] = field(default_factory=dict)

    @property
    def short_name(self) -> str:
        return self.name.split(".")[-1]

    @property
    def is_divergence(self) -> bool:
        return "diverg" in self.type

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "check": self.short_name,
            "category": self.category,
            "type": self.type,
            "kind": self.kind,
            "location": self.loc,
            "compared": (
                {"dossier_side": self.replace, "registry_side": self.with_,
                 "dossier_value": self.value_a, "registry_value": self.value_b}
                if self.replace
                else {}
            ),
            "consequences": self.consequences,
        }


def parse_items(text: str) -> list[ScreenItem]:
    """Parse `pg screen` output into structured items."""
    items: list[ScreenItem] = []
    for chunk in text.split(_ITEM_SPLIT)[1:]:
        fields = {key: (rx.search(chunk).group(1) if rx.search(chunk) else "") for key, rx in _FIELD_RX.items()}
        if not fields["name"]:
            continue
        kind_match = _KIND_RX.search(chunk)
        kind = (kind_match.group(1) or kind_match.group(2)) if kind_match else ""
        item = ScreenItem(
            name=fields["name"],
            category=fields["category"],
            type=fields["type"],
            kind=kind,
            loc=fields["loc"],
            detail=chunk.split("detail=", 1)[1].strip().rstrip(")\n ") if "detail=" in chunk else "",
        )
        diff = _DIFF_RX.search(chunk)
        if diff:
            item.replace = diff.group("replace")
            item.with_ = diff.group("with_")
            item.value_a = diff.group("value_a").strip()
            item.value_b = diff.group("value_b").strip()
            item.consequences = {
                node: [v.strip() for v in values.split(",")]
                for node, values in _CONSEQUENCE_RX.findall(diff.group("divergences"))
            }
        items.append(item)
    return items


@dataclass
class EngineResult:
    integrity: str = "unknown"
    load_errors: list[str] = None  # type: ignore[assignment]
    issues: list[ScreenItem] = None  # type: ignore[assignment]
    warnings: list[ScreenItem] = None  # type: ignore[assignment]
    stats: dict = None  # type: ignore[assignment]
    values: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.load_errors = self.load_errors or []
        self.issues = self.issues or []
        self.warnings = self.warnings or []
        self.stats = self.stats or {}
        self.values = self.values or {}

    @property
    def quotes_verified(self) -> bool:
        return self.integrity == "verified"

    def to_json(self) -> dict:
        return {
            "integrity": self.integrity,
            "quotes_verified": self.quotes_verified,
            "load_errors": self.load_errors,
            "issues": [i.to_json() for i in self.issues],
            "warnings": [w.to_json() for w in self.warnings],
            "stats": self.stats,
            "values": self.values,
        }


def _pg(binary: str, args: list[str], cwd: Path, timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        [binary, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _pg_ready(binary: str, args: list[str], cwd: Path, attempts: int = 8, delay: int = 8) -> str:
    """Run a bench query, waiting out the daemon's initialisation window."""
    for attempt in range(attempts):
        proc = _pg(binary, args, cwd)
        out = (proc.stdout or "") + (proc.stderr or "")
        if _NOT_READY not in out:
            return out
        if attempt < attempts - 1:
            time.sleep(delay)
    raise EngineError(f"pg-bench never finished loading: {' '.join(args)}")


def run_screening(
    entry: Path,
    value_nodes: list[str],
    pg_binary: str = "pg",
    keep_running: bool = False,
) -> EngineResult:
    """Start the bench on ``entry``, screen it, and read the adjudication values."""
    binary = shutil.which(pg_binary) or pg_binary
    if shutil.which(binary) is None and not Path(binary).exists():
        raise EngineError(
            f"{pg_binary} not found on PATH — install parseltongue-dsl, or pass --pg-binary"
        )

    root = entry.parent
    _pg(binary, ["stop"], root, timeout=60)
    shutil.rmtree(root / ".parseltongue-bench", ignore_errors=True)

    started = _pg(binary, ["start", entry.name], root)
    if started.returncode != 0:
        raise EngineError(f"pg start failed: {started.stderr.strip()[:400]}")
    _pg(binary, ["wait"], root)

    result = EngineResult()

    status = _pg(binary, ["status"], root).stdout
    match = _INTEGRITY_RX.search(status)
    result.integrity = match.group("state") if match else "unknown"
    collecting = False
    for line in status.splitlines():
        if "load error" in line:
            collecting = True
            continue
        if collecting and line.strip():
            result.load_errors.append(line.strip())

    issues_out = _pg_ready(binary, ["screen", "--what", "issues"], root)
    result.issues = parse_items(issues_out)

    warnings_out = _pg_ready(binary, ["screen", "--what", "warnings"], root)
    result.warnings = parse_items(warnings_out)

    stats_out = _pg_ready(binary, ["screen", "--what", "stats"], root)
    brace = stats_out.find("{")
    if brace != -1:
        try:
            result.stats = json.loads(stats_out[brace:])
        except json.JSONDecodeError:
            result.stats = {"raw": stats_out[:400]}

    for node in value_nodes:
        out = _pg_ready(binary, ["eval", f'(scope lens (value "{node}"))'], root)
        result.values[node] = out.strip().strip('"')

    if not keep_running:
        _pg(binary, ["stop"], root, timeout=60)

    return result
