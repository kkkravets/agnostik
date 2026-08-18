# Stages 5 and 6 — example output

A full run of both stages over the stage-4 fixture exports.

* `stage5-output/` — the citation resolving check: `citations.md` to read,
  `citations.json` for the grades, `docs/registry-*.txt` for the recorded
  registry responses, and `src/*.pltg` for the Parseltongue facts stage 6
  consumes.
* `stage6-output/` — the formal screening: `consistency.md`, `consistency.json`,
  and `system/`, the generated Parseltongue system itself. That directory runs
  on its own:

```bash
cd examples/stage5-6/stage6-output/system
pg start main.pltg && pg wait
pg screen --what issues
pg eval '(scope lens (value "src.checks.proven-verdicts"))'
```

Reproduce both:

```bash
uv run agnostik-citecheck \
    --export examples/stage4/fixtures/crc6-dossiers.html \
    --export examples/stage4/fixtures/crc6-verdicts.html \
    --out results/stage5

uv run agnostik-consistency \
    --export examples/stage4/fixtures/crc6-dossiers.html \
    --export examples/stage4/fixtures/crc6-verdicts.html \
    --citecheck results/stage5 --out results/stage6
```

Registry state moves. Re-running later can legitimately produce different
grades — a record can be retracted, a title corrected, an indication added.
