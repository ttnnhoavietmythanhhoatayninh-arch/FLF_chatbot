import contextlib
import csv
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook
import main
from excelqa.api import OpenRouterClient
from test_api import Handler

class EntrypointTests(unittest.TestCase):
    def fixture(self,root):
        inp=root/'input';inp.mkdir();w=Workbook();s=w.active;s.title='Inventory'
        s.append(['Product','Quantity']);s.append(['Blue',17]);s.append(['Red',25]);w.save(inp/'fresh.xlsx')
        q=root/'queries.json';q.write_text(json.dumps([{'id':'007','file_name':'fresh.xlsx','query':'How many red items are available? Answer with only the integer.'}]))
        return inp,q

    def test_all_six_btc_arguments_route_to_csv_via_http(self):
        import threading
        from http.server import ThreadingHTTPServer
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            Handler.status=200;Handler.response={'model':'qwen/qwen3.7-flash','choices':[{'finish_reason':'stop','message':{'content':json.dumps({'expression':{'cell':'Inventory!B3'}})}}],
                                               'usage':{'cost':0.0001,'prompt_tokens':50,'completion_tokens':20}}
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);inp,q=self.fixture(root);output=root/'output'/'submission.csv'
                before=(inp/'fresh.xlsx').read_bytes();errors=io.StringIO()
                def factory(key,model,base,*a):
                    return OpenRouterClient(key,model,f'http://127.0.0.1:{server.server_port}/api/v1',input_price='0.0000001',output_price='0.0000001',allow_local=True)
                args=['--xlsx-dir',str(inp),'--queries',str(q),'--output',str(output),
                      '--openrouter-key','secret-test-key','--openrouter-model','qwen/qwen3.7-flash',
                      '--openrouter-base-url','https://openrouter.ai/api/v1','--solver','llm']
                with patch('main.OpenRouterClient',side_effect=factory),contextlib.redirect_stderr(errors):code=main.main(args)
                self.assertEqual(code,0);self.assertNotIn('secret-test-key',errors.getvalue())
                with output.open(newline='',encoding='utf-8') as f:self.assertEqual(list(csv.DictReader(f)),[{'id':'007','answer':'25'}])
                self.assertEqual((inp/'fresh.xlsx').read_bytes(),before)
        finally:server.shutdown();server.server_close();thread.join()

    def test_unanswered_is_valid_empty_string_per_faq(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp,q=self.fixture(root);output=root/'submission.csv'
            with contextlib.redirect_stderr(io.StringIO()):code=main.main(['--xlsx-dir',str(inp),'--queries',str(q),'--output',str(output),'--solver','offline'])
            self.assertEqual(code,0)
            with output.open(newline='',encoding='utf-8') as f:self.assertEqual(list(csv.DictReader(f)),[{'id':'007','answer':''}])

    def test_offline_never_constructs_client_even_with_key(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp,q=self.fixture(root);output=root/'submission.csv';report=root/'report.json'
            with patch('main.OpenRouterClient',side_effect=AssertionError('Network forbidden')),contextlib.redirect_stderr(io.StringIO()):
                code=main.main(['--xlsx-dir',str(inp),'--queries',str(q),'--output',str(output),'--solver','offline','--openrouter-key','must-not-be-used','--report',str(report)])
            self.assertEqual(code,0)
            self.assertEqual(json.loads(report.read_text())['llm_calls'],0)
            self.assertIn('no API request made',json.loads(report.read_text())['records'][0]['error'])
            self.assertTrue(output.exists())

    def test_failed_workbook_does_not_poison_previous_workbook_cache(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir()
            w=Workbook();s=w.active;s.append(['Age','Construction','Manufacturing']);s.append(['TOTAL']);s.append(['20 to 24 years',7,12]);w.save(inp/'a.xlsx')
            (inp/'broken.xlsx').write_text('not a ZIP')
            question='What is the total number of employed persons aged 20 to 24 years in Construction and Manufacturing combined? Answer with only the integer.'
            q=root/'q.json';q.write_text(json.dumps([{'id':str(i),'file_name':f,'query':question} for i,f in enumerate(['a.xlsx','broken.xlsx','a.xlsx'])]))
            output=root/'submission.csv'
            with contextlib.redirect_stderr(io.StringIO()):code=main.main(['--xlsx-dir',str(inp),'--queries',str(q),'--output',str(output),'--solver','offline'])
            with output.open(newline='',encoding='utf-8') as f:answers=[r['answer'] for r in csv.DictReader(f)]
            self.assertEqual(code,2);self.assertEqual(answers,['19','','19'])

if __name__=='__main__':unittest.main()
