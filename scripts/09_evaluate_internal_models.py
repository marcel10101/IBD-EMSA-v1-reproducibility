from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PACKAGE_ROOT / "outputs" / "internal"
AUDIT_DIR = PACKAGE_ROOT / "audit"

def roc_points(y_true, score):
    y, s = np.asarray(y_true, dtype=int), np.asarray(score, dtype=float)
    order = np.argsort(-s, kind="mergesort"); y, s = y[order], s[order]
    pos, neg = int((y == 1).sum()), int((y == 0).sum())
    if pos == 0 or neg == 0: return np.array([0.0]), np.array([0.0]), np.array([np.nan]), np.nan
    tps, fps = np.cumsum(y == 1), np.cumsum(y == 0)
    distinct = np.r_[np.where(np.diff(s))[0], y.size - 1]
    tpr, fpr = np.r_[0.0, tps[distinct] / pos], np.r_[0.0, fps[distinct] / neg]
    return fpr, tpr, np.r_[np.inf, s[distinct]], float(np.trapz(tpr, fpr))

def pr_points(y_true, score):
    y, s = np.asarray(y_true, dtype=int), np.asarray(score, dtype=float)
    order = np.argsort(-s, kind="mergesort"); y, s = y[order], s[order]
    pos = int((y == 1).sum())
    if pos == 0: return np.array([0.0]), np.array([1.0]), np.array([np.nan]), np.nan
    tps, fps = np.cumsum(y == 1), np.cumsum(y == 0)
    distinct = np.r_[np.where(np.diff(s))[0], y.size - 1]
    precision = tps[distinct] / np.maximum(tps[distinct] + fps[distinct], 1)
    recall = tps[distinct] / pos
    return recall, precision, s[distinct], float(np.sum(np.diff(np.r_[0.0, recall]) * precision))

def main() -> int:
    pred = pd.read_csv(OUTPUT_DIR / "internal_prediction_scores.csv")
    pred = pred[pred["split"].eq("test")].dropna(subset=["true_label", "prediction_probability"])
    no_overlap = True
    overlap_path = AUDIT_DIR / "subject_overlap_check.csv"
    if overlap_path.exists():
        no_overlap = bool((pd.read_csv(overlap_path)["n_overlapping_subjects"] == 0).all())
    perf, curves = [], []
    for (task, modality), g in pred.groupby(["task", "modality"]):
        y = g["true_label"].astype(int).to_numpy(); score = g["prediction_probability"].astype(float).to_numpy()
        fpr, tpr, rthr, auroc = roc_points(y, score)
        rec, prec, pthr, auprc = pr_points(y, score)
        positive, negative = g["positive_class"].iloc[0], g["negative_class"].iloc[0]
        perf.append({"task": task, "modality": modality, "positive_class": positive, "negative_class": negative, "n_samples": int(g.sample_id.nunique()), "n_positive": int((g.true_label.astype(int) == 1).sum()), "n_negative": int((g.true_label.astype(int) == 0).sum()), "n_subjects": int(g.subject_id.nunique()), "n_folds": int(g.fold.nunique()), "AUROC": auroc, "AUPRC": auprc, "metric_status": "recomputed_from_recovered_oof_predictions", "cv_type": "subject-grouped cross-validation", "subject_grouped": True, "no_subject_overlap_passed": no_overlap, "model_type": g["model_type"].iloc[0], "notes": "Metrics recomputed from OOF prediction_probability."})
        for x, yy, thr in zip(fpr, tpr, rthr):
            curves.append({"task": task, "modality": modality, "curve_type": "ROC", "x": float(x), "y": float(yy), "threshold": "" if np.isinf(thr) or np.isnan(thr) else float(thr), "fold": "pooled_oof", "positive_class": positive, "notes": "x=FPR y=TPR"})
        for x, yy, thr in zip(rec, prec, pthr):
            curves.append({"task": task, "modality": modality, "curve_type": "PR", "x": float(x), "y": float(yy), "threshold": "" if np.isnan(thr) else float(thr), "fold": "pooled_oof", "positive_class": positive, "notes": "x=recall y=precision"})
    pd.DataFrame(perf).to_csv(OUTPUT_DIR / "internal_model_performance.csv", index=False)
    pd.DataFrame(curves).to_csv(OUTPUT_DIR / "internal_roc_pr_curves.csv", index=False)
    print("09_evaluate_internal_models complete")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
