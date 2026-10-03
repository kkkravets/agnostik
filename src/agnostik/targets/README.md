# Target discovery

Turns a TCGA tumour code into a ranked shortlist of candidate genes, instead of
the fixed v1 panel.

```bash
uv run agnostik READ --top-n 20
```

## How it works

1. **Name the tumour** (`resolve.py`). The GDC names the TCGA project:
   `READ` -> "Rectum Adenocarcinoma". An unknown code stops here.
2. **Match a disease** (`resolve.py`, `opentargets.py`). Open Targets search
   finds the disease for that name. A warning is printed when the match is
   inexact (`--disease "name"` searches another name) or when a runner-up scored
   close (`--disease-id MONDO_...` skips the search).
3. **Add parents** (`opentargets.py`). The disease's parent diseases are ranked
   together with it, so evidence recorded one level up is not lost (colon
   adenocarcinoma also gets what is known about colorectal adenocarcinoma).
   `--no-parents` ranks the matched disease alone.
4. **Rank** (`opentargets.py`). The top protein-coding genes by Open Targets
   association score are fetched for each disease and merged; a gene keeps its
   best score and the list is cut to `--top-n` (default 20). Evidence recorded
   on subtypes below a disease is included unless `--direct-only`.

## Therapeutic areas

Open Targets tags every disease with broad categories such as "gastrointestinal
disease", "endocrine system disorder" or "cancer or benign tumor". Parents are
kept only if they share an organ-related category with the matched disease.
"Cancer" and "phenotype" are ignored because every cancer has them. That drops
generic parents: "exocrine pancreatic carcinoma" is kept for pancreatic
adenocarcinoma, "adenocarcinoma" (all organs) is not.

## "Ranked together with"

The output line `Ranked together with: exocrine pancreatic carcinoma` means the
shortlist is not taken from one disease. For PAAD:

1. The top genes are fetched for the matched disease (pancreatic adenocarcinoma,
   `MONDO_0006047`).
2. The top genes are also fetched for each kept parent (exocrine pancreatic
   carcinoma, `MONDO_0005192`).
3. The lists are merged: a gene in both keeps its higher score.
4. The merged list is sorted by score and cut to `--top-n`.

The `disease_id` column of `candidates.csv` says which disease gave each gene
its score. In a real PAAD run the top two genes, KRAS and TP53, got theirs from
the parent.

This does not separate the two diseases. TCGA has one pancreatic cohort
(`PAAD`), so there is no code that picks one or the other, and the merged
ranking does not tell them apart beyond the `disease_id` column. Two costs:

- The parent is broader than the cohort. Exocrine pancreatic carcinoma includes
  types PAAD does not, such as acinar cell carcinoma, so their evidence can lift
  genes that are not PAAD-specific.
- Association scores are computed per disease, so taking the higher one across
  diseases is approximate.

Parents are included because evidence recorded on a broader term would
otherwise be missed (Lynch-syndrome genes sit under "colorectal cancer", not
"colon adenocarcinoma"). Use `--no-parents` for the matched disease alone.

## Output

Written to `results/targets/<tumour>/` (or `--out-dir`):

| File | Contents |
|---|---|
| `symbols.txt` | ranked gene symbols, one per line |
| `candidates.csv` | rank, Ensembl ID, symbol, name, biotype, score, and the disease that gave the gene its best score |
| `resolution.json` | tumour code, search term, matched disease, parents, alternatives, warnings |

`agnostik-collect-evidence` and `agnostik-parseltongue` use `symbols.txt`
automatically when it exists for the tumour (`--fixed-panel` forces the v1
panel) and take their search term from `resolution.json`.

## Caveats

- The lookup needs the network (GDC and Open Targets). `agnostik <code>
  --fixed-panel` is offline.
- Results follow Open Targets releases, so a rerun can differ; `resolution.json`
  and the saved files record what a run used.
- The match can be broader or narrower than the TCGA cohort. Across the 33 TCGA
  projects the name search found a plausible disease for 31; DLBC and LGG found
  none and need `--disease`. CESC, ESCA, TGCT and UCEC match a related but
  different term than OncoTree's NCI Thesaurus entry, so check them.
- Rankings order genes by disease association, not by druggability.
