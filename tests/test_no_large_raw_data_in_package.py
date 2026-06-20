from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BAD_PARTS = {'codextools','Inkscape','site-packages','__pycache__','venv','venvs','.cache'}
BAD_EXTS = {'.pyc','.pyd','.raw','.mzml','.fastq','.gz','.zip','.7z','.tiff','.tif','.pdf','.svg'}
for p in ROOT.rglob('*'):
    if p.is_file():
        assert not (set(p.parts) & BAD_PARTS), str(p)
        assert p.suffix.lower() not in BAD_EXTS, str(p)
        assert p.stat().st_size <= 20 * 1024 * 1024, str(p)
print('test_no_large_raw_data_in_package passed')
