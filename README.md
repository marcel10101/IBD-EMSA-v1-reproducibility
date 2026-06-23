# IBD-EMSA v1 Public Repository Package

This repository supports the IBD-EMSA v1 exploratory evidence-to-state framework for inflammatory bowel disease gut multi-omics. It is intended for reproducibility, auditability, and transparent interpretation of the revised JCC submission package.

IBD-EMSA v1 is not a clinical diagnostic, prognostic, relapse-prediction, or treatment-decision tool.

## Repository Contents

The repository contains scripts, source manifests, processed/audit-level tables, recovered internal model outputs, locked-subset scoring files, ST001000 summary-level projection audit materials, figure source-data/status files, expected outputs, and standalone checks.

## Scientific Scope After JCC Reviewer-Comment Patch

- ST001000 is documented as summary-level external faecal metabolomics projection only. No end-to-end external validation claim is made. Cross-platform projection is constrained by metabolite nomenclature, annotation confidence, ion mode, feature coverage, batch structure and quantitative scaling.
- Locked primary internal model rows use ridge logistic regression.
- UC vs non-IBD locked ridge metabolomics result: AUROC 0.855; AUPRC 0.894.
- Elastic-net, random forest, XGBoost, and PLS-DA are supplementary sensitivity or comparison models only.
- Candidate prioritisation uses six-domain evidence annotation and rule-based evidence-tiering.
- The representative state score is the representative metabolomics state score. Microbiome taxonomy is treated as an upstream ecological-background layer; metabolomics is treated as a closer functional-output layer reflecting microbial metabolism, host inflammation, diet exposure, barrier status and co-metabolism.
- The 1,470-feature modelling universe and 499 retained candidate set are documented as aggregate and identifier-harmonisation audit layers unless a complete recomputed bridge file is explicitly supplied.

## Data Sources

Covered sources include the 491-record evidence map, HMP2/IBDMDB processed matrices, ST001000 summary-level external metabolomics projection audit outputs, intermediate candidate/scoring matrices, figure source-data records, and Supplementary Tables S1-S10 source records. Restricted raw third-party datasets are not redistributed.

## Installation

```bash
pip install -r requirements.txt
```

## Minimum Reproducibility

```bash
python reproduce_minimal_results.py
python run_all_reproducible_steps.py
```

## Candidate Feature Filtering

The package documents the 81,867 metabolomics feature space to 1,000 locked modelling features, 1,479 taxa to 470 locked taxa, and 1,470 upstream modelling universe to 499 directly detected candidate features as aggregate and identifier-harmonisation audit layers. Raw restricted matrices are not redistributed.

## HMP2/IBDMDB Internal Model

The internal evaluation uses subject-grouped cross-validation with no subject overlap between train/test folds. Ridge logistic regression is the locked primary model for the reported internal proof-of-concept rows. Other model families are sensitivity or comparison analyses.

## ST001000 Summary-Level Projection

ST001000 is included as a summary-level external faecal metabolomics projection and recoverability audit. Repository files should not be described as complete row-level ST001000 recomputation unless a row-level recomputation workbook and script set are explicitly present.

## Figure Handling

Do not export from the old `Figure.pptx`. Manual figure exports should be made from the corrected JCC deck described in `docs/figure_manual_export_instructions.md`.

## Data Not Redistributed

Excluded data include patient-private data, raw restricted ST001000 matrices, raw ENA/NCBI/Qiita/Transcriptomics downloads, unlicensed third-party raw data, tool environments, package caches, and compiled artifacts.

## GitHub and DOI

The GitHub repository is intended as the maintainable code repository. A permanent archive DOI should be added only after it is verified from the final public release record.

## Reviewer-Comment Patch Alignment

- Weak or non-significant exploratory associations with HBI, SCCAI and faecal calprotectin are interpreted as scope boundaries, not as clinical validation failures.
- IBD-EMSA v1 should not replace clinical activity indices, faecal calprotectin, endoscopy, relapse prediction or treatment-response assessment.
- Future work requires prospectively harmonised paired multi-omics cohorts with synchronised clinical indices, faecal calprotectin, endoscopy and treatment exposure records.

## Manual Pre-Upload Checklist

Before public release, the depositor should:

- manually export figures from the corrected PPTX if image files are required;
- replace the license placeholder with the final license;
- add the verified final GitHub repository URL and archive DOI if available;
- complete final public-release sensitivity review;
- approve final repository wording and file order.
