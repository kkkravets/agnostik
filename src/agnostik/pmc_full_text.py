"""Download open-access, original-research full-text articles from PubMed Central.

The PubMed Summariser bundled with ClawBio deliberately emits only a short
abstract excerpt.  This module is the explicit full-text stage: it searches
the PMC Open Access subset and downloads authoritative JATS XML through NCBI
E-utilities.  Each article is stored twice and only twice: the raw JATS XML
as the archival record, and a Markdown-style ``.txt`` rendering that serves
both Parseltongue and human reading.  Only records tagged
``article-type="research-article"`` in their JATS metadata are kept, so
review articles (and other non-original-research types) are excluded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PMC_ARTICLE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/"
USER_AGENT = "agnostik/0.1 (open-access oncology literature notebook)"
MAX_ARTICLES = 3000
EFETCH_BATCH_SIZE = 25
# JATS <article article-type="..."> value for original research; excludes
# review-article, case-report, editorial, correction, etc.
EXPERIMENTAL_ARTICLE_TYPE = "research-article"
# Extra candidate IDs to request beyond max_articles, since some fetched
# articles will be filtered out for not being research-article type.
OVERSAMPLE_FACTOR = 3


@dataclass(frozen=True)
class FullTextArticle:
    """Files and identifiers for one downloaded PMC article."""

    pmc_id: str
    pmid: str
    doi: str
    title: str
    source_url: str
    source_path: Path
    xml_path: Path

    def manifest_entry(self, root: Path) -> dict[str, str]:
        entry = asdict(self)
        entry["source_path"] = str(self.source_path.relative_to(root))
        entry["xml_path"] = str(self.xml_path.relative_to(root))
        return entry


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _request_bytes(url: str, params: dict[str, object], timeout: float) -> bytes:
    request_url = f"{url}?{urlencode(params)}"
    request = Request(request_url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"NCBI request failed: {request_url}") from exc


def _article_id(article: ET.Element, kind: str) -> str:
    for element in article.findall(".//article-id"):
        if element.attrib.get("pub-id-type") == kind:
            return _text(element)
    return ""


def _plain_blocks(elements: Iterable[ET.Element], level: int = 1) -> str:
    blocks: list[str] = []
    for element in elements:
        tag = _local_name(element.tag)
        if tag == "title":
            continue
        if tag == "sec":
            title = _text(element.find("title")) or "Section"
            blocks.append(f"{'#' * min(level + 1, 6)} {title}")
            blocks.append(_plain_blocks(element, level + 1))
        elif tag == "p":
            blocks.append(_text(element))
        elif tag == "list":
            items = [f"- {_text(item)}" for item in element.findall("list-item")]
            blocks.append("\n".join(items))
        elif tag == "fig":
            label = _text(element.find("label"))
            caption = _text(element.find("caption"))
            blocks.append(f"{label}: {caption}".strip(": "))
        elif tag == "table-wrap":
            caption = _text(element.find("caption"))
            rows = []
            for row in element.findall(".//tr"):
                cells = [_text(cell) for cell in row if _local_name(cell.tag) in {"th", "td"}]
                if cells:
                    rows.append("\t".join(cells))
            blocks.append("\n".join(part for part in (caption, *rows) if part))
        elif tag == "ref-list":
            title = _text(element.find("title")) or "References"
            references = [f"{index}. {_text(ref)}" for index, ref in enumerate(element.findall("ref"), 1)]
            blocks.append(f"## {title}\n" + "\n".join(references))
        else:
            nested = _plain_blocks(element, level)
            if nested:
                blocks.append(nested)
    return "\n\n".join(block for block in blocks if block.strip())


def render_article_text(article: ET.Element, source_url: str) -> str:
    """Render a clean full-text source suitable for Parseltongue load-document."""

    title = _text(article.find(".//article-title")) or "Untitled PMC article"
    journal = _text(article.find(".//journal-title"))
    pmc_id = _article_id(article, "pmcid") or _article_id(article, "pmc")
    pmid = _article_id(article, "pmid")
    doi = _article_id(article, "doi")
    authors = []
    for contributor in article.findall(".//contrib[@contrib-type='author']"):
        surname = _text(contributor.find(".//surname"))
        given = _text(contributor.find(".//given-names"))
        name = " ".join(part for part in (given, surname) if part)
        if name:
            authors.append(name)
    abstract = article.find(".//abstract")
    body = article.find("body")
    back = article.find("back")
    parts = [
        f"# {title}",
        f"Authors: {', '.join(authors)}",
        f"Journal: {journal}",
        f"PMCID: {pmc_id}",
        f"PMID: {pmid}",
        f"DOI: {doi}",
        f"Canonical source: {source_url}",
        "## Abstract",
        _plain_blocks(abstract) if abstract is not None else "No abstract supplied.",
        "## Full article",
        _plain_blocks(body) if body is not None else "No article body supplied.",
    ]
    if back is not None:
        parts.append(_plain_blocks(back))
    return "\n\n".join(part for part in parts if part.strip()) + "\n"


def download_open_access_articles(
    query: str,
    max_articles: int,
    output_dir: Path,
    *,
    artifacts_dir: Path | None = None,
    email: str = "agnostik@example.com",
    timeout: float = 30,
) -> list[FullTextArticle]:
    """Search and save at most ``max_articles`` complete OA PMC articles.

    Only original-research articles are kept: each fetched JATS record is
    checked for ``article-type="research-article"`` and anything else
    (``review-article``, case reports, editorials, corrections, ...) is
    skipped. PubMed Central does not expose a reliable server-side filter for
    this distinction, so it is applied locally against the authoritative JATS
    metadata after fetch.

    Fewer records may be returned when the Open Access subset does not contain
    enough qualifying research articles.  Abstract-only PubMed records are
    never substituted.
    """

    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= max_articles <= MAX_ARTICLES:
        raise ValueError(f"max_articles must be between 1 and {MAX_ARTICLES}")

    common = {"tool": "agnostik", "email": email}
    search_bytes = _request_bytes(
        ESEARCH_URL,
        {
            **common,
            "db": "pmc",
            "term": f"({query}) AND open access[filter]",
            "retmax": min(max_articles * OVERSAMPLE_FACTOR, MAX_ARTICLES),
            "retmode": "json",
            "sort": "relevance",
        },
        timeout,
    )
    search = json.loads(search_bytes)
    ids = search.get("esearchresult", {}).get("idlist", [])
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = artifacts_dir or output_dir.parent / f"{output_dir.name}_artifacts"
    xml_dir = artifacts_dir / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("PMC*.txt"):
        stale.unlink()
    for stale in xml_dir.glob("PMC*.xml"):
        stale.unlink()
    if not ids:
        return []

    def fetch_article_elements():
        for offset in range(0, len(ids), EFETCH_BATCH_SIZE):
            batch = ids[offset : offset + EFETCH_BATCH_SIZE]
            article_set = _request_bytes(
                EFETCH_URL,
                {**common, "db": "pmc", "id": ",".join(batch), "retmode": "xml"},
                timeout,
            )
            root = ET.fromstring(article_set)
            yield from (
                root.findall(".//article")
                if _local_name(root.tag) != "article"
                else [root]
            )

    downloaded: list[FullTextArticle] = []
    skipped_non_research = 0
    for index, article in enumerate(fetch_article_elements(), start=1):
        if len(downloaded) >= max_articles:
            break
        if article.attrib.get("article-type") != EXPERIMENTAL_ARTICLE_TYPE:
            skipped_non_research += 1
            continue
        pmc_id = _article_id(article, "pmcid") or _article_id(article, "pmc")
        if pmc_id and not pmc_id.upper().startswith("PMC"):
            pmc_id = f"PMC{pmc_id}"
        pmc_id = pmc_id or f"PMC-unknown-{index}"
        pmid = _article_id(article, "pmid")
        doi = _article_id(article, "doi")
        title = _text(article.find(".//article-title")) or pmc_id
        source_url = PMC_ARTICLE_URL.format(pmc_id=pmc_id)
        source_path = output_dir / f"{pmc_id}.txt"
        xml_path = xml_dir / f"{pmc_id}.xml"
        source_path.write_text(render_article_text(article, source_url), encoding="utf-8")
        xml_path.write_bytes(ET.tostring(article, encoding="utf-8", xml_declaration=True))
        downloaded.append(
            FullTextArticle(pmc_id, pmid, doi, title, source_url, source_path, xml_path)
        )

    manifest = {
        "query": query,
        "requested": max_articles,
        "downloaded": len(downloaded),
        "skipped_non_research": skipped_non_research,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "NCBI PubMed Central Open Access subset via E-utilities",
        "source_directory": str(output_dir),
        "articles": [article.manifest_entry(artifacts_dir.parent) for article in downloaded],
    }
    (artifacts_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return downloaded
