#!/usr/bin/env python3
"""Exact string comparison only. Never imported by the answering application."""
import argparse
import csv
import json
from pathlib import Path

def read_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f)
        if r.fieldnames!=['id','answer']:raise ValueError('CSV columns must be exactly id,answer')
        out={}
        for row in r:
            if None in row or row.get('answer') is None or row['id'] in out:raise ValueError('Duplicate ID or invalid CSV row')
            out[row['id']]=row['answer']
        return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--queries',required=True);p.add_argument('--prediction',required=True)
    p.add_argument('--reference',required=True);p.add_argument('--report');a=p.parse_args()
    try:
        items=json.loads(Path(a.queries).read_text(encoding='utf-8-sig'));ids=[str(x['id']) for x in items]
        pred=read_csv(a.prediction);gold=read_csv(a.reference)
        if len(ids)!=len(set(ids)) or set(pred)!=set(ids) or set(gold)!=set(ids):raise ValueError('Missing, duplicate or extra IDs')
        errors=[{'id':i,'predicted':pred[i],'reference':gold[i]} for i in ids if pred[i]!=gold[i]]
        report={'questions':len(ids),'exact_match':len(ids)-len(errors),'unanswered':sum(not pred[i] for i in ids),'differences':errors}
        text=json.dumps(report,ensure_ascii=False,indent=2);print(text)
        if a.report:Path(a.report).write_text(text,encoding='utf-8')
        return 1 if errors else 0
    except (ValueError,KeyError,OSError) as e:print(json.dumps({'invalid':str(e)}));return 2
if __name__=='__main__':raise SystemExit(main())
