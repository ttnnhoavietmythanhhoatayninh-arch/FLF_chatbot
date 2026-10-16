import csv
import json
import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook
from excelqa.workbook import Book
from excelqa.contract import write_results, read_queries, InputError
from excelqa.expressions import Evaluator, format_answer, inferred_format
from excelqa.solver import execute
from excelqa.local import local_plan

class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def book(self,rows):
        w=Workbook();s=w.active;s.title='Changed'
        for r in rows:s.append(r)
        p=self.root/'random.xlsx';w.save(p);return Book(p)
    def test_numeric_ids_sorted_without_losing_original_representation(self):
        p=self.root/'out.csv';write_results(p,[{'id':10,'answer':'A'},{'id':'002','answer':''},{'id':1,'answer':'C'}])
        with p.open(newline='') as f:self.assertEqual([r['id'] for r in csv.DictReader(f)],['1','002','10'])
    def test_numeric_aliases_are_duplicate(self):
        p=self.root/'q.json';p.write_text(json.dumps([{'id':x,'file_name':'x.xlsx','query':'Q'} for x in [2,'002']]))
        with self.assertRaises(InputError):read_queries(p)
    def test_compound_answer_formats_only_numeric_component(self):
        from decimal import Decimal
        self.assertEqual(format_answer(['Group',Decimal('0.7')],{'type':'fixed','decimals':2}),'Group, 0.70')
    def test_one_three_and_multilingual_decimal_requirements(self):
        for q,n in [('exactly one decimal place',1),('rounded to three decimal places',3),('đúng một chữ số thập phân',1),('avec une décimale',1),('소수점 둘째 자리까지',2),('保留一位小数',1)]:
            self.assertEqual(inferred_format(q),{'type':'fixed','decimals':n})
    def test_tuple_format_preserves_integer_year(self):
        self.assertEqual(format_answer([2025,0.7],{'type':'tuple','items':[{'type':'integer'},{'type':'fixed','decimals':2}]}),'2025, 0.70')
    def test_model_tuple_preserves_year_when_only_difference_requires_decimals(self):
        b=self.book([['Year','Value'],[2025,0.7]])
        plan={'expression':{'op':'list','args':[{'cell':'Changed!A2'},{'cell':'Changed!B2'}]},'format':{'type':'tuple','items':[{'type':'integer'},{'type':'fixed','decimals':2}]}}
        self.assertEqual(execute(b,plan,'Answer as year, difference with exactly two decimal places for the difference.')[0],'2025, 0.70')
    def test_numeric_filter_skips_missing_values(self):
        b=self.book([['Code','Rate'],['123456',6],['234567','..'],['23',9]])
        e={'op':'count','args':[{'op':'table','sheet':'Changed','row_range':[2,4], 'where':{'op':'and','args':[{'op':'is_numeric','args':[{'col':'B'}]},{'op':'gt','args':[{'col':'B'},{'constant':5}]}]},'value':{'col':'A'}}]}
        self.assertEqual(Evaluator(b,query='above 5').run(e),2)
    def test_generic_naics_count_uses_changed_values_and_exact_digit_depth(self):
        b=self.book([['Industry','NAICS code','Total recordable cases'],['Alpha',123456,7],['Parent',1234,10],['Beta',234567,2],['Gamma',345678,8]])
        q='How many industries with a 6-digit NAICS code have a total recordable cases incidence rate above 6.0? Answer with only the integer.'
        p=local_plan(b,q);self.assertIsNotNone(p);self.assertEqual(execute(b,p,q)[0],'2')
    def test_generic_annual_ranking_excludes_quarters(self):
        b=self.book([['Year','Sector A'],[2010,12],[2011,15],['2011 Q1',90],[2012,8]])
        q="Using the annual figures (rows labelled with a year, not with a quarter), in which year did the 'Sector A' sector have the highest output per job? Answer with only the year."
        p=local_plan(b,q);self.assertIsNotNone(p);self.assertEqual(execute(b,p,q)[0],'2011')
    def test_percentage_ratio_uses_changed_values(self):
        b=self.book([['Trình độ','nam','nữ'],['Nhóm học A',80,30]])
        q='Ở nhóm Nhóm học A, thu nhập của nữ bằng bao nhiêu phần trăm so với nam? Làm tròn đến một chữ số thập phân.'
        p=local_plan(b,q);self.assertIsNotNone(p);self.assertEqual(execute(b,p,q)[0],'37.5')
    def test_employment_series_changed_years_and_values(self):
        b=self.book([['Year','Employed',None], [None,'Total','Agriculture'],[2018,100,3],[2019,120,9],[2020,70,4]])
        q='In which year did the number of employed people fall the most compared with the previous year, and by how many thousand? Answer as year, decrease, as integers.'
        p=local_plan(b,q);self.assertIsNotNone(p);self.assertEqual(execute(b,p,q)[0],'2020, 50')
        q='Find the year in which employment in agriculture was the highest and state the total employed population in that year. Answer as year, total employed, as integers.'
        p=local_plan(b,q);self.assertIsNotNone(p);self.assertEqual(execute(b,p,q)[0],'2019, 120')
    def test_vietnamese_gap_does_not_include_total(self):
        b=self.book([['Trình độ','nam','nữ'],['Tổng thu nhập',1000,1],['Nhóm A',90,30],['Nhóm B',70,50]])
        q='Giữa các nhóm trình độ học vấn (không tính dòng tổng), chênh lệch thu nhập tiền lương và tiền công trung vị giữa nam và nữ lớn nhất là bao nhiêu đô la? Chỉ trả lời bằng số nguyên, không có dấu phẩy.'
        p=local_plan(b,q);self.assertIsNotNone(p);self.assertEqual(execute(b,p,q)[0],'60')

class AnnualFilterTests(unittest.TestCase):
    def book(self, values):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        w=Workbook();s=w.active;s.title='Random sheet'
        s.append(['Year','Civilian labor force',None,None,None])
        s.append([None,'Total','Unemployed','Employed','Unemployed'])
        s.append([None,None,'Percent of labor force','Percent of population','Number'])
        for row in values:s.append(row)
        p=Path(tmp.name)/'renamed.xlsx';w.save(p);return Book(p)
    def test_year_filter_recalculates_changed_thresholds_and_reordered_columns(self):
        b=self.book([[1991,800,8,59,7],[1992,600,9,60,4],[1993,500,2,51,3]])
        q='Identify the year when the unemployment rate exceeded 7% and the total civilian labor force was below 700 (in thousands). Answer with only the year.'
        p=local_plan(b,q);self.assertIsNotNone(p)
        self.assertEqual(execute(b,p,q)[0],'1992')
    def test_unemployed_number_is_not_rate(self):
        b=self.book([[1991,800,8,59,7],[1992,600,9,60,4],[1993,500,2,51,3]])
        q='In which year did the number of unemployed individuals (in thousands) drop below 5 while the employed percentage of the population was above 55%? Answer with only the year.'
        p=local_plan(b,q);self.assertIsNotNone(p)
        self.assertEqual(execute(b,p,q)[0],'1992')
    def test_ambiguous_year_filter_defers_instead_of_guessing(self):
        b=self.book([[1991,600,8,59,7],[1992,500,9,60,4]])
        q='Identify the year when the unemployment rate exceeded 7% and the total civilian labor force was below 700 (in thousands). Answer with only the year.'
        from excelqa.structured import annual_thresholds
        self.assertIsNone(annual_thresholds(b.sheets[0],q))

if __name__=='__main__':unittest.main()
