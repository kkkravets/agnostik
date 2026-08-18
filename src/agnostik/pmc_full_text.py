"""Download open-access full-text articles from PubMed Central.

The PubMed Summariser bundled with ClawBio deliberately emits only a short
abstract excerpt.  This module is the explicit full-text stage: it searches
the PMC Open Access subset, downloads authoritative JATS XML through NCBI
E-utilities, and writes both the source XML and a readable local HTML version.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
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
    html_path: Path

    def manifest_entry(self, root: Path) -> dict[str, str]:
        entry = asdict(self)
        entry["source_path"] = str(self.source_path.relative_to(root))
        entry["xml_path"] = str(self.xml_path.relative_to(root))
        entry["html_path"] = str(self.html_path.relative_to(root))
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


def _inline(element: ET.Element) -> str:
    chunks: list[str] = []
    if element.text:
        chunks.append(escape(element.text))
    for child in element:
        tag = _local_name(child.tag)
        content = _inline(child)
        if tag in {"bold", "strong"}:
            content = f"<strong>{content}</strong>"
        elif tag in {"italic", "em"}:
            content = f"<em>{content}</em>"
        elif tag == "sup":
            content = f"<sup>{content}</sup>"
        elif tag == "sub":
            content = f"<sub>{content}</sub>"
        elif tag in {"ext-link", "uri"}:
            href = child.attrib.get("{http://www.w3.org/1999/xlink}href", "")
            if href.startswith(("http://", "https://")):
                content = f'<a href="{escape(href, quote=True)}">{content}</a>'
        chunks.append(content)
        if child.tail:
            chunks.append(escape(child.tail))
    return "".join(chunks)


def _render_table(table_wrap: ET.Element) -> str:
    caption = _text(table_wrap.find("caption"))
    table = table_wrap.find(".//table")
    if table is None:
        return f"<p>{escape(_text(table_wrap))}</p>"
    rows: list[str] = []
    for row in table.findall(".//tr"):
        cells: list[str] = []
        for cell in row:
            tag = _local_name(cell.tag)
            if tag not in {"th", "td"}:
                continue
            cells.append(f"<{tag}>{_inline(cell)}</{tag}>")
        if cells:
            rows.append(f"<tr>{''.join(cells)}</tr>")
    caption_html = f"<figcaption>{escape(caption)}</figcaption>" if caption else ""
    return f"<figure class=\"table-wrap\">{caption_html}<table>{''.join(rows)}</table></figure>"


def _render_blocks(elements: Iterable[ET.Element], heading_level: int = 2) -> str:
    rendered: list[str] = []
    for element in elements:
        tag = _local_name(element.tag)
        if tag == "title":
            continue
        if tag == "sec":
            title = _text(element.find("title")) or "Section"
            level = min(heading_level, 6)
            rendered.append(f"<h{level}>{escape(title)}</h{level}>")
            rendered.append(_render_blocks(element, heading_level + 1))
        elif tag == "p":
            rendered.append(f"<p>{_inline(element)}</p>")
        elif tag == "list":
            list_tag = "ol" if element.attrib.get("list-type") == "order" else "ul"
            items = []
            for item in element.findall("list-item"):
                items.append(f"<li>{_render_blocks(item) or _inline(item)}</li>")
            rendered.append(f"<{list_tag}>{''.join(items)}</{list_tag}>")
        elif tag == "disp-quote":
            rendered.append(f"<blockquote>{_render_blocks(element) or _inline(element)}</blockquote>")
        elif tag == "fig":
            label = _text(element.find("label"))
            caption = _text(element.find("caption"))
            rendered.append(
                f"<figure><figcaption><strong>{escape(label)}</strong> "
                f"{escape(caption)}</figcaption></figure>"
            )
        elif tag == "table-wrap":
            rendered.append(_render_table(element))
        elif tag in {"boxed-text", "statement", "ack"}:
            rendered.append(f"<aside>{_render_blocks(element, heading_level)}</aside>")
        elif tag == "ref-list":
            title = _text(element.find("title")) or "References"
            references = [f"<li>{escape(_text(ref))}</li>" for ref in element.findall("ref")]
            rendered.append(f"<h2>{escape(title)}</h2><ol class=\"references\">{''.join(references)}</ol>")
        else:
            rendered.append(_render_blocks(element, heading_level))
    return "".join(rendered)


def render_article_html(article: ET.Element, source_url: str) -> str:
    """Render the complete main JATS text into a standalone readable HTML file."""

    title = _text(article.find(".//article-title")) or "Untitled PMC article"
    journal = _text(article.find(".//journal-title"))
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
    license_text = _text(article.find(".//license-p"))

    abstract_html = _render_blocks(abstract) if abstract is not None else "<p>No abstract supplied.</p>"
    body_html = _render_blocks(body) if body is not None else "<p>No article body supplied.</p>"
    back_html = _render_blocks(back) if back is not None else ""
    author_line = ", ".join(authors)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
body{{font:17px/1.65 system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1.5rem;color:#17202a}}
h1,h2,h3,h4{{line-height:1.25}} .meta{{color:#52606d}} a{{color:#075985}}
table{{border-collapse:collapse;display:block;overflow-x:auto}} th,td{{border:1px solid #bbb;padding:.45rem;vertical-align:top}}
figure,aside,blockquote{{margin:1rem 0;padding:.8rem 1rem;background:#f4f7f9;border-left:4px solid #78909c}}
.notice{{background:#fff8e1;border:1px solid #e0c46c;padding:1rem}} .references{{font-size:.9rem}}
</style></head><body>
<p class="notice">Downloaded from the PubMed Central Open Access subset. The source JATS XML is saved beside this file. <a href="{escape(source_url, quote=True)}">View the canonical PMC record</a>.</p>
<h1>{escape(title)}</h1>
<p class="meta">{escape(author_line)}<br>{escape(journal)}</p>
<h2>Abstract</h2>{abstract_html}
<main>{body_html}</main>
<footer>{back_html}<h2>License supplied by the article</h2><p>{escape(license_text or 'See the canonical PMC record for licensing details.')}</p></footer>
</body></html>"""


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

    Fewer records may be returned when the Open Access subset does not contain
    enough matches.  Abstract-only PubMed records are never substituted.
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
            "retmax": max_articles,
            "retmode": "json",
            "sort": "relevance",
        },
        timeout,
    )
    search = json.loads(search_bytes)
    ids = search.get("esearchresult", {}).get("idlist", [])
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = artifacts_dir or output_dir.parent / f"{output_dir.name}_artifacts"
    html_dir = artifacts_dir / "html"
    xml_dir = artifacts_dir / "xml"
    html_dir.mkdir(parents=True, exist_ok=True)
    xml_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("PMC*.txt"):
        stale.unlink()
    for stale in html_dir.glob("PMC*.html"):
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
    for index, article in enumerate(fetch_article_elements(), start=1):
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
        html_path = html_dir / f"{pmc_id}.html"
        source_path.write_text(render_article_text(article, source_url), encoding="utf-8")
        xml_path.write_bytes(ET.tostring(article, encoding="utf-8", xml_declaration=True))
        html_path.write_text(render_article_html(article, source_url), encoding="utf-8")
        downloaded.append(
            FullTextArticle(pmc_id, pmid, doi, title, source_url, source_path, xml_path, html_path)
        )

    manifest = {
        "query": query,
        "requested": max_articles,
        "downloaded": len(downloaded),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "NCBI PubMed Central Open Access subset via E-utilities",
        "source_directory": str(output_dir),
        "articles": [article.manifest_entry(artifacts_dir.parent) for article in downloaded],
    }
    (artifacts_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    links = "".join(
        f'<li><a href="{escape(article.html_path.relative_to(artifacts_dir).as_posix())}">'
        f"{escape(article.title)}</a> ({escape(article.pmc_id)})</li>"
        for article in downloaded
    )
    (artifacts_dir / "index.html").write_text(
        "<!doctype html><meta charset=\"utf-8\"><title>PMC full-text articles</title>"
        f"<h1>PMC full-text articles</h1><p>Query: <code>{escape(query)}</code></p><ol>{links}</ol>",
        encoding="utf-8",
    )
    return downloaded
