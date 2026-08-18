# Objections to the CRC target shortlist

Generated 2026-08-18 14:23 UTC · model `zai-org/GLM-5.2` · export `['C:\\Users\\neu\\PycharmProjects\\agnostik\\results\\clawbio_skill_trial\\tcga-coad\\parseltongue_stage3_sample\\stage3-export.partial.json']`

4 targets reviewed — 3 promising, 1 rejected. Each objection is five sentences, every sentence cited into the Parseltongue derivation.

## EGFR — engine verdict: promising (verified)

Verdict node `stage3.egfr.egfr-verdict` · 23 citable items · 0/0 external ids resolve

1. The entire derivation rests on a single internal document [E1][E5] with no external record cited, so the "promising" verdict inherits all limitations of one uncorroborated source without independent replication.
2. The clinical benefit in [E1] comes from adagrasib, a KRASG12C inhibitor, combined with cetuximab, yet the synthetic-lethal and dual-inhibition proliferation evidence relies on MRTX1133, a KRASG12D inhibitor [E13][E18], leaving the derivation without clinical data for the exact mutation context it uses to establish mechanism.
3. The AKPE signature that drives the survival stratification fails completely in KRAS-wild-type patients [E3], and EGFR deletion in KRAS-wild-type tumor cells does not reduce tumor growth [E8], meaning the promise is confined to KRAS-mutant tumors only, a restriction the verdict does not qualify.
4. The criterion "combo-evidence-overcomes-resistance-implies-promise" does the decisive work, but it must overcome the fact that only 50% of eligible patients respond to anti-EGFR therapy for unknown reasons [E19] and that the metabolic phenotype is not exclusively WNT-driven [E17], undermining the clean mechanistic rationale the rule presupposes.
5. The SMOC2 rescue data [E20][E21] and the TCGA negative correlation [E22] are observed only in KRAS-mutant subsets, so the derivation never tests whether the non-redundant EGFR-KRAS axis [E16] holds for KRAS variants beyond G12C and G12D, leaving the generalizability of the "promising" label unverified.

**Audit flags fed to the model:**
- no citation in this ledger reaches an external record — all evidence is internal document text

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E1 | doc:PMC12162862 | — | `stage3.egfr.adagrasib-cetuximab-benefit` | heavily pretreated patients with metastatic colorectal cancer were shown to benefit from the treatment of adag |
| E3 | doc:PMC12162862 | — | `stage3.egfr.akpe-signature-kraswt-no-stratification` | the AKPE signature could only stratify KRASmt patients with AKPE high signature from low signature expressors  |
| E5 | doc:PMC12162862 | — | `stage3.egfr.combo-evidence-overcomes-resistance-implies-promise` | recent reports highlight EGFR as a crucial target to be co-inhibited with RAS inhibitors for effective treatme |
| E8 | doc:PMC12162862 | — | `stage3.egfr.combo-evidence-overcomes-resistance-implies-promise` | EGFR deletion in KRASwt tumor cells did not reduce tumor growth |
| E13 | doc:PMC12162862 | — | `stage3.egfr.egfr-essential-synthetic-lethal` | KRAS inhibitor studies demonstrate EGFR to be essential for synthetic lethal action in combination with the no |
| E16 | doc:PMC12162862 | — | `stage3.egfr.egfr-nonredundant-kras` | we propose that the KRASG12D allele is critical in maintaining the axis of sustained proliferation, while upst |
| E17 | doc:PMC12162862 | — | `stage3.egfr.metabolic-phenotype-not-exclusively-wnt` | the metabolic phenotype induced by EGFR deletion is not exclusively driven by WNT signaling but involves broad |
| E18 | doc:PMC12162862 | — | `stage3.egfr.mrtx1133-complete-akpe` | MRTX1133 treatment had a minimal impact on the proliferation of AKP organoids, while it completely inhibited p |
| E19 | doc:PMC12162862 | — | `stage3.egfr.only-50pct-respond-anti-egfr` | Only 50% of patients eligible for anti-EGFR therapy respond to treatment, while the rest display primary resis |
| E20 | doc:PMC12162862 | — | `stage3.egfr.smoc2-key-mediator` | Smoc2 was identified as a key upregulated target mediating these phenotypes that could be rescued upon additio |
| E21 | doc:PMC12162862 | — | `stage3.egfr.smoc2-knockout-rescues-all` | additional Smoc2-knockout could revert all these phenotypes induced by EGFR deletion, demonstrating that SMOC2 |
| E22 | doc:PMC12162862 | — | `stage3.egfr.smoc2-negative-correlation-krasmt-tcga` | by correlating SMOC2 to EGFR expression in patients of the TCGA-COAD cohort, we observed a negative correlatio |

## ERBB2 — engine verdict: rejected (verified)

Verdict node `stage3.erbb2.erbb2-verdict` · 40 citable items · 0/0 external ids resolve

1. The disqualifying combination that drives the rejection rests on three quotes [E1][E2][E3] that the audit flags explicitly mark as "QUOTE UNVERIFIED," meaning the factual basis for the most consequential node in the derivation was never checked against its source documents.
2. While the engine weights HERACLES-B's failed primary endpoint at 9.7% ORR [E8][E19] as disqualifying, it simultaneously acknowledges that MOUNTAINEER achieved 55% ORR with 6.2 months median PFS [E35], DESTINY-CRC01 cohort A reached 45.3% ORR [E39], and MyPathway reported 32% ORR [E24], all vastly exceeding the standard-of-care comparators TAS-102 at 2% and regorafenib at 1% [E25].
3. The "no guideline endorsement" criterion relies solely on ESMO's silence [E7][E33], yet the ledger shows NCCN guidelines explicitly recommend ERBB2 testing in RAS/BRAF wild-type mCRC and list ERBB2-targeted therapies as subsequent treatment options [E20][E21], which the derivation's rule for no-guideline-endorsement never incorporated.
4. The two grade 5 ILD deaths in DESTINY-CRC01 [E34] are treated as "unacceptable safety" without the ledger providing any denominator to calculate a fatality rate, and the 19% CNS progression signal [E28] is a drug distribution limitation rather than evidence that ERBB2 is an intrinsically unsafe target.
5. The neratinib-cetuximab no-response signal [E9][E36] is counted against the target, but this was one specific combination in quadruple-WT patients, while the derivation never tested whether the durable case benefit from trastuzumab [E26][E27] or the cross-trial efficacy synthesis [E24] outweighs a

**Audit flags fed to the model:**
- quote not verified against its document: E1, E2, E3, E4, E5, E6
- no citation in this ledger reaches an external record — all evidence is internal document text

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E1 | doc:ERBB2 Disqualifying Evidence Combination | — | `stage3.erbb2.disqualifying-evidence-combination` | Grade 5 interstitial lung disease events were reported in the DESTINY-CRC01 trial |
| E2 | doc:ERBB2 Disqualifying Evidence Combination | — | `stage3.erbb2.disqualifying-evidence-combination` | HERACLES-B primary endpoint was not met |
| E3 | doc:ERBB2 Disqualifying Evidence Combination | — | `stage3.erbb2.disqualifying-evidence-combination` | No ERBB2-targeted therapies are approved for metastatic colorectal cancer |
| E7 | doc:ERBB2 in COAD Opposing Evidence | — | `stage3.erbb2.opposing-evidence-bundle` | ESMO guidelines make no mention of ERBB2 as a therapeutic target in mCRC |
| E8 | doc:ERBB2 in COAD Opposing Evidence | — | `stage3.erbb2.opposing-evidence-bundle` | HERACLES-B primary endpoint was not met |
| E9 | doc:ERBB2 in COAD Opposing Evidence | — | `stage3.erbb2.opposing-evidence-bundle` | Neratinib plus cetuximab showed no response in HER2-positive mCRC |
| E19 | doc:PMC9367374 | — | `stage3.erbb2.heracles-b-primary-endpoint-negative` | being negative for this endpoint (9.7%, 95% CI: 0–28) |
| E20 | doc:PMC9367374 | — | `stage3.erbb2.nccn-recommends-erbb2-testing-mcrc` | The NCCN (National Comprehensive Cancer Network) guidelines state that testing ERBB2 amplification/overexpress |
| E21 | doc:PMC9367374 | — | `stage3.erbb2.nccn-recommends-erbb2-testing-mcrc` | ERBB2-targeted therapies are recommended as subsequent therapy options, encouraging enrollment in a clinical t |
| E24 | doc:Multi-Trial Efficacy Synthesis | — | `stage3.erbb2.trial-efficacy-broad` | MOUNTAINEER, DESTINY-CRC01, MyPathway, HERACLES, and TRIUMPH all reported ORR signals in HER2-positive mCRC |
| E25 | doc:Multi-Trial Efficacy Synthesis | — | `stage3.erbb2.trial-efficacy-broad` | Standard-of-care comparators include TAS-102 and regorafenib for later-line mCRC |
| E26 | doc:PMC4506361 | — | `stage3.erbb2.case-treatment-duration-months` | Treatment with trastuzumab continued for 12 months in total |
| E27 | doc:PMC4506361 | — | `stage3.erbb2.case-treatment-duration-months` | The patient's performance status began to improve within two months of initiating treatment, with an ECOG scor |
| E28 | doc:PMC9367374 | — | `stage3.erbb2.cns-progression-heracles-pct` | CNS progression appeared in up to 19% of patients treated in this trial |
| E33 | doc:PMC9367374 | — | `stage3.erbb2.esmo-no-erbb2-mention-guideline` | The ESMO (European Society of. Medical Oncology) guidelines do not mention ERBB2 amplification/overexpression |
| E34 | doc:PMC9367374 | — | `stage3.erbb2.ild-grade5-deaths-destiny` | Five patients had interstitial lung disease or pneumonitis (two grade 2; one grade 3; two grade 5, the only tr |
| E35 | doc:PMC9367374 | — | `stage3.erbb2.mountaineer-mpfs-months` | The ORR was 55%, mPFS was 6.2 m (95% CI: 3.5–NE), and mOS 17.3 m (95% CI: 12.3–NE). |
| E36 | doc:PMC9367374 | — | `stage3.erbb2.neratinib-cetuximab-no-response` | it did not show responses: seven received stable disease |
| E39 | doc:PMC9367374 | — | `stage3.erbb2.destiny-crc01-a-orr-pct` | The ORR was 45.3% in cohort A |

## KRAS — engine verdict: promising (verified)

Verdict node `stage3.kras.kras-status-needed-therapeutic-decision` · 31 citable items · 0/0 external ids resolve

1. The regulatory-proof-exists node rests on FDA approvals for sotorasib and adagrasib that target only KRAS G12C [E11][E12], a mutation occurring in approximately 3% of MSS CRC and absent in MSI cases [E14], so the verdict leverages regulatory success in a minuscule patient subset as proof for the entire target.
2. The next-gen-overcomes-limitations node depends on preclinical evidence—MRTX1133 tumor regression is demonstrated only in in vivo models [E25] and RAS(ON) sustained regression is preclinical [E27]—while the phase 1/2 trial claim [E30] offers only "early results" with no confirmed clinical benefit.
3. Three unverified quotes underpin the pipeline-at-scale and caveats nodes: the 80 recruiting trials [E5], the 106 compounds [E8], and the undruggable history [E19], meaning the engine's pipeline breadth rests on unchecked document text.
4. The combination-efficacy-demonstrated node is driven by language characterizing combinations as "promising" [E7] and showing "potential" to improve outcomes [E6], not by demonstrated clinical efficacy, yet the node label asserts efficacy is demonstrated.
5. The engine counts 156 trials as evidence of pipeline-at-scale [E3] while simultaneously acknowledging that 52 of them target exclusively the rare G12C mutation [E4], a misallocation that inflates the pipeline metric with trials irrelevant to the prevalent G12D and G12V mutations [E15].

**Audit flags fed to the model:**
- quote not verified against its document: E5, E8, E19
- no citation in this ledger reaches an external record — all evidence is internal document text

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E3 | doc:PMC12658183 | — | `stage3.kras.clinical-trials-156-crc` | A systematic examination of the Clinical Trials Database (https://clinicaltrials.gov), combining automatic sea |
| E4 | doc:PMC12658183 | — | `stage3.kras.clinical-trials-52-g12c-only` | Of the 156 clinical trials, 52 evaluated compounds exclusively targeting KRAS G12C (Fig. 9), despite the very  |
| E5 | doc:PMC12658183 | — | `stage3.kras.clinical-trials-80-recruiting` | Eighty of these trials are currently recruiting patients, and 11 will recruit patients in the near future, ref |
| E6 | doc:PMC12658183 | — | `stage3.kras.combination-improved-response-pfs` | Recent preclinical and clinical studies have demonstrated the potential of these combination approaches to imp |
| E7 | doc:PMC12658183 | — | `stage3.kras.combination-therapy-promise` | Combining KRAS inhibitors with anti-EGFR therapy or other targeted agents has emerged as a promising approach, |
| E8 | doc:PMC12658183 | — | `stage3.kras.compounds-106-targeting-kras` | A systematic search of the NCI Thesaurus and PubChem, combining automated searches and manual curation (see \u |
| E11 | doc:PMC12658183 | — | `stage3.kras.fda-approved-adagrasib-crc` | Adagrasib (Krazati) was FDA-approved for KRAS G12C-mutated locally advanced or metastatic CRC on June 21, 2024 |
| E12 | doc:PMC12658183 | — | `stage3.kras.fda-approved-sotorasib-crc` | Sotorasib (Lumakras) in combination with panitumumab (Vectibix) was approved by the FDA for CRC on January 16, |
| E14 | doc:PMC12658183 | — | `stage3.kras.g12c-3pct-mss-absent-msi` | Despite their approval, these two inhibitors exclusively target the rare KRAS G12C mutation, which occurs in a |
| E15 | doc:PMC12658183 | — | `stage3.kras.g12c-inhibitors-not-active-prevalent` | KRAS G12C inhibitors have shown remarkable success in cancers harboring the G12C mutation, but as they are des |
| E19 | doc:PMC12658183 | — | `stage3.kras.kras-long-considered-undruggable` | Due to repeated failures of both direct and indirect approaches, KRAS was long considered \u201cundruggable.\u |
| E25 | doc:PMC12658183 | — | `stage3.kras.mrtx1133-tumor-regression-crc` | MRTX1133 is highly selective for KRAS G12D and induces tumor regression in multiple in vivo models, including  |
| E27 | doc:PMC12658183 | — | `stage3.kras.preclinical-ras-on-sustained-regression` | Preclinical studies show sustained suppression of RAS pathway signaling and prolonged tumor regression, wherea |
| E30 | doc:PMC12658183 | — | `stage3.kras.several-novel-inhibitors-phase-1-2` | Several of these novel inhibitors are already in phase 1 and 2 clinical trials (Fig. 9), and early results sug |

## WRN — engine verdict: promising (verified)

Verdict node `stage3.wrn.wrn-verdict` · 16 citable items · 0/0 external ids resolve

1. The entire promising verdict rests on a single retrospective database extraction with very limited clinical data [E11], so the biomarker-enrichment and checkpoint-option counters are derived from a study design that cannot support direct therapeutic conclusions.
2. The engine treats WRN-mut median TMB of 49 mut/MB as exceeding a 41 mut/MB checkpoint-response cutoff [E9][E10], but the same source states median-level differences between WRN-mut and WRN-wt subgroups were not statistically significant [E13], undermining the TMB-based rationale.
3. The synthetic-lethality and selectivity claims rely on in vitro cell-line observations that WRN is dispensable in MSS cells [E3][E8], while no cited evidence demonstrates in vivo efficacy or clinical validation of WRN inhibitors, and [E5] explicitly states none are in clinical trials.
4. The checkpoint-inhibition rationale is weakened because PD-L1 expression is not predictive of CRC checkpoint response [E14], and WRN itself is an inferior methylation marker compared with validated CIMP-high markers [E15], limiting biomarker confidence.
5. Moreover, the derivation imports a WRN copy-loss/CIN association from an unverified quote [E16], and CIN is linked to poor prognosis and treatment resistance [E12], so the verdict may conflate CIN-driven aggressiveness with MSI-selective vulnerability rather than establishing WRN as a clinically actionable target.

**Audit flags fed to the model:**
- quote not verified against its document: E16
- no citation in this ledger reaches an external record — all evidence is internal document text

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E3 | doc:PMC7281075 | — | `stage3.wrn.wrn-dispensable-mss` | In contrast, in MSS cell lines, WRN was dispensable for cell survival |
| E5 | doc:PMC7281075 | — | `stage3.wrn.wrn-inhibitors-identified` | Inhibitors, such as NSC19630 [35], NSC617145 [36], ML216 [37], NCGC00029283, NCGC00063279, and NCGC00357377 [3 |
| E8 | doc:PMC7281075 | — | `stage3.wrn.wrn-synthetic-lethality-msi` | In tumor cell lines, the co-occurrence of WRN inactivation and MSI leads to cell death and cell cycle arrest v |
| E9 | doc:PMC7281075 | — | `stage3.wrn.wrn-tmb-exceeds-cutoff` | In our cohort, the median TMB in WRN-mut tumors was significantly higher (49 mut/MB) than in WRN-wt tumors (10 |
| E10 | doc:PMC7281075 | — | `stage3.wrn.wrn-tmb-exceeds-cutoff` | In a retrospective study of MSI-H/dMMR metastatic CRC featuring patients who underwent treatment with a checkp |
| E11 | doc:PMC7281075 | — | `stage3.wrn.retrospective-limited` | Our study has important limitations, such as retrospective data extraction from a large database including onl |
| E12 | doc:PMC8478156 | — | `stage3.wrn.cin-poor-prognosis` | CIN is a critical hallmark of cancer and is closely related to tumor metastasis, treatment resistance, and poo |
| E13 | doc:PMC7281075 | — | `stage3.wrn.median-tmb-not-significant` | However, when looking at median levels, the differences observed with mean levels are no longer statistically  |
| E14 | doc:PMC7281075 | — | `stage3.wrn.pdl1-not-predictive-crc` | In the setting of CRC, PD-L1 expression levels do not seem to play a major role in predicting response upon ch |
| E15 | doc:PMC2579485 | — | `stage3.wrn.wrn-cimp-marker-inferior` | Performance of the 5 new markers (CACNA1G, IGF2, NEUROG1, RUNX3, and SOCS1), CRABP1 and MLH1 was consistently  |
| E16 | doc:PMC8478156 | — | `stage3.wrn.wrn-copy-loss-cin` | we observed broad copy number loss of WRN, NAT1, NF2, and BUB1B, as well as copy number gain of MYC, ERBB2, EG |
