import datetime as dt
from decimal import Decimal
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
import openpyxl
from openpyxl.utils import get_column_letter

class WorkbookError(ValueError):pass

def clean(v):
    if v is None:return ''
    if isinstance(v,(dt.date,dt.datetime)):return v.isoformat()
    # Join hyphenated line wraps but keep numeric intervals intact.
    return re.sub(r'\s+',' ',re.sub(r'(?<=[A-Za-z])-\s*\n\s*(?=[A-Za-z])','',str(v))).strip()

def norm(v):
    t=clean(v).lower().replace('–','-').replace('—','-')
    t=re.sub(r'\(\d+\)|\b\d+/','',t)
    t=re.sub(r'\bsep(?:tember)?\.?','sep',t);t=re.sub(r'\boct(?:ober)?\.?','oct',t)
    t=re.sub(r'(\d)\s*-\s*(\d)',r'\1 to \2',t)
    return re.sub(r'[^a-z0-9]+',' ',t).strip()

def number(v):
    if isinstance(v,bool):raise ValueError('Boolean is not numeric')
    if isinstance(v,(int,float,Decimal)):return v
    if isinstance(v,str):
        t=v.strip().replace(',','').replace('−','-')
        if t.startswith('(') and t.endswith(')'):t='-'+t[1:-1]
        if re.fullmatch(r'[-+]?\d+(\.\d+)?',t):return float(t) if '.' in t else int(t)
    raise ValueError('Not numeric')

@dataclass
class Sheet:
    name:str
    cells:dict
    merged:list
    rows:int
    cols:int
    indents:dict
    def value(self,r,c):return self.cells.get((r,c))
    def expanded(self,r,c):
        v=self.value(r,c)
        if v is not None:return v
        for r1,c1,r2,c2 in self.merged:
            if r1<=r<=r2 and c1<=c<=c2:return self.value(r1,c1)
        return None
    def ref(self,r,c):return f'{self.name}!{get_column_letter(c)}{r}'
    def numeric_rows(self):
        out=[]
        for r in range(1,self.rows+1):
            if isinstance(self.value(r,1),str) and clean(self.value(r,1)):
                nums=[]
                for c in range(2,self.cols+1):
                    try:number(self.value(r,c));nums.append(c)
                    except ValueError:pass
                if nums:out.append((r,nums))
        return out
    def header(self,r,c):
        # Header block preceding current row, bounded by nearest table restart.
        candidates=[]
        numeric=self.numeric_rows()
        first=next((rr for rr,_ in numeric if rr<=r),None)
        if first is None:return ''
        # A new table header has a populated data-column string and no row label,
        # after an earlier data region (fiscal/calendar blocks, repeated tables).
        start=1
        for rr in range(first+1,r):
            v=self.value(rr,c)
            if isinstance(v,str) and self.value(rr,1) in (None,'') and clean(v) and not v.startswith('='):
                if not any(x==rr for x,_ in numeric):start=rr
        end=first if start==1 else next((rr for rr,_ in numeric if rr>start),r)
        for rr in range(start,end):
            v=self.expanded(rr,c)
            if v is None:continue
            t=clean(v)
            if len(t)>150 or (rr,c) in self.cells and c==1:continue
            if t and t not in candidates:candidates.append(t)
        return ' / '.join(candidates)

class Book:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.stat().st_size>40_000_000:raise WorkbookError('Workbook too large')
        with zipfile.ZipFile(self.path) as z:
            if sum(x.file_size for x in z.infolist())>180_000_000:raise WorkbookError('Expanded workbook exceeds limit')
        wb=openpyxl.load_workbook(path,data_only=False,keep_links=False)
        cache=openpyxl.load_workbook(path,data_only=True,keep_links=False)
        self.sheets=[];self._map={};self.formulas={};self.missing=[]
        try:
            total=0
            for ws in wb:
                if ws.max_row*ws.max_column>1_000_000:raise WorkbookError('Sheet dimensions exceed safe limit')
                cells={};indents={}
                for row in ws:
                    for c in row:
                        v=c.value
                        if v is None:continue
                        total+=1
                        if total>150000:raise WorkbookError('Workbook has too many populated cells')
                        if c.data_type=='f':
                            self.formulas[f'{ws.title}!{c.coordinate}']=v
                            v=cache[ws.title][c.coordinate].value
                            # Resolve only safe, direct in-sheet formula references.
                            if v is None and re.fullmatch(r'=\$?[A-Z]+\$?\d+',c.value):
                                target=c.value[1:].replace('$','');v=cache[ws.title][target].value
                            if v is None:self.missing.append(f'{ws.title}!{c.coordinate}')
                        if c.data_type=='e':v=None
                        if v is not None:cells[(c.row,c.column)]=v
                        if c.alignment.indent:indents[(c.row,c.column)]=c.alignment.indent
                merged=[(x.min_row,x.min_col,x.max_row,x.max_col) for x in ws.merged_cells.ranges]
                s=Sheet(ws.title,cells,merged,ws.max_row,ws.max_column,indents)
                self.sheets.append(s);self._map[s.name]=s
        finally:wb.close();cache.close()
    def get(self,ref):
        from openpyxl.utils.cell import coordinate_to_tuple
        if not isinstance(ref,str) or '!' not in ref:raise WorkbookError('Expected sheet!A1 reference')
        name,coord=ref.rsplit('!',1);name=name.strip("'")
        if name not in self._map or not re.fullmatch(r'[A-Z]+[1-9]\d*',coord):raise WorkbookError('Invalid cell reference')
        r,c=coordinate_to_tuple(coord);s=self._map[name]
        v=s.value(r,c)
        if v is None:raise WorkbookError('Missing, error or uncached formula cell')
        return v
    def context(self,query,max_bytes=160000):
        """Lossless cell values for small files; whole-sheet packs with row coordinates.
        Refuse rather than silently truncating relevant global comparisons.
        """
        blocks=[]
        for s in self.sheets:
            lines=[f'SHEET {json.dumps(s.name,ensure_ascii=False)} rows={s.rows} cols={s.cols}',
                   'MERGED '+json.dumps([[f'{get_column_letter(c1)}{r1}',f'{get_column_letter(c2)}{r2}'] for r1,c1,r2,c2 in s.merged])]
            for r in range(1,s.rows+1):
                vals={get_column_letter(c):clean(s.value(r,c)) for c in range(1,s.cols+1) if s.value(r,c) is not None}
                if vals:lines.append(f'ROW {r} '+json.dumps(vals,ensure_ascii=False,separators=(',',':')))
            blocks.append('\n'.join(lines))
        text='\n\n'.join(blocks)
        if self.missing:text+='\nWARNING unresolved formula cells: '+', '.join(self.missing)
        if len(text.encode('utf-8'))>max_bytes:raise WorkbookError('Workbook context exceeds safe size; no silent truncation')
        return text
