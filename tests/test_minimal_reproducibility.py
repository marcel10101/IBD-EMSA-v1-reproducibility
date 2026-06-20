import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p = subprocess.run([sys.executable, 'reproduce_minimal_results.py'], cwd=ROOT, text=True, capture_output=True)
assert p.returncode == 0, p.stdout + p.stderr
assert 'st001000_strict_projection_recomputed' in p.stdout
print('test_minimal_reproducibility passed')
