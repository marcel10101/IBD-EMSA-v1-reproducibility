from __future__ import annotations
import json, subprocess, sys
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / 'audit'
AUDIT.mkdir(exist_ok=True)
def run(label, args):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    return {'command': label, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr, 'status': 'passed' if p.returncode == 0 else 'failed'}
def main():
    results = [run('python reproduce_minimal_results.py', [sys.executable, 'reproduce_minimal_results.py'])]
    results += [run(f'python tests/{p.name}', [sys.executable, str(p)]) for p in sorted((ROOT / 'tests').glob('test_*.py'))]
    status = {'generated': datetime.now().isoformat(timespec='seconds'), 'results': results, 'overall_status': 'passed' if all(r['returncode'] == 0 for r in results) else 'failed'}
    (AUDIT / 'repository_run_status.json').write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding='utf-8')
    (AUDIT / 'repository_run_status.md').write_text('# Repository Run Status\n\n' + f"Generated: {status['generated']}\nOverall status: `{status['overall_status']}`\n\n" + '\n'.join(f"- `{r['command']}`: {r['status']}" for r in results) + '\n', encoding='utf-8')
    print(json.dumps({'overall_status': status['overall_status']}, indent=2))
    return 0 if status['overall_status'] == 'passed' else 1
if __name__ == '__main__':
    raise SystemExit(main())
