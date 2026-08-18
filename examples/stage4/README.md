# Stage 4 example material

Everything here exists so stage 4 can be run and reviewed without stages 1–3.

* `fixtures/` — a **stand-in** for stages 1–3: live evidence collected from
  PubMed, ClinicalTrials.gov and UniProt (`collect.py`), turned into a
  Parseltongue system (`build_pltg.py`), and exported with pg-bench
  (`crc6-dossiers.html`, `crc6-verdicts.html`). Replace with the real upstream
  export when it lands.
* `sample-output/` — one full run over those exports:
  `objections.md` to read, `objections.html` to click through the backtrace,
  `objections.json` for the machine-readable record, and `prompt-MYC.txt` for
  the exact prompt the model was given.

Reproduce the sample:

```bash
uv run agnostik-objections run \
    --export examples/stage4/fixtures/crc6-dossiers.html \
    --export examples/stage4/fixtures/crc6-verdicts.html \
    --out results/stage4
```
