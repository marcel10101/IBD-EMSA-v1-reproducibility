from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
pattern = re.compile(r'(?<!<)[A-Za-z]:[\\\\/]')
for p in list(ROOT.glob('*.md')) + list((ROOT / 'docs').glob('*.md')):
    text = p.read_text(encoding='utf-8', errors='replace')
    assert not pattern.search(text), f'absolute path in {p}'
print('test_no_absolute_paths_in_public_docs passed')
