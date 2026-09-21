# Objection workflow example

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
    --export examples/objection-workflow/fixtures/candidate-dossiers.html \
    --export examples/objection-workflow/fixtures/candidate-verdicts.html \
    --out results/objections
```

These fixtures are also used by `tests/test_objections_fixtures.py`. They are
separate from the individual PMC full-text articles used by the verdict notebook.
The integration tests load `shortlist.pltg` and its documents, check quoted
evidence and verdicts against the checked-in exports, and check citation URLs.
They make no model or registry API calls and do not regenerate the fixtures.

Run from the repository root (UTF-8 mode is needed for the fixture text on Windows
because the Parseltongue loader uses the platform default encoding):

```bash
uv run python -X utf8 -m unittest discover -s tests -p 'test_objections_fixtures.py' -v
```
