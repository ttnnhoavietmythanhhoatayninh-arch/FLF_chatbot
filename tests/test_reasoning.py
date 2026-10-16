import json,threading,time,unittest
from http.server import ThreadingHTTPServer
from test_api import Handler
from excelqa.api import OpenRouterClient
from excelqa.budget import Budget

class ReasoningTests(unittest.TestCase):
    def test_separates_reasoning_tokens_from_completion(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        self.addCleanup(t.join);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        Handler.status=200;Handler.response={'model':'qwen/qwen3.7-flash','choices':[{'finish_reason':'stop','message':{'content':'{}'}}], 'usage':{'cost':0.001,'prompt_tokens':20,'completion_tokens':12,'completion_tokens_details':{'reasoning_tokens':8}}}
        c=OpenRouterClient('test',base_url=f'http://127.0.0.1:{server.server_port}/api/v1',input_price='0.0000001',output_price='0.0000001',allow_local=True)
        c.complete([{'role':'user','content':'Q'}],Budget(),time.monotonic()+10)
        self.assertEqual(c.reasoning_tokens,8);self.assertTrue(c.reasoning_usage_complete)
