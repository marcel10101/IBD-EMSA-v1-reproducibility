from __future__ import annotations
import csv
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read_csv(rel):
    with (ROOT / rel).open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def main():
    rows = read_csv('data/processed/candidate_499_master_table.csv')
    print({'candidate_rows': len(rows), 'reported_chain': '1,470 upstream candidates -> 499 directly detected candidates'})
if __name__ == '__main__':
    main()
