"""Small OpenRouter HTTP client with preflight reservations and no secret logging."""
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from .budget import BudgetError,money

MODEL='qwen/qwen3.7-flash'
class APIError(RuntimeError):
    def __init__(self,message,retryable=True):super().__init__(message);self.retryable=retryable

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None

class OpenRouterClient:
    def __init__(self,key,model=MODEL,base_url='https://openrouter.ai/api/v1',input_price=None,output_price=None,allow_local=False):
        if model!=MODEL:raise ValueError('Only the competition model is allowed')
        u=urllib.parse.urlsplit(base_url)
        if u.username or u.password or u.query or u.fragment:raise ValueError('Invalid API base URL')
        local=allow_local and u.hostname in ('127.0.0.1','localhost')
        if not local and (u.scheme!='https' or u.hostname!='openrouter.ai' or u.path.rstrip('/')!='/api/v1'):
            raise ValueError('API base URL must be https://openrouter.ai/api/v1')
        if not key or '\n' in key or '\r' in key:raise ValueError('Missing or invalid API key')
        self.key=key;self.model=model;self.base=base_url.rstrip('/');self.input_price=money(input_price) if input_price is not None else None
        self.output_price=money(output_price) if output_price is not None else None
        if (self.input_price is None)!=(self.output_price is None):raise ValueError('Both token price caps are required')
        self.reasoning_tokens=0;self.reasoning_usage_complete=True
        self.calls=0;self.prompt_tokens=0;self.completion_tokens=0;self.last_usage={}
        self.opener=urllib.request.build_opener(NoRedirect())
    def _request(self,path,data=None,timeout=20,auth=True):
        headers={'Content-Type':'application/json','User-Agent':'ExcelQA-AI2026/1.0'}
        if auth:headers['Authorization']='Bearer '+self.key
        req=urllib.request.Request(self.base+path,data=json.dumps(data,ensure_ascii=False).encode() if data is not None else None,headers=headers)
        try:
            with self.opener.open(req,timeout=max(.1,timeout)) as r:
                raw=r.read(4_000_001)
                if len(raw)>4_000_000:raise APIError('API response exceeds safety limit')
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            status=e.code;e.close()
            raise APIError('API HTTP '+str(status),status in (408,429,500,502,503,504)) from None
        except (urllib.error.URLError,socket.timeout,TimeoutError):raise APIError('API connection or timeout error') from None
        except (json.JSONDecodeError,UnicodeDecodeError):raise APIError('Invalid JSON API response') from None
    def ensure_prices(self,deadline):
        if self.input_price is not None:return
        data=self._request('/models',timeout=min(15,max(.1,deadline-time.monotonic())),auth=False)
        try:
            row=next(x for x in data['data'] if x['id']==self.model);p=row['pricing']
            a=money(p['prompt']);b=money(p['completion'])
            if money(p.get('request',0))!=0:raise ValueError()
            # Accommodate provider variation but enforce these caps in every request.
            self.input_price=a*Decimal('1.25');self.output_price=b*Decimal('1.25')
        except (KeyError,StopIteration,TypeError,ValueError,BudgetError):
            raise APIError('Cannot verify model token prices; supply explicit price caps for development',False) from None
    def complete(self,messages,budget,deadline,max_tokens=3072):
        remaining=deadline-time.monotonic()
        if remaining<=.2:raise APIError('Question time budget exhausted',False)
        self.ensure_prices(deadline)
        # UTF-8 bytes + ample message framing allowance provide a deliberately
        # conservative token bound for the text-only requests used here.
        nbytes=sum(len(m['content'].encode('utf-8')) for m in messages)+1024+256*len(messages)
        upper=self.input_price*nbytes+self.output_price*max_tokens
        token=budget.reserve(upper);actual=None
        try:
            payload={'model':self.model,'messages':messages,'temperature':0,'max_tokens':max_tokens,
                     'stream':False,'response_format':{'type':'json_object'},
                     'provider':{'max_price':{'prompt':float(self.input_price*1000000),
                                               'completion':float(self.output_price*1000000),'request':0}}}
            self.calls+=1
            data=self._request('/chat/completions',payload,timeout=min(75,max(.1,deadline-time.monotonic())))
            usage=data.get('usage') or {};self.last_usage=usage
            if usage.get('cost') is not None:actual=money(usage['cost'])
            elif isinstance(usage.get('prompt_tokens'),int) and isinstance(usage.get('completion_tokens'),int):
                actual=self.input_price*usage['prompt_tokens']+self.output_price*usage['completion_tokens']
            self.prompt_tokens+=max(0,int(usage.get('prompt_tokens',0)))
            self.completion_tokens+=max(0,int(usage.get('completion_tokens',0)))
            details=usage.get('completion_tokens_details') or {}
            reasoning=details.get('reasoning_tokens') if isinstance(details,dict) else None
            if type(reasoning)==int and reasoning>=0:self.reasoning_tokens+=reasoning
            else:self.reasoning_usage_complete=False
            if type(usage.get('prompt_tokens'))!=int:self.reasoning_usage_complete=False
            if data.get('model') not in (None,self.model):raise APIError('Unexpected returned model',False)
            if 'error' in data:raise APIError('API returned an error object')
            choice=data.get('choices',[{}])[0]
            if choice.get('finish_reason')!='stop':raise APIError('Completion incomplete or blocked')
            content=choice.get('message',{}).get('content')
            if not isinstance(content,str) or not content.strip():raise APIError('Empty completion')
            return content
        except (KeyError,IndexError,TypeError,ValueError) as e:
            if isinstance(e,BudgetError):raise
            raise APIError('Malformed API response') from None
        finally:
            # A failed/timeout request may have consumed tokens without reporting usage.
            if actual is None:self.reasoning_usage_complete=False
            budget.settle(token,actual)
