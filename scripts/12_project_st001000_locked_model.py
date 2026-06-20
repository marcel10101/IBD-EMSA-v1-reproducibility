from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(r"<PROJECT_ROOT>")
ST001000_ROOT = PROJECT_ROOT / "Data" / "外部验证数据" / "代谢组外部队列验证数据" / "ST001000"
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
DATA_DIR.mkdir(parents=True, exist_ok=True)

MATCHING_FILE = DATA_DIR / "st001000_feature_matching_table.csv"
PROJECTION_FILE = DATA_DIR / "st001000_projection_scores.csv"

TASKS = {
    "UC vs Control": {
        "coefficient_task": "UC vs nonIBD",
        "positive_class": "UC",
        "negative_class": "Control",
        "positive_groups": {"UC"},
        "negative_groups": {"Control"},
        "notes": "nonIBD harmonized as Control for ST001000.",
    },
    "CD vs Control": {
        "coefficient_task": "CD vs nonIBD",
        "positive_class": "CD",
        "negative_class": "Control",
        "positive_groups": {"CD"},
        "negative_groups": {"Control"},
        "notes": "nonIBD harmonized as Control for ST001000.",
    },
    "IBD vs Control": {
        "coefficient_task": "nonIBD vs IBD",
        "positive_class": "IBD",
        "negative_class": "Control",
        "positive_groups": {"CD", "UC"},
        "negative_groups": {"Control"},
        "notes": "IBD harmonized as CD or UC; nonIBD harmonized as Control.",
    },
    "CD vs UC": {
        "coefficient_task": "CD vs UC",
        "positive_class": "CD",
        "negative_class": "UC",
        "positive_groups": {"CD"},
        "negative_groups": {"UC"},
        "notes": "",
    },
    "UC vs nonIBD": {
        "coefficient_task": "UC vs nonIBD",
        "positive_class": "UC",
        "negative_class": "nonIBD",
        "positive_groups": {"UC"},
        "negative_groups": {"Control"},
        "notes": "nonIBD harmonized as Control for ST001000.",
    },
    "CD vs nonIBD": {
        "coefficient_task": "CD vs nonIBD",
        "positive_class": "CD",
        "negative_class": "nonIBD",
        "positive_groups": {"CD"},
        "negative_groups": {"Control"},
        "notes": "nonIBD harmonized as Control for ST001000.",
    },
    "nonIBD vs IBD": {
        "coefficient_task": "nonIBD vs IBD",
        "positive_class": "IBD",
        "negative_class": "nonIBD",
        "positive_groups": {"CD", "UC"},
        "negative_groups": {"Control"},
        "notes": "IBD harmonized as CD or UC; nonIBD harmonized as Control.",
    },
}

OUTPUT_COLUMNS = [
    "task",
    "sample_id",
    "raw_file",
    "original_group_label",
    "harmonized_group_label",
    "true_label",
    "included_in_projection",
    "n_matched_features_used",
    "locked_feature_denominator",
    "matching_proportion",
    "linear_predictor",
    "prediction_probability",
    "projection_status",
    "reason_if_not_projected",
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


def load_sample_map() -> pd.DataFrame:
    path = ST001000_ROOT / "ST001000_metabolomics" / "ST001000_RawFile_SampleID_mapping.csv"
    if not path.exists():
        return pd.DataFrame()
    mapping = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "" in mapping.columns:
        mapping = mapping.drop(columns=[""])
    sample_col = "Sample Name" if "Sample Name" in mapping.columns else mapping.columns[0]
    group_col = "Diagnosis" if "Diagnosis" in mapping.columns else ""
    raw_cols = [c for c in ["C8-POS", "C18-NEG", "HILIC-POS", "HILIC-NEG"] if c in mapping.columns]
    rows = []
    for _, rec in mapping.iterrows():
        sid = str(rec.get(sample_col, "")).strip()
        group = str(rec.get(group_col, "")).strip() if group_col else ""
        rows.append(
            {
                "sample_id": sid,
                "raw_file": ";".join(str(rec.get(c, "")).strip() for c in raw_cols if str(rec.get(c, "")).strip()),
                "original_group_label": group,
                "harmonized_group_label": harmonize_group(group),
                "source_label_file": str(path),
            }
        )
    return pd.DataFrame(rows)


def model_intercept_available() -> tuple[bool, str]:
    if not COEFF_FILE.exists():
        return False, "locked_coefficient_file_missing"
    coef = pd.read_csv(COEFF_FILE, dtype=str, keep_default_na=False)
    lower_cols = {c.lower(): c for c in coef.columns}
    intercept_cols = [c for c in coef.columns if "intercept" in c.lower()]
    if intercept_cols:
        non_empty = coef[intercept_cols].replace("", np.nan).dropna(how="all")
        if not non_empty.empty:
            return True, f"intercept found in columns {intercept_cols}"
    feature_col = lower_cols.get("feature")
    if feature_col:
        intercept_rows = coef[coef[feature_col].astype(str).str.lower().isin(["intercept", "(intercept)", "bias"])]
        if not intercept_rows.empty:
            return True, "intercept row found in coefficient file"
    return False, "model_intercept_missing"


def preprocessing_certified() -> tuple[bool, str]:
    if not PREPROCESSING_FILE.exists():
        return False, "preprocessing_scaling_file_missing"
    try:
        params = json.loads(PREPROCESSING_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"preprocessing_scaling_file_unreadable: {exc}"
    text = json.dumps(params, ensure_ascii=False).lower()
    if "external" in text and ("scaler" in text or "mean" in text or "standard" in text):
        return True, "external-compatible preprocessing/scaling appears documented"
    return False, "preprocessing_scaling_not_certified"


def matching_summary(matching: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if matching.empty:
        return pd.DataFrame(columns=["coefficient_task", "locked_feature_denominator", "matched_feature_count", "matching_proportion"])
    for task, sub in matching.groupby("task", dropna=False):
        denom = len(sub)
        matched = int(
            (
                sub["matched_yes_no"].eq("yes")
                & sub["match_confidence"].isin(["high", "medium"])
                & sub["included_in_projection"].astype(bool)
            ).sum()
        )
        rows.append(
            {
                "coefficient_task": task,
                "locked_feature_denominator": denom,
                "matched_feature_count": matched,
                "matching_proportion": matched / denom if denom else np.nan,
            }
        )
    return pd.DataFrame(rows)


def projection_block_reason(intercept_ok: bool, intercept_reason: str, preprocessing_ok: bool, preprocessing_reason: str, matched: int, denom: int) -> str:
    reasons = []
    if not intercept_ok:
        reasons.append(intercept_reason)
    if not preprocessing_ok:
        reasons.append(preprocessing_reason)
    if matched == 0:
        reasons.append("no_matched_features")
    if matched < denom:
        reasons.append("incomplete_feature_matching")
    if not reasons:
        return ""
    return ";".join(reasons)


def true_label_for_group(group: str, task_def: dict[str, Any]) -> str:
    if group in task_def["positive_groups"]:
        return "1"
    if group in task_def["negative_groups"]:
        return "0"
    return ""


def build_projection_scores() -> pd.DataFrame:
    sample_map = load_sample_map()
    if MATCHING_FILE.exists():
        matching = pd.read_csv(MATCHING_FILE, dtype=str, keep_default_na=False)
        if "included_in_projection" in matching.columns:
            matching["included_in_projection"] = matching["included_in_projection"].astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        matching = pd.DataFrame()
    ms = matching_summary(matching)
    by_task = ms.set_index("coefficient_task").to_dict("index") if not ms.empty else {}
    intercept_ok, intercept_reason = model_intercept_available()
    preprocessing_ok, preprocessing_reason = preprocessing_certified()
    rows = []

    if sample_map.empty:
        rows.append(
            {
                "task": "",
                "sample_id": "",
                "raw_file": "",
                "original_group_label": "",
                "harmonized_group_label": "",
                "true_label": "",
                "included_in_projection": False,
                "n_matched_features_used": 0,
                "locked_feature_denominator": 0,
                "matching_proportion": "",
                "linear_predictor": "",
                "prediction_probability": "",
                "projection_status": "not_projected",
                "reason_if_not_projected": "sample_mapping_missing",
                "notes": "Projection cannot run without ST001000 sample labels.",
                "recoverable_status": "not_recoverable",
                "reason_if_not_recoverable": "sample_mapping_missing",
                "required_missing_files": "ST001000_RawFile_SampleID_mapping.csv",
            }
        )
        return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)

    for validation_task, task_def in TASKS.items():
        coef_task = task_def["coefficient_task"]
        stats = by_task.get(coef_task, {})
        denom = int(stats.get("locked_feature_denominator", 0) or 0)
        matched = int(stats.get("matched_feature_count", 0) or 0)
        prop = stats.get("matching_proportion", "")
        reason = projection_block_reason(intercept_ok, intercept_reason, preprocessing_ok, preprocessing_reason, matched, denom)
        strict_ok = not reason
        for _, rec in sample_map.iterrows():
            group = rec.get("harmonized_group_label", "")
            true_label = true_label_for_group(group, task_def)
            if true_label == "":
                continue
            rows.append(
                {
                    "task": validation_task,
                    "sample_id": rec.get("sample_id", ""),
                    "raw_file": rec.get("raw_file", ""),
                    "original_group_label": rec.get("original_group_label", ""),
                    "harmonized_group_label": group,
                    "true_label": true_label,
                    "included_in_projection": bool(strict_ok),
                    "n_matched_features_used": matched,
                    "locked_feature_denominator": denom,
                    "matching_proportion": prop,
                    "linear_predictor": "",
                    "prediction_probability": "",
                    "projection_status": "strict_projected" if strict_ok else "not_projected",
                    "reason_if_not_projected": "" if strict_ok else reason,
                    "notes": task_def["notes"] + (" Strict projection blocked; no 0 intercept substitution was used." if reason else ""),
                    "recoverable_status": "recoverable" if strict_ok else "not_recoverable",
                    "reason_if_not_recoverable": "" if strict_ok else reason,
                    "required_missing_files": "" if strict_ok else "model intercept; certified preprocessing/scaling; complete feature matching",
                }
            )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def main() -> None:
    scores = build_projection_scores()
    scores.to_csv(PROJECTION_FILE, index=False, encoding="utf-8-sig")
    print(f"[{datetime.now().isoformat(timespec='seconds')}] wrote {len(scores)} projection score/status rows")
    print(f"Output: {PROJECTION_FILE}")


if __name__ == "__main__":
    main()
