#!/usr/bin/env python3
"""Build the actual submission ZIP: Dockerfile at its root, no secrets/data/cache."""
import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def build(team,out):
    if not re.fullmatch(r'[\w.-]{1,80}',team) or team in ('.','..'):
        raise ValueError('Use a team name without spaces or path separators')
    files=[ROOT/x for x in ('Dockerfile','.dockerignore','requirements.txt','main.py','README.md','VALIDATION.md','RUN_WINDOWS.ps1')]
    for folder in ('excelqa','tests','tools'):
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.md'))
    files.extend((ROOT/'dependency_wheels').glob('*.whl'))
    files=sorted(set(files))
    entries={str(p.relative_to(ROOT)).replace('\\','/'):p.read_bytes() for p in files}
    for name,content in entries.items():
        if re.search(rb'sk-or-v1-[A-Za-z0-9]{24,}',content):raise ValueError('Possible real API key in '+name)
    manifest='\n'.join(hashlib.sha256(v).hexdigest()+'  '+k for k,v in sorted(entries.items()))+'\n'
    entries['MANIFEST.sha256']=manifest.encode()
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);target=out/(team+'.zip')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            z.writestr(info,data)
    with zipfile.ZipFile(target) as z:
        assert 'Dockerfile' in z.namelist() and z.testzip() is None
        assert all(not n.startswith('/') and '..' not in Path(n).parts for n in z.namelist())
    if target.stat().st_size>100_000_000:raise ValueError('ZIP exceeds 100 MB')
    return target
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--team',required=True);p.add_argument('--out',default='dist');a=p.parse_args()
    print(build(a.team,a.out))
