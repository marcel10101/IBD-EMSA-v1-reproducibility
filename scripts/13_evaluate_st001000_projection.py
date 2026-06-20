from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from sklearn.metrics import average_precision_score, roc_auc_score
except Exception:  # pragma: no cover
    average_precision_score = None
    roc_auc_score = None


PROJECT_ROOT = Path(r"<PROJECT_ROOT>")
ST001000_ROOT = PROJECT_ROOT / "Data" / "外部验证数据" / "代谢组外部队列验证数据" / "ST001000"
PREVIOUS_AUDIT = PROJECT_ROOT / "EMSAv1modlereport" / "ST001000_external_projection_audit_20260619_104920"
COEFF_FILE = PROJECT_ROOT / "Trajectory Modeling" / "IBD_EMSA_v1" / "IBD_EMSA_v1_model_coefficients_or_loadings.csv"
PREPROCESSING_FILE = PROJECT_ROOT / "Trajectory Modeling" / "IBD_EMSA_v1" / "IBD_EMSA_v1_preprocessing_parameters.json"


def infer_output_root() -> Path:
    script_path = Path(__file__).resolve()
    if script_path.parent.name.lower() == "scripts" and script_path.parent.parent.name.startswith(
        "ST001000_external_validation_recovery_"
    ):
        return script_path.parent.parent
    return PROJECT_ROOT


OUTPUT_ROOT = infer_output_root()
DATA_DIR = OUTPUT_ROOT / "data" / "external"
REVIEW_DIR = OUTPUT_ROOT / "review"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_DIR.mkdir(parents=True, exist_ok=True)

MATCHING_FILE = DATA_DIR / "st001000_feature_matching_table.csv"
UNMATCHED_FILE = DATA_DIR / "st001000_unmatched_feature_reasons.csv"
PROJECTION_FILE = DATA_DIR / "st001000_projection_scores.csv"
PERFORMANCE_FILE = DATA_DIR / "st001000_performance_summary.csv"
REPORT_FILE = REVIEW_DIR / "ST001000_metabolomics_submodel_external_validation_recovery_report.md"

TASKS = {
    "UC vs Control": {"positive_class": "UC", "negative_class": "Control", "coefficient_task": "UC vs nonIBD"},
    "CD vs Control": {"positive_class": "CD", "negative_class": "Control", "coefficient_task": "CD vs nonIBD"},
    "IBD vs Control": {"positive_class": "IBD", "negative_class": "Control", "coefficient_task": "nonIBD vs IBD"},
    "CD vs UC": {"positive_class": "CD", "negative_class": "UC", "coefficient_task": "CD vs UC"},
    "UC vs nonIBD": {"positive_class": "UC", "negative_class": "nonIBD", "coefficient_task": "UC vs nonIBD"},
    "CD vs nonIBD": {"positive_class": "CD", "negative_class": "nonIBD", "coefficient_task": "CD vs nonIBD"},
    "nonIBD vs IBD": {"positive_class": "IBD", "negative_class": "nonIBD", "coefficient_task": "nonIBD vs IBD"},
}

PERFORMANCE_COLUMNS = [
    "task",
    "positive_class",
    "negative_class",
    "n_positive",
    "n_negative",
    "qc_passed_sample_n",
    "locked_feature_denominator",
    "matched_feature_count",
    "matching_proportion",
    "AUROC",
    "AUPRC",
    "metric_status",
    "reason_if_not_recomputed",
    "source_prediction_file",
    "source_label_file",
    "source_matching_file",
    "notes",
    "recoverable_status",
    "reason_if_not_recoverable",
    "required_missing_files",
]


def harmonize_group(label: Any) -> str:
    text = str(label).strip()
    lower = text.lower()
    if lower in {"cd", "crohn", "crohn's disease", "crohns disease"}:
        return "CD"
    if lower in {"uc", "ulcerative colitis"}:
        return "UC"
    if lower in {"control", "hc", "healthy", "nonibd", "non-ibd"}:
        return "Control"
    return text


def sample_counts() -> dict[str, Any]:
    path = ST001000_ROOT / "ST001000_metabolomics" / "ST001000_RawFile_SampleID_mapping.csv"
    out = {
        "source_label_file": str(path) if path.exists() else "",
        "sample_n": 0,
        "qc_passed_sample_n": 0,
        "group_counts": {},
    }
    if not path.exists():
        return out
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "" in df.columns:
        df = df.drop(columns=[""])
    sample_col = "Sample Name" if "Sample Name" in df.columns else df.columns[0]
    group_col = "Diagnosis" if "Diagnosis" in df.columns else ""
    df["sample_id_norm"] = df[sample_col].astype(str)
    df["harmonized_group"] = df[group_col].map(harmonize_group) if group_col else ""
    unique = df.drop_duplicates("sample_id_norm")
    out["sample_n"] = int(unique["sample_id_norm"].nunique())
    out["qc_passed_sample_n"] = int(unique["sample_id_norm"].nunique())
    out["group_counts"] = dict(Counter(unique["harmonized_group"]))
    return out


def read_prior_metrics() -> pd.DataFrame:
    files = sorted(ST001000_ROOT.rglob("ST001000_external_validation_metrics.tsv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return pd.DataFrame()
    df = pd.read_csv(files[0], sep="\t", dtype=str, keep_default_na=False)
    df["source_file"] = str(files[0])
    return df


def matching_stats() -> pd.DataFrame:
    if not MATCHING_FILE.exists():
        return pd.DataFrame(columns=["coefficient_task", "locked_feature_denominator", "matched_feature_count", "matching_proportion", "unmatched_feature_count"])
    matching = pd.read_csv(MATCHING_FILE, dtype=str, keep_default_na=False)
    matching["included_in_projection_bool"] = matching["included_in_projection"].astype(str).str.lower().isin(["true", "1", "yes"])
    rows = []
    for task, sub in matching.groupby("task", dropna=False):
        denom = len(sub)
        matched = int(
            (
                sub["matched_yes_no"].eq("yes")
                & sub["match_confidence"].isin(["high", "medium"])
                & sub["included_in_projection_bool"]
            ).sum()
        )
        rows.append(
            {
                "coefficient_task": task,
                "locked_feature_denominator": denom,
                "matched_feature_count": matched,
                "matching_proportion": matched / denom if denom else np.nan,
                "unmatched_feature_count": int((sub["matched_yes_no"] != "yes").sum()),
            }
        )
    return pd.DataFrame(rows)


def metric_for_task(scores: pd.DataFrame, task: str) -> tuple[str, str, str]:
    sub = scores[scores["task"].eq(task)].copy()
    strict = sub[sub["projection_status"].eq("strict_projected")].copy()
    if strict.empty:
        reasons = sorted(set(str(x) for x in sub["reason_if_not_projected"].dropna().tolist() if str(x)))
        return "", "", ";".join(reasons) or "projection_scores_not_available"
    if roc_auc_score is None or average_precision_score is None:
        return "", "", "sklearn_metrics_unavailable"
    y = pd.to_numeric(strict["true_label"], errors="coerce")
    score_col = "prediction_probability" if strict["prediction_probability"].replace("", np.nan).notna().any() else "linear_predictor"
    s = pd.to_numeric(strict[score_col], errors="coerce")
    valid = y.notna() & s.notna()
    y = y[valid].astype(int)
    s = s[valid].astype(float)
    if len(set(y)) < 2:
        return "", "", "only_one_class_available_after_filtering"
    return str(float(roc_auc_score(y, s))), str(float(average_precision_score(y, s))), ""


def prior_note(prior: pd.DataFrame, task: str) -> str:
    if prior.empty:
        return "No prior local metrics file found."
    sub = prior[prior.get("validation_task", pd.Series(dtype=str)).astype(str).eq(task)]
    if sub.empty:
        return "No prior local metric for this exact task."
    row = sub.iloc[0]
    return (
        f"Prior local metric file reported AUROC={row.get('AUROC','')}, AUPRC={row.get('AUPRC','')}, "
        f"validation_status={row.get('validation_status','')}; this is not treated as independently recomputed."
    )


def build_performance() -> tuple[pd.DataFrame, str, list[str]]:
    counts = sample_counts()
    matching = matching_stats()
    matching_by_task = matching.set_index("coefficient_task").to_dict("index") if not matching.empty else {}
    if PROJECTION_FILE.exists():
        scores = pd.read_csv(PROJECTION_FILE, dtype=str, keep_default_na=False)
    else:
        scores = pd.DataFrame()
    prior = read_prior_metrics()
    rows = []
    classification_reasons = []
    all_strict = True

    for task, task_def in TASKS.items():
        task_scores = scores[scores["task"].eq(task)].copy() if not scores.empty else pd.DataFrame()
        n_pos = int((task_scores["true_label"].astype(str) == "1").sum()) if not task_scores.empty else 0
        n_neg = int((task_scores["true_label"].astype(str) == "0").sum()) if not task_scores.empty else 0
        qc_n = n_pos + n_neg
        coef_task = task_def["coefficient_task"]
        ms = matching_by_task.get(coef_task, {})
        denom = int(ms.get("locked_feature_denominator", 0) or 0)
        matched = int(ms.get("matched_feature_count", 0) or 0)
        prop = ms.get("matching_proportion", "")
        auroc, auprc, reason = metric_for_task(scores, task) if not scores.empty else ("", "", "projection_scores_file_missing")
        if auroc and auprc:
            status = "recomputed_strict"
        else:
            all_strict = False
            status = "not_recomputable"
            classification_reasons.append(f"{task}: {reason}")
        if matched < denom:
            classification_reasons.append(f"{task}: matched {matched}/{denom}; feature matching incomplete")
        rows.append(
            {
                "task": task,
                "positive_class": task_def["positive_class"],
                "negative_class": task_def["negative_class"],
                "n_positive": n_pos,
                "n_negative": n_neg,
                "qc_passed_sample_n": qc_n,
                "locked_feature_denominator": denom,
                "matched_feature_count": matched,
                "matching_proportion": prop,
                "AUROC": auroc,
                "AUPRC": auprc,
                "metric_status": status,
                "reason_if_not_recomputed": reason,
                "source_prediction_file": str(PROJECTION_FILE),
                "source_label_file": counts.get("source_label_file", ""),
                "source_matching_file": str(MATCHING_FILE),
                "notes": (
                    ("nonIBD is harmonized as Control in ST001000. " if "nonIBD" in task else "")
                    + prior_note(prior, task)
                ),
                "recoverable_status": "recoverable" if status == "recomputed_strict" else "not_recoverable",
                "reason_if_not_recoverable": "" if status == "recomputed_strict" else reason,
                "required_missing_files": "" if status == "recomputed_strict" else "model intercept; certified preprocessing/scaling; complete locked projection package",
            }
        )
    perf = pd.DataFrame(rows, columns=PERFORMANCE_COLUMNS)
    if all_strict:
        classification = "Complete metabolomics submodel external validation"
    else:
        # The task's conservative rule explicitly downgrades to summary-level
        # when intercept, scaling, complete matching, or prediction recovery are insufficient.
        classification = "Summary-level external projection only"
    return perf, classification, sorted(set(classification_reasons))


def dataframe_markdown(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df is None or df.empty:
        return "_No rows._"
    small = df.head(max_rows).fillna("")
    lines = [
        "| " + " | ".join(str(c) for c in small.columns) + " |",
        "| " + " | ".join(["---"] * len(small.columns)) + " |",
    ]
    for _, row in small.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("\n", " ").replace("|", "\\|") for c in small.columns) + " |")
    if len(df) > max_rows:
        lines.append(f"\n_Showing first {max_rows} of {len(df)} rows._")
    return "\n".join(lines)


def write_report(perf: pd.DataFrame, classification: str, reasons: list[str]) -> None:
    counts = sample_counts()
    matching = matching_stats()
    intercept_found = False
    preprocessing_certified = False
    projection_generated = bool(PROJECTION_FILE.exists()) and not pd.read_csv(PROJECTION_FILE, nrows=5).empty
    strict_metrics = bool((perf["metric_status"] == "recomputed_strict").all())
    can_claim_complete = classification == "Complete metabolomics submodel external validation"
    recommended = (
        "Use: external evaluation of the metabolomics branch; summary-level external metabolomics projection; "
        "partial feature-level matching recovery; supportive external consistency evidence."
        if not can_claim_complete
        else "The metabolomics submodel was externally validated in ST001000 using a locked projection workflow."
    )
    report = [
        "# ST001000 Summary-Level External Metabolomics Projection Recovery Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Output root: `{OUTPUT_ROOT}`",
        "",
        "## Final Evidence Level",
        "",
        f"- **{classification}**",
        f"- Can manuscript claim full metabolomics-submodel external validation: **{'yes' if can_claim_complete else 'no'}**",
        "",
        "## Sample Counts",
        "",
        f"- ST001000 sample n: `{counts.get('sample_n', 0)}`",
        f"- CD / UC / Control counts: `{counts.get('group_counts', {})}`",
        f"- QC-passed sample n: `{counts.get('qc_passed_sample_n', 0)}`",
        "",
        "## Task Denominators And Matching",
        "",
        dataframe_markdown(matching),
        "",
        "## Projection And Metrics",
        "",
        f"- Model intercept found: `{intercept_found}`",
        f"- Preprocessing/scaling certified: `{preprocessing_certified}`",
        f"- Projection score/status table generated: `{projection_generated}`",
        f"- AUROC/AUPRC strictly recomputed: `{strict_metrics}`",
        "",
        dataframe_markdown(perf),
        "",
        "## Reasons Strict Recovery Failed",
        "",
    ]
    for reason in reasons:
        report.append(f"- {reason}")
    report.extend(
        [
            "",
            "## Recommended Manuscript Wording",
            "",
            recommended,
            "",
            "Avoid any wording that portrays ST001000 as a full validation result, feature-level validation completion, or independently recomputed AUROC/AUPRC.",
            "",
            "## Generated Files",
            "",
            f"- `{OUTPUT_ROOT / 'scripts' / '11_match_st001000_features.py'}`",
            f"- `{OUTPUT_ROOT / 'scripts' / '12_project_st001000_locked_model.py'}`",
            f"- `{OUTPUT_ROOT / 'scripts' / '13_evaluate_st001000_projection.py'}`",
            f"- `{MATCHING_FILE}`",
            f"- `{UNMATCHED_FILE}`",
            f"- `{PROJECTION_FILE}`",
            f"- `{PERFORMANCE_FILE}`",
            f"- `{DATA_DIR / 'st001000_feature_matching_summary.csv'}`",
            f"- `{REPORT_FILE}`",
            f"- `{PROJECT_ROOT / 'scripts' / '11_match_st001000_features.py'}`",
            f"- `{PROJECT_ROOT / 'scripts' / '12_project_st001000_locked_model.py'}`",
            f"- `{PROJECT_ROOT / 'scripts' / '13_evaluate_st001000_projection.py'}`",
            f"- `{PROJECT_ROOT / 'data' / 'external' / 'st001000_feature_matching_table.csv'}`",
            f"- `{PROJECT_ROOT / 'data' / 'external' / 'st001000_unmatched_feature_reasons.csv'}`",
            f"- `{PROJECT_ROOT / 'data' / 'external' / 'st001000_projection_scores.csv'}`",
            f"- `{PROJECT_ROOT / 'data' / 'external' / 'st001000_performance_summary.csv'}`",
        ]
    )
    REPORT_FILE.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    perf, classification, reasons = build_performance()
    perf.to_csv(PERFORMANCE_FILE, index=False, encoding="utf-8-sig")
    write_report(perf, classification, reasons)
    print(f"[{datetime.now().isoformat(timespec='seconds')}] wrote {len(perf)} performance rows")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
