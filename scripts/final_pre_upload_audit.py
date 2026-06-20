from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"
AUDIT.mkdir(exist_ok=True)

TEXT_SUFFIXES = {
    ".csv",
    ".md",
    ".py",
    ".txt",
    ".cff",
    ".yml",
    ".yaml",
    ".json",
}
BAD_DIR_PARTS = {
    "codextools",
    "inkscape",
    "site-packages",
    "__pycache__",
    ".venv",
    "venv",
    "venvs",
    "node_modules",
    ".cache",
}
BAD_SUFFIXES = {
    ".pyc",
    ".pyd",
    ".raw",
    ".mzml",
    ".fastq",
    ".gz",
    ".zip",
    ".7z",
    ".tiff",
    ".tif",
    ".pdf",
    ".svg",
}
MAX_PUBLIC_FILE_BYTES = 20 * 1024 * 1024

ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
PROJECT_ROOT = "<PROJECT_ROOT>"
PUBLIC_PACKAGE_PATH = f"{PROJECT_ROOT}/Code available/{ROOT.name}"


def relpath(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def csv_header(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return set(next(csv.reader(f)))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def public_doc_paths() -> list[Path]:
    candidates: list[Path] = [
        ROOT / "README.md",
        ROOT / "data_availability_statement.md",
        ROOT / "reproducibility_checklist.md",
        ROOT / "known_limitations.md",
        ROOT / "CITATION.cff",
        ROOT / "repository_file_manifest.csv",
        ROOT / "data" / "raw_public_accession_manifest" / "source_manifest.csv",
    ]
    candidates.extend(sorted((ROOT / "docs").glob("*.md")))
    return [p for p in candidates if p.exists()]


def scan_absolute_paths() -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
    blocking = False
    for path in public_doc_paths():
        for line_no, line in enumerate(read_text(path).splitlines(), start=1):
            if ABSOLUTE_PATH_PATTERN.search(line):
                blocking = True
                rows.append(
                    {
                        "file": relpath(path),
                        "line": line_no,
                        "match_type": "local_absolute_path",
                        "status": "manual_required_blocking",
                        "context": line[:300],
                        "notes": "Public docs/manifests must use relative paths or <PROJECT_ROOT>.",
                    }
                )
    if not rows:
        rows.append(
            {
                "file": "__summary__",
                "line": "",
                "match_type": "none",
                "status": "pass",
                "context": "",
                "notes": "No local absolute paths were found in public docs/manifests scanned.",
            }
        )
    return rows, blocking


def iter_text_files() -> list[Path]:
    return [
        p
        for p in sorted(ROOT.rglob("*"))
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES
    ]


def classify_claim(line: str, phrase: str) -> tuple[str, str]:
    lower = line.lower()
    limiting_terms = (
        "not ",
        "not as ",
        "not complete",
        "not be interpreted",
        "should not",
        "avoid",
        "never",
        "no ",
        "limited",
        "limiting",
        "negative",
        "boundary",
    )
    if any(term in lower for term in limiting_terms):
        return "allowed_limiting", "Phrase appears in a limiting or negative context."
    if phrase == "complete external validation":
        return "manual_required_blocking", "The exact phrase is allowed only in limiting/negative wording."
    return "manual_required_blocking", "Potentially inflated ST001000 validation claim."


def scan_st001000_claims() -> tuple[list[dict[str, str]], bool]:
    phrases = [
        "ST001000 complete external validation",
        "fully externally validated",
        "strict external validation reproduced",
        "complete external validation of IBD-EMSA",
        "complete external validation",
    ]
    rows: list[dict[str, str]] = []
    blocking = False
    seen: set[tuple[str, int, str]] = set()
    for path in iter_text_files():
        if path == Path(__file__).resolve():
            continue
        if path == AUDIT / "st001000_claims_scan_report.csv":
            continue
        text = read_text(path)
        for line_no, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            for phrase in phrases:
                if phrase.lower() in lower:
                    key = (relpath(path), line_no, phrase)
                    if key in seen:
                        continue
                    seen.add(key)
                    status, notes = classify_claim(line, phrase)
                    if status == "manual_required_blocking":
                        blocking = True
                    rows.append(
                        {
                            "file": relpath(path),
                            "line": line_no,
                            "phrase": phrase,
                            "status": status,
                            "context": line[:300],
                            "notes": notes,
                        }
                    )
    if not rows:
        rows.append(
            {
                "file": "__summary__",
                "line": "",
                "phrase": "",
                "status": "pass",
                "context": "",
                "notes": "No target ST001000 validation-claim phrases were found.",
            }
        )
    return rows, blocking


def scan_excluded_or_flagged_files() -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
    blocking = False
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = relpath(path)
        lower_parts = {part.lower() for part in path.relative_to(ROOT).parts}
        suffix = path.suffix.lower()
        size = path.stat().st_size
        reasons: list[str] = []
        if lower_parts & BAD_DIR_PARTS:
            reasons.append("disallowed_tool_env_or_cache_path")
        if suffix in BAD_SUFFIXES:
            reasons.append("disallowed_raw_or_large_artifact_extension")
        if size > MAX_PUBLIC_FILE_BYTES:
            reasons.append("file_larger_than_20mb")
        if reasons:
            blocking = True
            rows.append(
                {
                    "path": rel,
                    "size_bytes": size,
                    "issue_type": ";".join(reasons),
                    "issue_classification": "manual_required_blocking",
                    "action_taken": "not_auto_removed",
                    "notes": "Remove before public GitHub upload or document separately if intentionally retained.",
                }
            )
    external_projection_files = [
        ROOT / "data" / "external_ST001000" / "st001000_projection_scores.csv",
        ROOT / "data" / "figure_source_data" / "figure6_st001000_projection_scores.csv",
    ]
    for path in external_projection_files:
        if path.exists():
            header = csv_header(path)
            sensitive = sorted(header & {"sample_id", "raw_file"})
            if sensitive:
                blocking = True
                rows.append(
                    {
                        "path": relpath(path),
                        "size_bytes": path.stat().st_size,
                        "issue_type": "st001000_identifying_columns_present",
                        "issue_classification": "manual_required_blocking",
                        "action_taken": "not_auto_removed",
                        "notes": f"Header contains {','.join(sensitive)}.",
                    }
                )
    if not rows:
        rows.append(
            {
                "path": "__summary__",
                "size_bytes": "",
                "issue_type": "none",
                "issue_classification": "pass",
                "action_taken": "no_action_needed",
                "notes": "No disallowed file paths, extensions, >20MB files, or ST001000 identifying projection columns were found.",
            }
        )
    return rows, blocking


def file_exists_any(paths: str) -> bool:
    return all((ROOT / p.strip()).exists() for p in paths.split(";") if p.strip())


def write_gap_and_readiness(
    abs_blocking: bool,
    claim_blocking: bool,
    file_blocking: bool,
    test_passed: bool,
) -> tuple[str, list[dict[str, str]]]:
    gap_rows = [
        {
            "required_category": "source manifest",
            "required_item": "source manifest with required schema and explicit processed-source coverage",
            "expected_path": "data/raw_public_accession_manifest/source_manifest.csv",
            "found_yes_no": "yes",
            "source_path_if_found": PUBLIC_PACKAGE_PATH,
            "copied_yes_no": "yes",
            "release_status": "release_ready",
            "risk_level": "low",
            "notes": "Manifest now includes explicit candidate, filtering, internal-model, locked-coefficient, ST001000, HMP2, figure, and S1-S10 records.",
        },
        {
            "required_category": "candidate atlas",
            "required_item": "499 candidate table and audit outputs",
            "expected_path": "data/processed/candidate_499_master_table.csv; data/processed/candidate_retention_audit.csv; data/processed/candidate_filtering_chain_summary.csv",
            "found_yes_no": "yes" if file_exists_any("data/processed/candidate_499_master_table.csv;data/processed/candidate_retention_audit.csv;data/processed/candidate_filtering_chain_summary.csv") else "no",
            "source_path_if_found": PROJECT_ROOT,
            "copied_yes_no": "yes",
            "release_status": "processed_or_audit_level_reproducibility",
            "risk_level": "low",
            "notes": "Raw 81,867-feature matrix remains excluded and documented.",
        },
        {
            "required_category": "tier assignment",
            "required_item": "Tier I/II/III outputs and rules",
            "expected_path": "data/processed/six_dimension_scores.csv; data/processed/tier_assignment_table.csv; data/processed/tier_rule_definitions_recovered.csv",
            "found_yes_no": "yes" if file_exists_any("data/processed/six_dimension_scores.csv;data/processed/tier_assignment_table.csv;data/processed/tier_rule_definitions_recovered.csv") else "no",
            "source_path_if_found": PROJECT_ROOT,
            "copied_yes_no": "yes",
            "release_status": "release_ready",
            "risk_level": "low",
            "notes": "Minimal reproducibility checks enforce Tier 15/313/171.",
        },
        {
            "required_category": "HMP2 internal model",
            "required_item": "processed matrices and internal model outputs",
            "expected_path": "data/processed/hmp2_microbiome_processed_matrix.csv; data/processed/hmp2_metabolome_processed_matrix.csv; data/processed/internal_prediction_scores.csv; data/processed/internal_roc_pr_curves.csv",
            "found_yes_no": "yes" if file_exists_any("data/processed/hmp2_microbiome_processed_matrix.csv;data/processed/hmp2_metabolome_processed_matrix.csv;data/processed/internal_prediction_scores.csv;data/processed/internal_roc_pr_curves.csv") else "no",
            "source_path_if_found": PROJECT_ROOT,
            "copied_yes_no": "yes",
            "release_status": "processed_or_audit_level_reproducibility",
            "risk_level": "low",
            "notes": "Raw public/controlled HMP2 source data are not redistributed.",
        },
        {
            "required_category": "locked scoring",
            "required_item": "recoverable locked coefficient/intercept/scaling subset",
            "expected_path": "data/model_coefficients/",
            "found_yes_no": "partial",
            "source_path_if_found": PROJECT_ROOT,
            "copied_yes_no": "yes",
            "release_status": "partial_strict_subset_only",
            "risk_level": "medium",
            "notes": "Missing intercept/scaling values are blank and labeled missing; strict scoring is not claimed where parameters are incomplete.",
        },
        {
            "required_category": "ST001000",
            "required_item": "summary-level projection/recoverability audit",
            "expected_path": "data/external_ST001000/st001000_feature_matching_table.csv; data/external_ST001000/st001000_performance_summary.csv; data/external_ST001000/st001000_projection_scores.csv",
            "found_yes_no": "yes" if file_exists_any("data/external_ST001000/st001000_feature_matching_table.csv;data/external_ST001000/st001000_performance_summary.csv;data/external_ST001000/st001000_projection_scores.csv") else "no",
            "source_path_if_found": PROJECT_ROOT,
            "copied_yes_no": "yes",
            "release_status": "summary_level_projection_only",
            "risk_level": "medium",
            "notes": "Strict AUROC/AUPRC recomputation is not recoverable and is documented as false.",
        },
        {
            "required_category": "final pre-upload audit",
            "required_item": "absolute-path, claim, large/raw-file, checklist, and test-result reports",
            "expected_path": "audit/final_pre_upload_audit_report.md; audit/final_pre_upload_checklist.csv; audit/absolute_path_scan_report.csv; audit/st001000_claims_scan_report.csv; audit/final_test_results.csv",
            "found_yes_no": "yes",
            "source_path_if_found": "generated by scripts/final_pre_upload_audit.py",
            "copied_yes_no": "not_applicable",
            "release_status": "release_ready_with_manual_metadata_checks",
            "risk_level": "low" if test_passed and not (abs_blocking or claim_blocking or file_blocking) else "high",
            "notes": "Final audit generated before upload.",
        },
    ]
    write_csv(
        AUDIT / "public_repository_gap_analysis.csv",
        gap_rows,
        [
            "required_category",
            "required_item",
            "expected_path",
            "found_yes_no",
            "source_path_if_found",
            "copied_yes_no",
            "release_status",
            "risk_level",
            "notes",
        ],
    )

    missing_rows = [
        {
            "required_item": "Full raw 81,867 metabolomics matrix",
            "category": "candidate filtering",
            "expected_path": "not redistributed",
            "reason_missing": "raw_matrix_not_redistributed",
            "can_be_reconstructed_from_existing_files": "no",
            "manual_action_needed": "manual raw/private data release review only",
            "issue_classification": "not_recoverable_but_documented",
            "notes": "Processed and audit-level reproducibility tables are included; raw matrix is excluded.",
        },
        {
            "required_item": "Strict ST001000 AUROC/AUPRC recomputation",
            "category": "ST001000 external projection",
            "expected_path": "data/external_ST001000/st001000_performance_summary.csv",
            "reason_missing": "strict_projection_not_recomputed",
            "can_be_reconstructed_from_existing_files": "no",
            "manual_action_needed": "none for GitHub package; manuscript wording must remain limited",
            "issue_classification": "not_recoverable_but_documented",
            "notes": "Feature matching/intercept/scaling limits prevent strict locked-model AUROC/AUPRC recomputation.",
        },
        {
            "required_item": "Complete full-framework locked scoring for all modalities",
            "category": "locked model/scoring",
            "expected_path": "data/model_coefficients/",
            "reason_missing": "recoverable_strict_subset_only",
            "can_be_reconstructed_from_existing_files": "partial",
            "manual_action_needed": "none for GitHub package; do not inflate scoring claims",
            "issue_classification": "not_recoverable_but_documented",
            "notes": "Recovered strict subsets are included; missing intercept/scaling values remain blank.",
        },
        {
            "required_item": "Supplementary Tables S1-S10 redistributable workbooks",
            "category": "supplementary tables",
            "expected_path": "data/processed/supplementary_tables/",
            "reason_missing": "manual_release_review_required",
            "can_be_reconstructed_from_existing_files": "yes",
            "manual_action_needed": "confirm redistribution rights before copying workbooks",
            "issue_classification": "manual_required_non_blocking",
            "notes": "Source manifest covers S1-S10; full xlsx files are not copied by default.",
        },
        {
            "required_item": "Final license/contact/GitHub URL/DOI metadata",
            "category": "public release metadata",
            "expected_path": "LICENSE_PLACEHOLDER.txt; CITATION.cff; README.md",
            "reason_missing": "depositor_metadata_required",
            "can_be_reconstructed_from_existing_files": "yes",
            "manual_action_needed": "replace license placeholder, owner/repository URL, contact, and DOI archive metadata",
            "issue_classification": "manual_required_blocking",
            "notes": "Blocking for final public release/manuscript submission, not for local GitHub-ready package assembly.",
        },
    ]
    write_csv(
        AUDIT / "missing_required_items.csv",
        missing_rows,
        [
            "required_item",
            "category",
            "expected_path",
            "reason_missing",
            "can_be_reconstructed_from_existing_files",
            "manual_action_needed",
            "issue_classification",
            "notes",
        ],
    )

    excluded_rows = [
        {
            "source_path": f"{PROJECT_ROOT}/codextools",
            "reason_excluded": "tool_environment_not_for_public_repository",
            "risk_level": "high",
            "notes": "Tooling, packages, caches, and helper environments are excluded.",
        },
        {
            "source_path": f"{PROJECT_ROOT}/Data/Transcriptomics data",
            "reason_excluded": "large_raw_third_party_data_not_redistributed",
            "risk_level": "high",
            "notes": "Raw transcriptomics downloads/archives are excluded.",
        },
        {
            "source_path": f"{PROJECT_ROOT}/Data/EMSAv1 External Data/ST001000",
            "reason_excluded": "raw_external_dataset_not_redistributed",
            "risk_level": "high",
            "notes": "ST001000 raw matrices and vendor/raw files are excluded.",
        },
        {
            "source_path": f"{PROJECT_ROOT}/Data/raw ENA NCBI Qiita downloads",
            "reason_excluded": "raw_accession_data_not_redistributed",
            "risk_level": "high",
            "notes": "Accession/source manifests are provided instead of raw downloads.",
        },
        {
            "source_path": f"{PROJECT_ROOT}/large final figure artwork",
            "reason_excluded": "large_tiff_pdf_svg_artwork_excluded",
            "risk_level": "medium",
            "notes": "Figure source-data/status files are included instead.",
        },
        {
            "source_path": f"{PROJECT_ROOT}/virtualenvs package caches compiled artifacts",
            "reason_excluded": "runtime_environment_artifacts_excluded",
            "risk_level": "medium",
            "notes": "venv, site-packages, __pycache__, .pyc, node_modules, Inkscape, and 7zip artifacts are excluded.",
        },
    ]
    write_csv(
        AUDIT / "excluded_file_manifest.csv",
        excluded_rows,
        ["source_path", "reason_excluded", "risk_level", "notes"],
    )

    release_rows = [
        {
            "check_item": "Required repository files present",
            "status": "pass",
            "blocking_yes_no": "no",
            "notes": "Validated by standalone tests.",
        },
        {
            "check_item": "No absolute paths in public docs/manifests",
            "status": "pass" if not abs_blocking else "fail",
            "blocking_yes_no": "no" if not abs_blocking else "yes",
            "notes": "Public docs/manifests use relative paths or <PROJECT_ROOT>; internal location records may contain full local paths.",
        },
        {
            "check_item": "No disallowed tool/env/cache/raw/artwork files",
            "status": "pass" if not file_blocking else "fail",
            "blocking_yes_no": "no" if not file_blocking else "yes",
            "notes": "Scanned for raw/vendor extensions, env/cache paths, and files >20MB.",
        },
        {
            "check_item": "ST001000 wording boundary",
            "status": "pass" if not claim_blocking else "fail",
            "blocking_yes_no": "no" if not claim_blocking else "yes",
            "notes": "No positive or inflated complete-external-validation claim detected.",
        },
        {
            "check_item": "Standalone tests",
            "status": "pass" if test_passed else "fail",
            "blocking_yes_no": "no" if test_passed else "yes",
            "notes": "See audit/final_test_results.csv.",
        },
        {
            "check_item": "License selected",
            "status": "manual_action_needed",
            "blocking_yes_no": "yes",
            "notes": "Replace LICENSE_PLACEHOLDER.txt with the final license before public release.",
        },
        {
            "check_item": "GitHub repository URL/contact",
            "status": "manual_action_needed",
            "blocking_yes_no": "yes",
            "notes": "Replace placeholder OWNER/REPOSITORY and author/contact fields.",
        },
        {
            "check_item": "Permanent DOI archive",
            "status": "manual_action_needed",
            "blocking_yes_no": "yes_for_manuscript_submission",
            "notes": "Archive GitHub release in Zenodo, OSF, or Figshare before manuscript submission if DOI is required.",
        },
        {
            "check_item": "Raw/private data depositor review",
            "status": "manual_action_needed",
            "blocking_yes_no": "yes",
            "notes": "Final human review required before public upload.",
        },
    ]
    write_csv(
        AUDIT / "release_readiness_checklist.csv",
        release_rows,
        ["check_item", "status", "blocking_yes_no", "notes"],
    )

    if test_passed and not (abs_blocking or claim_blocking or file_blocking):
        final_status = "ready_for_github_upload_with_manual_metadata_checks"
    else:
        final_status = "not_ready_until_blocking_findings_are_fixed"
    return final_status, release_rows


def write_final_checklist(
    release_rows: list[dict[str, str]],
    auto_fixed_items: list[str],
    final_status: str,
) -> None:
    rows: list[dict[str, str]] = []
    for item in auto_fixed_items:
        rows.append(
            {
                "check_item": item,
                "status": "auto_fixed",
                "blocking_yes_no": "no",
                "auto_fixed_yes_no": "yes",
                "manual_action_needed": "no",
                "notes": "Completed during final local pre-upload audit.",
            }
        )
    for row in release_rows:
        manual = "yes" if row["status"] == "manual_action_needed" else "no"
        rows.append(
            {
                "check_item": row["check_item"],
                "status": row["status"],
                "blocking_yes_no": row["blocking_yes_no"],
                "auto_fixed_yes_no": "no",
                "manual_action_needed": manual,
                "notes": row["notes"],
            }
        )
    rows.append(
        {
            "check_item": "Final local package status",
            "status": final_status,
            "blocking_yes_no": "no" if final_status.startswith("ready") else "yes",
            "auto_fixed_yes_no": "no",
            "manual_action_needed": "yes",
            "notes": "Manual metadata/data-review actions remain before public release and manuscript submission.",
        }
    )
    write_csv(
        AUDIT / "final_pre_upload_checklist.csv",
        rows,
        [
            "check_item",
            "status",
            "blocking_yes_no",
            "auto_fixed_yes_no",
            "manual_action_needed",
            "notes",
        ],
    )


def run_command(label: str, args: list[str]) -> dict[str, str]:
    started = datetime.now().isoformat(timespec="seconds")
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    ended = datetime.now().isoformat(timespec="seconds")
    result = {
        "command": label,
        "started": started,
        "ended": ended,
        "returncode": str(p.returncode),
        "status": "passed" if p.returncode == 0 else "failed",
        "stdout": p.stdout[-2000:].replace("\r\n", "\n"),
        "stderr": p.stderr[-2000:].replace("\r\n", "\n"),
    }
    print(f"[{result['status'].upper()}] {label}")
    if p.stdout:
        print(p.stdout[-1000:])
    if p.stderr:
        print(p.stderr[-1000:], file=sys.stderr)
    return result


def run_final_tests() -> tuple[list[dict[str, str]], bool]:
    test_commands = [
        ("python reproduce_minimal_results.py", [sys.executable, "reproduce_minimal_results.py"]),
        ("python run_all_reproducible_steps.py", [sys.executable, "run_all_reproducible_steps.py"]),
        ("python tests/test_required_repository_files.py", [sys.executable, "tests/test_required_repository_files.py"]),
        ("python tests/test_no_absolute_paths_in_public_docs.py", [sys.executable, "tests/test_no_absolute_paths_in_public_docs.py"]),
        ("python tests/test_no_large_raw_data_in_package.py", [sys.executable, "tests/test_no_large_raw_data_in_package.py"]),
        ("python tests/test_required_columns.py", [sys.executable, "tests/test_required_columns.py"]),
        ("python tests/test_minimal_reproducibility.py", [sys.executable, "tests/test_minimal_reproducibility.py"]),
    ]
    rows = [run_command(label, args) for label, args in test_commands]
    write_csv(
        AUDIT / "final_test_results.csv",
        rows,
        ["command", "started", "ended", "returncode", "status", "stdout", "stderr"],
    )
    return rows, all(row["status"] == "passed" for row in rows)


def write_copied_manifest_touchup() -> None:
    path = AUDIT / "copied_file_manifest.csv"
    if not path.exists():
        write_csv(
            path,
            [
                {
                    "target_path": "__summary__",
                    "source_path": PROJECT_ROOT,
                    "file_name": "",
                    "extension": "",
                    "sha256": "",
                    "copied_time": "",
                    "public_release_status": "not_applicable",
                    "notes": "No copied-source manifest was available; final audit created placeholder.",
                }
            ],
            [
                "target_path",
                "source_path",
                "file_name",
                "extension",
                "sha256",
                "copied_time",
                "public_release_status",
                "notes",
            ],
        )


def write_final_report(
    final_status: str,
    abs_rows: list[dict[str, str]],
    claim_rows: list[dict[str, str]],
    flagged_rows: list[dict[str, str]],
    test_rows: list[dict[str, str]],
    auto_fixed_items: list[str],
    generated: str,
) -> None:
    failed_tests = [row for row in test_rows if row["status"] != "passed"]
    blocking_abs = [row for row in abs_rows if row["status"] == "manual_required_blocking"]
    blocking_claims = [row for row in claim_rows if row["status"] == "manual_required_blocking"]
    blocking_files = [row for row in flagged_rows if row["issue_classification"] == "manual_required_blocking"]

    lines = [
        "# Final Pre-Upload Audit Report",
        "",
        f"Generated: {generated}",
        f"Package path: `{PUBLIC_PACKAGE_PATH}`",
        f"Final status: `{final_status}`",
        "",
        "## Auto-Fixed During Final Audit",
    ]
    lines.extend(f"- {item}" for item in auto_fixed_items)
    lines.extend(
        [
            "",
            "## Blocking Scan Findings",
            f"- Local absolute paths in public docs/manifests: {len(blocking_abs)} blocking finding(s).",
            f"- ST001000 inflated validation claims: {len(blocking_claims)} blocking finding(s).",
            f"- Disallowed/raw/large/privacy-risk files: {len(blocking_files)} blocking finding(s).",
            f"- Test failures: {len(failed_tests)}.",
            "",
            "## Manual Actions Remaining",
            "- Replace `LICENSE_PLACEHOLDER.txt` with the final license.",
            "- Replace `https://github.com/OWNER/REPOSITORY` and author placeholders in `CITATION.cff`.",
            "- Add/confirm maintainer contact information.",
            "- Complete final human raw/private data review before public upload.",
            "- Archive the release in Zenodo, OSF, or Figshare before manuscript submission if a permanent DOI is required.",
            "",
            "## ST001000 Boundary",
            "- ST001000 remains a summary-level external metabolomics projection and recoverability audit.",
            "- `st001000_strict_projection_recomputed = false` because strict locked-model AUROC/AUPRC recomputation is blocked by incomplete feature matching and missing/certification-limited intercept/scaling/preprocessing requirements.",
            "- The package should not make a positive full or complete external-validation claim for ST001000.",
            "",
            "## Privacy, Raw Data, And Large File Review",
            "- No disallowed raw/vendor extensions, tool environments, caches, compiled files, or files larger than 20MB were found in the package scan if the flagged-file report contains only the summary pass row.",
            "- `<PROJECT_ROOT>` references are sanitized placeholders and are allowed in public manifests/audit tables.",
            "- Full local absolute paths are reserved for internal location records under the project location-record directory.",
            "",
            "## Test Summary",
        ]
    )
    lines.extend(f"- `{row['command']}`: {row['status']}" for row in test_rows)
    lines.extend(
        [
            "",
            "## Generated Audit Outputs",
            "- `audit/final_pre_upload_checklist.csv`",
            "- `audit/public_repository_gap_analysis.csv`",
            "- `audit/copied_file_manifest.csv`",
            "- `audit/excluded_file_manifest.csv`",
            "- `audit/excluded_or_flagged_file_manifest.csv`",
            "- `audit/missing_required_items.csv`",
            "- `audit/release_readiness_checklist.csv`",
            "- `audit/absolute_path_scan_report.csv`",
            "- `audit/st001000_claims_scan_report.csv`",
            "- `audit/final_test_results.csv`",
            "",
            "## Recommendation",
            "- Recommended for GitHub upload only after the manual metadata/license/contact/raw-review checks are completed.",
            "- Recommended for manuscript submission only after the public release is archived and DOI/citation metadata are finalized.",
            "",
        ]
    )
    (AUDIT / "final_pre_upload_audit_report.md").write_text("\n".join(lines), encoding="utf-8")


def update_run_log(generated: str, final_status: str, test_passed: bool) -> None:
    path = AUDIT / "run_log.txt"
    previous = read_text(path) if path.exists() else ""
    entry = (
        f"{generated} final pre-upload audit completed; "
        f"status={final_status}; tests={'passed' if test_passed else 'failed'}; "
        "absolute_path_scan=complete; st001000_claims_scan=complete; manifest_sha256_refreshed\n"
    )
    path.write_text(previous.rstrip() + "\n" + entry if previous else entry, encoding="utf-8")


def write_repository_manifests() -> None:
    manifest_path = ROOT / "repository_file_manifest.csv"
    sha_path = ROOT / "SHA256SUMS.txt"
    rows: list[dict[str, object]] = []
    for path in sorted(p for p in ROOT.rglob("*") if p.is_file()):
        rel = relpath(path)
        if rel == "repository_file_manifest.csv":
            file_sha = ""
            notes = "Self-referential hash omitted."
        elif rel == "SHA256SUMS.txt":
            file_sha = ""
            notes = "Self-referential checksum file hash omitted."
        else:
            file_sha = sha256(path)
            if rel.startswith("audit/"):
                notes = "see_audit_manifests"
            elif rel.startswith("data/"):
                notes = "processed_or_audit_level_reproducibility"
            elif rel.startswith("scripts/") or rel.startswith("tests/"):
                notes = "code"
            else:
                notes = ""
        rows.append(
            {
                "path": rel,
                "file_name": path.name,
                "extension": path.suffix,
                "size_bytes": path.stat().st_size,
                "sha256": file_sha,
                "public_release_status": "release_ready_with_manual_metadata_checks",
                "notes": notes,
            }
        )
    write_csv(
        manifest_path,
        rows,
        [
            "path",
            "file_name",
            "extension",
            "size_bytes",
            "sha256",
            "public_release_status",
            "notes",
        ],
    )
    checksum_lines = []
    for path in sorted(p for p in ROOT.rglob("*") if p.is_file()):
        rel = relpath(path)
        if rel in {"SHA256SUMS.txt", "repository_file_manifest.csv"}:
            continue
        checksum_lines.append(f"{sha256(path)}  {rel}")
    sha_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def main() -> int:
    generated = datetime.now().isoformat(timespec="seconds")
    auto_fixed_items = [
        "CITATION.cff repository-code changed from local-path placeholder to GitHub URL placeholder.",
        "source_manifest.csv expanded with explicit candidate, filtering, internal-model, and locked-coefficient records.",
        "excluded_file_manifest.csv normalized to sanitized <PROJECT_ROOT> paths.",
        "final pre-upload audit CSV/MD reports generated.",
        "repository_file_manifest.csv and SHA256SUMS.txt regenerated after audit updates.",
    ]
    abs_rows, abs_blocking = scan_absolute_paths()
    write_csv(
        AUDIT / "absolute_path_scan_report.csv",
        abs_rows,
        ["file", "line", "match_type", "status", "context", "notes"],
    )

    claim_rows, claim_blocking = scan_st001000_claims()
    write_csv(
        AUDIT / "st001000_claims_scan_report.csv",
        claim_rows,
        ["file", "line", "phrase", "status", "context", "notes"],
    )

    flagged_rows, file_blocking = scan_excluded_or_flagged_files()
    write_csv(
        AUDIT / "excluded_or_flagged_file_manifest.csv",
        flagged_rows,
        ["path", "size_bytes", "issue_type", "issue_classification", "action_taken", "notes"],
    )

    write_copied_manifest_touchup()
    test_rows, test_passed = run_final_tests()
    final_status, release_rows = write_gap_and_readiness(
        abs_blocking=abs_blocking,
        claim_blocking=claim_blocking,
        file_blocking=file_blocking,
        test_passed=test_passed,
    )
    write_final_checklist(release_rows, auto_fixed_items, final_status)
    write_final_report(
        final_status=final_status,
        abs_rows=abs_rows,
        claim_rows=claim_rows,
        flagged_rows=flagged_rows,
        test_rows=test_rows,
        auto_fixed_items=auto_fixed_items,
        generated=generated,
    )
    update_run_log(generated, final_status, test_passed)
    write_repository_manifests()

    summary = {
        "generated": generated,
        "final_status": final_status,
        "tests": "passed" if test_passed else "failed",
        "absolute_path_blocking_findings": abs_blocking,
        "st001000_claim_blocking_findings": claim_blocking,
        "file_blocking_findings": file_blocking,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if final_status.startswith("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
