import csv
import json
import os
import tempfile
from pathlib import Path

class InputError(ValueError): pass

def read_queries(path):
    path=Path(path)
    if path.stat().st_size>8_000_000: raise InputError('Queries file exceeds safety limit')
    with path.open(encoding='utf-8-sig') as f: items=json.load(f)
    if not isinstance(items,list) or not items: raise InputError('queries.json must be a nonempty list')
    seen=set()
    for x in items:
        if not isinstance(x,dict) or not all(k in x for k in ('id','file_name','query')):
            raise InputError('Every query needs id, file_name, query')
        if type(x['id']) not in (str,int) or str(x['id']) in seen or not str(x['id']):
            raise InputError('IDs must be distinct nonempty strings or integers, also when CSV encoded')
        seen.add(str(x['id']))
        if not isinstance(x['file_name'],str) or not x['file_name'].lower().endswith('.xlsx'):
            raise InputError('file_name must identify an .xlsx workbook')
        if not isinstance(x['query'],str) or not x['query'].strip() or len(x['query'])>20000:
            raise InputError('query must be nonempty and at most 20000 characters')
    return items

def workbook_path(root,name):
    root=Path(root).resolve(); p=(root/name).resolve()
    if not p.is_relative_to(root) or not p.is_file(): raise InputError('Workbook missing or outside xlsx-dir')
    return p

def check_output(path,xlsx_dir,queries):
    p=Path(path).resolve(); root=Path(xlsx_dir).resolve(); q=Path(queries).resolve()
    if p.is_relative_to(root) or p==q or p.is_relative_to(Path('/input')):
        raise InputError('Output must not overwrite input data')
    return p

def write_results(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    ids=[str(r['id']) for r in rows]
    if len(ids)!=len(set(ids)):raise InputError('Duplicate output IDs')
    fd,tmp=tempfile.mkstemp(prefix='.excelqa-',suffix='.csv',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['id','answer'],extrasaction='raise')
            w.writeheader(); w.writerows(rows); f.flush();os.fsync(f.fileno())
        with open(tmp,encoding='utf-8',newline='') as f:
            rd=csv.DictReader(f)
            if rd.fieldnames!=['id','answer'] or [r['id'] for r in rd]!=ids:
                raise InputError('Output validation failed')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
