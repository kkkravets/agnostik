# Objection-generation example

Everything here exists so objection generation can be run and reviewed without
the preceding evidence and verdict stages.

* `fixtures/` — a **stand-in** for stages 1–3: live evidence collected from
  PubMed, ClinicalTrials.gov and UniProt (`collect.py`), turned into a
  Parseltongue system (`build_pltg.py`), and exported with pg-bench
  (`candidate-dossiers.html`, `candidate-verdicts.html`). Replace these with the
  real upstream export when it lands.
* `output/` — one full run over those exports:
  `objections.md` to read, `objections.html` to click through the backtrace,
  `objections.json` for the machine-readable record, and `prompt-MYC.txt` for
  the exact prompt the model was given.

Reproduce the sample:

```bash
uv run agnostik-objections run \
    --export examples/objections/fixtures/candidate-dossiers.html \
    --export examples/objections/fixtures/candidate-verdicts.html \
    --out results/objections
```
