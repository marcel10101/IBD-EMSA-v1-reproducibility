from pathlib import Path
import csv
ROOT = Path(__file__).resolve().parents[1]
def header(rel):
    with (ROOT / rel).open('r', encoding='utf-8-sig', newline='') as f:
        return set(next(csv.reader(f)))
assert {'source_item','dataset_or_table','accession_or_identifier','PMID_or_DOI','source_url_or_database','local_processed_file','generating_script','sha256','public_release_status','notes'} <= header('data/raw_public_accession_manifest/source_manifest.csv')
assert {'feature_id','feature_name','omics_type','coefficient','intercept','scaling_mean','scaling_sd','model_task','recoverable_status','notes'} <= header('data/model_coefficients/locked_metabolome_coefficients.csv')
assert {'task','qc_passed_sample_n','locked_feature_denominator','matched_feature_count','metric_status'} <= header('data/external_ST001000/st001000_performance_summary.csv')
assert {'feature_id','evidence_tier','source_status'} <= header('data/processed/tier_assignment_table.csv')
print('test_required_columns passed')
