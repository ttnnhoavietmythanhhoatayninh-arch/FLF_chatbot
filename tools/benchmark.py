#!/usr/bin/env python3
"""Run on public data, then score separately. Reference never enters the solver."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',required=True,help='Contains queries.json and xlsx_files/')
    p.add_argument('--output-dir',required=True)
    p.add_argument('--solver',choices=['offline','hybrid','llm'],default='offline')
    p.add_argument('--question-budget',default='0.09');p.add_argument('--time-limit',type=int,default=2300)
    a=p.parse_args();data=Path(a.data_dir).resolve();out=Path(a.output_dir).resolve()
    if out.is_relative_to(data):p.error('Keep output-dir outside data-dir')
    for path in (data/'queries.json',data/'xlsx_files'):
        if not path.exists():p.error('Missing queries.json or xlsx_files')
    reference=data/'answers.json'
    if not reference.exists():reference=data/'sample_submission.csv'
    if not reference.exists():p.error('No reference answers.json or sample_submission.csv')
    out.mkdir(parents=True,exist_ok=True)
    # Key inherited via environment, never placed in subprocess arguments or logs.
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--xlsx-dir',str(data/'xlsx_files'),
        '--queries',str(data/'queries.json'),'--output',str(out/'submission.csv'),
        '--report',str(out/'run_report.json'),'--solver',a.solver,'--question-budget',a.question_budget,
        '--time-limit',str(a.time_limit)],cwd=ROOT)
    if result.returncode!=0:return result.returncode
    return subprocess.run([sys.executable,str(ROOT/'tools/evaluate.py'),'--queries',str(data/'queries.json'),
        '--prediction',str(out/'submission.csv'),'--reference',str(reference),'--report',str(out/'evaluation.json')],cwd=ROOT).returncode
if __name__=='__main__':raise SystemExit(main())
