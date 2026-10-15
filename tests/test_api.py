import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from excelqa.api import OpenRouterClient, APIError
from excelqa.budget import Budget

class Handler(BaseHTTPRequestHandler):
    status=200
    response={}
    received=[]
    def log_message(self,*a):pass
    def do_GET(self):
        payload=json.dumps({'data':[{'id':'qwen/qwen3.7-flash','pricing':{'prompt':'0.00000003','completion':'0.00000013','request':'0'}}]}).encode()
        self.send_response(200);self.end_headers();self.wfile.write(payload)
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.__class__.received.append(body)
        payload=json.dumps(self.__class__.response).encode()
        self.send_response(self.__class__.status);self.send_header('Content-Type','application/json')
        self.end_headers();self.wfile.write(payload)

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def client(self):
        return OpenRouterClient('not-a-real-key','qwen/qwen3.7-flash',
             f'http://127.0.0.1:{self.server.server_port}/api/v1',input_price='0.000001',output_price='0.000001',allow_local=True)
    def test_posts_configured_model_and_accounts_cost(self):
        Handler.status=200;Handler.response={'choices':[{'finish_reason':'stop','message':{'content':'{"expression":{"cell":"S!A1"}}'}}],
                                           'usage':{'prompt_tokens':20,'completion_tokens':10,'cost':0.00003}}
        b=Budget();client=self.client();text=client.complete([{'role':'user','content':'test'}],b,time.monotonic()+5,max_tokens=100)
        self.assertIn('expression',text);self.assertEqual(str(b.spent),'0.00003')
        self.assertEqual(Handler.received[-1]['model'],'qwen/qwen3.7-flash')
    def test_401_does_not_expose_key_or_response_body(self):
        Handler.status=401;Handler.response={'error':'not-a-real-key'}
        with self.assertRaises(APIError) as e:self.client().complete([{'role':'user','content':'test'}],Budget(),time.monotonic()+5)
        self.assertNotIn('not-a-real-key',str(e.exception));self.assertFalse(e.exception.retryable)
    def test_truncated_completion_is_rejected(self):
        Handler.status=200;Handler.response={'choices':[{'finish_reason':'length','message':{'content':'{"expression":'}}],
                                           'usage':{'cost':0.00001,'prompt_tokens':10,'completion_tokens':20}}
        with self.assertRaises(APIError):self.client().complete([{'role':'user','content':'x'}],Budget(),time.monotonic()+5)
    def test_unapproved_model_rejected(self):
        with self.assertRaises(ValueError):OpenRouterClient('x','other/model','https://openrouter.ai/api/v1')

    def test_fetches_live_pricing_metadata_before_paid_request(self):
        c=OpenRouterClient('x','qwen/qwen3.7-flash',f'http://127.0.0.1:{self.server.server_port}/api/v1',allow_local=True)
        c.ensure_prices(time.monotonic()+5)
        self.assertGreater(float(c.input_price),0)
        self.assertEqual(c.calls,0)

    def test_missing_usage_reserves_upper_bound(self):
        Handler.status=200;Handler.response={'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
        b=Budget();self.client().complete([{'role':'user','content':'test'}],b,time.monotonic()+5,max_tokens=100)
        self.assertGreater(float(b.spent),0)

if __name__=='__main__':unittest.main()
