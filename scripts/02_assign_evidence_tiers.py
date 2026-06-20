from __future__ import annotations
import csv
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read_csv(rel):
    with (ROOT / rel).open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def main():
    rows = read_csv('data/processed/tier_assignment_table.csv')
    counts = {}
    for r in rows:
        counts[r.get('evidence_tier','')] = counts.get(r.get('evidence_tier',''), 0) + 1
    print(counts)
if __name__ == '__main__':
    main()
