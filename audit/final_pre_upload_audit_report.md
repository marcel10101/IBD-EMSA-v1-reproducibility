# Final Pre-Upload Audit Report

Generated: 2026-06-20T14:41:35
Package path: `<PROJECT_ROOT>/Code available/public_repository_code_package_GitHub_ready_20260620_141023`
Final status: `ready_for_github_upload_with_manual_metadata_checks`

## Auto-Fixed During Final Audit
- CITATION.cff repository-code changed from local-path placeholder to GitHub URL placeholder.
- source_manifest.csv expanded with explicit candidate, filtering, internal-model, and locked-coefficient records.
- excluded_file_manifest.csv normalized to sanitized <PROJECT_ROOT> paths.
- final pre-upload audit CSV/MD reports generated.
- repository_file_manifest.csv and SHA256SUMS.txt regenerated after audit updates.

## Blocking Scan Findings
- Local absolute paths in public docs/manifests: 0 blocking finding(s).
- ST001000 inflated validation claims: 0 blocking finding(s).
- Disallowed/raw/large/privacy-risk files: 0 blocking finding(s).
- Test failures: 0.

## Manual Actions Remaining
- Replace `LICENSE_PLACEHOLDER.txt` with the final license.
- Replace `https://github.com/OWNER/REPOSITORY` and author placeholders in `CITATION.cff`.
- Add/confirm maintainer contact information.
- Complete final human raw/private data review before public upload.
- Archive the release in Zenodo, OSF, or Figshare before manuscript submission if a permanent DOI is required.

## ST001000 Boundary
- ST001000 remains a summary-level external metabolomics projection and recoverability audit.
- `st001000_strict_projection_recomputed = false` because strict locked-model AUROC/AUPRC recomputation is blocked by incomplete feature matching and missing/certification-limited intercept/scaling/preprocessing requirements.
- The package should not make a positive full or complete external-validation claim for ST001000.

## Privacy, Raw Data, And Large File Review
- No disallowed raw/vendor extensions, tool environments, caches, compiled files, or files larger than 20MB were found in the package scan if the flagged-file report contains only the summary pass row.
- `<PROJECT_ROOT>` references are sanitized placeholders and are allowed in public manifests/audit tables.
- Full local absolute paths are reserved for internal location records under the project location-record directory.

## Test Summary
- `python reproduce_minimal_results.py`: passed
- `python run_all_reproducible_steps.py`: passed
- `python tests/test_required_repository_files.py`: passed
- `python tests/test_no_absolute_paths_in_public_docs.py`: passed
- `python tests/test_no_large_raw_data_in_package.py`: passed
- `python tests/test_required_columns.py`: passed
- `python tests/test_minimal_reproducibility.py`: passed

## Generated Audit Outputs
- `audit/final_pre_upload_checklist.csv`
- `audit/public_repository_gap_analysis.csv`
- `audit/copied_file_manifest.csv`
- `audit/excluded_file_manifest.csv`
- `audit/excluded_or_flagged_file_manifest.csv`
- `audit/missing_required_items.csv`
- `audit/release_readiness_checklist.csv`
- `audit/absolute_path_scan_report.csv`
- `audit/st001000_claims_scan_report.csv`
- `audit/final_test_results.csv`

## Recommendation
- Recommended for GitHub upload only after the manual metadata/license/contact/raw-review checks are completed.
- Recommended for manuscript submission only after the public release is archived and DOI/citation metadata are finalized.
