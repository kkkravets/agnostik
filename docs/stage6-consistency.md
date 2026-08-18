# Stage 6 — formal consistency screening

This stage replaces a weighted target-validation score. Nothing in it adds
points up, and there is no threshold to tune.

Two independent descriptions of the **same** citation set are written as
separate Parseltongue fact modules — what the stage-4 dossier asserts, and what
the registries returned in stage 5. Every place they can disagree is declared as
a `diff`. The engine decides which of them actually diverge, and it refuses to
decide anything on evidence it cannot verify against a quoted document.

What replaces what:

| target-validation-scorer | stage 6 |
|---|---|
| 5 components × 20 points → 0–100 | no score exists |
| threshold → GO / NO-GO | verdict is proven or unproven, by derivation |
| weights chosen by the author | invariants quoted from a charter the engine reads |
| evidence cited in prose | evidence quoted verbatim and machine-verified |
| disagreement summarised | disagreement proved, with both values and its downstream consequences |

## What is compared

Set-wise identical on both sides — the records the dossier itself rests on.
Comparing a dossier-wide query total against a spot-checked registry sample
would produce divergences that mean nothing.

Per target:

```lisp
(diff egfr-support-base                     ; how many records support this target
    :replace dossier_egfr.cited-records     ; dossier: 8
    :with registry_egfr.subject-records)    ; registry: 2

(diff egfr-off-target      :replace dossier_egfr.assumed-off-target :with registry_egfr.off-target)
(diff egfr-retracted       :replace dossier_egfr.assumed-retracted  :with registry_egfr.retracted)
(diff egfr-unresolved      :replace dossier_egfr.assumed-unresolved :with registry_egfr.unresolved)
```

plus one `diff` per individual record the dossier treats as support and the
registry does not.

## How a verdict is adjudicated

Three questions are kept apart on purpose:

| derivation | asks |
|---|---|
| `<t>-base-intact` | are the two support bases identical? |
| `<t>-base-usable` | no off-target, no retracted, no unresolved records, and at least one subject-level record |
| `<t>-verdict-proven` | gated on `base-usable` |

Exact agreement of the two bases is almost never true — dossiers cite records
that merely mention their target. So it is **recorded, not used as the gate**;
gating on it would mark all six targets unproven and tell you nothing. What
gates the verdict is whether the base that survived verification can still carry
it.

## Input

* `--export` — the pg-bench export (the dossier side)
* `--citecheck DIR` — the stage 5 output directory

Stage 5's own registry snapshots are copied into the generated system rather
than paraphrased, so the engine verifies the quotes against the file the
registry responses were written to.

## Output

| file | contents |
|---|---|
| `consistency.json` | engine integrity, every proved divergence with both values and its consequences, per-target adjudication |
| `consistency.md` | the divergence table, the nodes the engine marked unsafe, and the per-target standing |
| `system/` | the generated Parseltongue system — `main.pltg`, `src/*.pltg`, `docs/*` — runnable and inspectable on its own |

Exit codes: `0` clean, `4` if the engine could not run, `5` if quote integrity
failed or the system had load errors.

## Usage

```bash
uv run agnostik-consistency \
    --export examples/stage4/fixtures/crc6-dossiers.html \
    --export examples/stage4/fixtures/crc6-verdicts.html \
    --citecheck results/stage5 \
    --out results/stage6
```

`--generate-only` writes the system without running the engine. Inspect it by
hand with the same tools stage 3 uses:

```bash
cd results/stage6/system && pg start main.pltg && pg wait
pg screen --what issues
pg eval '(scope lens (value "src.checks.proven-verdicts"))'
```

## The sample run

Engine integrity `verified` — every quote on both sides checked out against its
document. 58 proved inconsistencies. 5 of 6 verdicts proven.

| target | asserted | cited | subject-level | off-target | standing |
|---|---|---|---|---|---|
| EGFR | promising | 8 | 2 | 0 | proven on a narrowed base |
| ERBB2 | promising | 10 | 3 | 0 | proven on a narrowed base |
| KRAS | promising | 11 | 3 | 1 | **unproven** — a cited record never names KRAS |
| MYC | rejected | 8 | 2 | 0 | proven on a narrowed base |
| WRN | promising | 11 | 4 | 0 | proven on a narrowed base |
| PRMT5 | rejected | 9 | 2 | 0 | proven on a narrowed base |

The engine reports what each divergence would change:
`egfr-support-base` compares 8 against 2, and records that
`egfr-base-intact` would flip from `False` to `True` if the dossier used the
verified base. That is the inconsistency stated exactly, with no judgement
attached to it.
