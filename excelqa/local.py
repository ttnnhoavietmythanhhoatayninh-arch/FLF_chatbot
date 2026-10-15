"""Conservative semantic fast path. No query IDs, file names or stored answers.
Unrecognized/ambiguous selections defer to the LLM planner.
"""
import re
from .workbook import norm,clean,number
from .expressions import inferred_format

STOP={'the','of','and','in','for','by','a','an','or','to','at','only','number','persons','people','workers','employees','employed','employment','occupations','industry','industries','years','year'}

def terms(t):
    t=norm(t).replace(' and related','').replace('agricultural','agriculture').replace('nonagricultural','nonagriculture')
    return {x for x in t.split() if x not in STOP}

def matches(label,query):
    a=terms(label);b=terms(query)
    return bool(a) and a<=b

def ref(s,r,c):return {'cell':s.ref(r,c)}
def op(name,*args):return {'op':name,'args':list(args)}

def numeric(v):
    try:number(v);return True
    except ValueError:return False

def meta(s):
    rs=[]
    for r in range(1,s.rows+1):
        if not isinstance(s.value(r,1),str):continue
        label=clean(s.value(r,1))
        nums=[c for c in range(2,s.cols+1) if numeric(s.value(r,c))]
        if not label or not nums:continue
        if len(nums)==1 and 1900<=number(s.value(r,nums[0]))<=2100 and not rs:continue
        rs.append((r,nums))
    if not rs:return None
    first=rs[0][0]
    headers={}
    leaves={}
    for c in range(2,s.cols+1):
        vals=[]
        for r in range(1,first):
            x=clean(s.expanded(r,c))
            if x and len(x)<150 and x not in vals:vals.append(x)
        headers[c]=' / '.join(vals);leaves[c]=vals[-1] if vals else ''
    group='total'; scopes={}
    for r in range(first,s.rows+1):
        label=norm(s.value(r,1));nums=[c for rr,cs in rs if rr==r for c in cs]
        if not label:continue
        if label in ('men','women','total') or label.startswith(('men 16','women 16')):
            group='women' if label.startswith('women') else 'men' if label.startswith('men') else 'total'
        elif not nums and len(label)<80 and not label.startswith(('footnotes','note','1 ','2 ')):
            group=label
        scopes[r]=group
    return rs,headers,leaves,scopes

def local_plan(book,query):
    q=norm(query)
    if re.search(r'\bmen\b',q) and re.search(r'\bwomen\b',q):return None
    fmt=inferred_format(query)
    candidates=[]
    for s in book.sheets:
        # Flat person tables are eligible only when the date basis is explicit.
        pp=person_plan(s,query)
        if pp is not None:candidates.append(pp);continue
        mm=meta(s)
        if not mm:continue
        rs,headers,leaves,scopes=mm
        # Refuse fiscal/calendar duplicate blocks; the LLM uses full raw context.
        if any('fiscal' in norm(v) or 'calendar' in norm(v) for v in s.cells.values() if isinstance(v,str)):
            continue
        sex='women' if re.search(r'\b(women|female)\b',q) else 'men' if re.search(r'\b(men|male)\b',q) else None
        pool=[(r,cs) for r,cs in rs if sex is None or scopes.get(r)==sex]
        if sex is None:
            # Use overall block only, avoid adding male/female/race duplicates.
            first_group=scopes.get(rs[0][0])
            pool=[(r,cs) for r,cs in rs if scopes.get(r)==first_group]
        row_hits=[(r,cs) for r,cs in pool if matches(s.value(r,1),q)]
        # Remove generic total rows if a more specific row was mentioned.
        specific=[(r,cs) for r,cs in row_hits if not norm(s.value(r,1)).startswith('total')]
        if specific:row_hits=specific
        cols=[]
        for c,hdr in headers.items():
            parts=[x for x in hdr.split(' / ') if not re.fullmatch(r'\d{4}',x)]
            meaningful=[x for x in parts if norm(x) not in ('total','total 2','total employed','total at work')]
            if not meaningful:continue
            if matches(meaningful[-1],q):
                # Disambiguate column families using explicit query qualifiers.
                ht=terms(hdr);qt=terms(q)
                if 'agriculture' in qt and 'nonagriculture' in ht:continue
                if 'nonagriculture' in qt and 'nonagriculture' not in ht:continue
                if ('percentage' in qt or 'percent' in qt) and 'percent' not in ht:continue
                if 'percent' in ht and not ('percentage' in qt or 'percent' in qt):continue
                if 'unadjusted' in qt and 'unadjusted' not in ht:continue
                cols.append(c)
        # A family Total is not an extra value when a specific measure was matched.
        specific_cols=[c for c in cols if norm(leaves[c]) not in ('total','total 2') or re.search(r'\d',effective_header(headers[c]))]
        if specific_cols:cols=specific_cols
        if 'average' in q and 'unemployment rate' in q:
            chosen=[(r,cs) for r,cs in pool if norm(s.value(r,1))=='unemployment rate']
            if len(chosen)==1:
                r,cs=chosen[0];candidates.append({'expression':op('mean',*[ref(s,r,c) for c in cs]),'format':fmt});continue
        if ('rank' in q or 'descending order' in q) and len(row_hits)>=2:
            # Match a column by token coverage; a parent header is insufficient.
            if len(cols)==1:
                c=cols[0];items=[{'label':label_expr(s,r,1,q),'value':ref(s,r,c)} for r,cs in row_hits if c in cs]
                candidates.append({'expression':{'op':'rank_labels','items':items},'format':{'type':'auto'}});continue
        if ('highest' in q or 'lowest' in q) and ('which' in q or 'identify' in q or 'infer' in q):
            name='argmin' if 'lowest' in q else 'argmax'
            if len(row_hits)==1 and not cols:
                r,cs=row_hits[0]
                items=[{'label':{'op':'text','args':[{'cell':s.ref(header_row(s,rs[0][0],c),c)}]},'value':ref(s,r,c)} for c in cs if header_row(s,rs[0][0],c)]
            elif len(cols)==1 and not row_hits:
                c=cols[0];rr=[(r,cs) for r,cs in pool if not norm(s.value(r,1)).startswith(('total','average')) and c in cs]
                items=[{'label':label_expr(s,r,1,q),'value':op('abs',ref(s,r,c)) if 'absolute' in q else ref(s,r,c)} for r,cs in rr]
            else:items=[]
            if items:candidates.append({'expression':{'op':name,'items':items},'format':fmt});continue
        # Without explicit row labels, overall total can answer a direct total query.
        if not row_hits:
            totals=[(r,cs) for r,cs in pool if norm(s.value(r,1)).startswith('total')]
            if len(totals)==1:row_hits=totals
        if len(row_hits)==1 and not cols:
            # Total at work is a distinct header, not a generic arbitrary first column.
            totals=[c for c in headers if re.fullmatch(r'(?:\d{4} / )?Total(?: at work| employed)?',headers[c],flags=re.I)]
            if len(totals)==1:cols=totals
        if len(row_hits)>1 and not cols and ('difference' in q or 'how many more' in q):
            # Industry comparison tables with an explicit Total at work column.
            totals=[c for c in headers if 'total at work' in norm(headers[c]) and 'average' not in norm(headers[c]) and 'worked' not in norm(headers[c])]
            if len(totals)==1:cols=totals
        # All-industries row difference is sum across the mutually exclusive industry columns.
        if 'how many more' in q and 'all industries' in q and len(row_hits)==2 and not cols:
            row_hits.sort(key=lambda x:mention_index(s.value(x[0],1),q))
            expr=op('sub',*[op('sum',*[ref(s,r,c) for c in cs]) for r,cs in row_hits])
            candidates.append({'expression':expr,'format':fmt});continue
        if not row_hits or not cols:continue
        row_hits.sort(key=lambda x:mention_index(s.value(x[0],1),q))
        cols.sort(key=lambda c:mention_index(effective_header(headers[c]),q))
        values=[ref(s,r,c) for r,cs in row_hits for c in cols if c in cs]
        if len(values)!=len(row_hits)*len(cols):continue
        expr=None
        if len(values)==1:expr=values[0]
        elif ('difference' in q or 'how many more' in q) and len(values)==2:
            expr=op('sub',*values)
            if 'absolute' in q:expr=op('abs',expr)
        elif ('exceed' in q or 'greater than' in q or 'less than' in q) and len(values)==2:
            expr=op('lt' if 'less than' in q else 'gt',*values)
        elif 'combined' in q or 'final sum' in q:expr=op('sum',*values)
        elif 'two integers' in q or 'men women' in q:expr=op('list',*values)
        if expr is not None:candidates.append({'expression':expr,'format':fmt})
    return candidates[0] if len(candidates)==1 else None

def effective_header(h):
    parts=[p for p in h.split(' / ') if norm(p) not in ('total','total 2','total employed','total at work') and not re.fullmatch(r'\d{4}',p)]
    return parts[-1] if parts else h.split(' / ')[-1]

def mention_index(label,q):
    ts=terms(label)
    positions=[q.find(t) for t in ts if q.find(t)>=0]
    return min(positions) if positions else len(q)

def header_row(s,first,c):
    for r in range(first-1,0,-1):
        if isinstance(s.value(r,c),str) and len(clean(s.value(r,c)))<150:return r
    return None

def label_expr(s,r,c,q):
    return {'op':'text','args':[ref(s,r,c)],'remove_related_suffix':norm(s.value(r,c))=='agriculture and related' and 'agriculture and related' not in q}

def person_plan(s,query):
    q=norm(query)
    if not ('youngest' in q or 'oldest' in q):return None
    # No unstated age basis. Ambiguous queries go to the language model.
    if 'admission' not in q:return None
    header={}
    for (r,c),v in s.cells.items():
        if r<=12 and norm(v) in ('birth','admission','last','score'):header[norm(v)]=(r,c)
    if not all(x in header for x in ('birth','admission','last','score')):return None
    rows=[]
    import datetime
    for r in range(max(x[0] for x in header.values())+1,s.rows+1):
        if isinstance(s.value(r,header['birth'][1]),(datetime.date,datetime.datetime)):
            rows.append(r)
    if not rows:return None
    target='last' if 'last name' in q else 'score' if 'score' in q else None
    if not target:return None
    words={'first':1,'second':2,'third':3,'fourth':4,'fifth':5,'ten':10}
    n=next((v for k,v in words.items() if re.search(r'\b'+k+r'\b',q)),1)
    items=[{'label':ref(s,r,header[target][1]),'result':ref(s,r,header[target][1]),
            'value':op('days_between',ref(s,r,header['birth'][1]),ref(s,r,header['admission'][1]))} for r in rows]
    return {'expression':{'op':'pick','items':items,'n':n,'descending':'oldest' in q},'format':inferred_format(query)}
