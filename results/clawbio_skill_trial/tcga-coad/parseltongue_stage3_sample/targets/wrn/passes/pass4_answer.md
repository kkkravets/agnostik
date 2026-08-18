> **Data integrity warning:** One supporting fact — `wrn-copy-loss-cin` — could not be verified against its cited source document (PMC8478156). The quote was not found in the document text, and the fact has been flagged as unverified [[fact:wrn-copy-loss-cin]]. To assess the impact, a parallel scenario (`wrn-copy-loss-cin-suppressed = False`) was constructed and the verdict re-evaluated; it remained **True** under both conditions [[diff:verdict-cin-robustness]]. Additionally, two sensitivity analyses reveal that the verdict is **not robust** to adding extra requirements: requiring TP53-wild-type context flips the verdict to **False** [[diff:verdict-tp53-sensitivity]], and requiring the absence of mutation-prevalence constraints also flips it to **False** [[diff:verdict-mutation-constraint-sensitivity]]. These are model sensitivity tests, not data conflicts — but they highlight conditions under which the conclusion would change.

---

# WRN Therapeutic Targeting in Colon Adenocarcinoma: Evidence Dossier

## Summary Verdict

**WRN is a promising therapeutic target in COAD.** The final verdict node `wrn-verdict` evaluates to **True** [[term:wrn-verdict]], meaning the supporting evidence outweighs the opposition under the defined decision framework.

The verdict requires all of the following to hold simultaneously:
1. Synthetic lethality + MSS dispensability (tumour selectivity)
2. Target druggability
3. Biomarker enrichment (MSI-high, high TMB, TMB exceeding the predictive cutoff)
4. Immunotherapy rationale (MSI predicts PD-1 response, checkpoint inhibition available)
5. No fatal opposition (the target must be druggable AND all opposition factors must coincide to trigger a veto)

---

## Supporting Evidence

### 1. Synthetic Lethality and Tumour Selectivity

WRN inactivation combined with MSI leads to cell death in tumour cell lines, while WRN is dispensable in MSS cells — the core biological rationale for selective targeting:

> "In tumor cell lines, the co-occurrence of WRN inactivation and MSI leads to cell death and cell cycle arrest via the acquisition of double-strand breaks and chromosomal instability." [[quote:wrn-synthetic-lethality-msi]]

> "In contrast, in MSS cell lines, WRN was dispensable for cell survival" [[quote:wrn-dispensable-mss]]

These two facts combine into the selectivity assessment `sl-selectivity`, which evaluates to **True** [[term:sl-selectivity]]. An independent reformulation using an if-then-else structure (`sl-selectivity-alt`) also evaluates to **True** [[term:sl-selectivity-alt]], and the two formulations agree [[diff:sl-selectivity-crosscheck]].

### 2. Druggability

The WRN helicase domain is explicitly identified as a therapeutic target, and multiple small-molecule inhibitors have been identified preclinically:

> "As described recently, the helicase domain of WRN is considered as a therapeutic target for synthetic lethality, as the exonuclease domain is dispensable for cell survival in MSI-H tumor cells." [[quote:wrn-helicase-target]]

> "Inhibitors, such as NSC19630 [35], NSC617145 [36], ML216 [37], NCGC00029283, NCGC00063279, and NCGC00357377 [38] have been identified in drug-screening studies [39]; however, none of them are in a clinical trial yet." [[quote:wrn-inhibitors-identified]]

The combined druggability node `wrn-druggable` evaluates to **True** [[term:wrn-druggable]].

### 3. Biomarker Enrichment

WRN-mutant CRC is enriched for MSI-high status, high TMB, and the TMB value exceeds the predictive cutoff for immune checkpoint response:

> "In WRN-mut CRC, in contrast to WRN-wt, a higher co-occurrence of MSI-H/dMMR was observed (56% vs. 7%, p < 0.0001, Figure 3)." [[quote:wrn-mut-msi-high]]

> "WRN-mut CRCs were associated with a higher mean tumor mutational burden (TMB) (49 vs. 10.7 mutations/megabase [mut/MB], p < 0.0001)" [[quote:wrn-mut-tmb-high]]

> "In a retrospective study of MSI-H/dMMR metastatic CRC featuring patients who underwent treatment with a checkpoint inhibitor, a TMB score of more than 41 mut/MB was determined as a predictive cut-off [29]." [[quote:tmb-predictive-cutoff]]

The mean TMB of 49 mut/MB in WRN-mut tumours exceeds the 41 mut/MB cutoff [[fact:wrn-mut-tmb-value]] [[fact:tmb-predictive-cutoff]], confirmed by the computed term `wrn-tmb-exceeds-cutoff` (**True**) [[term:wrn-tmb-exceeds-cutoff]]. An independent recomputation using `wrn-mut-tmb-mean-value` (49) and `tmb-immunotherapy-cutoff` (41) also yields **True** [[term:tmb-exceeds-cutoff-recomputed]], and the two formulations agree [[diff:tmb-cutoff-crosscheck]].

The combined enrichment node `wrn-biomarker-enriched` evaluates to **True** [[term:wrn-biomarker-enriched]].

### 4. Immunotherapy Rationale

MSI-high status independently predicts response to PD-1 blockade, and checkpoint inhibition is an available option for MSI-high COAD:

> "MSI-H/dMMR status has been identified as an independent predictor of response to PD-1 blockade by pembrolizumab [27]" [[quote:msi-pd1-predictor]]

> "Taking the high rate of MSI-H/dMMR and the high TMB score into consideration, checkpoint inhibition might be an option in WRN-mut CRC." [[quote:checkpoint-option]]

The combined immunotherapy rationale `immuno-rationale` evaluates to **True** [[term:immuno-rationale]].

### 5. BRCAness and PARP Inhibitor Precedent

WRN-mutant tumours exhibit BRCAness-like genomic features, and the authors hypothesize PARP inhibitor benefit:

> "a higher proportion of 'BRCAness' genes were detected in WRN-mut cases: BRCA1 (8% vs. 1%), BRCA2 (15% vs. 2%), and ATM (10% vs. 4%)." [[quote:wrn-mut-brcaness]]

> "We hypothesize that patients with WRN-mut CRC may also benefit from PARP inhibitor treatment [21]." [[quote:wrn-parp-hypothesis]]

The BRCAness paradigm node `wrn-brca-paradigm` evaluates to **True** [[term:wrn-brca-paradigm]].

### 6. Molecular Co-segregation with MSI

WRN methylation clusters with MSI and BRAF mutation, WRN promoter methylation is linked to MSI, and MSI tumours harbour fewer copy-number variants:

> "the 5 markers (CACNA1G, IGF2, NEUROG1, RUNX3 and SOCS1), CDKN2A, CRABP1, MINT31, MLH1, p14 and WRN were generally clustered with each other and with MSI and BRAF mutation." [[quote:wrn-clusters-with-msi-braf]]

> "A correlation between WRN promotor methylation and the CIMP phenotype has been described earlier, linking deficiency in WRN gene function and MSI [26]." [[quote:wrn-methylation-msi-link]]

> "In colorectal and gastric cancers, tumors with MSI demonstrated much fewer copy number changes than microsatellite stable (MSS) tumors." [[quote:msi-fewer-cnv]]

The MSI-association node `wrn-msi-associated` evaluates to **True** [[term:wrn-msi-associated]].

### 7. TP53 Wild-type Sensitivity

TP53-wild-type MSI-H tumour cells retain sensitivity to WRN loss:

> "Chan and colleagues [11] also investigated the dependency of WRN depletion on TP53 status. They found that TP53-wt/MSI-H tumor cells were more sensitive to WRN loss than TP53-mut/MSI-H cells" [[quote:tp53-wt-sensitive]]

However, TP53 mutations may impair WRN inhibitor efficacy:

> "For the success of WRN inhibitors, it could be essential to assess, besides MSI status, TP53 mutations as a biomarker of response, as a mutated TP53 could impair efficacy of WRN inhibition." [[quote:tp53-impairs-wrn]]

The TP53 context node `tp53-context` evaluates to **False** [[term:tp53-context]] because TP53 mutations do impair WRN function — but this factor is **not** required by the main verdict; it is tested only in the sensitivity analysis (see below).

---

## Opposing Evidence

### 1. Clinical Immaturity

Despite preclinical inhibitor identification, no WRN inhibitor has entered clinical trials:

> "Inhibitors, such as NSC19630 [35], NSC617145 [36], ML216 [37], NCGC00029283, NCGC00063279, and NCGC00357377 [38] have been identified in drug-screening studies [39]; however, none of them are in a clinical trial yet." [[quote:no-wrn-inhibitors-clinical]]

### 2. Biomarker Limitations

**Median TMB not significant:** The median TMB difference between subgroups loses statistical significance:

> "However, when looking at median levels, the differences observed with mean levels are no longer statistically significant." [[quote:median-tmb-not-significant]]

**WRN methylation marker inferior:** WRN underperforms as a CIMP methylation marker compared to validated panels:

> "Performance of the 5 new markers (CACNA1G, IGF2, NEUROG1, RUNX3, and SOCS1), CRABP1 and MLH1 was consistently superior to that of WRN, MINT1, CHFR, IGFBP3, HIC1 and MGMT." [[quote:wrn-cimp-marker-inferior]]

**PD-L1 not predictive in CRC:**

> "In the setting of CRC, PD-L1 expression levels do not seem to play a major role in predicting response upon checkpoint therapy, as was observed in the Checkmate 142 trial [32]" [[quote:pdl1-not-predictive-crc]]

The combined biomarker-limitations node evaluates to **True** (limitations are present) [[term:biomarker-limit]].

### 3. CIN and Prognosis Risk

CIN is associated with poor prognosis and treatment resistance:

> "CIN is a critical hallmark of cancer and is closely related to tumor metastasis, treatment resistance, and poor prognosis (Pikor et al., 2013; Bakhoum and Cantley, 2018)." [[quote:cin-poor-prognosis]]

A proposed link between WRN copy-number loss and CIN could not be verified — the attributed quote was **not found** in source document PMC8478156 [[fact:wrn-copy-loss-cin]]. The CIN risk node `cin-risk` evaluates to **True** [[term:cin-risk]] (driven by the verified `cin-poor-prognosis` fact), but the specific WRN→CIN mechanistic link remains unproven.

### 4. Retrospective Study Limitations

> "Our study has important limitations, such as retrospective data extraction from a large database including only very limited basic clinical data." [[quote:retrospective-limited]]

### 5. Mutation Prevalence Constraint

WRN mutations are rare and none fall in the helicase domain:

> "WRN mutations (WRN-mut) were observed in 80 of 6854 samples (1.2%, see Table 1)." [[quote:wrn-mut-rare]]

> "No mutations were observed in the helicase domain (see Figure 1)." [[quote:no-helicase-mutations]]

The mutation-constraint node `wrn-mutation-constraint` evaluates to **True** (constraints exist) [[term:wrn-mutation-constraint]].

---

## Opposition Assessment

The full opposition dossier aggregates: no clinical inhibitors, biomarker limitations, CIN/prognosis risk, and retrospective study limitations. The opposition node `wrn-opposition` evaluates to **True** (opposition factors exist) [[term:wrn-opposition]].

However, the **fatal veto** condition requires that the target is **not druggable** AND the full opposition holds simultaneously:

- `wrn-opposition-fatal` = (not wrn-druggable) AND wrn-opposition

Since `wrn-druggable` is **True** [[term:wrn-druggable]], the fatal veto evaluates to **False** [[term:wrn-opposition-fatal]]. Opposition alone does not reject a druggable target.

---

## Final Verdict and Dependency Chain

The verdict node is defined as:

> `wrn-verdict` = sl-selectivity AND wrn-druggable AND wrn-biomarker-enriched AND immuno-rationale AND (not wrn-opposition-fatal) [[term:wrn-verdict]]

**Evaluation: True** — WRN is a promising therapeutic target.

The complete dependency chain terminates in quoted facts:

| Intermediate Node | Value | Depends On |
|---|---|---|
| `sl-selectivity` | True | `wrn-synthetic-lethality-msi`, `wrn-dispensable-mss` |
| `wrn-druggable` | True | `wrn-helicase-target`, `wrn-inhibitors-identified` |
| `wrn-biomarker-enriched` | True | `wrn-mut-msi-high`, `wrn-mut-tmb-high`, `wrn-tmb-exceeds-cutoff` |
| `immuno-rationale` | True | `msi-pd1-predictor`, `checkpoint-option` |
| `wrn-opposition-fatal` | False | `wrn-druggable`, `wrn-opposition` |
| `wrn-opposition` | True | `no-wrn-inhibitors-clinical`, `biomarker-limit`, `cin-risk`, `retrospective-limited` |
| **`wrn-verdict`** | **True** | all of the above |

Every leaf in this chain is a fact with a verbatim document quote (except `wrn-copy-loss-cin`, which failed verification and whose impact was tested and found non-decisive).

---

## Robustness and Sensitivity Analysis

| Sensitivity Test | Main Verdict | Alternative | Verdict Holds? |
|---|---|---|---|
| Remove CIN from opposition | True | True [[term:wrn-verdict-no-cin]] | ✅ Yes [[diff:verdict-cin-robustness]] |
| Require TP53-wt context | True | False [[term:wrn-verdict-with-tp53]] | ❌ No [[diff:verdict-tp53-sensitivity]] |
| Require no mutation constraints | True | False [[term:wrn-verdict-requires-common-mutations]] | ❌ No [[diff:verdict-mutation-constraint-sensitivity]] |

The verdict is **robust** to the CIN concern — removing the unverified WRN→CIN link from the opposition does not change the outcome. However, the verdict is **not robust** to adding TP53 wild-type as a mandatory requirement or to demanding that mutation prevalence constraints be absent. These additional criteria would flip the verdict to **False**, indicating that the target's promise is conditional on not over-constraining the eligible patient population.

---

## Caveats

1. **Unverified evidence:** The fact `wrn-copy-loss-cin` cites a quote attributed to PMC8478156 that was not found in the document text [[fact:wrn-copy-loss-cin]]. A controlled sensitivity test (`wrn-copy-loss-cin-suppressed = False`) confirmed the verdict does not depend on this unverified fact [[term:wrn-verdict-no-cin]] [[diff:verdict-cin-robustness]].

2. **Composite terms without structured evidence:** Several intermediate composite terms (e.g., `biomarker-limit`, `cin-risk`, `wrn-opposition`, `wrn-verdict`) were defined with plain-text origins rather than quote-verified evidence blocks. Their constituent facts, however, all carry verbatim quotes from source documents — the structured evidence exists at the leaf level and propagates upward through the dependency chain.

3. **Sources:** The evidence base draws from three documents: PMC7281075 (primary WRN-mut CRC study), PMC2579485 (WRN methylation clustering study), and PMC8478156 (CIN and copy-number study). All quotes from PMC7281075 and PMC2579485 were verified with high confidence (scores ≥ 0.968). The single unverified quote was from PMC8478156.
