import csv
import json
import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook

from excelqa.workbook import Book
from excelqa.expressions import Evaluator, PlanError, format_answer
from excelqa.contract import read_queries, write_results, InputError
from excelqa.budget import Budget, BudgetError


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        wb = Workbook(); s = wb.active; s.title = 'Data 1'
        s.append(['Industry', 'Employees', 'Rate'])
        s.append(['Construction', 1055, 3.145])
        s.append(['Manufacturing', 1163, 2.5])
        s.merge_cells('B5:C5'); s['B5'] = 'Merged header'
        wb.save(self.root / 'table.xlsx')
        self.book = Book(self.root / 'table.xlsx')

    def test_sum_uses_current_values_and_records_evidence(self):
        ev = Evaluator(self.book)
        self.assertEqual(ev.run({'op':'sum','args':[{'cell':'Data 1!B2'}, {'cell':'Data 1!B3'}]}), 2218)
        self.assertEqual(set(ev.evidence), {'Data 1!B2','Data 1!B3'})

    def test_cell_reference_must_exist(self):
        with self.assertRaises(PlanError): Evaluator(self.book).run({'cell':'missing!B2'})

    def test_no_literal_number_answers_or_code_execution(self):
        for expr in [2218, {'literal':2218}, {'op':'exec','args':['print(1)']}]:
            with self.assertRaises(PlanError): Evaluator(self.book).run(expr)

    def test_argmax_returns_source_label(self):
        expr={'op':'argmax','items':[{'label':{'cell':'Data 1!A2'},'value':{'cell':'Data 1!B2'}},
                                    {'label':{'cell':'Data 1!A3'},'value':{'cell':'Data 1!B3'}}]}
        self.assertEqual(Evaluator(self.book).run(expr),'Manufacturing')

    def test_csv_quotes_comma_and_preserves_exact_ids(self):
        dest=self.root/'out.csv'
        write_results(dest,[{'id':'001','answer':'40.60, 37.60'}])
        with dest.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
        self.assertEqual(rows,[{'id':'001','answer':'40.60, 37.60'}])

    def test_duplicate_ids_are_rejected(self):
        q=self.root/'q.json'; q.write_text(json.dumps([{'id':1,'file_name':'a.xlsx','query':'x'},
                                                    {'id':'1','file_name':'a.xlsx','query':'y'}]))
        with self.assertRaises(InputError): read_queries(q)

    def test_merged_header_keeps_anchor(self):
        self.assertEqual(self.book.sheets[0].expanded(5,3),'Merged header')
        self.assertIsNone(self.book.sheets[0].value(5,3))

    def test_half_up_and_strict_integer(self):
        self.assertEqual(format_answer(3.145, {'type':'fixed','decimals':2}), '3.15')
        with self.assertRaises(PlanError):format_answer(3.14, {'type':'integer'})

    def test_budget_reserves_before_request(self):
        b=Budget(limit='0.09')
        token=b.reserve('0.06')
        with self.assertRaises(BudgetError): b.reserve('0.04')
        b.settle(token,'0.02')
        self.assertEqual(str(b.spent),'0.02')

    def test_unknown_cost_is_not_zero(self):
        b=Budget(limit='0.09'); t=b.reserve('0.04'); b.settle(t,None)
        self.assertEqual(str(b.spent),'0.04')

    def test_table_ranking_with_row_bound_column_references(self):
        expr={'op':'table','sheet':'Data 1','row_range':[2,3],
              'sort_by':{'col':'B'},'descending':True,'take':1,'value':{'col':'A'}}
        self.assertEqual(Evaluator(self.book).run(expr),['Manufacturing'])

    def test_column_reference_outside_table_rejected(self):
        with self.assertRaises(PlanError):Evaluator(self.book).run({'col':'B'})

    def test_conditional_count_uses_threshold_from_question(self):
        expr={'op':'count','args':[{'op':'table','sheet':'Data 1','row_range':[2,3],
              'where':{'op':'gt','args':[{'col':'B'},{'constant':1100}]},'value':{'col':'A'}}]}
        self.assertEqual(Evaluator(self.book,query='How many have more than 1100 employees?').run(expr),1)

    def test_filter_constant_must_be_grounded_in_question(self):
        with self.assertRaises(PlanError):Evaluator(self.book,query='What is the value?').run({'constant':987654})

    def test_no_matching_rows_count_is_zero(self):
        expr={'op':'count','args':[{'op':'table','sheet':'Data 1','row_range':[2,3],
              'where':{'op':'gt','args':[{'col':'B'},{'constant':9999}]},'value':{'col':'A'}}]}
        self.assertEqual(Evaluator(self.book,query='How many exceed 9999?').run(expr),0)


if __name__=='__main__': unittest.main()
