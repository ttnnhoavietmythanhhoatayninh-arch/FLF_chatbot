import datetime as dt
import math
import re
from decimal import Decimal, ROUND_HALF_UP
from .workbook import number, clean, WorkbookError

class PlanError(ValueError):pass

class Evaluator:
    """Bounded declarative computation. No eval, exec, shell or generated Python."""
    def __init__(self,book,query=''):self.book=book;self.query=query;self.evidence={};self.nodes=0
    def run(self,e,depth=0):
        self.nodes+=1
        if self.nodes>12000 or depth>24:raise PlanError('Expression too complex')
        if not isinstance(e,dict):raise PlanError('Expressions must be objects grounded in cells')
        if set(e)=={'constant'}:
            v=e['constant']
            if type(v) not in (str,int,float):raise PlanError('Invalid question constant')
            text=str(v)
            if not text or not re.search(r'(?<![A-Za-z0-9])'+re.escape(text)+r'(?![A-Za-z0-9])',self.query,flags=re.I):
                raise PlanError('Constant is not present in the question')
            return v
        if set(e)=={'cell'}:
            try:v=self.book.get(e['cell'])
            except (WorkbookError,ValueError) as ex:raise PlanError(str(ex)) from None
            self.evidence[e['cell']]=clean(v);return v
        if 'range' in e and set(e)=={'range'}:
            from openpyxl.utils.cell import range_boundaries
            try:
                sh,rg=e['range'].rsplit('!',1);a,b,c,d=range_boundaries(rg)
                if (c-a+1)*(d-b+1)>5000:raise ValueError()
                return [self.run({'cell':f'{sh}!{__import__("openpyxl").utils.get_column_letter(col)}{row}'},depth+1)
                        for row in range(b,d+1) for col in range(a,c+1)]
            except (ValueError,TypeError):raise PlanError('Invalid range') from None
        op=e.get('op')
        if op=='table':
            sheet=e.get('sheet')
            if sheet not in self.book._map:raise PlanError('Unknown table sheet')
            if 'row_range' in e:
                bounds=e['row_range']
                if not isinstance(bounds,list) or len(bounds)!=2 or not all(type(x)==int for x in bounds):raise PlanError('Invalid row range')
                a,b=bounds
                if not 1<=a<=b<=self.book._map[sheet].rows or b-a>3000:raise PlanError('Table row range exceeds bounds')
                rows=list(range(a,b+1))
            else:
                rows=e.get('rows')
                if not isinstance(rows,list) or not 1<=len(rows)<=3000 or not all(type(x)==int and 1<=x<=self.book._map[sheet].rows for x in rows):raise PlanError('Invalid table rows')
                if len(rows)!=len(set(rows)):raise PlanError('Duplicate table rows')
            def bind(obj,row):
                if isinstance(obj,dict):
                    if set(obj)=={'col'}:
                        if not isinstance(obj['col'],str) or not re.fullmatch('[A-Z]+',obj['col']):raise PlanError('Invalid column')
                        return {'cell':f'{sheet}!{obj["col"]}{row}'}
                    return {k:bind(v,row) for k,v in obj.items()}
                if isinstance(obj,list):return [bind(v,row) for v in obj]
                return obj
            if 'where' in e:
                filtered=[]
                for row in rows:
                    accepted=self.run(bind(e['where'],row),depth+1)
                    if not isinstance(accepted,bool):raise PlanError('Table where must evaluate to boolean')
                    if accepted:filtered.append(row)
                rows=filtered
            if 'sort_by' in e:
                keys={r:self.run(bind(e['sort_by'],r),depth+1) for r in rows}
                try:rows.sort(key=lambda r:keys[r],reverse=bool(e.get('descending',False)))
                except TypeError:raise PlanError('Incomparable table sort keys') from None
            if 'take' in e:rows=rows[:self._index(e['take'],len(rows))]
            if 'at' in e:
                n=self._index(e['at'],len(rows));return self.run(bind(e['value'],rows[n-1]),depth+1)
            return [self.run(bind(e['value'],r),depth+1) for r in rows]
        if op in ('argmax','argmin','rank_labels','pick','top_values'):
            items=e.get('items')
            if not isinstance(items,list) or not 1<=len(items)<=3000:raise PlanError('Invalid ranking items')
            records=[(self.run(x['label'],depth+1),self._num(self.run(x['value'],depth+1)),x) for x in items]
            desc=op!='argmin' and e.get('descending',True)
            records.sort(key=lambda x:x[1],reverse=desc)
            if op=='rank_labels':return [x[0] for x in records]
            if op=='top_values':
                n=self._index(e.get('n',1),len(records));return [self.run(x[2]['result'],depth+1) for x in records[:n]]
            n=self._index(e.get('n',1),len(records));chosen=records[n-1]
            return self.run(chosen[2]['result'],depth+1) if op=='pick' and 'result' in chosen[2] else chosen[0]
        args=e.get('args',[])
        if not isinstance(args,list):raise PlanError('args must be a list')
        vs=[self.run(x,depth+1) for x in args]
        flat=[]
        for v in vs:flat.extend(v if isinstance(v,list) else [v])
        if op=='list':return flat
        if op in ('sum','mean','min','max','count'):
            if op=='count':return len(flat)
            if not flat:raise PlanError('Empty aggregation')
            ns=[self._num(x) for x in flat]
            return {'sum':lambda:sum(ns),'mean':lambda:sum(ns)/len(ns),'min':lambda:min(ns),'max':lambda:max(ns)}[op]()
        if op in ('and','or'):
            if not vs or not all(isinstance(v,bool) for v in vs):raise PlanError('Boolean arguments required')
            return all(vs) if op=='and' else any(vs)
        if op=='not' and len(vs)==1 and isinstance(vs[0],bool):return not vs[0]
        if op=='eq' and len(vs)==2 and any(isinstance(v,str) for v in vs):
            return clean(vs[0]).casefold()==clean(vs[1]).casefold()
        if op=='contains' and len(vs)==2:return clean(vs[1]).casefold() in clean(vs[0]).casefold()
        if op in ('sub','div','mul','gt','lt','eq','ge','le','percent_change'):
            if len(vs)!=2:raise PlanError('Binary operation needs two arguments')
            a,b=map(self._num,vs)
            if op in ('div','percent_change') and b==0:raise PlanError('Division by zero')
            return {'sub':lambda:a-b,'div':lambda:a/b,'mul':lambda:a*b,'gt':lambda:a>b,
                    'lt':lambda:a<b,'eq':lambda:a==b,'ge':lambda:a>=b,'le':lambda:a<=b,
                    'percent_change':lambda:(a-b)/b*100}[op]()
        if op=='abs' and len(vs)==1:return abs(self._num(vs[0]))
        if op in ('days_between','age_years') and len(vs)==2:
            def date(x):
                if isinstance(x,dt.datetime):return x.date()
                if isinstance(x,dt.date):return x
                try:return dt.date.fromisoformat(str(x)[:10])
                except ValueError:raise PlanError('Invalid date') from None
            birth,end=map(date,vs)
            if end<birth:raise PlanError('Negative age')
            return (end-birth).days if op=='days_between' else end.year-birth.year-((end.month,end.day)<(birth.month,birth.day))
        if op=='text' and len(vs)==1:
            t=clean(vs[0]);t=re.sub(r'\(\d+\)','',t).strip()
            if e.get('remove_related_suffix'):t=re.sub(r' and related$', '',t,flags=re.I)
            return t
        if op=='concat':return e.get('separator',' ').join(clean(x) for x in flat)
        raise PlanError('Unsupported or malformed expression')
    @staticmethod
    def _num(v):
        try:n=number(v)
        except ValueError:raise PlanError('Expected a number') from None
        if not math.isfinite(n):raise PlanError('Nonfinite number')
        return Decimal(str(n))
    @staticmethod
    def _index(n,length):
        if type(n)!=int or not 1<=n<=length:raise PlanError('Invalid rank')
        return n

def parse_plan(text):
    import json
    t=text.strip()
    if t.startswith('```'):
        t=re.sub(r'^```(?:json)?\s*','',t);t=re.sub(r'\s*```$','',t)
    try:p=json.loads(t,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError,TypeError):raise PlanError('Model did not return valid JSON') from None
    if not isinstance(p,dict) or set(p)-{'expression','format','note'} or 'expression' not in p:
        raise PlanError('Expected expression and format JSON plan')
    return p

def format_answer(value,spec=None):
    spec=spec or {'type':'auto'}
    if not isinstance(spec,dict):raise PlanError('Invalid answer format')
    typ=spec.get('type','auto')
    if isinstance(value,list):
        item=spec.get('item',{'type':'auto'})
        return ', '.join(format_answer(v,item) for v in value)
    if isinstance(value,bool):return 'Yes' if value else 'No'
    if typ=='yes_no':raise PlanError('Yes/No needs a comparison')
    if typ in ('integer','fixed','number') or isinstance(value,(int,float,Decimal)):
        try:d=Decimal(str(value))
        except Exception:raise PlanError('Invalid numeric answer') from None
        if not d.is_finite():raise PlanError('Nonfinite result')
        if typ=='integer':
            if abs(d-d.to_integral_value())>Decimal('0.000000001'):raise PlanError('Integer output would discard a fraction')
            return str(int(d.to_integral_value()))
        if typ=='fixed':
            n=spec.get('decimals',2)
            if type(n)!=int or not 0<=n<=10:raise PlanError('Invalid decimal places')
            try:return format(d.quantize(Decimal(1).scaleb(-n),rounding=ROUND_HALF_UP),f'.{n}f')
            except Exception:raise PlanError('Cannot round result') from None
        return format(d,'f').rstrip('0').rstrip('.') if '.' in format(d,'f') else format(d,'f')
    if typ not in ('auto','text'):raise PlanError('Invalid format type')
    ans=clean(value)
    if not ans or len(ans)>2000:raise PlanError('Empty or excessive answer')
    return ans

def inferred_format(query):
    q=query.lower()
    if 'two decimal' in q or '2 decimal' in q:
        f={'type':'fixed','decimals':2}
        return {'type':'list','item':f} if 'separat' in q or 'men, women' in q else f
    if 'two integers' in q:return {'type':'list','item':{'type':'integer'}}
    if 'integer' in q:return {'type':'integer'}
    if 'yes or no' in q:return {'type':'yes_no'}
    return {'type':'auto'}
