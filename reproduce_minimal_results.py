from __future__ import annotations
import csv, json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def read_csv(rel):
    with (ROOT / rel).open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
def exists(rel): return (ROOT / rel).exists()
def main():
    candidates = read_csv('data/processed/candidate_499_master_table.csv')
    tiers = read_csv('data/processed/tier_assignment_table.csv')
    omics = Counter((r.get('omics_layer') or r.get('omics_type') or '') for r in candidates)
    tier_counts = Counter(r.get('evidence_tier','') for r in tiers)
    report = {
        'checks': {
            'candidate_count': {'observed': len(candidates), 'expected': 499, 'pass': len(candidates) == 499},
            'omics_split': {'observed': dict(omics), 'expected': {'microbiome': 345, 'metabolome': 154}, 'pass': omics.get('microbiome') == 345 and omics.get('metabolome') == 154},
            'tier_counts': {'observed': dict(tier_counts), 'expected': {'Evidence Tier I': 15, 'Evidence Tier II': 313, 'Evidence Tier III': 171}, 'pass': tier_counts.get('Evidence Tier I') == 15 and tier_counts.get('Evidence Tier II') == 313 and tier_counts.get('Evidence Tier III') == 171},
            'internal_model_results_table_exists': {'path': 'outputs_expected/expected_internal_model_results.csv', 'pass': exists('outputs_expected/expected_internal_model_results.csv')},
            'st001000_performance_status_table_exists': {'path': 'data/external_ST001000/st001000_performance_summary.csv', 'pass': exists('data/external_ST001000/st001000_performance_summary.csv')},
        },
        'st001000_strict_projection_recomputed': False,
        'reason': 'mapping_insufficient_or_locked_projection_incomplete',
    }
    report['overall_pass'] = all(v.get('pass') for v in report['checks'].values())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['overall_pass'] else 1
if __name__ == '__main__':
    raise SystemExit(main())
