from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['README.md','LICENSE_PLACEHOLDER.txt','CITATION.cff','requirements.txt','environment.yml','SHA256SUMS.txt','data_availability_statement.md','reproduce_minimal_results.py','run_all_reproducible_steps.py','repository_file_manifest.csv','reproducibility_checklist.md','known_limitations.md','data/raw_public_accession_manifest/source_manifest.csv','data/processed/six_dimension_scores.csv','data/processed/tier_assignment_table.csv','data/processed/candidate_499_master_table.csv','data/external_ST001000/st001000_feature_matching_table.csv','data/figure_source_data/figure_source_data_status.csv','audit/public_repository_gap_analysis.csv']
for rel in REQUIRED:
    assert (ROOT / rel).exists(), rel
scripts = ['01_score_six_dimensions.py','02_assign_evidence_tiers.py','03_filter_metabolomics_features.py','04_filter_microbiome_taxa.py','05_build_499_candidate_atlas.py','06_prepare_hmp2_matrices.py','07_train_internal_models.py','08_grouped_cross_validation.py','09_evaluate_internal_models.py','10_score_new_samples.py','11_match_st001000_features.py','12_project_st001000_locked_model.py','13_evaluate_st001000_projection.py']
for script in scripts:
    assert (ROOT / 'scripts' / script).exists(), script
print('test_required_repository_files passed')
