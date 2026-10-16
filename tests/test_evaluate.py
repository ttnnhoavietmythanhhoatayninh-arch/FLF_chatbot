import csv,json,tempfile,unittest
from pathlib import Path
from tools.evaluate import read_reference

class EvaluationTests(unittest.TestCase):
    def test_reads_btc_answers_json_and_keeps_decimal_text(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'answers.json';p.write_text(json.dumps([{'id':1,'answer':'0.70'},{'id':2,'answer':'Group, 4.3'}]))
            self.assertEqual(read_reference(p),{'1':'0.70','2':'Group, 4.3'})
    def test_duplicate_reference_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'answers.json';p.write_text(json.dumps([{'id':1,'answer':'A'},{'id':1,'answer':'B'}]))
            with self.assertRaises(ValueError):read_reference(p)
