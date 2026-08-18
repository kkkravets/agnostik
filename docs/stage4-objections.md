# Stage 4 — objections with a backtrace

Stage 4 of the CRC target-triage pipeline. Stages 1–3 collect evidence and let
Parseltongue derive a verdict per target. This stage argues against every
verdict — and shows its work.

For each target it produces a **five-sentence objection** written by a Nebius
Token Factory model, where

* every sentence cites at least one ledger key (`[E7]`),
* every key resolves to a Parseltongue node, a source document and a verbatim
  quote,
* every external identifier (PMID, NCT, UniProt) is checked against its
  registry before the model is allowed to lean on it,
* and the objection is rejected and rewritten if it cites something that is not
  there.

The point is not fluent criticism. It is criticism you can walk backwards:
sentence → citation key → derivation node → quoted document line → the record
in PubMed or ClinicalTrials.gov.

## Input

One or more **pg-bench JSON exports**. Produce them from the stage-3 system:

```bash
pg start shortlist.pltg && pg wait
pg eval '(fmt "viz" (scope lens (focus "src.")))'      > dossiers.html
pg eval '(fmt "viz" (scope lens (fuzzy "promising")))' > verdicts.html
```

Accepted containers — all carry the same four globals:

| form | how it is produced |
|---|---|
| `*.html` | `pg eval '(fmt "viz" …)' > export.html` |
| `*.js` | `sh extract_viz_data.sh export.html` |
| `*.json` | `{"DATA": [...], "STRUCTURE_DATA": [...], "LAYERS": {...}, "TAINT_DATA": {...}}`, or a bare `DATA` array |

Pass `--export` once per file; they are merged, so a dossier view and a verdict
view can be handed over separately.

**What the export must contain**

| needed | where it comes from | if missing |
|---|---|---|
| a verdict node per target | node id matching `verdict\|promising\|rejected\|shortlist\|decision` (override with `--verdict-pattern`) | the target is skipped |
| claim nodes with `inputs` | `(derive …  :using (…))` | the ledger is shallow — only direct evidence |
| fact nodes with `evidence` | `(fact … :evidence (evidence "doc" :quotes ("…")))` | nothing citable; the target is skipped |
| PMID / NCT / UniProt ids | evidence `explanation`, node name (`paper-42345355`, `trial-NCT06940778`), the quote, or its context | the citation stays a document-level one |

Targets default to the fixed six-gene panel (`EGFR, ERBB2, KRAS, MYC, WRN,
PRMT5`); override with `--targets`.

**Credentials** — read from the environment only, never from a flag:
`TOKENFACTORY_TOKEN` or `NEBIUS_API_KEY` (a `.env` is picked up when
`python-dotenv` is installed). Optional: `NEBIUS_MODEL`, `NEBIUS_BASE_URL`.

## Output

Written to `--out` (default `out/`):

| file | contents |
|---|---|
| `objections.json` | everything: verdict, claims, full ledger, derivation chain, model attempts, and per-sentence verification with its backtrace |
| `objections.md` | digest — the five sentences per target plus a backtrace table of the cited evidence |
| `objections.html` | the reviewable artefact: each sentence expands into its citations, each citation shows node, quote, registry status and a link to the record |
| `prompt-<TARGET>.txt` | with `--print-prompt`: the exact prompt the model saw |
| `.resolve-cache.json` | registry lookups, so repeat runs cost nothing |

Shape of one objection in `objections.json`:

```jsonc
{
  "target": "PRMT5",
  "verdict": "rejected",                  // as derived by stage 3
  "verdict_node": "prmt5-promising",
  "model": "moonshotai/Kimi-K3",
  "claims":    [ { "id": "src.prmt5.druggable", "value": "True", "rule": "...", "inputs": [...] } ],
  "flags":     [ "counter at zero: src.prmt5.trials-recruiting = 0", ... ],
  "ledger":    [ { "key": "E13", "node": "src.prmt5.paper-41513606",
                   "doc": "pubmed-PRMT5", "quote": "TITLE: ...",
                   "source": { "type": "pmid", "id": "41513606", "url": "https://..." },
                   "resolution": { "resolves": true, "title": "..." } } ],
  "derivation_chain": [ { "node": "prmt5-promising", "hops": 0 }, ... ],
  "verification": {
    "verified": true,
    "sentences": [ { "index": 1, "text": "...", "keys": ["E3","E4"],
                     "grounded": true, "backtrace": [ /* full citation records */ ] } ]
  }
}
```

## Verification contract

An objection is only reported as `verified` when all of this holds:

1. exactly five sentences (`--sentences` to change),
2. every sentence carries at least one citation key,
3. every key exists in that target's ledger,
4. no PMID or NCT id appears in the text unless it is in the ledger.

Numbers absent from every cited quote, citations that do not resolve, and
quotes Parseltongue could not verify are recorded as **warnings** — they do not
fail the objection, they travel with it into the report. On failure the model
is re-prompted once with the verifier's findings (`--attempts`).

## Usage

```bash
uv run agnostik-objections run \
    --export examples/stage4/fixtures/crc6-dossiers.html \
    --export examples/stage4/fixtures/crc6-verdicts.html \
    --out results/stage4 --print-prompt
```

Inspect what was parsed out of an export before spending anything:

```bash
uv run agnostik-objections inspect \
    --export examples/stage4/fixtures/crc6-dossiers.html --ledger
```

List the live Token Factory catalogue:

```bash
uv run agnostik-objections models
```

Useful flags: `--dry-run` (compose offline, no API call, no spend — the
verifier, backtrace and reports all still run), `--no-resolve` (skip registry
checks), `--ledger-limit`, `--max-hops`, `--model`, `--temperature`.

## What is a stand-in here

`examples/stage4/fixtures/` is a **development stand-in for stages 1–3**, not part of
this stage's deliverable:

* `collect.py` pulls live evidence for the six targets (PubMed E-utilities,
  ClinicalTrials.gov v2, UniProt) via the ClawBio skills,
* `build_pltg.py` writes the source documents, one Parseltongue module per
  target, the charter-grounded rules, and the entry point,
* `crc6-dossiers.html` / `crc6-verdicts.html` are the resulting pg-bench
  exports, checked in so stage 4 runs without stages 1–3.

Replace them with the real upstream export as soon as stages 1–3 emit one;
nothing in `src/agnostik/objections/` knows about the fixture. Regenerate the
stand-in with:

```bash
uv run python examples/stage4/fixtures/collect.py       # live evidence -> raw/*.json + docs/
uv run python examples/stage4/fixtures/build_pltg.py    # -> src/*.pltg + shortlist.pltg
cd examples/stage4/fixtures && pg start shortlist.pltg && pg wait
pg eval '(fmt "viz" (scope lens (focus "src.")))'      > crc6-dossiers.html
pg eval '(fmt "viz" (scope lens (fuzzy "promising")))' > crc6-verdicts.html
```

## Tests

```bash
uv run python -m unittest discover -s tests -p 'test_objections_*.py'
```

The stage adds no third-party dependencies — `agnostik.objections` is standard
library only, and picks up `.env` through `python-dotenv` when it is present.

## Where it sits in the pipeline

```
stage 1-3  ──  Parseltongue shortlist system  ──►  pg-bench export (.html/.js/.json)
                                                        │
                                                        ▼
stage 4                                   agnostik.objections
                                          ├─ bundle.py      parse + merge exports
                                          ├─ targets.py     find targets, claims, verdicts
                                          ├─ backtrace.py   derivation closure -> evidence ledger
                                          ├─ resolve.py     PMID / NCT / UniProt resolving check
                                          ├─ prompt.py      ledger + audit flags -> prompt
                                          ├─ tokenfactory.py  Nebius Token Factory call
                                          ├─ verify.py      five sentences, all cited, nothing invented
                                          ├─ fallback.py    offline composer for --dry-run
                                          └─ report.py      objections.json / .md / .html
```
