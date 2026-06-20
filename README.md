# IBD-EMSA v1 Public Repository Package

IBD-EMSA v1 is a reproducible public code and audit package for an inflammatory bowel disease eco-metabolic state assessment framework.

## Repository Contents

The repository contains scripts, source manifests, processed/audit tables, recovered internal model outputs, locked-subset scoring files, ST001000 summary-level projection audit tables, figure source-data/status files, and standalone tests.

## Data Sources

Covered sources include the 491-study evidence map, HMP2/IBDMDB processed matrices, ST001000 summary-level external metabolomics projection audit outputs, intermediate candidate/scoring matrices, figure source data, and Supplementary Tables S1-S10 source records. Restricted raw third-party datasets are not redistributed.

## Installation

```bash
pip install -r requirements.txt
```

## Minimum Reproducibility

```bash
python reproduce_minimal_results.py
python run_all_reproducible_steps.py
```

## Six-Dimensional Scoring

Dimensions: reproducibility, direction_consistency, effect_strength, disease_process_coverage, mechanistic_relevance, and model_support. Public scripts are audit/wrapper scripts derived from supplementary and recovered audit tables, not original training scripts.

## Candidate Feature Filtering

The package documents 81,867 metabolomics features to 1,000; 1,479 taxa to 470; 1,470 upstream candidates to 499 directly detected candidates; and 499 = 345 microbiome + 154 metabolome. Raw matrices are not redistributed.

## HMP2/IBDMDB Internal Model

The internal evaluation uses subject-grouped CV with no subject overlap, ridge logistic models where recovered/rebuilt, and microbiome, metabolome, and paired late-fusion modalities.

## Locked Scoring

Strict locked-model scoring is available only for model tasks and modalities with recovered coefficients, intercepts, and training-set scaling parameters. Missing intercept/scaling are never imputed as zero.

## ST001000 Summary-Level External Projection

ST001000 is provided as a summary-level external metabolomics projection and recoverability audit, not as complete external validation of the full IBD-EMSA framework.

Sample n = 220; CD = 88; UC = 76; Control = 56; QC-passed samples = 220; task-specific locked feature denominator = 25; UC vs nonIBD matched = 8/25; CD vs nonIBD matched = 5/25; nonIBD vs IBD matched = 4/25; CD vs UC matched = 2/25. Strict AUROC/AUPRC were not independently recomputed.

## Figure Generation

Figure scripts and release-screened source-data/status files are provided. Large final TIFF/PDF/SVG artwork is excluded.

## Data Not Redistributed

Excluded data include patient-private data, raw ST001000 matrices, raw ENA/NCBI/Qiita/Transcriptomics downloads, unlicensed raw third-party data, tool environments, package caches, and compiled artifacts.

## GitHub And DOI

The GitHub repository is intended as the maintainable code repository. A permanent archived release DOI should be generated through Zenodo, OSF, or Figshare before manuscript submission.

## Citation And Contact

Update `CITATION.cff`, license, repository URL, and contact details before public upload.

## Manual Pre-Upload Checklist

The package is locally ready for GitHub upload with manual metadata checks. Before public release, the depositor must:

- replace `LICENSE_PLACEHOLDER.txt` with the final license;
- add the final GitHub repository URL to `CITATION.cff`;
- add maintainer/contact information;
- complete final raw/private data review;
- archive the release in Zenodo, OSF, or Figshare before manuscript submission if a permanent DOI is required.

The package should not be described as fully ready for manuscript submission until license, contact, DOI/archive, and final raw/private data review are complete.
