from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PACKAGE_ROOT / "data" / "internal"
OUTPUT_DIR = PACKAGE_ROOT / "outputs" / "internal"
AUDIT_DIR = PACKAGE_ROOT / "audit"
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

def main() -> int:
    ap = argparse.ArgumentParser(description="Reconstruct subject-grouped CV splits from recovered OOF predictions.")
    ap.add_argument("--prediction-scores", default=str(OUTPUT_DIR / "internal_prediction_scores.csv"))
    args = ap.parse_args()
    pred = pd.read_csv(args.prediction_scores)
    pred = pred[pred["split"].eq("test")].copy()
    meta = pd.read_csv(DATA_DIR / "hmp2_sample_metadata.csv").drop_duplicates("sample_id").set_index("sample_id")
    avail_micro = set(pred.loc[pred.modality.eq("microbiome"), "sample_id"])
    avail_met = set(pred.loc[pred.modality.eq("metabolome"), "sample_id"])
    avail_fusion = set(pred.loc[pred.modality.eq("paired_late_fusion"), "sample_id"])
    split_rows, checks = [], []
    for task in sorted(pred["task"].dropna().unique()):
        task_pred = pred[pred.task.eq(task)]
        universe = task_pred[["sample_id", "subject_id", "true_label"]].drop_duplicates("sample_id")
        for fold in sorted(task_pred["fold"].dropna().unique()):
            test_df = task_pred[task_pred.fold.eq(fold)][["sample_id", "subject_id"]].drop_duplicates()
            test_samples, test_subjects = set(test_df.sample_id), set(test_df.subject_id)
            train = universe[~universe.subject_id.isin(test_subjects)]
            test = universe[universe.sample_id.isin(test_samples)]
            overlap = sorted(set(train.subject_id) & set(test.subject_id))
            for split, frame in [("train", train), ("test", test)]:
                for _, row in frame.iterrows():
                    sid = row.sample_id
                    group = meta.loc[sid, "group_label"] if sid in meta.index and "group_label" in meta.columns else ""
                    split_rows.append({"task": task, "fold": int(fold), "sample_id": sid, "subject_id": row.subject_id, "group_label": group, "binary_label": int(row.true_label), "split": split, "modality_available_microbiome": sid in avail_micro, "modality_available_metabolome": sid in avail_met, "included_in_microbiome_model": sid in avail_micro, "included_in_metabolome_model": sid in avail_met, "included_in_paired_late_fusion": sid in avail_fusion})
            checks.append({"task": task, "fold": int(fold), "n_train_samples": int(train.sample_id.nunique()), "n_test_samples": int(test.sample_id.nunique()), "n_train_subjects": int(train.subject_id.nunique()), "n_test_subjects": int(test.subject_id.nunique()), "n_overlapping_subjects": len(overlap), "overlap_subject_ids": ";".join(overlap), "pass_no_subject_overlap": len(overlap) == 0, "notes": "Reconstructed from recovered OOF test-fold membership."})
    splits, check = pd.DataFrame(split_rows), pd.DataFrame(checks)
    splits.to_csv(DATA_DIR / "internal_cv_splits.csv", index=False)
    check.to_csv(AUDIT_DIR / "subject_overlap_check.csv", index=False)
    if (check["n_overlapping_subjects"] > 0).any():
        raise SystemExit("Subject overlap detected.")
    print("08_grouped_cross_validation complete")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
