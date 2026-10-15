import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook
from excelqa.contract import check_output,workbook_path,InputError
from excelqa.budget import Budget,BudgetError
from excelqa.solver import solve,SolveError
from excelqa.workbook import Book

class SafetyTests(unittest.TestCase):
    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'input').mkdir();(p/'outside.xlsx').write_text('x')
            with self.assertRaises(InputError):workbook_path(p/'input','../outside.xlsx')
    def test_output_under_input_rejected(self):
        with self.assertRaises(InputError):check_output('/input/new.csv','/input/xlsx_files','/input/queries.json')
    def test_budget_over_point_one_rejected(self):
        with self.assertRaises(BudgetError):Budget('0.1001')
    def test_invalid_plan_repair_is_bounded(self):
        class Client:
            calls=0;prompt_tokens=0;completion_tokens=0
            def complete(self,messages,budget,deadline,max_tokens):
                self.calls+=1
                return '{"expression":{"cell":"Absent!Z9"}}'
        with tempfile.TemporaryDirectory() as d:
            w=Workbook();w.active.append(['A',1]);p=Path(d)/'x.xlsx';w.save(p)
            c=Client()
            with self.assertRaises(SolveError) as caught:solve(Book(p),'Question',c,'llm',time.monotonic()+5)
            self.assertEqual(c.calls,3)
            self.assertEqual(caught.exception.trace['attempts'],3)
            self.assertIn('cost_accounted_usd',caught.exception.trace)
    def test_large_context_refuses_instead_of_silent_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            w=Workbook();w.active['A1']='x'*5000;p=Path(d)/'x.xlsx';w.save(p)
            from excelqa.workbook import WorkbookError
            with self.assertRaises(WorkbookError):Book(p).context('q',max_bytes=1000)

if __name__=='__main__':unittest.main()
