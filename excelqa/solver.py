import json
import time
from .api import APIError
from .budget import Budget,BudgetError
from .expressions import Evaluator,PlanError,parse_plan,format_answer,inferred_format
from .local import local_plan
from .prompts import SYSTEM

class SolveError(RuntimeError):
    def __init__(self,message,trace=None):
        super().__init__(message);self.trace=trace or {}


def execute(book,plan,query):
    ev=Evaluator(book,query=query);value=ev.run(plan['expression'])
    fmt=inferred_format(query)
    if fmt=={'type':'auto'} or (isinstance(value,list) and isinstance(plan.get('format'),dict) and plan['format'].get('type')=='tuple'):
        fmt=plan.get('format',fmt)
    answer=format_answer(value,fmt)
    if not ev.evidence:raise PlanError('Answer has no source cells')
    return answer,ev.evidence

def solve(book,query,client,mode,deadline,limit='0.09',max_context=200000):
    budget=Budget(limit);trace={'method':None,'attempts':0,'cost_usd':0,'evidence':{}}
    local=None
    if mode!='llm':
        try:local=local_plan(book,query)
        except (ValueError,TypeError,KeyError,IndexError):local=None
    if local is not None:
        try:
            ans,ev=execute(book,local,query)
            trace.update(method='local',plan=local,evidence=ev)
            return ans,trace
        except (PlanError,ArithmeticError):pass
    if mode=='offline':
        trace['method']='local'
        raise SolveError('Unsupported offline question; answer left empty; no API request made',trace)
    if client is None:raise SolveError('No supported local plan; OpenRouter API key is required',trace)
    context=book.context(query,max_bytes=max_context)
    messages=[{'role':'system','content':SYSTEM},
              {'role':'user','content':json.dumps({'question':query,'workbook':context},ensure_ascii=False)}]
    last='No valid plan';calls_before=client.calls;pt=client.prompt_tokens;ct=client.completion_tokens
    for attempt in range(3):
        if time.monotonic()>=deadline:break
        text=None
        try:
            text=client.complete(messages,budget,deadline,max_tokens=3072 if attempt<2 else 6144)
            plan=parse_plan(text);ans,ev=execute(book,plan,query)
            trace.update(method='llm',plan=plan,evidence=ev,cost_usd=float(budget.spent),
                         attempts=client.calls-calls_before,cost_accounted_usd=float(budget.spent),prompt_tokens=client.prompt_tokens-pt,
                         completion_tokens=client.completion_tokens-ct)
            return ans,trace
        except APIError as e:
            last=str(e)
            if not e.retryable:break
            if attempt<2:
                remaining=deadline-time.monotonic()
                if remaining>2:time.sleep(min(1.0,remaining/4))
        except (PlanError,KeyError,TypeError,ArithmeticError,ValueError) as e:
            # The validation error contains no API key, response body or workbook text.
            last=str(e)[:200]
            messages=messages[:2]+([{'role':'assistant','content':text[:16000]}] if text else [])+[{'role':'user','content':'Previous plan was invalid: '+last+'. Return a corrected JSON plan using only supported expressions. Re-check all sheet names and coordinates.'}]
        except BudgetError as e:
            last=str(e);break
    trace.update(method='llm',attempts=client.calls-calls_before,cost_accounted_usd=float(budget.spent),
                 prompt_tokens=client.prompt_tokens-pt,completion_tokens=client.completion_tokens-ct)
    raise SolveError(last,trace)
