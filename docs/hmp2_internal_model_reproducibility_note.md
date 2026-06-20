# HMP2/IBDMDB Internal Model Recovery Report

Generated: 2026-06-19T12:33:54

1. Microbiome matrix found: **yes**; 388 samples and 470 features.
2. Metabolome matrix found: **yes**; 388 samples and 1000 features.
3. Sample metadata found: **yes**; direct age/sex/BMI fields excluded.
4. `subject_id` found: **yes**.
5. Original CV split found: **partial**; aggregate fold overlap counts were recovered and sample-level splits were reconstructed from OOF test-fold membership.
6. Subject-grouped CV confirmed: **yes** for recovered ridge logistic OOF folds.
7. No subject overlap confirmed: **yes**, all task/fold overlaps are zero.
8. Ridge logistic model code found or rebuilt: **rebuilt** in scripts 06-09 with recovered old script evidence in the inventory.
9. Positive class definition found: **yes**, in `audit/positive_class_definition.csv`.
10. Microbiome/metabolome/paired late-fusion results found: **yes**.
11. AUROC/AUPRC recomputation: **yes**, from recovered OOF probabilities.
12. Missing for full raw-to-final regeneration: exact raw ingestion chain, historical bootstrap CIs, original coefficient intercepts, and project-specific late-fusion training metadata beyond recovered OOF predictions.
13. Public package integration: scripts 06-09, internal matrices, metadata, CV splits, prediction scores, coefficient rows, performance, ROC/PR curves, and documentation note.
14. Data Availability should state that processed HMP2/IBDMDB-derived matrices and recovered OOF outputs are included for reproducibility review, while raw source files and sensitive clinical metadata must be obtained from the original data source or controlled local archive as applicable.

## Recomputed Metric Table

| task | modality | n_samples | n_subjects | AUROC | AUPRC | metric_status |
| --- | --- | --- | --- | --- | --- | --- |
| CD vs UC | metabolome | 283 | 79 | 0.71612 | 0.524332 | recomputed_from_recovered_oof_predictions |
| CD vs UC | microbiome | 283 | 79 | 0.650959 | 0.487826 | recomputed_from_recovered_oof_predictions |
| CD vs UC | paired_late_fusion | 283 | 79 | 0.680045 | 0.506976 | recomputed_from_recovered_oof_predictions |
| CD vs nonIBD | metabolome | 286 | 75 | 0.783636 | 0.846437 | recomputed_from_recovered_oof_predictions |
| CD vs nonIBD | microbiome | 286 | 75 | 0.437648 | 0.587136 | recomputed_from_recovered_oof_predictions |
| CD vs nonIBD | paired_late_fusion | 286 | 75 | 0.762589 | 0.822075 | recomputed_from_recovered_oof_predictions |
| UC vs nonIBD | metabolome | 207 | 56 | 0.856396 | 0.903381 | recomputed_from_recovered_oof_predictions |
| UC vs nonIBD | microbiome | 207 | 56 | 0.522456 | 0.548487 | recomputed_from_recovered_oof_predictions |
| UC vs nonIBD | paired_late_fusion | 207 | 56 | 0.820542 | 0.880277 | recomputed_from_recovered_oof_predictions |
| nonIBD vs IBD | metabolome | 388 | 105 | 0.755073 | 0.875988 | recomputed_from_recovered_oof_predictions |
| nonIBD vs IBD | microbiome | 388 | 105 | 0.456503 | 0.719188 | recomputed_from_recovered_oof_predictions |
| nonIBD vs IBD | paired_late_fusion | 388 | 105 | 0.776746 | 0.91277 | recomputed_from_recovered_oof_predictions |
