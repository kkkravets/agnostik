# Agnostik

Hackathon workspace for **“pick a cancer target you would defend.”** The system
evaluates a fixed oncology target panel while making the case against each
target as visible as the case for it. Every verdict retains a traceable evidence
path.

## v1 scope

The v1 workflow receives a TCGA tumour type as input and evaluates this fixed
gene panel:

```text
EGFR, ERBB2, KRAS, MYC, WRN, PRMT5
```

The panel is predefined for v1. All six candidates continue through evidence
collection, verdict generation, and objection generation.

Display the fixed candidate panel with:

```bash
uv run agnostik BRCA
```

Expected output:

```text
Tumour type: BRCA
Candidates: EGFR, ERBB2, KRAS, MYC, WRN, PRMT5
```

Use `--json` for machine-readable output:

```bash
uv run agnostik BRCA --json
```

## End-to-end COAD workflow

Run these commands from the repository root. `COAD` is the TCGA tumour code;
the workflow takes the human-readable disease term ("colon adenocarcinoma")
from the GDC project name for the code (or the saved `resolution.json`); pass
`--cancer-term` to override it.

1. Match the tumour to a disease and write the ranked candidate shortlist
   (see [Find target candidates](#find-target-candidates)):

   ```bash
   uv run agnostik COAD
   ```

2. Collect PubMed, open-access PMC full text, and ClinicalTrials.gov evidence
   for every candidate. Everything lands under `--output`, including
   `<tumour>/corpus.json` — the deduplicated article list the formalization stage consumes,
   which references the per-gene PMC files rather than copying them:

   ```bash
   uv run agnostik-collect-evidence COAD \
     --max-articles-per-gene 300 \
     --max-trials 100 \
     --output results/evidence \
     --skip-existing
   ```

3. Preview the formalization stage without API calls. The plan lists every
   document each target will read, every source it leaves out and why, the
   review rules as the pipeline read them, and the number of model calls:

   ```bash
   uv run agnostik-parseltongue COAD \
     --input results/evidence/coad/corpus.json \
     --output results/clawbio_skill_trial/tcga-coad/formalization_sample \
     --dry-run
   ```

4. Run the pipeline. Every document that mentions a target is read on its own:
   two model calls per document, then two per target. Targets and the documents
   within a target can run concurrently, and runtime grows with the number of
   calls the dry run prints. Keep `--resume` enabled so finished documents and
   targets survive an interruption:

   ```bash
   uv run agnostik-parseltongue COAD \
     --input results/evidence/coad/corpus.json \
     --output results/clawbio_skill_trial/tcga-coad/formalization_sample \
     --workers 3 \
     --document-workers 2 \
     --attempts 3 \
     --resume
   ```

5. At any time, snapshot completed targets without making model calls:

   ```bash
   uv run agnostik-parseltongue COAD \
     --output results/clawbio_skill_trial/tcga-coad/formalization_sample \
     --export-completed
   ```

6. Open
   [`notebooks/02_verdict_generation.ipynb`](notebooks/02_verdict_generation.ipynb)
   and run Sections 3–7 to refresh the partial export, validate verdicts, read
   candidate reports, inspect the JSON, and generate objections.

7. Alternatively, generate the final objection files entirely from the terminal:

   ```bash
   uv run agnostik-objections run \
     --export results/clawbio_skill_trial/tcga-coad/formalization_sample/formal-system.partial.json \
     --out results/objections-sample
   ```

The result path is `results/objections-sample/`: open `objections.html` for the
browsable report, `objections.md` for the text report, or `objections.json` for
the machine-readable record. Once all six targets finish, use the canonical
`formal-system.json` instead of `formal-system.partial.json` for the final
handoff.

### Review criteria

Every target is judged by the rules in a criteria file: by default the shipped
[`criteria/target-shortlist.md`](criteria/target-shortlist.md), or another one
passed with `--criteria`. The rules are not built into the code or the prompts,
so each project can bring its own file.

Each rule is a `##` section: the rule as one prose line, which is the text
quoted as evidence, followed by indented lines the pipeline reads:

```markdown
## R1 Chemical matter
A target has chemical matter when at least three of the supplied publications describe an inhibitor, degrader, small molecule or antibody acting on it.

    applies to: publications
    ask: Does this publication describe an inhibitor, degrader, small molecule or antibody acting on the target?
    met when: at least 3 documents answer yes
```

- `applies to` is `publications`, `trials`, or `publications and trials`.
- `ask` is the yes/no question put to each such document on its own.
- `met when: at least N documents answer yes` makes the rule count toward the
  verdict. A rule that is recorded and weighed but never decides the verdict
  carries the bare line `record only` instead.
- One section carries `verdict:`, rule ids joined by `and`, `or`, `not` and
  parentheses (the shipped file: `verdict: R1 and R3 and R4`).
- A section without indented lines, such as R7 Provenance, is prose only.

How the rules are applied to each target:

1. **Extract**, one call per document: the model reads that document alone and
   writes facts quoting it, aimed at the rules' questions.
2. **Judge**, one call per document: from those facts, with their values hidden,
   the model answers each question that applies to the document by deriving a
   true/false result named after the document and the rule, such as `pmc123.r3`.
3. **Combine**, no model: the pipeline writes Parseltongue statements that count
   each rule's yes answers and compute `<target>-verdict` from the `verdict:`
   line. Each statement quotes its rule from the criteria file, and those quotes
   are verified like any other.
4. **Check and report**, one call each: a fact-check and the human-readable
   answer, both given a per-rule summary instead of every fact.

`--dry-run` prints each rule's prose next to what the pipeline read from it, so a
mismatch (the prose says "two", the rule says 3) is visible before any spend, and
a malformed rule stops the run before any model call. The file is part of the
`--resume` fingerprint: editing a rule's `ask` or the scope line re-runs the
documents it concerns; any other edit re-runs only the combine and
check-and-report steps.

The shipped file is cancer-agnostic. It talks about "the disease named in the
review request", so the same file serves any tumour code. Its rules, in short:

| Rule | Meaning |
|---|---|
| R1 Chemical matter | at least three publications describe an inhibitor, degrader, small molecule or antibody against the target |
| R2 Mechanistic support | experimental work links the target to the disease (supporting, not decisive) |
| R3 In vivo support | an animal model, xenograft or similar experiment |
| R4 Clinical traction | a trial for the disease tests a therapy aimed at the target, names it or an alias in its own text, and is phase 3+ or recruiting |
| R5 Opposing evidence | evidence against the target is recorded and weighed, never dropped (record only) |
| R6 Verdict | promising = chemical matter + in vivo support + clinical traction; otherwise rejected |
| R7 Provenance | every fact quotes its document; an untraceable verdict is void |

Phrase rules only in terms of what the supplied documents can show (published
articles and clinical-trial records). Rules that need other data, such as
protein annotations, cannot be satisfied and will push verdicts to "rejected".
Thresholds such as "at least three publications" are yours to change.

### Target aliases

A document that names a target by another name (HER2 for ERBB2) counts as naming
it, both when documents are selected and in the rules' questions. The fixed
panel's aliases are `PRESELECTED_ALIASES` in `src/agnostik/candidates.py`; a
`--targets-file` CSV can add an `aliases` column with names separated by `;`.

Lines the pipeline adds to a source file, such as a trial's `Retrieved for
target:` line or the note that references were omitted, are removed before the
model sees the document. They are not part of the record, so they can never be
quoted as evidence.

This is separate from `examples/objection-workflow/fixtures/docs/charter.md`,
which is a colorectal-only demo input for the example and is not read by the
pipeline.

### Finding a cited document

The model refers to each document by a short key (the file name without its
extension, for example `PMC12162862`). The export also records the real file
name in a `SOURCES` map, and the objections backtrace shows it as
`doc:<file name>`: `doc:PMC12162862.txt` for an article,
`doc:trial-EGFR-NCT01234567.txt` for a trial record, `doc:target-shortlist.md`
for the criteria file. That file is the exact text snapshot the model read, not
the live web page, so it stays reproducible even if the article or trial record
later changes. To open one, look up its name in `corpus.json` (the file passed
to `--input`): each entry lists the `path`, relative to that file, and a
`sha256` to check the text has not changed. An export without a `SOURCES` map
(for example one produced by `pg-bench` directly) simply shows the bare key.

The article `.txt` files are a reading copy: abstract and body, without the
reference list. Other papers' titles are not evidence, and they would use up the
model's input budget and inflate the count of how often a target is mentioned.
The last line of such a text says so (`[References omitted from this text; …]`),
the `corpus.json` entry lists `"omitted": ["references"]`, and the complete
article, references included, stays in the archival XML under
`literature/artifacts/xml/`.

## Objections — with a backtrace

Once evidence collection and formalization have produced a Parseltongue verdict per target, the objections stage argues
against every verdict. For each target it writes a five-sentence objection with
a Nebius Token Factory model, where every sentence cites evidence by key, every
key resolves to a Parseltongue node and a verbatim document quote, and every
PMID / NCT / UniProt id is checked against its registry before the objection is
allowed to lean on it. An objection that miscounts its sentences, cites a key
that does not exist, or names an identifier absent from the ledger is rejected
and rewritten.

**Input:** one or more pg-bench JSON exports of the formalization system (`.html` from
`pg eval '(fmt "viz" …)'`, `.js` from `extract_viz_data.sh`, or plain JSON).
**Output:** `objections.json` (full record with per-sentence backtrace),
`objections.md` (digest plus backtrace table), `objections.html` (each sentence
expands into the nodes, quotes and source records it cites).

```bash
uv run agnostik-objections run \
    --export examples/objection-workflow/fixtures/candidate-dossiers.html \
    --export examples/objection-workflow/fixtures/candidate-verdicts.html \
    --out results/objections
```

Add `--dry-run` to exercise the ledger, verifier and reports with no API call
and no spend. Full contract, flags and the fixture stand-in for evidence collection and formalization:
[`docs/objections.md`](docs/objections.md).

## Prerequisites

- Python 3.11 (3.12 and 3.13 are also accepted by the project metadata)
- [`uv`](https://docs.astral.sh/uv/) for dependency and environment management
- Docker with Compose, only if using the container workflow
- Network access while installing dependencies and while querying UCSC Xena,
  PubMed, and clinical-trial sources

The environment pins ClawBio 0.6.1 and Parseltongue DSL 0.7.4. The lockfile is
the source of truth for all transitive Python dependencies.

## Connect project to Nebius

Nebius Token Factory exposes an OpenAI-compatible API. Copy `.env.example` to
`.env`, add your Nebius API key and a tool-calling model ID available to your
account, then run the connectivity check:

```bash
uv run agnostik-nebius-smoke
```


Do not pass the API key on the command line or commit `.env`. To use a custom
or dedicated OpenAI-compatible endpoint, set `NEBIUS_BASE_URL`.

## Run locally in a virtual environment

Create and activate a conventional `.venv`, then let `uv` synchronize the
locked dependencies into it.

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
uv sync --active --frozen
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
uv sync --active --frozen
```

Confirm both core dependencies import successfully:

```bash
uv run python -c "import clawbio, parseltongue; print('environment ready')"
```

Deactivate the virtual environment later with `deactivate`.

## Run with Docker

Build the locked environment once:

```bash
docker compose build
```

Open an interactive analysis shell:

```bash
docker compose run --rm analysis
```

The repository is mounted at `/workspace`; generated files therefore remain on
the host. Inside the container, confirm the environment with:

```bash
uv run python -c "import clawbio, parseltongue; print('environment ready')"
```

Exit the shell with `exit`. To execute a one-off command instead:

```bash
docker compose run --rm analysis uv run agnostik BRCA
```

## Find target candidates

`agnostik` takes a TCGA code (default `COAD`, colorectal cancer). The
GDC names the TCGA project (`READ` is "Rectum Adenocarcinoma"), Open Targets
search matches that name to a disease, and the top protein-coding genes are
written to `results/targets/<tumour>/`:

```bash
uv run agnostik READ --top-n 20
```

- `symbols.txt` is the ranked gene list, one symbol per line; `candidates.csv`
  adds scores for review; `resolution.json` records the disease match.
- The later stages use `symbols.txt` automatically when it exists (`--fixed-panel`
  forces the v1 panel), and take their search term from `resolution.json`.
- More detail: [`src/agnostik/targets/README.md`](src/agnostik/targets/README.md).
- The match is printed with warnings when it is inexact or has a close runner-up.
  `--disease "rectal cancer"` searches another name, `--disease-id MONDO_...`
  skips the search, and `agnostik READ --fixed-panel` prints the v1 panel offline.

## Collect literature and trial evidence

The `agnostik-collect-evidence` pipeline step applies one base disease query to every
candidate gene. The base query is the quoted cancer term, so for COAD each
PubMed/PMC expression has this form:

```text
"colon adenocarcinoma"[Title/Abstract] AND GENE[Title/Abstract]
```

The tumour code itself is not searched: acronyms such as READ collide with ordinary
words. To widen the search (for example to `colorectal`), pass `--article-query`.

Run all six predefined genes from the host console, requesting up to 300
complete open-access articles per gene:

```bash
uv run agnostik-collect-evidence COAD \
  --max-articles-per-gene 300 \
  --output results/evidence \
  --skip-existing
```

Run the identical step through Docker:

```bash
docker compose run --rm analysis \
  uv run agnostik-collect-evidence COAD \
  --max-articles-per-gene 300 \
  --output results/evidence \
  --skip-existing
```

All runs are grouped beneath the single tumour root `results/evidence/coad/`.
Gene and run-ID subdirectories prevent parallel or repeated runs from
overwriting one another, while `results/evidence/coad/batch_manifest.json`
records every generated query and result location. Use repeated `--gene`
options to run a subset, or `--article-query` to replace the base disease
expression; the pipeline still appends `AND GENE[Title/Abstract]` to each one.

## Run Parseltongue over the COAD full-text corpus

The next pipeline step reads `results/evidence/coad/corpus.json` and loads the
`.txt` articles and trial records it references, which stay where the collection
stage wrote them. For each fixed candidate (`EGFR, ERBB2, KRAS, MYC, WRN, PRMT5`)
it selects every document that mentions the target or one of its aliases, reads
each one on its own, and applies the [review criteria](#review-criteria):
extract, judge, combine, check and report. Each target ends with one Boolean
`<target>-verdict` whose `:using` chain passes through the per-document answers
and terminates in facts carrying verified, verbatim document quotes.

Inspect the plan without API calls, output writes, or model spend:

```bash
uv run agnostik-parseltongue COAD --dry-run
```

Run locally using `NEBIUS_API_KEY`, `NEBIUS_MODEL`, and optionally
`NEBIUS_BASE_URL` from `.env`:

```bash
uv run agnostik-parseltongue COAD --resume
```

Process independent targets, and the documents within a target, concurrently:

> **Runtime:** two model calls per document plus two per target; `--dry-run`
> prints the total. Each document is cached as soon as its two calls succeed,
> so rerunning with `--resume` repeats no call whose prompt is unchanged. If a
> document still fails after `--attempts`, the run stops and names it; the next
> `--resume` retries only that document.

```bash
uv run agnostik-parseltongue COAD --resume --workers 3 --document-workers 2 --attempts 3
```

Run the same step through Docker:

```bash
docker compose run --rm analysis \
  uv run agnostik-parseltongue COAD --resume
```

Results are written to
`results/clawbio_skill_trial/tcga-coad/formalization/`:

- `formal-system.json` — the primary deliverable for the objections stage, containing
  `DATA`, `STRUCTURE_DATA`, `LAYERS`, and `TAINT_DATA`;
- `targets/<target>/system.json` — the formal system for one candidate;
- `targets/<target>/answer.md` — the human-readable candidate report;
- `targets/<target>/documents/<document>/` — per document: the raw extraction
  and judgement outputs, the statements loaded from them, and `record.json`
  with the fact count, any truncation, and every statement that failed, was
  loaded under a new name, or was recovered from unbalanced parentheses;
- `targets/<target>/passes/` — the combine statements written from the criteria,
  the fact-check output, and the raw answer;
- `targets/<target>/manifest.json` — the verdict, each rule's count and which
  documents answered yes, no or nothing, every document read, every source
  left out with the reason, and the number of model calls;
- `manifest.json` — the six-target formalization run manifest.

The generated JSON is parsed immediately with the real objections loader. The run
fails unless all requested candidates have a Boolean verdict and at least one
verified quoted fact. Hand it to the objections stage with:

```bash
uv run agnostik-objections run \
  --export results/clawbio_skill_trial/tcga-coad/formalization/formal-system.json \
  --out results/objections
```

By default every document that mentions a target is read.
`--max-documents-per-target N` keeps at most N articles and N trial records per
target, the most target-specific first; the rest are listed in the target
manifest. A document longer than `--max-document-chars` (default 120,000) is cut
for the prompt and recorded as truncated; quotes are still verified against its
full text. `--resume` reuses finished documents and targets whose fingerprint is
unchanged; `--overwrite` starts fresh. The source article folder is never
modified.

A statement the model writes never replaces an existing one. Parseltongue itself
would overwrite a reused name, so a clash is loaded under a new name (`x.2`)
next to a diff against the original, which the consistency report then shows.
An unmatched `)`, which would make Parseltongue drop every statement after it,
is skipped and recorded instead.

### Inspect results before every target has finished

Completed targets are durable: each receives its `system.json`, `answer.md`,
and `manifest.json` before the next target finishes. If a later target fails or
the long-running command is interrupted, create an objections-compatible partial
export from everything completed so far. This command makes no model calls:

```bash
uv run agnostik-parseltongue COAD \
  --output results/clawbio_skill_trial/tcga-coad/formalization_sample \
  --export-completed
```

It writes:

```text
results/clawbio_skill_trial/tcga-coad/formalization_sample/formal-system.partial.json
```

To produce the target systems used by the sample notebook, run the formalization stage from the
repository root with matching input, output, and context settings:

```bash
uv run agnostik-parseltongue COAD \
  --input results/evidence/coad/corpus.json \
  --output results/clawbio_skill_trial/tcga-coad/formalization_sample \
  --max-documents-per-target 3 \
  --workers 3 \
  --attempts 3 \
  --resume
```

`--max-documents-per-target 3` keeps the sample small: three articles and three
trial records per target. `--workers 3` processes up to three targets
concurrently. `--attempts 3` retries a model call that fails; a statement that
does not load is recorded in its document's `record.json` rather than failing
the target. `--resume` reuses documents and targets whose fingerprint still
matches.

### Explore the partial export in the notebook

Open
[`notebooks/02_verdict_generation.ipynb`](notebooks/02_verdict_generation.ipynb).
The notebook does not run the long formalization model pipeline. Its result workflow
is:

1. Run the setup/configuration cell so paths and imports point at this checkout.
2. Section 3 refreshes `formal-system.partial.json` using the same
   `export_completed_targets` implementation as the `--export-completed` CLI
   flag; it makes no model calls.
3. Section 4 validates the completed targets with the real objections loader and
   displays their verdict summary.
4. Section 5 renders each completed target's `answer.md` report.
5. Section 6 displays the partial JSON contract and provides a file link.
6. Section 7 first inspects the evidence ledger, then generates Objections
   objections. Its two code cells are standalone and locate the partial export
   directly.

The second Section-7 cell may make Token Factory model calls when an API key is
available. Add `--dry-run` to its argument list for offline objection
generation.

The equivalent terminal commands are:

```bash
uv run agnostik-objections inspect \
  --export results/clawbio_skill_trial/tcga-coad/formalization_sample/formal-system.partial.json \
  --ledger

uv run agnostik-objections run \
  --export results/clawbio_skill_trial/tcga-coad/formalization_sample/formal-system.partial.json \
  --out results/objections-sample
```

The objections stage writes the final browsable and machine-readable results to:

```text
results/objections-sample/objections.md
results/objections-sample/objections.html
results/objections-sample/objections.json
```

When all six targets finish, the formalization command also writes the canonical
`formal-system.json` and top-level `manifest.json`. Use that full export instead
of the partial export for the final six-target handoff.

## Access ClawBio skill scripts directly

The installed ClawBio distribution bundles its `skills` directory. Resolve its
location once so scripts can be called by direct path, as required by the
challenge.

### macOS / Linux or the Docker shell

```bash
CLAWBIO_ROOT="$(uv run python -c 'from pathlib import Path; import clawbio; print(Path(clawbio.__file__).parent)')"

uv run python "$CLAWBIO_ROOT/skills/xena-tcga-gene-query/scripts/query_tcga_api.py" \
  --demo --output results/xena \
  diff-expr --gene EGFR --cancer BRCA
```

### Windows PowerShell

```powershell
$clawbioRoot = uv run python -c "from pathlib import Path; import clawbio; print(Path(clawbio.__file__).parent)"

uv run python "$clawbioRoot/skills/xena-tcga-gene-query/scripts/query_tcga_api.py" `
  --demo --output results/xena `
  diff-expr --gene EGFR --cancer BRCA
```

Keep global flags such as `--demo` and `--output` before the subcommand
(`diff-expr` in this example). Read each relevant `SKILL.md` before running its
script.

## Implemented analysis workflow

The v1 workflow:

1. Accepts a TCGA tumour code and returns the fixed six-candidate panel. This
   validates the code's format; it does not discover or rank candidate genes.
2. Collects PubMed summaries, complete open-access PMC articles, and
   ClinicalTrials.gov evidence for every candidate.
3. Records the unique collected full-text articles, plus one rendered text per clinical trial, in one formalization corpus manifest.
4. Selects every document that mentions each candidate, has Parseltongue extract
   and judge each one on its own against the review criteria, and derives one
   grounded Boolean verdict per candidate from those per-document answers.
5. Exports all completed candidate systems in the JSON contract consumed by
   the objection stage.
6. Generates an objection to every available verdict, traces its citations back
   to evidence nodes and source quotes, checks external identifiers, and records
   unresolved or weak evidence in the report.

Analysis artifacts are written below `results/`.

## Dependency changes

Edit dependencies with `uv add` or update them deliberately, then regenerate
and commit the lockfile:

```bash
uv lock
uv sync
```

Run the current test suite with:

```bash
uv run python -m unittest discover -s tests
```

On Windows, set `PYTHONUTF8=1` as well:

```powershell
$env:PYTHONUTF8 = "1"; uv run python -m unittest discover -s tests
```

Parseltongue opens `load-document` sources with `open(path)` and no `encoding=`,
so on Windows it reads them as cp1252. The objection fixture's documents are
UTF-8 journal text, so without UTF-8 mode one test errors in `setUpClass` and
takes its whole class with it — the suite reports 49 tests instead of 53.
`PYTHONUTF8=1` makes `open()` default to UTF-8 and the difference disappears.

This affects only code that hands Parseltongue a *path*. The formalization stage
reads articles itself and registers them with `add_document(name, text=...)`,
which never touches the filesystem, so it is unaffected on every platform.

Useful upstream references:

- [ClawBio](https://github.com/ClawBio/ClawBio)
- [Parseltongue](https://github.com/sci2sci-opensource/parseltongue)
- [Challenge 2 data notes](https://docs.clawbio.ai/hackathon/berlin/data/#challenge-2-a-cancer-target-you-would-defend)
