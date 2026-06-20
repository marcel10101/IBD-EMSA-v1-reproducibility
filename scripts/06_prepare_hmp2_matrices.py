from __future__ import annotations
import argparse, csv, hashlib, os
from pathlib import Path
import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PACKAGE_ROOT / "data" / "internal"
AUDIT_DIR = PACKAGE_ROOT / "audit"
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

def find_one(root: Path, pattern: str) -> Path | None:
    hits = sorted(root.rglob(pattern)) if root.exists() else []
    return hits[0] if hits else None

def copy_matrix(src: Path | None, dst: Path, modality: str) -> tuple[int, int, str]:
    if src is None or not src.exists():
        if dst.exists() and dst.stat().st_size:
            return -1, len(pd.read_csv(dst, nrows=1).columns), "existing_package_matrix_retained"
        pd.DataFrame([{"sample_id": "requires_original_HMP2_IBDMDB_data", "matrix_status": "not_recoverable_from_current_archive", "modality": modality, "notes": "Provide original processed matrix and rerun."}]).to_csv(dst, index=False)
        return 1, 4, "template_only"
    with src.open("r", encoding="utf-8", newline="") as fin, dst.open("w", encoding="utf-8", newline="") as fout:
        reader, writer = csv.reader(fin), csv.writer(fout)
        header = next(reader); header[0] = "sample_id"; writer.writerow(header)
        n = 0
        for row in reader:
            writer.writerow(row); n += 1
    return n, len(header), "recovered_processed_matrix"

def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare HMP2/IBDMDB processed matrices.")
    ap.add_argument("--source-root", default=os.environ.get("HMP2_SOURCE_ROOT", str(PACKAGE_ROOT)))
    args = ap.parse_args()
    root = Path(args.source_root)
    rows = []
    for role, pattern, out, modality in [
        ("microbiome_matrix", "stage18C_filtered_metagenomics_matrix.csv", "hmp2_microbiome_processed_matrix.csv", "microbiome"),
        ("metabolome_matrix", "stage18C_filtered_metabolomics_matrix.csv", "hmp2_metabolome_processed_matrix.csv", "metabolome"),
    ]:
        n, c, status = copy_matrix(find_one(root, pattern), DATA_DIR / out, modality)
        rows.append({"role": role, "file_name": out, "rows": n, "columns": c, "source_status": status, "public_release_status": "requires_original_data", "notes": "sample_id first column"})
    meta_src = find_one(root, "stage18A_paired_metadata_labels.csv")
    meta_out = DATA_DIR / "hmp2_sample_metadata.csv"
    if meta_src and meta_src.exists():
        meta = pd.read_csv(meta_src).rename(columns={"paired_sample_id": "sample_id", "diagnosis_standard": "diagnosis"})
        keep = [c for c in ["sample_id", "subject_id", "diagnosis", "disease_subtype", "timepoint_order"] if c in meta.columns]
        meta = meta[keep].drop_duplicates("sample_id")
        meta["group_label"] = meta["diagnosis"].replace({"HC": "nonIBD", "Control": "nonIBD"}) if "diagnosis" in meta.columns else ""
        meta["metadata_status"] = "recovered_from_stage18A_paired_metadata_labels"
        meta.to_csv(meta_out, index=False)
        rows.append({"role": "sample_metadata", "file_name": meta_out.name, "rows": len(meta), "columns": len(meta.columns), "source_status": "recovered_metadata", "public_release_status": "requires_original_data", "notes": "Direct age/sex/BMI fields excluded."})
    elif meta_out.exists() and meta_out.stat().st_size:
        rows.append({"role": "sample_metadata", "file_name": meta_out.name, "rows": -1, "columns": len(pd.read_csv(meta_out, nrows=1).columns), "source_status": "existing_package_metadata_retained", "public_release_status": "summary_only", "notes": "Existing metadata retained."})
    else:
        pd.DataFrame([{"sample_id": "requires_original_HMP2_IBDMDB_data", "subject_id": "", "diagnosis": "", "group_label": "", "metadata_status": "template_only", "notes": "Metadata not recovered."}]).to_csv(meta_out, index=False)
    pd.DataFrame(rows).to_csv(AUDIT_DIR / "hmp2_input_inventory.csv", index=False)
    print("06_prepare_hmp2_matrices complete")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
