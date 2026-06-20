from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(r"<PROJECT_ROOT>")
ST001000_ROOT = PROJECT_ROOT / "Data" / "外部验证数据" / "代谢组外部队列验证数据" / "ST001000"
PREVIOUS_AUDIT = PROJECT_ROOT / "EMSAv1modlereport" / "ST001000_external_projection_audit_20260619_104920"


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

COEFF_FILE = PROJECT_ROOT / "Trajectory Modeling" / "IBD_EMSA_v1" / "IBD_EMSA_v1_model_coefficients_or_loadings.csv"
FEATURE_LIST_FILE = PROJECT_ROOT / "Trajectory Modeling" / "IBD_EMSA_v1" / "IBD_EMSA_v1_feature_list_metabolomics.csv"

MZ_PPM_TOL = 10.0
MZ_DA_TOL = 0.01
RT_TOL_MIN = 0.30

PLATFORM_BY_ANALYSIS = {
    "AN001878": "HILIC-pos",
    "AN001879": "HILIC-neg",
    "AN001880": "C18-neg",
    "AN001881": "C8-pos",
}

PLATFORM_BY_INTERNAL_PREFIX = {
    "C18n": "C18-neg",
    "C8p": "C8-pos",
    "HILp": "HILIC-pos",
    "HILn": "HILIC-neg",
}

MATCHING_COLUMNS = [
    "task",
    "locked_feature_id",
    "locked_feature_name",
    "locked_HMDB",
    "locked_KEGG",
    "locked_mz",
    "locked_RT",
    "locked_adduct",
    "locked_coefficient",
    "st001000_feature_id",
    "st001000_feature_name",
    "st001000_HMDB",
    "st001000_KEGG",
    "st001000_mz",
    "st001000_RT",
    "st001000_adduct",
    "match_type",
    "match_confidence",
    "matched_yes_no",
    "unmatched_reason",
    "manual_review_yes_no",
    "included_in_projection",
    "source_locked_model_file",
    "source_st001000_file",
    "notes",
]

UNMATCHED_COLUMNS = [
    "task",
    "locked_feature_id",
    "locked_feature_name",
    "unmatched_reason",
    "identifier_available_in_locked_model",
    "identifier_available_in_st001000",
    "candidate_st001000_features_checked",
    "manual_review_needed",
    "notes",
]


def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return ""
    text = unicodedata.normalize("NFKD", text)
    for src, dst in {
        "α": "alpha",
        "β": "beta",
        "γ": "gamma",
        "δ": "delta",
        "ω": "omega",
    }.items():
        text = text.replace(src, dst).replace(src.upper(), dst)
    text = re.sub(r"\[[^\]]*(?:m\+h|m-h|adduct|pos|neg)[^\]]*\]", "", text, flags=re.I)
    text = re.sub(r"\([^)]*(?:m\+h|m-h|adduct|pos|neg)[^)]*\)", "", text, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def parse_mz_rt(value: Any) -> tuple[float | None, float | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)_([0-9]+(?:\.[0-9]+)?)\s*$", text)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def number_or_none(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        val = float(value)
        if math.isnan(val):
            return None
        return val
    except Exception:
        return None


def platform_from_internal_id(feature_id: str) -> str:
    for prefix, platform in PLATFORM_BY_INTERNAL_PREFIX.items():
        if str(feature_id).startswith(prefix + "_") or str(feature_id).startswith(prefix):
            return platform
    return ""


def mz_tolerance(mz: float) -> float:
    return max(MZ_DA_TOL, abs(mz) * MZ_PPM_TOL / 1_000_000.0)


def latest_internal_metadata_file() -> Path | None:
    files = sorted(ST001000_ROOT.rglob("internal_locked_metabolomics_feature_metadata.tsv"))
    if files:
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return None


def load_locked_features() -> pd.DataFrame:
    if not COEFF_FILE.exists():
        return pd.DataFrame()
    coef = pd.read_csv(COEFF_FILE, dtype=str, keep_default_na=False)
    if "modality" in coef.columns:
        coef = coef[coef["modality"].str.lower().eq("metabolome")].copy()
    coef["locked_feature_id"] = coef["feature"].astype(str)
    coef["locked_coefficient"] = coef["coefficient"]

    feature_names: dict[str, str] = {}
    if FEATURE_LIST_FILE.exists():
        fl = pd.read_csv(FEATURE_LIST_FILE, dtype=str, keep_default_na=False)
        if {"feature_id", "feature_name_or_annotation"}.issubset(fl.columns):
            feature_names = fl.set_index("feature_id")["feature_name_or_annotation"].to_dict()

    meta_path = latest_internal_metadata_file()
    meta_by_id: dict[str, dict[str, Any]] = {}
    if meta_path and meta_path.exists():
        meta = pd.read_csv(meta_path, sep="\t", dtype=str, keep_default_na=False)
        if "internal_feature_id" in meta.columns:
            meta_by_id = meta.set_index("internal_feature_id").to_dict("index")

    rows = []
    for _, rec in coef.iterrows():
        fid = str(rec.get("locked_feature_id", ""))
        meta = meta_by_id.get(fid, {})
        name = str(meta.get("internal_feature_name", "") or feature_names.get(fid, ""))
        rows.append(
            {
                "task": rec.get("task", ""),
                "locked_feature_id": fid,
                "locked_feature_name": name,
                "locked_HMDB": meta.get("internal_hmdb", ""),
                "locked_KEGG": "",
                "locked_mz": meta.get("internal_mz", ""),
                "locked_RT": meta.get("internal_rt", ""),
                "locked_adduct": "",
                "locked_coefficient": rec.get("locked_coefficient", ""),
                "source_locked_model_file": str(COEFF_FILE),
                "interpretation_limit": rec.get("interpretation_limit", ""),
                "model_artifact_role": rec.get("model_artifact_role", ""),
            }
        )
    return pd.DataFrame(rows)


def read_st001000_features() -> pd.DataFrame:
    rows = []
    result_files = sorted((ST001000_ROOT / "ST001000_metabolomics").glob("ST001000_AN*_Results.txt"))
    for path in result_files:
        analysis_match = re.search(r"(AN\d+)", path.name)
        analysis_id = analysis_match.group(1) if analysis_match else path.stem
        platform = PLATFORM_BY_ANALYSIS.get(analysis_id, "")
        raw = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
        id_cols = [c for c in ["Compound", "FeatureID"] if c in raw.columns]
        if not id_cols:
            continue
        factor_mask = raw[id_cols[0]].astype(str).eq("Factors")
        for idx, rec in raw.loc[~factor_mask].iterrows():
            compound = str(rec.get("Compound", "")).strip()
            feature_id = str(rec.get("FeatureID", "")).strip() if "FeatureID" in rec.index else ""
            mz, rt = parse_mz_rt(compound)
            rows.append(
                {
                    "analysis_id": analysis_id,
                    "platform_method": platform,
                    "st001000_feature_id": feature_id or compound,
                    "st001000_feature_name": compound,
                    "st001000_HMDB": "",
                    "st001000_KEGG": "",
                    "st001000_mz": mz,
                    "st001000_RT": rt,
                    "st001000_adduct": "",
                    "source_st001000_file": str(path),
                    "row_index": idx,
                    "id_norm": normalize_name(feature_id or compound),
                    "name_norm": normalize_name(compound),
                }
            )
    return pd.DataFrame(rows)


def identifier_available_locked(row: pd.Series) -> str:
    fields = []
    for label, col in [
        ("feature_id", "locked_feature_id"),
        ("name", "locked_feature_name"),
        ("HMDB", "locked_HMDB"),
        ("KEGG", "locked_KEGG"),
        ("mz", "locked_mz"),
        ("RT", "locked_RT"),
        ("adduct", "locked_adduct"),
    ]:
        if str(row.get(col, "")).strip():
            fields.append(label)
    return ";".join(fields)


def choose_unique(candidates: pd.DataFrame) -> tuple[pd.Series | None, str, str]:
    if candidates.empty:
        return None, "no", "no_candidate"
    if len(candidates) == 1:
        return candidates.iloc[0], "yes", "unique_candidate"
    ordered = candidates.sort_values(["match_distance", "st001000_feature_id"], kind="mergesort")
    if len(ordered) > 1 and float(ordered["match_distance"].iloc[0]) < float(ordered["match_distance"].iloc[1]) - 1e-12:
        return ordered.iloc[0], "yes", f"nearest_unique_among_{len(candidates)}"
    return ordered.iloc[0], "ambiguous", f"ambiguous_{len(candidates)}_candidates"


def match_feature(row: pd.Series, st_features: pd.DataFrame) -> dict[str, Any]:
    base = {
        "st001000_feature_id": "",
        "st001000_feature_name": "",
        "st001000_HMDB": "",
        "st001000_KEGG": "",
        "st001000_mz": "",
        "st001000_RT": "",
        "st001000_adduct": "",
        "match_type": "unmatched",
        "match_confidence": "not_applicable",
        "matched_yes_no": "no",
        "unmatched_reason": "",
        "manual_review_yes_no": "no",
        "included_in_projection": False,
        "source_st001000_file": "",
        "notes": "",
        "candidate_st001000_features_checked": 0,
    }
    if st_features.empty:
        return {
            **base,
            "match_type": "not_evaluable",
            "matched_yes_no": "not_evaluable",
            "unmatched_reason": "source_file_missing",
            "notes": "ST001000 result matrices not found.",
        }

    fid = str(row.get("locked_feature_id", "")).strip()
    name = str(row.get("locked_feature_name", "")).strip()
    fid_norm = normalize_name(fid)
    name_norm = normalize_name(name)
    locked_mz = number_or_none(row.get("locked_mz", ""))
    locked_rt = number_or_none(row.get("locked_RT", ""))
    platform = platform_from_internal_id(fid)

    candidates = st_features[(st_features["id_norm"].eq(fid_norm)) | (st_features["name_norm"].eq(fid_norm))].copy()
    if not candidates.empty:
        candidates["match_distance"] = 0.0
        selected, yes_no, note = choose_unique(candidates)
        return finalize_match(base, selected, "exact_name", "high" if yes_no == "yes" else "low", yes_no, note)

    if name_norm:
        candidates = st_features[(st_features["id_norm"].eq(name_norm)) | (st_features["name_norm"].eq(name_norm))].copy()
        if not candidates.empty:
            candidates["match_distance"] = 0.0
            selected, yes_no, note = choose_unique(candidates)
            return finalize_match(base, selected, "exact_name", "medium" if yes_no == "yes" else "low", yes_no, note)

    if locked_mz is None or locked_rt is None:
        return {
            **base,
            "unmatched_reason": "mz_rt_missing",
            "candidate_st001000_features_checked": int(len(st_features[st_features["platform_method"].eq(platform)])) if platform else 0,
            "notes": "Locked feature lacks recoverable m/z or RT for local m/z/RT matching.",
        }

    same_platform = st_features[st_features["platform_method"].eq(platform)].copy() if platform else pd.DataFrame()
    if same_platform.empty:
        return {
            **base,
            "unmatched_reason": "feature_absent_in_ST001000",
            "candidate_st001000_features_checked": 0,
            "notes": f"No ST001000 features found for inferred platform {platform}.",
        }
    same_platform["mz_num"] = pd.to_numeric(same_platform["st001000_mz"], errors="coerce")
    same_platform["rt_num"] = pd.to_numeric(same_platform["st001000_RT"], errors="coerce")
    tol = mz_tolerance(locked_mz)
    candidates = same_platform[
        same_platform["mz_num"].notna()
        & same_platform["rt_num"].notna()
        & ((same_platform["mz_num"] - locked_mz).abs() <= tol)
        & ((same_platform["rt_num"] - locked_rt).abs() <= RT_TOL_MIN)
    ].copy()
    if candidates.empty:
        return {
            **base,
            "unmatched_reason": "feature_absent_in_ST001000",
            "candidate_st001000_features_checked": int(len(same_platform)),
            "notes": f"No same-platform candidate within mz_tolerance=max({MZ_PPM_TOL} ppm,{MZ_DA_TOL} Da) and rt_tolerance={RT_TOL_MIN} min.",
        }
    candidates["match_distance"] = (
        (candidates["mz_num"] - locked_mz).abs() / tol + (candidates["rt_num"] - locked_rt).abs() / RT_TOL_MIN
    )
    selected, yes_no, note = choose_unique(candidates)
    confidence = "medium" if yes_no == "yes" else "low"
    return finalize_match(
        base,
        selected,
        "m/z_RT_adduct",
        confidence,
        yes_no,
        f"{note}; same-platform m/z/RT match; adduct unavailable locally; mz_tolerance_ppm={MZ_PPM_TOL}; rt_tolerance_min={RT_TOL_MIN}",
    )


def finalize_match(
    base: dict[str, Any],
    selected: pd.Series | None,
    match_type: str,
    confidence: str,
    yes_no: str,
    note: str,
) -> dict[str, Any]:
    if selected is None:
        return {**base, "unmatched_reason": "feature_absent_in_ST001000", "notes": note}
    matched = yes_no == "yes"
    return {
        **base,
        "st001000_feature_id": selected.get("st001000_feature_id", ""),
        "st001000_feature_name": selected.get("st001000_feature_name", ""),
        "st001000_HMDB": selected.get("st001000_HMDB", ""),
        "st001000_KEGG": selected.get("st001000_KEGG", ""),
        "st001000_mz": selected.get("st001000_mz", ""),
        "st001000_RT": selected.get("st001000_RT", ""),
        "st001000_adduct": selected.get("st001000_adduct", ""),
        "match_type": match_type if matched else "ambiguous",
        "match_confidence": confidence,
        "matched_yes_no": yes_no,
        "unmatched_reason": "" if matched else "ambiguous_duplicate_candidates",
        "manual_review_yes_no": "no" if matched else "yes",
        "included_in_projection": bool(matched and confidence in {"high", "medium"}),
        "source_st001000_file": selected.get("source_st001000_file", ""),
        "notes": note,
        "candidate_st001000_features_checked": 1 if matched else 0,
    }


def build_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    locked = load_locked_features()
    st_features = read_st001000_features()
    match_rows = []
    unmatched_rows = []
    for _, row in locked.iterrows():
        match = match_feature(row, st_features)
        out = {
            "task": row.get("task", ""),
            "locked_feature_id": row.get("locked_feature_id", ""),
            "locked_feature_name": row.get("locked_feature_name", ""),
            "locked_HMDB": row.get("locked_HMDB", ""),
            "locked_KEGG": row.get("locked_KEGG", ""),
            "locked_mz": row.get("locked_mz", ""),
            "locked_RT": row.get("locked_RT", ""),
            "locked_adduct": row.get("locked_adduct", ""),
            "locked_coefficient": row.get("locked_coefficient", ""),
            **{k: match.get(k, "") for k in MATCHING_COLUMNS if k.startswith("st001000_")},
            "match_type": match.get("match_type", ""),
            "match_confidence": match.get("match_confidence", ""),
            "matched_yes_no": match.get("matched_yes_no", ""),
            "unmatched_reason": match.get("unmatched_reason", ""),
            "manual_review_yes_no": match.get("manual_review_yes_no", "no"),
            "included_in_projection": bool(match.get("included_in_projection", False)),
            "source_locked_model_file": row.get("source_locked_model_file", ""),
            "source_st001000_file": match.get("source_st001000_file", ""),
            "notes": match.get("notes", ""),
        }
        match_rows.append(out)
        if out["matched_yes_no"] != "yes":
            unmatched_rows.append(
                {
                    "task": out["task"],
                    "locked_feature_id": out["locked_feature_id"],
                    "locked_feature_name": out["locked_feature_name"],
                    "unmatched_reason": out["unmatched_reason"] or "not_evaluable_without_original_run_package",
                    "identifier_available_in_locked_model": identifier_available_locked(row),
                    "identifier_available_in_st001000": "feature_id/name/mz/RT; no local HMDB/KEGG/adduct columns",
                    "candidate_st001000_features_checked": match.get("candidate_st001000_features_checked", ""),
                    "manual_review_needed": out["manual_review_yes_no"],
                    "notes": out["notes"],
                }
            )

    matching = pd.DataFrame(match_rows, columns=MATCHING_COLUMNS)
    unmatched = pd.DataFrame(unmatched_rows, columns=UNMATCHED_COLUMNS)
    summary_rows = []
    for task, sub in matching.groupby("task", dropna=False):
        denom = len(sub)
        matched_n = int(
            (
                sub["matched_yes_no"].eq("yes")
                & sub["match_confidence"].isin(["high", "medium"])
                & sub["included_in_projection"].astype(bool)
            ).sum()
        )
        summary_rows.append(
            {
                "task": task,
                "locked_feature_denominator": denom,
                "matched_feature_count": matched_n,
                "matching_proportion": matched_n / denom if denom else np.nan,
                "unmatched_feature_count": int((sub["matched_yes_no"] != "yes").sum()),
                "recoverable_status": "feature_matching_recomputed_from_local_files",
                "reason_if_not_recoverable": "",
                "required_missing_files": "model intercept and certified preprocessing/scaling still required for strict projection",
            }
        )
    summary = pd.DataFrame(summary_rows)
    return matching, unmatched, summary


def main() -> None:
    matching, unmatched, summary = build_tables()
    matching.to_csv(DATA_DIR / "st001000_feature_matching_table.csv", index=False, encoding="utf-8-sig")
    unmatched.to_csv(DATA_DIR / "st001000_unmatched_feature_reasons.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(DATA_DIR / "st001000_feature_matching_summary.csv", index=False, encoding="utf-8-sig")
    print(f"[{datetime.now().isoformat(timespec='seconds')}] wrote {len(matching)} feature matching rows")
    print(f"Output: {DATA_DIR}")


if __name__ == "__main__":
    main()
