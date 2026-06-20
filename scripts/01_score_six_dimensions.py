from __future__ import annotations
import csv
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read_csv(rel):
    with (ROOT / rel).open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def main():
    rows = read_csv('data/processed/six_dimension_scores.csv')
    print({'six_dimension_scores': len(rows), 'source_status': 'derived_from_supplementary_table; not_original_training_script'})
if __name__ == '__main__':
    main()
