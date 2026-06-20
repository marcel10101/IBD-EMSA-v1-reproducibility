#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

VALID_STATUSES = {
    "scored_strict",
    "not_scoreable_missing_intercept",
    "not_scoreable_missing_scaling",
    "not_scoreable_insufficient_features",
    "not_scoreable_missing_input_matrix",
    "template_only",
}

TASK_ALIASES = {
    "A_IBD_vs_HC": "nonIBD vs IBD",
    "IBD vs HC": "nonIBD vs IBD",
    "nonIBD vs IBD": "nonIBD vs IBD",
    "B_CD_vs_HC": "CD vs nonIBD",
    "CD vs HC": "CD vs nonIBD",
    "CD vs nonIBD": "CD vs nonIBD",
    "C_UC_vs_HC": "UC vs nonIBD",
    "UC vs HC": "UC vs nonIBD",
    "UC vs Control": "UC vs nonIBD",
    "UC vs nonIBD": "UC vs nonIBD",
    "D_CD_vs_UC": "CD vs UC",
    "CD vs UC": "CD vs UC",
    "H_pre_vs_post_treatment": "pre-treatment vs post-treatment",
    "pre-treatment vs post-treatment": "pre-treatment vs post-treatment",
}


def normalize_task(task: str) -> str:
    return TASK_ALIASES.get(task, task)


def read_matrix(path_value: str | None) -> pd.DataFrame | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    df = pd.read_csv(path, sep=sep)
    if "sample_id" not in df.columns:
        first = df.columns[0]
        df = df.rename(columns={first: "sample_id"})
    df["sample_id"] = df["sample_id"].astype(str)
    return df


def sample_frame(metadata: str | None, matrix: pd.DataFrame | None) -> pd.DataFrame:
    if matrix is not None and "sample_id" in matrix.columns:
        return pd.DataFrame({"sample_id": matrix["sample_id"].astype(str).tolist()})
    meta = read_matrix(metadata)
    if meta is not None and "sample_id" in meta.columns:
        return pd.DataFrame({"sample_id": meta["sample_id"].astype(str).tolist()})
    return pd.DataFrame({"sample_id": ["NA"]})


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def empty_rows(samples: pd.DataFrame, task: str, modality: str, status: str, notes: str, n_required=0, n_matched=0, missing=""):
    assert status in VALID_STATUSES
    rows = []
    for sample_id in samples["sample_id"].astype(str):
        rows.append(
            {
                "sample_id": sample_id,
                "model_task": task,
                "modality": modality,
                "n_required_features": n_required,
                "n_matched_features": n_matched,
                "matching_proportion": (n_matched / n_required) if n_required else 0,
                "linear_predictor": pd.NA,
                "prediction_probability": pd.NA,
                "score_status": status,
                "missing_features": missing,
                "notes": notes,
            }
        )
    return pd.DataFrame(rows)


def match_columns(matrix: pd.DataFrame, required: pd.DataFrame, feature_col="feature_id") -> tuple[dict[str, str], list[str]]:
    available = set(matrix.columns)
    mapping = {}
    missing = []
    for _, row in required.iterrows():
        fid = str(row[feature_col])
        fname = str(row.get("feature_name", ""))
        candidates = [fid, fname]
        if fid.startswith("microbiome::"):
            candidates.append(fid.replace("microbiome::", "", 1))
        if fid.startswith("metabolome::"):
            candidates.append(fid.replace("metabolome::", "", 1))
        chosen = next((candidate for candidate in candidates if candidate in available), None)
        if chosen:
            mapping[fid] = chosen
        else:
            missing.append(fid)
    return mapping, missing


def score_linear(matrix: pd.DataFrame | None, samples: pd.DataFrame, coeffs: pd.DataFrame, task: str, modality: str) -> pd.DataFrame:
    if matrix is None:
        return empty_rows(samples, task, modality, "not_scoreable_missing_input_matrix", "Required input matrix is missing.")
    strict = coeffs[(coeffs["model_task"] == task) & (coeffs["modality"] == modality) & (coeffs["recoverable_status"] == "strict_scoreable")].copy()
    if strict.empty:
        return empty_rows(samples, task, modality, "not_scoreable_insufficient_features", "No strict coefficient set is available for this task and modality.")
    n_required = len(strict)
    if strict["intercept"].isna().any():
        return empty_rows(samples, task, modality, "not_scoreable_missing_intercept", "Intercept is not recovered.", n_required=n_required)
    if strict["scaling_mean"].isna().any() or strict["scaling_sd"].isna().any():
        return empty_rows(samples, task, modality, "not_scoreable_missing_scaling", "Scaling mean/sd is not recovered.", n_required=n_required)
    mapping, missing = match_columns(matrix, strict)
    if missing:
        return empty_rows(
            samples,
            task,
            modality,
            "not_scoreable_insufficient_features",
            "Input matrix lacks required model features.",
            n_required=n_required,
            n_matched=len(mapping),
            missing=";".join(missing),
        )
    strict = strict.set_index("feature_id")
    rows = []
    for _, sample in matrix.iterrows():
        sample_id = str(sample["sample_id"])
        values = []
        value_missing = []
        for fid, col in mapping.items():
            value = pd.to_numeric(pd.Series([sample[col]]), errors="coerce").iloc[0]
            if pd.isna(value):
                value_missing.append(fid)
            values.append(value)
        if value_missing:
            rows.append(
                {
                    "sample_id": sample_id,
                    "model_task": task,
                    "modality": modality,
                    "n_required_features": n_required,
                    "n_matched_features": len(mapping),
                    "matching_proportion": len(mapping) / n_required,
                    "linear_predictor": pd.NA,
                    "prediction_probability": pd.NA,
                    "score_status": "not_scoreable_insufficient_features",
                    "missing_features": ";".join(value_missing),
                    "notes": "Required feature values are missing for this sample.",
                }
            )
            continue
        ordered = strict.loc[list(mapping.keys())]
        x = np.asarray(values, dtype=float)
        mean = ordered["scaling_mean"].astype(float).to_numpy()
        sd = ordered["scaling_sd"].astype(float).to_numpy()
        coef = ordered["coefficient"].astype(float).to_numpy()
        if np.any(sd == 0) or np.any(~np.isfinite(sd)):
            status = "not_scoreable_missing_scaling"
            lp = pd.NA
            prob = pd.NA
            notes = "Scaling sd is zero or not finite."
        else:
            z = (x - mean) / sd
            lp = float(ordered["intercept"].astype(float).iloc[0] + np.sum(coef * z))
            prob = sigmoid(lp)
            status = "scored_strict"
            notes = "Strict coefficient/intercept/scaling formula applied."
        rows.append(
            {
                "sample_id": sample_id,
                "model_task": task,
                "modality": modality,
                "n_required_features": n_required,
                "n_matched_features": len(mapping),
                "matching_proportion": len(mapping) / n_required,
                "linear_predictor": lp,
                "prediction_probability": prob,
                "score_status": status,
                "missing_features": "",
                "notes": notes,
            }
        )
    return pd.DataFrame(rows)


def score_late_or_integrated(args, samples: pd.DataFrame, coeff_dir: Path, task: str, modality: str) -> pd.DataFrame:
    path = coeff_dir / "locked_late_fusion_coefficients.csv"
    if not path.exists():
        return empty_rows(samples, task, modality, "not_scoreable_insufficient_features", "Fusion coefficient table is missing.")
    table = pd.read_csv(path)
    if modality == "late_fusion":
        rows = table[(table["model_task"] == task) & (table["fusion_input_type"] == "base_model_probability")].copy()
        matrix = read_matrix(args.microbiome_matrix)
        if matrix is None:
            matrix = read_matrix(args.metabolome_matrix)
        if matrix is None:
            return empty_rows(samples, task, modality, "not_scoreable_missing_input_matrix", "Provide a matrix containing recovered base probability columns.")
        required = rows["fusion_feature"].astype(str).tolist()
        missing = [col for col in required if col not in matrix.columns]
        if missing:
            return empty_rows(samples, task, modality, "not_scoreable_insufficient_features", "Base probability inputs are missing.", len(required), len(required) - len(missing), ";".join(missing))
        out = []
        for _, sample in matrix.iterrows():
            values = pd.to_numeric(sample[required], errors="coerce")
            if values.isna().any():
                out.append(empty_rows(pd.DataFrame({"sample_id": [sample["sample_id"]]}), task, modality, "not_scoreable_insufficient_features", "Base probability values are missing.", len(required), len(required), ";".join(values.index[values.isna()].tolist())).iloc[0].to_dict())
                continue
            intercept = float(rows["intercept"].iloc[0])
            lp = float(intercept + np.sum(values.astype(float).to_numpy() * rows["coefficient"].astype(float).to_numpy()))
            out.append(
                {
                    "sample_id": str(sample["sample_id"]),
                    "model_task": task,
                    "modality": modality,
                    "n_required_features": len(required),
                    "n_matched_features": len(required),
                    "matching_proportion": 1.0,
                    "linear_predictor": lp,
                    "prediction_probability": sigmoid(lp),
                    "score_status": "scored_strict",
                    "missing_features": "",
                    "notes": "Late-fusion logistic formula applied to supplied base probabilities.",
                }
            )
        return pd.DataFrame(out)

    micro = read_matrix(args.microbiome_matrix)
    metab = read_matrix(args.metabolome_matrix)
    if micro is None or metab is None:
        return empty_rows(samples, task, modality, "not_scoreable_missing_input_matrix", "Integrated early fusion requires both microbiome and metabolome matrices.")
    merged = pd.merge(micro, metab, on="sample_id", how="inner", suffixes=("", ""))
    rows = table[(table["model_task"] == task) & (table["fusion_input_type"] == "integrated_early_fusion_feature") & (table["recoverable_status"] == "strict_scoreable_integrated_early_fusion")].copy()
    if rows.empty:
        return empty_rows(samples, task, modality, "not_scoreable_insufficient_features", "No strict integrated early-fusion coefficient set is available.")
    required = rows.rename(columns={"fusion_feature": "feature_id"}).assign(feature_name=lambda d: d["feature_id"].astype(str))
    mapping, missing = match_columns(merged, required, feature_col="feature_id")
    if missing:
        return empty_rows(samples, task, modality, "not_scoreable_insufficient_features", "Required integrated early-fusion features are missing.", len(required), len(mapping), ";".join(missing))
    rows = rows.set_index("fusion_feature").loc[list(mapping.keys())]
    out = []
    for _, sample in merged.iterrows():
        vals = []
        value_missing = []
        for fid, col in mapping.items():
            value = pd.to_numeric(pd.Series([sample[col]]), errors="coerce").iloc[0]
            if pd.isna(value):
                value_missing.append(fid)
            vals.append(value)
        if value_missing:
            out.append(empty_rows(pd.DataFrame({"sample_id": [sample["sample_id"]]}), task, modality, "not_scoreable_insufficient_features", "Required feature values are missing.", len(required), len(mapping), ";".join(value_missing)).iloc[0].to_dict())
            continue
        x = np.asarray(vals, dtype=float)
        mean = rows["scaling_mean"].astype(float).to_numpy()
        sd = rows["scaling_sd"].astype(float).to_numpy()
        coef = rows["coefficient"].astype(float).to_numpy()
        lp = float(rows["intercept"].astype(float).iloc[0] + np.sum(coef * ((x - mean) / sd)))
        out.append(
            {
                "sample_id": str(sample["sample_id"]),
                "model_task": task,
                "modality": modality,
                "n_required_features": len(required),
                "n_matched_features": len(mapping),
                "matching_proportion": len(mapping) / len(required),
                "linear_predictor": lp,
                "prediction_probability": sigmoid(lp),
                "score_status": "scored_strict",
                "missing_features": "",
                "notes": "Integrated early-fusion logistic formula applied.",
            }
        )
    return pd.DataFrame(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score new samples with recovered IBD-EMSA v1 locked coefficient tables when strict inputs are available.")
    parser.add_argument("--microbiome_matrix", default=None, help="CSV/TSV matrix with sample_id and microbiome feature columns.")
    parser.add_argument("--metabolome_matrix", default=None, help="CSV/TSV matrix with sample_id and metabolome feature columns.")
    parser.add_argument("--metadata", default=None, help="Optional CSV/TSV metadata with sample_id.")
    parser.add_argument("--coefficient_dir", required=True, help="Directory containing locked coefficient CSV files.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--task", required=True, help="Model task, e.g. 'nonIBD vs IBD' or 'A_IBD_vs_HC'.")
    parser.add_argument("--modality", required=True, help="microbiome, metabolome, late_fusion, or integrated_early_fusion.")
    args = parser.parse_args()

    task = normalize_task(args.task)
    modality = args.modality
    coeff_dir = Path(args.coefficient_dir)
    matrix = read_matrix(args.microbiome_matrix) if modality == "microbiome" else read_matrix(args.metabolome_matrix) if modality == "metabolome" else None
    samples = sample_frame(args.metadata, matrix)

    if modality in {"microbiome", "metabolome"}:
        table_path = coeff_dir / f"locked_{modality}_coefficients.csv"
        if not table_path.exists():
            out = empty_rows(samples, task, modality, "not_scoreable_insufficient_features", f"{table_path.name} is missing.")
        else:
            coeffs = pd.read_csv(table_path)
            out = score_linear(matrix, samples, coeffs, task, modality)
    elif modality in {"late_fusion", "integrated_early_fusion"}:
        out = score_late_or_integrated(args, samples, coeff_dir, task, modality)
    else:
        out = empty_rows(samples, task, modality, "not_scoreable_insufficient_features", "Unsupported modality.")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    status = sorted(set(out["score_status"].astype(str))) if "score_status" in out.columns else []
    print(json.dumps({"output": str(args.output), "statuses": status, "n_rows": int(len(out))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
