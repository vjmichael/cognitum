import unittest,tempfile
from pathlib import Path
from cognitum.spatial_mot_adapter import read_mot,evaluate,MOTRejected

class MOTTests(unittest.TestCase):
 def test_parse_real_mot_format_on_constructed_fixture(self):
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'gt.txt';p.write_text('1,22,10,20,5,8,1,1,0.8\n2,22,12,20,5,8,1,1,0.8\n')
        rows,h=read_mot(p,kind='gt');self.assertEqual(len(rows),2);self.assertEqual(len(h),64)
 def test_reject_id_switch_and_report(self):
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'gt.txt';p.write_text('1,22,10,20,5,8,1,1,0.8\n2,22,12,20,5,8,1,1,0.8\n')
        q=Path(d)/'pred.txt';q.write_text('1,1,10,20,5,8,0.9\n2,2,12,20,5,8,0.9\n')
        a,_=read_mot(p,kind='gt');b,_=read_mot(q,kind='prediction');m=evaluate(a,b)
        self.assertEqual(m['id_switches_diagnostic'],1);self.assertAlmostEqual(m['global_idf1_diagnostic'],.5)
 def test_perfect_identity(self):
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'gt.txt';p.write_text('1,11,10,20,5,8,1,1,0.8\n2,11,12,20,5,8,1,1,0.8\n')
        a,_=read_mot(p,kind='gt');self.assertEqual(evaluate(a,a)['global_idf1_diagnostic'],1)
 def test_reject_invalid_box(self):
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'bad.txt';p.write_text('1,22,10,20,-5,8,1,1,0.8\n')
        with self.assertRaises(MOTRejected):read_mot(p,kind='gt')
 def test_prediction_requires_positive_id(self):
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'bad.txt';p.write_text('1,-1,10,20,5,8,1,1,0.8\n')
        with self.assertRaises(MOTRejected):read_mot(p,kind='prediction')

if __name__=='__main__':unittest.main()
