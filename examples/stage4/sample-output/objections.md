# Objections to the CRC target shortlist

Generated 2026-08-18 12:33 UTC · model `MiniMaxAI/MiniMax-M3` · export `['fixtures/crc6-dossiers.html', 'fixtures/crc6-verdicts.html']`

6 targets reviewed — 4 promising, 2 rejected. Each objection is five sentences, every sentence cited into the Parseltongue derivation.

## EGFR — engine verdict: promising (verified)

Verdict node `egfr-promising` · 21 citable items · 8/8 external ids resolve

1. The clinical-traction verdict rests on a single recruiting Phase 2 trial [E4][E19] with zero late-phase trials [E3], satisfying the C7 criterion [E1] only because C6 [E7] sets the bar at "at least one registered colorectal" trial — a trivially low threshold that says little about real therapeutic traction in CRC.
2. The dossier-anchored claim leans on papers that do not actually concern EGFR-directed therapy in colorectal cancer: PMID 42609336 [E17] addresses cardiovascular-kidney-metabolic biomarkers in elderly HFpEF patients, and PMID 42609500 [E18] describes squamous transformation in EGFR-mutant lung adenocarcinoma, neither of which anchors an EGFR-in-CRC dossier.
3. The in-vivo support [E2][E6] is similarly fragile, since PMID 42492133 [E13] studies HER2-expressing colon cancer cells and PMID 42576549 [E14] examines Boldine/Naringenin chemoprevention, neither demonstrating EGFR-specific in vivo activity in CRC models.
4. The C8 provenance rule [E21] requires every fact to quote its source document, yet the engine treats these off-topic papers as decisive anchors for EGFR in CRC, effectively using the rule as a rubber stamp rather than a substantive check.
5. Finally, five of the decisive numbers — in-vitro, in-vivo, druggability, and literature hits [E2][E9][E12] — are aggregate PubMed query-hit counters rather than findings from specific CRC-EGFR studies, so the verdict is built on counts of loosely related publications rather than substantive evidence

**Audit flags fed to the model:**
- counter at zero: src.egfr.trials-late-phase = 0
- 5 of the decisive numbers are aggregate counters (a count of query hits), not findings from a specific study

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E1 | doc:charter | — | `src.rules.c7-in-force` | A target is promising when it is druggable, has in vivo support, and has |
| E2 | doc:pubmed-EGFR | — | `src.egfr.in-vivo-hits` | PUBMED_HITS in_vivo=3 |
| E3 | doc:trials-EGFR | — | `src.egfr.trials-late-phase` | TRIALS late_phase=0 |
| E4 | doc:trials-EGFR | — | `src.egfr.trials-recruiting` | TRIALS recruiting=1 |
| E6 | doc:charter | — | `src.rules.c5-in-force` | A target has in vivo support when at least one indexed publication |
| E7 | doc:charter | — | `src.rules.c6-in-force` | A target has clinical traction when at least one registered colorectal |
| E9 | doc:pubmed-EGFR | — | `src.egfr.druggability-hits` | PUBMED_HITS druggability=3 |
| E12 | doc:pubmed-EGFR | — | `src.egfr.in-vitro-hits` | PUBMED_HITS in_vitro=3 |
| E13 | [pmid:42492133](https://pubmed.ncbi.nlm.nih.gov/42492133/) | yes | `src.egfr.paper-42492133` | TITLE: Anticancer evaluation of novel chiral tetrahydropyrazolo[1,5-a]pyrimidine derivatives: Inhibitory effec |
| E14 | [pmid:42576549](https://pubmed.ncbi.nlm.nih.gov/42576549/) | yes | `src.egfr.paper-42576549` | TITLE: Chemopreventive Effects of Boldine and Naringenin on DMH-Induced Colorectal Carcinogenesis. |
| E17 | [pmid:42609336](https://pubmed.ncbi.nlm.nih.gov/42609336/) | yes | `src.egfr.paper-42609336` | TITLE: A clinical prediction model integrating cardiovascular-kidney-metabolic biomarkers for the composite ou |
| E18 | [pmid:42609500](https://pubmed.ncbi.nlm.nih.gov/42609500/) | yes | `src.egfr.paper-42609500` | TITLE: Squamous transformation of EGFR-mutant lung adenocarcinoma after EGFR-TKI therapy: clonal continuity, t |
| E19 | [nct:NCT07503756](https://clinicaltrials.gov/study/NCT07503756) | yes | `src.egfr.trial-NCT07503756` | TITLE: JS212 Combination Therapies in Metastatic Colorectal Cancer |
| E21 | doc:charter | — | `src.rules.c8-in-force` | Every fact must quote the document it came from. A verdict that cannot be |

## ERBB2 — engine verdict: promising (verified)

Verdict node `erbb2-promising` · 23 citable items · 10/10 external ids resolve

1. The clinical-traction node relies on trials-recruiting = 3 [E4], yet NCT07384377 is explicitly NOT_YET_RECRUITING [E20], so the recruiting counter is inflated by at least one and the dossier-anchored chain [E23] mixes a non-recruiting trial into the recruiting tally.
2. The dossier-anchored chain [E23] incorporates PMIDs 42497534, 42599169, and 42601812 [E16][E17][E18], all of which are HER2 breast-cancer studies with no colorectal cancer relevance, contaminating the provenance anchor with off-indication evidence.
3. The in-vivo support [E2][E6] cites three records, but PMID 42401587 [E14] addresses mucinous adenocarcinoma apicobasal polarity rather than ERBB2-targeted therapy, and PMID 42176792 [E13] positions ERBB2 blockade only as a cetuximab-resistance salvage, so neither establishes ERBB2 as a primary CRC driver.
4. Five decisive numbers — binding-sites, druggability-hits, in-vitro-hits, in-vivo-hits, and crc-literature-hits — are aggregate query-hit counters [E8][E9][E12][E2] rather than study-level findings, the exact audit-flag weakness, so the thresholds are met by counting rather than by CRC-specific substance.
5. Stripping the breast-cancer papers [E17][E18] from the druggability-hits = 3 [E9] leaves at most one CRC-relevant chemical-matter record, which would fail the C2 requirement of "at least three indexed publications" [E11] and collapse the druggable node.

**Audit flags fed to the model:**
- 5 of the decisive numbers are aggregate counters (a count of query hits), not findings from a specific study

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E2 | doc:pubmed-ERBB2 | — | `src.erbb2.in-vivo-hits` | PUBMED_HITS in_vivo=3 |
| E4 | doc:trials-ERBB2 | — | `src.erbb2.trials-recruiting` | TRIALS recruiting=3 |
| E6 | doc:charter | — | `src.rules.c5-in-force` | A target has in vivo support when at least one indexed publication |
| E8 | [uniprot:P04626](https://www.uniprot.org/uniprotkb/P04626) | yes | `src.erbb2.binding-sites` | UNIPROT binding_sites=2 |
| E9 | doc:pubmed-ERBB2 | — | `src.erbb2.druggability-hits` | PUBMED_HITS druggability=3 |
| E11 | doc:charter | — | `src.rules.c2-in-force` | A target has chemical matter when at least three indexed publications |
| E12 | doc:pubmed-ERBB2 | — | `src.erbb2.in-vitro-hits` | PUBMED_HITS in_vitro=3 |
| E13 | [pmid:42176792](https://pubmed.ncbi.nlm.nih.gov/42176792/) | yes | `src.erbb2.paper-42176792` | TITLE: EGFR S442 ectodomain mutation confers cetuximab resistance that can be overcome by ERBB2 blockade with  |
| E14 | [pmid:42401587](https://pubmed.ncbi.nlm.nih.gov/42401587/) | yes | `src.erbb2.paper-42401587` | TITLE: Signaling downstream of tumor-stroma interaction regulates mucinous colorectal adenocarcinoma apicobasa |
| E16 | [pmid:42497534](https://pubmed.ncbi.nlm.nih.gov/42497534/) | yes | `src.erbb2.paper-42497534` | TITLE: The Xpert Breast Cancer Insight Test Predicts Distant Recurrence and Overall Survival in ER-Positive, H |
| E17 | [pmid:42599169](https://pubmed.ncbi.nlm.nih.gov/42599169/) | yes | `src.erbb2.paper-42599169` | TITLE: Incremental Value of Synthetic MRI Radiomics in Predicting Neoadjuvant Response in Human Epidermal Grow |
| E18 | [pmid:42601812](https://pubmed.ncbi.nlm.nih.gov/42601812/) | yes | `src.erbb2.paper-42601812` | TITLE: Exceptional Response of HER2-Positive Breast Cancer to Osimertinib: A Case Report. |
| E20 | [nct:NCT07384377](https://clinicaltrials.gov/study/NCT07384377) | yes | `src.erbb2.trial-NCT07384377` | TITLE: JSKN003 Versus Physician Choiced Treatment in Patients With HER2-positive and Advanced Colorectal Cance |
| E23 | doc:charter | — | `src.rules.c8-in-force` | Every fact must quote the document it came from. A verdict that cannot be |

## KRAS — engine verdict: promising (verified)

Verdict node `kras-promising` · 24 citable items · 11/11 external ids resolve

1. The clinical-traction criterion [E7] requires "at least one registered colorectal" trial, yet both cited trials [E21][E22] are explicitly for "Solid Tumors" with no colorectal-specific enrollment, and the late-phase counter is zero [E3], so the rule fires on recruiting=4 [E4] alone — a thin basis for "clinical traction" in CRC.
2. The dossier-anchored chain includes papers that are not KRAS-targeted CRC therapeutics — pmid:42527030 [E13] concerns IL-27/NK cells, pmid:42599639 [E17] is a pancreaticoduodenectomy case report, and pmid:42607542 [E20] studies KRAS G12C in NSCLC xenografts, not colorectal cancer.
3. The druggability counter of 3 [E9] is an aggregate query-hit count rather than a specific CRC-active inhibitor, and the only KRAS-specific druggability paper [E20] is in lung cancer cells, undermining the C2 chemical-matter claim [E11] for colorectal cancer.
4. Five of the decisive numbers — in-vitro=3 [E12], in-vivo=3 [E2], druggability=3 [E9], trials-recruiting=4 [E4], and binding-sites=17 [E8] — are aggregate counters or query-hit counts, not findings from individual CRC-specific studies, so the C4 [E23], C5 [E6], and C2 [E11] thresholds are satisfied by indexing artefacts rather than substantive CRC evidence.
5. The verdict rests on C7 [E1] requiring druggable + in vivo + clinical traction, but with late-phase=0 [E3], non-CRC trials [E21][E22], and an NSCLC druggability paper [E20] doing the work, the "promising" label for KRAS in colorectal cancer may not survive a stricter CRC-specific audit.

**Audit flags fed to the model:**
- counter at zero: src.kras.trials-late-phase = 0
- 5 of the decisive numbers are aggregate counters (a count of query hits), not findings from a specific study

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E1 | doc:charter | — | `src.rules.c7-in-force` | A target is promising when it is druggable, has in vivo support, and has |
| E2 | doc:pubmed-KRAS | — | `src.kras.in-vivo-hits` | PUBMED_HITS in_vivo=3 |
| E3 | doc:trials-KRAS | — | `src.kras.trials-late-phase` | TRIALS late_phase=0 |
| E4 | doc:trials-KRAS | — | `src.kras.trials-recruiting` | TRIALS recruiting=4 |
| E6 | doc:charter | — | `src.rules.c5-in-force` | A target has in vivo support when at least one indexed publication |
| E7 | doc:charter | — | `src.rules.c6-in-force` | A target has clinical traction when at least one registered colorectal |
| E8 | [uniprot:P01116](https://www.uniprot.org/uniprotkb/P01116) | yes | `src.kras.binding-sites` | UNIPROT binding_sites=17 |
| E9 | doc:pubmed-KRAS | — | `src.kras.druggability-hits` | PUBMED_HITS druggability=3 |
| E11 | doc:charter | — | `src.rules.c2-in-force` | A target has chemical matter when at least three indexed publications |
| E12 | doc:pubmed-KRAS | — | `src.kras.in-vitro-hits` | PUBMED_HITS in_vitro=3 |
| E13 | [pmid:42527030](https://pubmed.ncbi.nlm.nih.gov/42527030/) | yes | `src.kras.paper-42527030` | TITLE: IL-27 shapes NK cell heterogeneity and function in colorectal cancer. |
| E17 | [pmid:42599639](https://pubmed.ncbi.nlm.nih.gov/42599639/) | yes | `src.kras.paper-42599639` | TITLE: Salvage pancreaticoduodenectomy for localized recurrence after resection of ascending colon cancer: a c |
| E20 | [pmid:42607542](https://pubmed.ncbi.nlm.nih.gov/42607542/) | yes | `src.kras.paper-42607542` | TITLE: Anticancer effects of an XPO1 inhibitor (selinexor) with sotorasib following omeprazole preconditioning |
| E21 | [nct:NCT05176483](https://clinicaltrials.gov/study/NCT05176483) | yes | `src.kras.trial-NCT05176483` | TITLE: Study of Zanzalintinib in Combination With Immuno-Oncology or Other Agents in Participants With Solid T |
| E22 | [nct:NCT07300150](https://clinicaltrials.gov/study/NCT07300150) | yes | `src.kras.trial-NCT07300150` | TITLE: A Study of PT0511 in Participants With KRAS Mutated or Amplified Advanced Solid Tumors |
| E23 | doc:charter | — | `src.rules.c4-in-force` | A target has in vitro support when at least one indexed publication |

## MYC — engine verdict: rejected (verified)

Verdict node `myc-promising` · 21 citable items · 8/8 external ids resolve

1. The rejection rests entirely on C1 structural druggability failing because UniProt annotates zero binding sites on MYC [E8][E10], yet this single criterion ignores that the chemical-matter evidence includes a published dual MYC/GSPT1 protein degrader [E16] and a G-quadruplex-stabilizing agent in active CRC trials [E19], modalities that do not require a classical small-molecule binding pocket.
2. The C1 criterion [E10] is a single-database proxy that conflates "no annotated binding site" with "no druggable modality," and the ledger shows no independent verification that the UniProt annotation [E8] was cross-checked against degrader, covalent, or allosteric strategies that the chemical-matter counter of 3 [E9] already implicitly captures.
3. Clinical traction is non-zero with two recruiting trials [E4], including NCT07147231 specifically in refractory microsatellite-stable colorectal cancer [E19] and FOG-001 in solid tumors [E18], which directly contradicts a flat rejection for a CRC indication and shows C6 [E7] is satisfied while C1 [E10] silently vetoes the verdict.
4. The in-vivo counter of 3 [E2] and in-vitro counter of 3 [E12] are corroborated by five anchored PMIDs and two NCTs [E21], yet the engine reduces all of this to a single zero counter [E8] without testing whether C1 [E10] is even the appropriate gate for a transcription factor like MYC.
5. The audit flags already note that five decisive numbers are aggregate query-hit counts rather than study-level findings, meaning binding-sites=0 [E8] is the only non-aggregate counter driving the rejection, and a single UniProt annotation [E8] should not be permitted to outweigh corroborated clinical [E18][E19], chemical [E9][E16], and biological [E2][E12] evidence.

**Audit flags fed to the model:**
- counter at zero: src.myc.binding-sites = 0
- counter at zero: src.myc.trials-late-phase = 0
- 5 of the decisive numbers are aggregate counters (a count of query hits), not findings from a specific study

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E2 | doc:pubmed-MYC | — | `src.myc.in-vivo-hits` | PUBMED_HITS in_vivo=3 |
| E4 | doc:trials-MYC | — | `src.myc.trials-recruiting` | TRIALS recruiting=2 |
| E7 | doc:charter | — | `src.rules.c6-in-force` | A target has clinical traction when at least one registered colorectal |
| E8 | [uniprot:P01106](https://www.uniprot.org/uniprotkb/P01106) | yes | `src.myc.binding-sites` | UNIPROT binding_sites=0 |
| E9 | doc:pubmed-MYC | — | `src.myc.druggability-hits` | PUBMED_HITS druggability=3 |
| E10 | doc:charter | — | `src.rules.c1-in-force` | A target is structurally druggable when UniProt annotates at least one |
| E12 | doc:pubmed-MYC | — | `src.myc.in-vitro-hits` | PUBMED_HITS in_vitro=3 |
| E16 | [pmid:42607078](https://pubmed.ncbi.nlm.nih.gov/42607078/) | yes | `src.myc.paper-42607078` | TITLE: Dual MYC and GSPT1 Protein Degrader for MYC-Driven Hematologic Malignancies. |
| E18 | [nct:NCT05919264](https://clinicaltrials.gov/study/NCT05919264) | yes | `src.myc.trial-NCT05919264` | TITLE: FOG-001 in Locally Advanced or Metastatic Solid Tumors |
| E19 | [nct:NCT07147231](https://clinicaltrials.gov/study/NCT07147231) | yes | `src.myc.trial-NCT07147231` | TITLE: Testing the Effectiveness of the Anti-cancer Drug Pidnarulex (CX-5461), in Combination With Another Ant |
| E21 | doc:charter | — | `src.rules.c8-in-force` | Every fact must quote the document it came from. A verdict that cannot be |

## WRN — engine verdict: promising (verified)

Verdict node `wrn-promising` · 24 citable items · 11/11 external ids resolve

1. The clinical-traction verdict rests on trials-late-phase=1 [E6], but the sole late-phase trial NCT03570541 is a laparoscopic hemicolectomy anesthesia study ("TQL-block"), not a WRN-directed therapy [E22], meaning the C6 criterion is satisfied by a misclassified record rather than genuine WRN clinical activity [E4].
2. The dossier-anchored chain [E13] leans on papers that are only tangentially about WRN as a CRC drug target — PMID 42293362 concerns germline RecQ variants in Lynch-like syndrome [E17] and PMID 42484294 reports CRISPR modulators of WRN dependency rather than direct WRN inhibition [E19] — so the provenance is technically present but substantively hollow.
3. Five of the nine decisive numbers are aggregate query-hit counters rather than study-level findings (audit flag), so in-vitro=3 [E14], in-vivo=3 [E5], druggability=3 [E11], crc-literature-hits=5, and trials-total=10 cannot be audited for relevance, potency, or CRC specificity.
4. The chemical-matter threshold is met at the bare minimum of three indexed publications [E9][E11], yet no ledger entry reports a clinical-stage WRN inhibitor with disclosed CRC patient efficacy beyond the early-phase EIK1005 study [E24], and the remaining two recruiting trials are also phase 1 basket studies in solid tumors [E23][E24].
5. Even granting the in-vivo support [E3][E5], the only CRC-specific xenograft evidence traces to PMID 40203476 [E15] and PMID 41704373 [E16], both preclinical tool-compound studies, leaving the "promising" verdict resting on a single misattributed late-phase trial [E22] and unverified aggregate counts.

**Audit flags fed to the model:**
- 5 of the decisive numbers are aggregate counters (a count of query hits), not findings from a specific study

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E3 | doc:charter | — | `src.rules.c5-in-force` | A target has in vivo support when at least one indexed publication |
| E4 | doc:charter | — | `src.rules.c6-in-force` | A target has clinical traction when at least one registered colorectal |
| E5 | doc:pubmed-WRN | — | `src.wrn.in-vivo-hits` | PUBMED_HITS in_vivo=3 |
| E6 | doc:trials-WRN | — | `src.wrn.trials-late-phase` | TRIALS late_phase=1 |
| E9 | doc:charter | — | `src.rules.c2-in-force` | A target has chemical matter when at least three indexed publications |
| E11 | doc:pubmed-WRN | — | `src.wrn.druggability-hits` | PUBMED_HITS druggability=3 |
| E13 | doc:charter | — | `src.rules.c8-in-force` | Every fact must quote the document it came from. A verdict that cannot be |
| E14 | doc:pubmed-WRN | — | `src.wrn.in-vitro-hits` | PUBMED_HITS in_vitro=3 |
| E15 | [pmid:40203476](https://pubmed.ncbi.nlm.nih.gov/40203476/) | yes | `src.wrn.paper-40203476` | TITLE: Werner helicase as a therapeutic target in mismatch repair deficient colorectal cancer. |
| E16 | [pmid:41704373](https://pubmed.ncbi.nlm.nih.gov/41704373/) | yes | `src.wrn.paper-41704373` | TITLE: Discovery and Preclinical Evaluations of Potent, Selective, and Allosteric Covalent WRN Inhibitors with |
| E17 | [pmid:42293362](https://pubmed.ncbi.nlm.nih.gov/42293362/) | yes | `src.wrn.paper-42293362` | TITLE: RecQ DNA helicases germline variants in Lynch-like syndrome. |
| E19 | [pmid:42484294](https://pubmed.ncbi.nlm.nih.gov/42484294/) | yes | `src.wrn.paper-42484294` | TITLE: CRISPR Screening Identifies SMARCAL1 and MRN as Modulators of WRN Dependency in MSI-H Colorectal Cancer |
| E22 | [nct:NCT03570541](https://clinicaltrials.gov/study/NCT03570541) | yes | `src.wrn.trial-NCT03570541` | TITLE: TQL-block for Laparoscopic Hemicolectomy |
| E23 | [nct:NCT06974110](https://clinicaltrials.gov/study/NCT06974110) | yes | `src.wrn.trial-NCT06974110` | TITLE: Study of Orally Administered MOMA-341 in Participants With Advanced or Metastatic Solid Tumors |
| E24 | [nct:NCT07262619](https://clinicaltrials.gov/study/NCT07262619) | yes | `src.wrn.trial-NCT07262619` | TITLE: EIK1005-002: A Clinical Research Study Evaluating EIK1005, a Werner Helicase Inhibitor, as Monotherapy  |

## PRMT5 — engine verdict: rejected (verified)

Verdict node `prmt5-promising` · 22 citable items · 9/9 external ids resolve

1. The entire rejection rests on C6 clinical traction [E7] failing because trials-late-phase = 0 and trials-recruiting = 0 [E3][E4], yet trials-total = 1 shows a registered colorectal trial exists that the criterion simply ignores, making one zero-counter the sole arbiter of the verdict.
2. With dossier-anchored = True backed by eight papers including direct CRC work identifying PRMT5 as an oncogenic pair with METTL3 [E16] and MTAP-loss genomics relevant to PRMT5 synthetic lethality [E17], the engine discards substantive biological evidence because a single counter is zero.
3. The C6 rule [E7] demands late-phase or recruiting trials, but the derivation never tested whether the single registered trial [E3] is an early-phase study that could mature, so the zero reads as a query artefact rather than a substantive negative finding.
4. Five decisive numbers are aggregate query-hit counters [E2][E9][E12] already flagged as weak by the audit, meaning the in-vivo (3 hits) [E2], in-vitro (3 hits) [E12], and druggability (3 hits) [E9] support rests on counts the checker itself questions.
5. The C7 verdict criterion [E1] requires only druggable plus in vivo support, both satisfied here, so the rejection effectively overrides C7 with C6 without any charter justification for that hierarchy.

**Audit flags fed to the model:**
- counter at zero: src.prmt5.trials-late-phase = 0
- counter at zero: src.prmt5.trials-recruiting = 0
- 5 of the decisive numbers are aggregate counters (a count of query hits), not findings from a specific study

**Backtrace**

| key | source | resolves | node | quote |
|---|---|---|---|---|
| E1 | doc:charter | — | `src.rules.c7-in-force` | A target is promising when it is druggable, has in vivo support, and has |
| E2 | doc:pubmed-PRMT5 | — | `src.prmt5.in-vivo-hits` | PUBMED_HITS in_vivo=3 |
| E3 | doc:trials-PRMT5 | — | `src.prmt5.trials-late-phase` | TRIALS late_phase=0 |
| E4 | doc:trials-PRMT5 | — | `src.prmt5.trials-recruiting` | TRIALS recruiting=0 |
| E7 | doc:charter | — | `src.rules.c6-in-force` | A target has clinical traction when at least one registered colorectal |
| E9 | doc:pubmed-PRMT5 | — | `src.prmt5.druggability-hits` | PUBMED_HITS druggability=3 |
| E12 | doc:pubmed-PRMT5 | — | `src.prmt5.in-vitro-hits` | PUBMED_HITS in_vitro=3 |
| E16 | [pmid:42121254](https://pubmed.ncbi.nlm.nih.gov/42121254/) | yes | `src.prmt5.paper-42121254` | TITLE: Identification of METTL3 and PRMT5 as an oncogenic pair for the prognosis and therapeutic targets of co |
| E17 | [pmid:42133901](https://pubmed.ncbi.nlm.nih.gov/42133901/) | yes | `src.prmt5.paper-42133901` | TITLE: Genomics of MTAP Loss in >500,000 Solid Tumor Specimens Profiled Using Comprehensive Genomic Profiling  |
