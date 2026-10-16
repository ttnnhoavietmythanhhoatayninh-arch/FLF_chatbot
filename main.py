#!/usr/bin/env python3
"""BTC Docker ENTRYPOINT. Never logs the API key or parsed command-line arguments."""
import argparse
import gc
import json
import os
import signal
import sys
import time
from pathlib import Path
from excelqa.api import OpenRouterClient,MODEL
from excelqa.contract import InputError,read_queries,workbook_path,check_output,write_results
from excelqa.solver import solve
from excelqa.workbook import Book

class DeadlineError(RuntimeError):pass

def log(event,**data):
    print(json.dumps({'event':event,**data},ensure_ascii=False,default=str),file=sys.stderr,flush=True)

def parser():
    p=argparse.ArgumentParser(description='ExcelQA AI2026 — spreadsheet question answering')
    p.add_argument('--xlsx-dir',required=True);p.add_argument('--queries',required=True);p.add_argument('--output',required=True)
    p.add_argument('--openrouter-key',default=os.environ.get('OPENROUTER_API_KEY',''))
    p.add_argument('--openrouter-model',default=MODEL)
    p.add_argument('--openrouter-base-url',default='https://openrouter.ai/api/v1')
    p.add_argument('--solver',choices=['hybrid','llm','offline'],default='hybrid')
    p.add_argument('--question-budget',default='0.09',help='USD per question, <=0.10')
    p.add_argument('--time-limit',type=int,default=2300,help='Whole run wall seconds, <=2350')
    p.add_argument('--question-timeout',type=int,default=110)
    p.add_argument('--max-context-bytes',type=int,default=200000)
    p.add_argument('--input-price-cap',help='Development override USD per INPUT token; pair with output cap')
    p.add_argument('--output-price-cap',help='Development override USD per OUTPUT token')
    p.add_argument('--report',help='Optional JSON verification report outside input directories')
    return p

def main(argv=None):
    started=time.monotonic();args=parser().parse_args(argv)
    if not 1<=args.time_limit<=2350 or not 1<=args.question_timeout<=300 or not 1000<=args.max_context_bytes<=1000000:
        log('configuration_error',message='Invalid time or context bounds');return 2
    # Single process, CPU-only. Limit virtual address space on Linux, below the FAQ 4 GB RAM allowance.
    if sys.platform.startswith('linux'):
        import resource
        old=resource.getrlimit(resource.RLIMIT_AS)
        cap=3500*1024*1024;resource.setrlimit(resource.RLIMIT_AS,(min(cap,old[0]) if old[0]>0 else cap,old[1]))
    def alarm(*_):raise DeadlineError('Whole-run time limit reached')
    if hasattr(signal,'setitimer'):
        signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,args.time_limit)
    queries=[];rows=[];records=[];failed=0;hard_errors=0;cache=None;cache_path=None
    client=None
    try:
        from excelqa.budget import Budget
        Budget(args.question_budget)
        if args.openrouter_model!=MODEL:raise InputError('Model must match the competition specification')
        output=check_output(args.output,args.xlsx_dir,args.queries)
        report_path=check_output(args.report,args.xlsx_dir,args.queries) if args.report else None
        if report_path==output:raise InputError('Report and CSV paths must differ')
        queries=read_queries(args.queries)
        paths=[workbook_path(args.xlsx_dir,q['file_name']) for q in queries]
        if output in paths or report_path in paths:raise InputError('Output collides with workbook')
        if args.openrouter_key and args.solver!='offline':
            client=OpenRouterClient(args.openrouter_key,args.openrouter_model,args.openrouter_base_url,
                                   args.input_price_cap,args.output_price_cap)
        elif args.solver=='llm':raise InputError('LLM mode requires an API key')
        log('start',questions=len(queries),solver=args.solver,model=args.openrouter_model,api_configured=client is not None)
        global_deadline=started+args.time_limit-4
        for i,(q,path) in enumerate(zip(queries,paths)):
            begin=time.monotonic();trace={};ans=''
            try:
                if begin>=global_deadline:raise DeadlineError('No execution time remaining')
                if cache_path!=path:
                    cache=None;cache_path=None;gc.collect();cache=Book(path);cache_path=path
                remaining=global_deadline-time.monotonic()
                # Adaptive fair allocation, retaining time for all remaining queries.
                per=min(args.question_timeout,max(.1,remaining/max(1,len(queries)-i)))
                ans,trace=solve(cache,q['query'],client,args.solver,min(global_deadline,time.monotonic()+per),
                                args.question_budget,args.max_context_bytes)
                trace['status']='ok'
            except DeadlineError:
                raise
            except Exception as e:
                failed+=1
                # Never echo arbitrary exceptions: they could contain secrets or request URLs.
                from excelqa.solver import SolveError
                from excelqa.workbook import WorkbookError
                from excelqa.budget import BudgetError
                safe=str(e) if isinstance(e,(SolveError,WorkbookError,BudgetError)) else type(e).__name__
                if not isinstance(e,SolveError):hard_errors+=1
                trace=dict(e.trace) if isinstance(e,SolveError) else {}
                trace.update(status='error',error=safe)
                log('question_error',id=q['id'],message=safe)
            rows.append({'id':q['id'],'answer':ans})
            trace.update(id=q['id'],seconds=round(time.monotonic()-begin,4))
            records.append(trace)
            log('question',id=q['id'],status=trace['status'],method=trace.get('method'),seconds=trace['seconds'],cost_usd=trace.get('cost_usd'))
        write_results(output,rows)
        peak=None
        if sys.platform.startswith('linux'):
            import resource
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        summary={'version':'1.1.1','questions':len(queries),'solved':len(queries)-failed,'failed':failed,'unanswered':sum(not r['answer'] for r in rows),'hard_errors':hard_errors,
                 'seconds':round(time.monotonic()-started,4),'peak_rss_mb':peak,
                 'llm_calls':client.calls if client else 0,
                 'prompt_tokens':client.prompt_tokens if client else 0,
                 'completion_tokens':client.completion_tokens if client else 0,
                 'reasoning_tokens':client.reasoning_tokens if client and client.reasoning_usage_complete else (None if client else 0),
                 'btc_input_plus_reasoning_tokens':(client.prompt_tokens+client.reasoning_tokens if client.reasoning_usage_complete else None) if client else 0,
                 'records':records}
        if report_path:
            report_path.parent.mkdir(parents=True,exist_ok=True)
            report_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        log('finish',questions=len(queries),solved=len(queries)-failed,failed=failed,seconds=summary['seconds'],peak_rss_mb=peak)
        return 0 if hard_errors==0 else 2
    except DeadlineError:
        # Preserve a diagnostic CSV with all IDs; mark the run as unsuccessful.
        if queries:
            done={str(r['id']) for r in rows}
            rows.extend({'id':q['id'],'answer':''} for q in queries if str(q['id']) not in done)
            write_results(output,rows)
        log('deadline_exceeded',completed=len(records));return 2
    except Exception as e:
        log('fatal',error_type=type(e).__name__,message='Input, configuration or execution error; no successful submission produced')
        return 2
    finally:
        if hasattr(signal,'setitimer'):signal.setitimer(signal.ITIMER_REAL,0)

if __name__=='__main__':sys.exit(main())
