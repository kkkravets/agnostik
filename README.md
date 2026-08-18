# Agnostik

Hackathon workspace for **“pick a cancer target you would defend.”** The goal is
to shortlist oncology targets from live TCGA evidence while making the case
against each target as visible as the case for it. At least one candidate must
be rejected explicitly, with a traceable reason.

The first workflow boundary is implemented: accept a TCGA tumour type and
return the fixed v1 candidate panel. Evidence collection and scoring are not
implemented yet.

## v1 scope

The v1 workflow receives a TCGA tumour type as input and evaluates this fixed
gene panel:

```text
EGFR, ERBB2, KRAS, MYC, WRN, PRMT5
```

Candidate-gene discovery is out of scope for v1: the three-target shortlist
must be selected from this predefined panel using the evidence collected by the
workflow.

Run the current selection step with:

```bash
uv run agnostik BRCA
```

Expected output:

```text
Tumour type: BRCA
Candidates: EGFR, ERBB2, KRAS, MYC, WRN, PRMT5
```

Use `--json` when feeding this selection into a later workflow stage:

```bash
uv run agnostik BRCA --json
```

## Prerequisites

- Python 3.11 (3.12 and 3.13 are also accepted by the project metadata)
- [`uv`](https://docs.astral.sh/uv/) for dependency and environment management
- Docker with Compose, only if using the container workflow
- Network access while installing dependencies and while querying UCSC Xena,
  PubMed, and clinical-trial sources

The environment pins ClawBio 0.6.1 and Parseltongue DSL 0.7.4. The lockfile is
the source of truth for all transitive Python dependencies.

## Connect Parseltongue to Nebius

Nebius Token Factory exposes an OpenAI-compatible API. Copy `.env.example` to
`.env`, add your Nebius API key and a tool-calling model ID available to your
account, then run the connectivity check:

```bash
uv run agnostik-nebius-smoke
```

A successful check prints:

```json
{"connected": true, "tool_result": {"status": "ok"}}
```

The project uses `agnostik.nebius.NebiusProvider`, which adapts
Parseltongue's forced tool calls to Nebius's explicit function-selection
format. Use it with the Python pipeline like this:

```python
from parseltongue import Pipeline, System

from agnostik.nebius import create_nebius_provider

pipeline = Pipeline(System(overridable=True), create_nebius_provider())
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

## Analysis workflow

The v1 workflow should:

1. Read the ClawBio instructions and the specifications for
   `xena-tcga-gene-query`, `target-validation-scorer`,
   `omics-target-evidence-mapper`, `clinical-trial-finder`, and
   `pubmed-summariser`.
2. Accept a TCGA tumour type as input and select the fixed candidate panel.
   This step is implemented. Do not search for candidate genes.
3. Query UCSC Xena live for tumour-versus-normal expression and survival
   association for `EGFR`, `ERBB2`, `KRAS`, `MYC`, `WRN`, and `PRMT5` in that
   tumour type.
4. Select a three-target shortlist from the fixed panel and give evidence for
   and against each target equal visibility.
5. Reject at least one target explicitly and record the evidence that killed it.
6. Check prior art in PubMed and clinical trials.
7. Resolve every PMID before it enters any output. If the source cannot be
   fetched and confirmed, drop the claim instead of citing it.

Analysis artifacts should be written below `results/`, which is intentionally
ignored by Git.

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

Useful upstream references:

- [ClawBio](https://github.com/ClawBio/ClawBio)
- [Parseltongue](https://github.com/sci2sci-opensource/parseltongue)
- [Challenge 2 data notes](https://docs.clawbio.ai/hackathon/berlin/data/#challenge-2-a-cancer-target-you-would-defend)
