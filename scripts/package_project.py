"""Arsip proyek tanpa cache, lingkungan Python, atau secret."""
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
target=root.parent/'Paket_UTS_Zidan_12030124130141.zip'
excluded={'.venv','__pycache__','.git','.pytest_cache'}
files=[p for p in root.rglob('*') if p.is_file() and not (set(p.relative_to(root).parts)&excluded)
       and p.name not in {'.env','secrets.toml'} and p.suffix not in {'.pyc','.log','.zip'}]
with ZipFile(target,'w',ZIP_DEFLATED) as archive:
    for file in sorted(files):archive.write(file,Path(root.name)/file.relative_to(root))
with ZipFile(target) as archive:
    assert archive.testzip() is None
    required=['app.py','README.md','sql/001_schema.sql','sql/002_business_logic.sql','Jawaban_UTS_Zidan.pdf',
              'docs/erd.svg','docs/hasil_uji.json','backend/api.py','docs/prompt_notebooklm.txt']
    assert all(f'{root.name}/{p}' in archive.namelist() for p in required)
print(json.dumps({'zip':str(target),'files':len(files),'bytes':target.stat().st_size},indent=2))
