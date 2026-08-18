# Stage 5 — citation resolving check

Stage 4 checks that an objection cites only what is in the ledger. Stage 5 asks
the prior question: **do the cited records say what the dossier claims they
say?**

Resolving an identifier is the weakest possible check. It proves the record
exists. It does not prove the paper is about the gene it was filed under, that
the quoted title is still the record's title, or that the paper has not been
retracted since it was indexed.

## What is graded

Four mechanical grades per citation, plus a retraction check:

| grade | question | values |
|---|---|---|
| resolution | does the registry return a record for this id | yes / no / unknown |
| title fidelity | does the quoted title still match the registry title | match / drift |
| subject role | where the attributed gene appears | title / abstract / absent |
| indication role | where the disease appears | title / abstract / absent / n/a |

Gene names are resolved through the reviewed **UniProt** entry, so `ERBB2` also
matches `HER2`, `Receptor tyrosine-protein kinase erbB-2` and every other name
that entry lists. Without this, most oncology literature reads as off-target.

Status is assigned in fixed precedence:

| status | meaning |
|---|---|
| `unresolved` | the registry returns no record |
| `retracted` | retracted, or under an expression of concern |
| `off-target` | the gene appears nowhere in the record, under any of its names |
| `title-drift` | resolves, but the quoted title no longer matches |
| `weak-attribution` | the gene is mentioned but is not the subject; or the record names no colorectal indication; or a trial matched the target only by free-text search |
| `sound` | resolves, title matches, gene is the subject, indication present |

Trials get their own rule. A trial record names drugs, not genes, so a missing
gene symbol there is not evidence of being off target — it means the trial was
pulled in by a text query, and only the indication lines up. That is reported as
weak attribution, not as an off-target record.

## Input

The same pg-bench export stage 4 consumes — `--export` once per file. Citations
are pulled with the same ledger machinery, so both stages talk about exactly the
same record set.

## Output

Written to `--out` (default `results/stage5`):

| file | contents |
|---|---|
| `citations.json` | every citation with all four grades, the registry title, and the reasons |
| `citations.md` | digest by target, flagged citations first |
| `docs/registry-<TARGET>.txt` | the recorded registry response, one document per target |
| `src/<target>.pltg` | those results as Parseltongue facts quoting the snapshot |
| `.registry-cache.json` | registry responses, so repeat runs cost nothing |

The last two exist for stage 6, which will not accept a JSON file it cannot
quote. Skip them with `--no-pltg`.

## Usage

```bash
uv run agnostik-citecheck \
    --export examples/stage4/fixtures/crc6-dossiers.html \
    --export examples/stage4/fixtures/crc6-verdicts.html \
    --out results/stage5
```

Exit codes: `0` clean, `3` when a citation lands in a status named by
`--fail-on` (default `off-target,retracted,unresolved`), so the check is usable
as a gate. `--offline` restricts the run to cached registry responses.

## What it found in the sample run

57 citations across the six targets: 21 subject-level, 1 off-target, 0 retracted,
0 unresolved, the rest weak attribution. Two examples of what the grade is for:

* `PMID 41630900`, filed under PRMT5 as in-vivo support, is about a nuclear
  HADH isoform — PRMT5 appears only in the abstract.
* `PMID 42527030`, filed under KRAS, never names KRAS at all.

Both resolve perfectly. A resolution-only check passes them.
