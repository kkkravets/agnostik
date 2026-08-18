# Formal consistency screening

Generated 2026-08-18 12:52 UTC · engine integrity **verified** · 58 proved inconsistencies · 5/6 verdicts proven (engine-computed)

Two independent descriptions of the same citation set — what the dossier asserts, and what the registries returned — are declared as Parseltongue `diff`s. What follows is what the engine proved, on evidence it verified against quoted documents. Nothing here is weighted or scored.

| target | asserted | cited | subject-level | off-target | retracted | unresolved | verdict |
|---|---|---|---|---|---|---|---|
| EGFR | promising | 8 | 2 | 0 | 0 | 0 | proven |
| ERBB2 | promising | 10 | 3 | 0 | 0 | 0 | proven |
| KRAS | promising | 11 | 3 | 1 | 0 | 0 | **unproven** |
| MYC | rejected | 8 | 2 | 0 | 0 | 0 | proven |
| WRN | promising | 11 | 4 | 0 | 0 | 0 | proven |
| PRMT5 | rejected | 9 | 2 | 0 | 0 | 0 | proven |

## Proved inconsistencies

| check | type | kind | where |
|---|---|---|---|
| `src.checks.egfr-base-intact` | potential_fabrication | derive | `src/checks.pltg:46:1` |
| `src.checks.erbb2-base-intact` | potential_fabrication | derive | `src/checks.pltg:120:1` |
| `src.checks.kras-base-intact` | potential_fabrication | derive | `src/checks.pltg:198:1` |
| `src.checks.kras-base-usable` | potential_fabrication | derive | `src/checks.pltg:218:1` |
| `src.checks.kras-clean-of-off-target` | potential_fabrication | derive | `src/checks.pltg:202:1` |
| `src.checks.kras-verdict-proven` | potential_fabrication | derive | `src/checks.pltg:223:1` |
| `src.checks.myc-base-intact` | potential_fabrication | derive | `src/checks.pltg:268:1` |
| `src.checks.prmt5-base-intact` | potential_fabrication | derive | `src/checks.pltg:416:1` |
| `src.checks.proven-verdicts` | potential_fabrication | derive | `src/checks.pltg:445:1` |
| `src.checks.wrn-base-intact` | potential_fabrication | derive | `src/checks.pltg:342:1` |
| `src.checks.egfr-support-base` | diff_divergence | diff | `src/checks.pltg:6:1` |
| `src.checks.erbb2-support-base` | diff_divergence | diff | `src/checks.pltg:76:1` |
| `src.checks.kras-support-base` | diff_divergence | diff | `src/checks.pltg:150:1` |
| `src.checks.myc-support-base` | diff_divergence | diff | `src/checks.pltg:228:1` |
| `src.checks.prmt5-support-base` | diff_divergence | diff | `src/checks.pltg:372:1` |
| `src.checks.wrn-support-base` | diff_divergence | diff | `src/checks.pltg:298:1` |
| `src.checks.egfr-supports-nct-NCT07503756` | diff_value_divergence | diff | `src/checks.pltg:42:1` |
| `src.checks.egfr-supports-pmid-42492133` | diff_value_divergence | diff | `src/checks.pltg:22:1` |
| `src.checks.egfr-supports-pmid-42576549` | diff_value_divergence | diff | `src/checks.pltg:26:1` |
| `src.checks.egfr-supports-pmid-42595923` | diff_value_divergence | diff | `src/checks.pltg:30:1` |
| `src.checks.egfr-supports-pmid-42609336` | diff_value_divergence | diff | `src/checks.pltg:34:1` |
| `src.checks.egfr-supports-pmid-42609500` | diff_value_divergence | diff | `src/checks.pltg:38:1` |
| `src.checks.erbb2-supports-nct-NCT03803553` | diff_value_divergence | diff | `src/checks.pltg:112:1` |
| `src.checks.erbb2-supports-nct-NCT07503756` | diff_value_divergence | diff | `src/checks.pltg:116:1` |
| `src.checks.erbb2-supports-pmid-42401587` | diff_value_divergence | diff | `src/checks.pltg:92:1` |
| `src.checks.erbb2-supports-pmid-42426557` | diff_value_divergence | diff | `src/checks.pltg:96:1` |
| `src.checks.erbb2-supports-pmid-42497534` | diff_value_divergence | diff | `src/checks.pltg:100:1` |
| `src.checks.erbb2-supports-pmid-42599169` | diff_value_divergence | diff | `src/checks.pltg:104:1` |
| `src.checks.erbb2-supports-pmid-42601812` | diff_value_divergence | diff | `src/checks.pltg:108:1` |
| `src.checks.kras-off-target` | diff_value_divergence | diff | `src/checks.pltg:154:1` |
| `src.checks.kras-supports-nct-NCT05176483` | diff_value_divergence | diff | `src/checks.pltg:194:1` |
| `src.checks.kras-supports-pmid-42527030` | diff_value_divergence | diff | `src/checks.pltg:166:1` |
| `src.checks.kras-supports-pmid-42557320` | diff_value_divergence | diff | `src/checks.pltg:170:1` |
| `src.checks.kras-supports-pmid-42570059` | diff_value_divergence | diff | `src/checks.pltg:174:1` |
| `src.checks.kras-supports-pmid-42599639` | diff_value_divergence | diff | `src/checks.pltg:178:1` |
| `src.checks.kras-supports-pmid-42605754` | diff_value_divergence | diff | `src/checks.pltg:182:1` |
| `src.checks.kras-supports-pmid-42606648` | diff_value_divergence | diff | `src/checks.pltg:186:1` |
| `src.checks.kras-supports-pmid-42607542` | diff_value_divergence | diff | `src/checks.pltg:190:1` |
| `src.checks.myc-supports-nct-NCT05919264` | diff_value_divergence | diff | `src/checks.pltg:260:1` |
| `src.checks.myc-supports-nct-NCT07147231` | diff_value_divergence | diff | `src/checks.pltg:264:1` |
| `src.checks.myc-supports-pmid-42497765` | diff_value_divergence | diff | `src/checks.pltg:244:1` |
| `src.checks.myc-supports-pmid-42548213` | diff_value_divergence | diff | `src/checks.pltg:248:1` |
| `src.checks.myc-supports-pmid-42607078` | diff_value_divergence | diff | `src/checks.pltg:252:1` |
| `src.checks.myc-supports-pmid-42608167` | diff_value_divergence | diff | `src/checks.pltg:256:1` |
| `src.checks.prmt5-supports-pmid-41513606` | diff_value_divergence | diff | `src/checks.pltg:388:1` |
| `src.checks.prmt5-supports-pmid-41629269` | diff_value_divergence | diff | `src/checks.pltg:392:1` |
| `src.checks.prmt5-supports-pmid-41630900` | diff_value_divergence | diff | `src/checks.pltg:396:1` |
| `src.checks.prmt5-supports-pmid-42133901` | diff_value_divergence | diff | `src/checks.pltg:400:1` |
| `src.checks.prmt5-supports-pmid-42326870` | diff_value_divergence | diff | `src/checks.pltg:404:1` |
| `src.checks.prmt5-supports-pmid-42603931` | diff_value_divergence | diff | `src/checks.pltg:408:1` |
| `src.checks.prmt5-supports-pmid-42607456` | diff_value_divergence | diff | `src/checks.pltg:412:1` |
| `src.checks.wrn-supports-nct-NCT03570541` | diff_value_divergence | diff | `src/checks.pltg:330:1` |
| `src.checks.wrn-supports-nct-NCT06974110` | diff_value_divergence | diff | `src/checks.pltg:334:1` |
| `src.checks.wrn-supports-nct-NCT07262619` | diff_value_divergence | diff | `src/checks.pltg:338:1` |
| `src.checks.wrn-supports-pmid-40203476` | diff_value_divergence | diff | `src/checks.pltg:314:1` |
| `src.checks.wrn-supports-pmid-42293362` | diff_value_divergence | diff | `src/checks.pltg:318:1` |
| `src.checks.wrn-supports-pmid-42593940` | diff_value_divergence | diff | `src/checks.pltg:322:1` |
| `src.checks.wrn-supports-pmid-42604630` | diff_value_divergence | diff | `src/checks.pltg:326:1` |

## EGFR — proven on a narrowed base — 2 of 8 cited records are subject-level, the rest only mention EGFR

The dossier rests on 8 records; the registries confirm 2 of them name EGFR as the subject (6 mention it only in passing, 0 never name it).

Failed checks:
- `src.checks.egfr-base-intact` — potential_fabrication at `src/checks.pltg:46:1`
- `src.checks.egfr-support-base` — diff_divergence at `src/checks.pltg:6:1`
- `src.checks.egfr-supports-nct-NCT07503756` — diff_value_divergence at `src/checks.pltg:42:1`
- `src.checks.egfr-supports-pmid-42492133` — diff_value_divergence at `src/checks.pltg:22:1`
- `src.checks.egfr-supports-pmid-42576549` — diff_value_divergence at `src/checks.pltg:26:1`
- `src.checks.egfr-supports-pmid-42595923` — diff_value_divergence at `src/checks.pltg:30:1`
- `src.checks.egfr-supports-pmid-42609336` — diff_value_divergence at `src/checks.pltg:34:1`
- `src.checks.egfr-supports-pmid-42609500` — diff_value_divergence at `src/checks.pltg:38:1`

## ERBB2 — proven on a narrowed base — 3 of 10 cited records are subject-level, the rest only mention ERBB2

The dossier rests on 10 records; the registries confirm 3 of them name ERBB2 as the subject (7 mention it only in passing, 0 never name it).

Failed checks:
- `src.checks.erbb2-base-intact` — potential_fabrication at `src/checks.pltg:120:1`
- `src.checks.erbb2-support-base` — diff_divergence at `src/checks.pltg:76:1`
- `src.checks.erbb2-supports-nct-NCT03803553` — diff_value_divergence at `src/checks.pltg:112:1`
- `src.checks.erbb2-supports-nct-NCT07503756` — diff_value_divergence at `src/checks.pltg:116:1`
- `src.checks.erbb2-supports-pmid-42401587` — diff_value_divergence at `src/checks.pltg:92:1`
- `src.checks.erbb2-supports-pmid-42426557` — diff_value_divergence at `src/checks.pltg:96:1`
- `src.checks.erbb2-supports-pmid-42497534` — diff_value_divergence at `src/checks.pltg:100:1`
- `src.checks.erbb2-supports-pmid-42599169` — diff_value_divergence at `src/checks.pltg:104:1`
- `src.checks.erbb2-supports-pmid-42601812` — diff_value_divergence at `src/checks.pltg:108:1`

## KRAS — unproven — 1 cited record(s) never name KRAS

The dossier rests on 11 records; the registries confirm 3 of them name KRAS as the subject (7 mention it only in passing, 1 never name it).

Failed checks:
- `src.checks.kras-base-intact` — potential_fabrication at `src/checks.pltg:198:1`
- `src.checks.kras-base-usable` — potential_fabrication at `src/checks.pltg:218:1`
- `src.checks.kras-clean-of-off-target` — potential_fabrication at `src/checks.pltg:202:1`
- `src.checks.kras-verdict-proven` — potential_fabrication at `src/checks.pltg:223:1`
- `src.checks.kras-support-base` — diff_divergence at `src/checks.pltg:150:1`
- `src.checks.kras-off-target` — diff_value_divergence at `src/checks.pltg:154:1`
- `src.checks.kras-supports-nct-NCT05176483` — diff_value_divergence at `src/checks.pltg:194:1`
- `src.checks.kras-supports-pmid-42527030` — diff_value_divergence at `src/checks.pltg:166:1`
- `src.checks.kras-supports-pmid-42557320` — diff_value_divergence at `src/checks.pltg:170:1`
- `src.checks.kras-supports-pmid-42570059` — diff_value_divergence at `src/checks.pltg:174:1`
- `src.checks.kras-supports-pmid-42599639` — diff_value_divergence at `src/checks.pltg:178:1`
- `src.checks.kras-supports-pmid-42605754` — diff_value_divergence at `src/checks.pltg:182:1`
- `src.checks.kras-supports-pmid-42606648` — diff_value_divergence at `src/checks.pltg:186:1`
- `src.checks.kras-supports-pmid-42607542` — diff_value_divergence at `src/checks.pltg:190:1`

## MYC — proven on a narrowed base — 2 of 8 cited records are subject-level, the rest only mention MYC

The dossier rests on 8 records; the registries confirm 2 of them name MYC as the subject (6 mention it only in passing, 0 never name it).

Failed checks:
- `src.checks.myc-base-intact` — potential_fabrication at `src/checks.pltg:268:1`
- `src.checks.myc-support-base` — diff_divergence at `src/checks.pltg:228:1`
- `src.checks.myc-supports-nct-NCT05919264` — diff_value_divergence at `src/checks.pltg:260:1`
- `src.checks.myc-supports-nct-NCT07147231` — diff_value_divergence at `src/checks.pltg:264:1`
- `src.checks.myc-supports-pmid-42497765` — diff_value_divergence at `src/checks.pltg:244:1`
- `src.checks.myc-supports-pmid-42548213` — diff_value_divergence at `src/checks.pltg:248:1`
- `src.checks.myc-supports-pmid-42607078` — diff_value_divergence at `src/checks.pltg:252:1`
- `src.checks.myc-supports-pmid-42608167` — diff_value_divergence at `src/checks.pltg:256:1`

## WRN — proven on a narrowed base — 4 of 11 cited records are subject-level, the rest only mention WRN

The dossier rests on 11 records; the registries confirm 4 of them name WRN as the subject (7 mention it only in passing, 0 never name it).

Failed checks:
- `src.checks.wrn-base-intact` — potential_fabrication at `src/checks.pltg:342:1`
- `src.checks.wrn-support-base` — diff_divergence at `src/checks.pltg:298:1`
- `src.checks.wrn-supports-nct-NCT03570541` — diff_value_divergence at `src/checks.pltg:330:1`
- `src.checks.wrn-supports-nct-NCT06974110` — diff_value_divergence at `src/checks.pltg:334:1`
- `src.checks.wrn-supports-nct-NCT07262619` — diff_value_divergence at `src/checks.pltg:338:1`
- `src.checks.wrn-supports-pmid-40203476` — diff_value_divergence at `src/checks.pltg:314:1`
- `src.checks.wrn-supports-pmid-42293362` — diff_value_divergence at `src/checks.pltg:318:1`
- `src.checks.wrn-supports-pmid-42593940` — diff_value_divergence at `src/checks.pltg:322:1`
- `src.checks.wrn-supports-pmid-42604630` — diff_value_divergence at `src/checks.pltg:326:1`

## PRMT5 — proven on a narrowed base — 2 of 9 cited records are subject-level, the rest only mention PRMT5

The dossier rests on 9 records; the registries confirm 2 of them name PRMT5 as the subject (7 mention it only in passing, 0 never name it).

Failed checks:
- `src.checks.prmt5-base-intact` — potential_fabrication at `src/checks.pltg:416:1`
- `src.checks.prmt5-support-base` — diff_divergence at `src/checks.pltg:372:1`
- `src.checks.prmt5-supports-pmid-41513606` — diff_value_divergence at `src/checks.pltg:388:1`
- `src.checks.prmt5-supports-pmid-41629269` — diff_value_divergence at `src/checks.pltg:392:1`
- `src.checks.prmt5-supports-pmid-41630900` — diff_value_divergence at `src/checks.pltg:396:1`
- `src.checks.prmt5-supports-pmid-42133901` — diff_value_divergence at `src/checks.pltg:400:1`
- `src.checks.prmt5-supports-pmid-42326870` — diff_value_divergence at `src/checks.pltg:404:1`
- `src.checks.prmt5-supports-pmid-42603931` — diff_value_divergence at `src/checks.pltg:408:1`
- `src.checks.prmt5-supports-pmid-42607456` — diff_value_divergence at `src/checks.pltg:412:1`

## Engine screening statistics

```json
{
 "by_category": {
  "dangling": 45,
  "issue": 58
 },
 "by_type": {
  "dangling": 45,
  "diff_value_divergence": 42,
  "potential_fabrication": 10,
  "diff_divergence": 6
 },
 "by_kind": {
  "diff": 48,
  "fact": 32,
  "derive": 17,
  "axiom": 6
 },
 "by_namespace": {
  "src": 103
 },
 "by_file": {
  "src/checks.pltg:46": 2,
  "src/checks.pltg:120": 2,
  "src/checks.pltg:198": 2,
  "src/checks.pltg:268": 2,
  "src/checks.pltg:416": 2,
  "src/checks.pltg:445": 2,
  "src/checks.pltg:342": 2,
  "src/checks.pltg:218": 1,
  "src/checks.pltg:202": 1,
  "src/checks.pltg:223": 1,
  "src/checks.pltg:6": 1,
  "src/checks.pltg:76": 1,
  "src/checks.pltg:150": 1,
  "src/checks.pltg:228": 1,
  "src/checks.pltg:372": 1,
  "src/checks.pltg:298": 1,
  "src/checks.pltg:42": 1,
  "src/checks.pltg:22": 1,
  "src/checks.pltg:26": 1,
  "src/checks.pltg:30": 1,
  "src/checks.pltg:34": 1,
  "src/checks.pltg:38": 1,
  "src/checks.pltg:112": 1,
  "src/checks.pltg:116": 1,
  "src/checks.pltg:92": 1,
  "src/checks.pltg:96": 1,
  "src/checks.pltg:100": 1,
  "src/checks.pltg:104": 1,
  "src/checks.pltg:108": 1,
  "src/checks.pltg:154": 1,
  "src/checks.pltg:194": 1,
  "src/checks.pltg:166": 1,
  "src/checks.pltg:170": 1,
  "src/checks.pltg:174": 1,
  "src/checks.pltg:178": 1,
  "src/checks.pltg:182": 1,
  "src/checks.pltg:186": 1,
  "src/checks.pltg:190": 1,
  "src/checks.pltg:260": 1,
  "src/checks.pltg:264": 1,
  "src/checks.pltg:244": 1,
  "src/checks.pltg:248": 1,
  "src/checks.pltg:252": 1,
  "src/checks.pltg:256": 1,
  "src/checks.pltg:388": 1,
  "src/checks.pltg:392": 1,
  "src/checks.pltg:396": 1,
  "src/checks.pltg:400": 1,
  "src/checks.pltg:404": 1,
  "src/checks.pltg:408": 1,
  "src/checks.pltg:412": 1,
  "src/checks.pltg:330": 1,
  "src/checks.pltg:334": 1,
  "src/checks.pltg:338": 1,
  "src/checks.pltg:314": 1,
  "src/checks.pltg:318": 1,
  "src/checks.pltg:322": 1,
  "src/checks.pltg:326": 1,
  "src/dossier_egfr.pltg:38": 1,
  "src/dossier_egfr.pltg:23": 1,
  "src/dossier_erbb2.pltg:63": 1,
  "src/dossier_erbb2.pltg:28": 1,
  "src/dossier_erbb2.pltg:23": 1,
  "src/dossier_kras.pltg:73": 1,
  "src/dossier_kras.pltg:43": 1,
  "src/dossier_kras.pltg:23": 1,
  "src/dossier_myc.pltg:38": 1,
  "src/dossier_myc.pltg:23": 1,
  "src/dossier_prmt5.pltg:43": 1,
  "src/dossier_prmt5.pltg:23": 1,
  "src/dossier_wrn.pltg:33": 1,
  "src/dossier_wrn.pltg:43": 1,
  "src/dossier_wrn.pltg:48": 1,
  "src/dossier_wrn.pltg:23": 1,
  "src/registry_egfr.pltg:38": 1,
  "src/registry_egfr.pltg:23": 1,
  "src/registry_erbb2.pltg:63": 1,
  "src/registry_erbb2.pltg:28": 1,
  "src/registry_erbb2.pltg:23": 1,
  "src/registry_kras.pltg:73": 1,
  "src/registry_kras.pltg:43": 1,
  "src/registry_kras.pltg:23": 1,
  "src/registry_myc.pltg:38": 1,
  "src/registry_myc.pltg:23": 1,
  "src/registry_prmt5.pltg:43": 1,
  "src/registry_prmt5.pltg:23": 1,
  "src/registry_wrn.pltg:33": 1,
  "src/registry_wrn.pltg:43": 1,
  "src/registry_wrn.pltg:48": 1,
  "src/registry_wrn.pltg:23": 1,
  "src/rules.pltg:33": 1,
  "src/rules.pltg:9": 1,
  "src/rules.pltg:15": 1,
  "src/rules.pltg:3": 1,
  "src/rules.pltg:21": 1,
  "src/rules.pltg:27": 1
 }
}
```
