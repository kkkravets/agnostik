"""Reports: machine-readable JSON, a Markdown digest, and a browsable HTML page.

The HTML is the one a reviewer actually reads: each sentence of each
objection expands into the ledger entries it cites, and each entry shows the
Parseltongue node, the verbatim quote, and a link to the source record.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["write_json", "write_markdown", "write_html"]

_VERDICT_BADGE = {"promising": "promising", "rejected": "rejected", "undecided": "undecided"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def write_json(results: list[dict], meta: dict, path: Path) -> None:
    path.write_text(
        json.dumps({"meta": meta, "objections": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_markdown(results: list[dict], meta: dict, path: Path) -> None:
    lines = [
        "# Objections to the CRC target shortlist",
        "",
        f"Generated {_now()} · model `{meta.get('model', 'n/a')}` · "
        f"export `{meta.get('export', 'n/a')}`",
        "",
    ]
    promising = [r for r in results if r["verdict"] == "promising"]
    rejected = [r for r in results if r["verdict"] == "rejected"]
    lines.append(
        f"{len(results)} targets reviewed — {len(promising)} promising, {len(rejected)} rejected. "
        f"Each objection is five sentences, every sentence cited into the Parseltongue derivation."
    )
    lines.append("")

    for r in results:
        v = r["verification"]
        status = "verified" if v["verified"] else "FAILED VERIFICATION"
        lines += [
            f"## {r['target']} — engine verdict: {r['verdict']} ({status})",
            "",
            f"Verdict node `{r['verdict_node']}` · {r['ledger_size']} citable items · "
            f"{r['resolution']['resolved']}/{r['resolution']['checked']} external ids resolve",
            "",
        ]
        for s in v["sentences"]:
            mark = "" if s["grounded"] else " ⚠"
            lines.append(f"{s['index']}.{mark} {s['text']}")
        lines.append("")
        if r["flags"]:
            lines.append("**Audit flags fed to the model:**")
            lines += [f"- {f}" for f in r["flags"]]
            lines.append("")
        lines.append("**Backtrace**")
        lines.append("")
        lines.append("| key | source | resolves | node | quote |")
        lines.append("|---|---|---|---|---|")
        cited = {k for s in v["sentences"] for k in s["keys"]}
        for c in r["ledger"]:
            if c["key"] not in cited:
                continue
            src = f"{c['source']['type']}:{c['source']['id']}" if c["source"]["id"] else f"doc:{c['doc']}"
            if c["source"]["url"]:
                src = f"[{src}]({c['source']['url']})"
            res = {True: "yes", False: "**no**", None: "—"}[c["resolution"]["resolves"]]
            quote = c["quote"].replace("|", "\\|")[:110]
            lines.append(f"| {c['key']} | {src} | {res} | `{c['node']}` | {quote} |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def write_html(results: list[dict], meta: dict, path: Path) -> None:
    rows = []
    for r in results:
        v = r["verification"]
        by_key = {c["key"]: c for c in r["ledger"]}
        sentences_html = []
        for s in v["sentences"]:
            cites = []
            for key in s["keys"]:
                c = by_key.get(key)
                if not c:
                    continue
                src = f"{c['source']['type']}:{c['source']['id']}" if c["source"]["id"] else f"doc:{c['doc']}"
                link = (
                    f'<a href="{_esc(c["source"]["url"])}" target="_blank" rel="noreferrer">{_esc(src)}</a>'
                    if c["source"]["url"]
                    else f"<span>{_esc(src)}</span>"
                )
                res = c["resolution"]["resolves"]
                badge = (
                    '<em class="ok">resolves</em>'
                    if res is True
                    else '<em class="bad">does not resolve</em>'
                    if res is False
                    else '<em class="warn">unchecked</em>'
                )
                title = f'<div class="title">{_esc(c["resolution"]["title"])}</div>' if c["resolution"]["title"] else ""
                cites.append(
                    f'<li><span class="key">{_esc(key)}</span> {link} {badge}'
                    f'<div class="node">node <code>{_esc(c["node"])}</code> · doc <code>{_esc(c["doc"])}</code></div>'
                    f'<blockquote>{_esc(c["quote"])}</blockquote>{title}</li>'
                )
            problems = "".join(f'<li class="bad">{_esc(p)}</li>' for p in s["problems"])
            warnings = "".join(f'<li class="warn">{_esc(w)}</li>' for w in s["warnings"])
            issues = f'<ul class="issues">{problems}{warnings}</ul>' if (problems or warnings) else ""
            sentences_html.append(
                f'<details class="sentence{"" if s["grounded"] else " ungrounded"}">'
                f"<summary><span class=\"num\">{s['index']}</span>{_esc(s['text'])}</summary>"
                f'{issues}<ul class="cites">{"".join(cites)}</ul></details>'
            )
        flags = "".join(f"<li>{_esc(f)}</li>" for f in r["flags"])
        flags_section = (
            f"<div class='flags'><h3>Audit flags fed to the model</h3><ul>{flags}</ul></div>"
            if flags
            else ""
        )
        rows.append(
            f'<section class="target {r["verdict"]}">'
            f'<h2>{_esc(r["target"])} <span class="badge">{_esc(_VERDICT_BADGE.get(r["verdict"], r["verdict"]))}</span>'
            f'<span class="vstat {"ok" if v["verified"] else "bad"}">'
            f'{"objection verified" if v["verified"] else "objection failed verification"}</span></h2>'
            f'<p class="meta">verdict node <code>{_esc(r["verdict_node"])}</code> · '
            f'{r["ledger_size"]} citable items · '
            f'{r["resolution"]["resolved"]}/{r["resolution"]["checked"]} external ids resolve · '
            f'model {_esc(r.get("model", ""))}</p>'
            f'{"".join(sentences_html)}'
            f"{flags_section}"
            f"</section>"
        )

    css = """
:root{--bg:#fbfaf8;--fg:#1c1b19;--mut:#6b6862;--line:#e2ded7;--ok:#1f7a4d;--bad:#a8321f;--warn:#8a6a12;--card:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#16150f;--fg:#eae7e0;--mut:#9b968c;--line:#332f28;--ok:#5fbf8e;--bad:#e2725b;--warn:#d3a83b;--card:#1e1d16}}
*{box-sizing:border-box}body{margin:0;padding:2rem 1.25rem 5rem;background:var(--bg);color:var(--fg);
font:16px/1.55 ui-serif,Georgia,serif;max-width:60rem;margin-inline:auto}
h1{font-size:1.7rem;margin:0 0 .3rem}h2{font-size:1.25rem;margin:0 0 .35rem;display:flex;gap:.6rem;align-items:baseline;flex-wrap:wrap}
.sub{color:var(--mut);margin:0 0 2rem;font-size:.9rem}
section.target{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1.1rem 1.2rem;margin:0 0 1.4rem}
.badge{font:600 .7rem/1 ui-sans-serif,system-ui;text-transform:uppercase;letter-spacing:.06em;padding:.3rem .5rem;border-radius:4px;border:1px solid var(--line);color:var(--mut)}
.promising .badge{color:var(--ok);border-color:var(--ok)}.rejected .badge{color:var(--bad);border-color:var(--bad)}
.vstat{font:600 .7rem/1 ui-sans-serif,system-ui;letter-spacing:.04em}.vstat.ok{color:var(--ok)}.vstat.bad{color:var(--bad)}
p.meta{color:var(--mut);font-size:.82rem;margin:.1rem 0 1rem;font-family:ui-sans-serif,system-ui}
details.sentence{border-top:1px solid var(--line);padding:.6rem 0}
details.sentence summary{cursor:pointer;list-style:none;display:flex;gap:.6rem}
details.sentence summary::-webkit-details-marker{display:none}
.num{color:var(--mut);font:600 .8rem/1.7 ui-sans-serif,system-ui;min-width:1.1rem}
details.ungrounded summary{color:var(--bad)}
ul.cites{list-style:none;margin:.7rem 0 .2rem;padding:0 0 0 1.7rem;display:grid;gap:.7rem}
ul.cites li{border-left:2px solid var(--line);padding-left:.8rem}
.key{font:600 .72rem/1 ui-sans-serif,system-ui;background:var(--line);padding:.22rem .4rem;border-radius:3px;margin-right:.4rem}
.node{color:var(--mut);font-size:.76rem;font-family:ui-sans-serif,system-ui;margin:.25rem 0}
blockquote{margin:.3rem 0;padding:.35rem .6rem;background:var(--bg);border-radius:4px;font-size:.88rem}
.title{color:var(--mut);font-size:.78rem;font-family:ui-sans-serif,system-ui}
em.ok{color:var(--ok);font-style:normal;font-size:.72rem;font-family:ui-sans-serif,system-ui}
em.bad{color:var(--bad);font-style:normal;font-size:.72rem;font-family:ui-sans-serif,system-ui}
em.warn{color:var(--warn);font-style:normal;font-size:.72rem;font-family:ui-sans-serif,system-ui}
ul.issues{margin:.4rem 0 0 1.7rem;padding:0;font-size:.8rem;font-family:ui-sans-serif,system-ui}
ul.issues .bad{color:var(--bad)}ul.issues .warn{color:var(--warn)}
.flags{margin-top:1rem;border-top:1px solid var(--line);padding-top:.7rem}
.flags h3{font:600 .75rem/1 ui-sans-serif,system-ui;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 .5rem}
.flags ul{margin:0;padding-left:1.1rem;font-size:.82rem;color:var(--mut);font-family:ui-sans-serif,system-ui}
code{font-size:.85em}
"""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Objections — CRC target shortlist</title><style>{css}</style></head><body>
<h1>Objections to the CRC target shortlist</h1>
<p class="sub">{_esc(_now())} · model <code>{_esc(meta.get('model', 'n/a'))}</code> ·
export <code>{_esc(str(meta.get('export', 'n/a')))}</code> ·
every sentence expands into the Parseltongue nodes and source records it cites</p>
{''.join(rows)}
</body></html>"""
    path.write_text(doc, encoding="utf-8")
