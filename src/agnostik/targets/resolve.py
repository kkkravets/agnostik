"""Resolve a TCGA tumour code to the disease vocabularies the pipeline queries.

The GDC names the TCGA project (READ -> "Rectum Adenocarcinoma"); Open Targets
search then finds the matching disease. That name also serves as the literature
and trial search term, so no per-tumour table is kept.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from agnostik.candidates import resolution_file
from agnostik.targets.opentargets import DiseaseHit, DiseaseRef, HttpJson, disease_context, http_json, search_diseases

GDC_PROJECT_URL = "https://api.gdc.cancer.gov/projects/TCGA-{code}?fields=name"
# A second hit scoring within 1/AMBIGUITY_RATIO of the best one is a close call.
AMBIGUITY_RATIO = 2.0


@dataclass(frozen=True, slots=True)
class Resolution:
    tumour_type: str
    cancer_term: str  # literature and trial search term
    disease_id: str
    disease_name: str  # Open Targets' name for disease_id
    source: str  # where the disease came from: "gdc", "disease" or "disease-id"
    parents: tuple[DiseaseRef, ...] = ()  # ranked together with the disease
    alternatives: tuple[DiseaseHit, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def gdc_project_name(tumour_type: str, *, http: HttpJson = http_json) -> str:
    """The GDC's disease name for a TCGA code; an unknown code is an error."""

    code = tumour_type.strip().upper()
    try:
        payload = http(GDC_PROJECT_URL.format(code=code), None)
    except OSError as error:
        raise ValueError(f"could not reach the GDC to look up TCGA-{code} ({error})") from error
    name = (payload.get("data") or {}).get("name")
    if not name:
        raise ValueError(payload.get("message") or f"TCGA-{code} was not found in the GDC")
    return name


def resolve_disease(
    tumour_type: str,
    *,
    disease: str | None = None,
    disease_id: str | None = None,
    include_parents: bool = True,
    http: HttpJson = http_json,
) -> Resolution:
    """Match a tumour to an Open Targets disease.

    ``disease`` replaces the GDC name as the text to search; ``disease_id``
    skips the search. The disease's organ-specific parents are included unless
    ``include_parents`` is false. The result carries warnings when the match may
    be ambiguous.
    """

    code = tumour_type.strip().upper()
    term = " ".join((disease or gdc_project_name(code, http=http)).split())
    cancer_term = term.lower()

    others: list[DiseaseHit] = []
    close: list[DiseaseHit] = []
    warnings = []
    if disease_id:
        source = "disease-id"
    else:
        hits = search_diseases(term, http=http)
        if not hits:
            raise ValueError(f"no Open Targets disease matches {term!r}; pass --disease-id")
        top, *others = hits
        disease_id, source = top.id, "disease" if disease else "gdc"
        close = [hit for hit in others if hit.score * AMBIGUITY_RATIO > top.score]
        if top.name.lower() != cancer_term:
            warnings.append(f"searched {term!r} and took the closest disease, {top.name!r}")

    disease_name, parents = disease_context(disease_id, http=http)
    parents = parents if include_parents else []
    # A close runner-up that is an included parent is not a problem: it is ranked too.
    for hit in close:
        if hit.id not in {parent.id for parent in parents}:
            warnings.append(f"{hit.name!r} scored close to {disease_name!r}; pass --disease-id to choose")
    return Resolution(code, cancer_term, disease_id, disease_name, source, tuple(parents), tuple(others), tuple(warnings))


def write_resolution(resolution: Resolution, out_dir: Path) -> Path:
    path = Path(out_dir) / "resolution.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(resolution.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def cancer_term_for(tumour_type: str, *, http: HttpJson = http_json) -> str:
    """The search term for a tumour: the saved resolution if there is one, else the GDC name."""

    saved = resolution_file(tumour_type)
    if saved.is_file():
        term = json.loads(saved.read_text(encoding="utf-8")).get("cancer_term")
        if term:
            return term
    return gdc_project_name(tumour_type, http=http).lower()
