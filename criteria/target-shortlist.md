# Target Shortlist Criteria — v2

Scope: therapeutic targets (genes or proteins) for the disease named in the review request. Only the supplied documents (published articles and clinical-trial records) count as evidence. Nothing outside them may be assumed.

## R1 Chemical matter
A target has chemical matter when at least three of the supplied publications describe an inhibitor, degrader, small molecule or antibody acting on it.

    applies to: publications
    ask: Does this publication describe an inhibitor, degrader, small molecule or antibody acting on the target?
    met when: at least 3 documents answer yes

## R2 Mechanistic support
A target has mechanistic support when at least one supplied publication reports experimental work, such as cell lines, organoids or patient samples, linking the target to the disease.

    applies to: publications
    ask: Does this publication report experimental work, such as cell lines, organoids or patient samples, linking the target to the disease?
    met when: at least 1 document answers yes

## R3 In vivo support
A target has in vivo support when at least one supplied publication reports an animal model, xenograft or other in vivo experiment on the target in the disease.

    applies to: publications
    ask: Does this publication report an animal model, xenograft or other in vivo experiment on the target in the disease?
    met when: at least 1 document answers yes

## R4 Clinical traction
A target has clinical traction when at least one supplied clinical-trial record for the disease tests a therapy aimed at the target, names the target or one of its aliases in the record itself, and is in phase 3 or later, or is currently recruiting.

    applies to: trials
    ask: Does this trial record test a therapy aimed at the target, name the target or one of its aliases in its own text, and show phase 3 or later or a currently recruiting status?
    met when: at least 1 document answers yes

## R5 Opposing evidence
Evidence against the target, such as resistance, lack of efficacy or an unfavourable safety finding, must be recorded as facts as well. It is never left out, and a conclusion must say whether it outweighs the supporting evidence.

    applies to: publications and trials
    ask: Does this document report evidence against the target, such as resistance, lack of efficacy or an unfavourable safety finding?
    record only

## R6 Verdict
A target is promising when it has chemical matter, has in vivo support, and has clinical traction. Every other target is rejected for this review. Mechanistic support strengthens a verdict but does not replace any of these three conditions.

    verdict: R1 and R3 and R4

## R7 Provenance
Every fact must quote the document it came from. A verdict that cannot be traced to quoted evidence is void.
