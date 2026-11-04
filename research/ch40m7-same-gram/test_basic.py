import os,sys,unittest
from fractions import Fraction as F
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'CH40M7'),str(ROOT/'CH40M6'),str(ROOT/'CH40L2'),str(ROOT/'CH40L'),str(ROOT/'CH40L3'),str(ROOT/'CH40M5'),str(ROOT/'CH40J/source')]
from mpfr_gram import at,decimal_bracket,weight_ceiling,log_frac_upper,upper
from compare_m6 import validate_original
from gram_psd import native_cap
from independent_psd_check import independent_bound
class Basic(unittest.TestCase):
 def test_decimal_brackets(self):
  for v in (F(1,7),F(-1,7),F(2,3),F(-2,3),F(0),F(2)**-200):
   l,h=map(F,decimal_bracket(v));self.assertLessEqual(l,v);self.assertGreaterEqual(h,v)
 def test_weight_rigorous(self):
  from rational_kernel40d import R
  for v in (F(0),F(1,7),F(-3,7),F(12),F(-100)):
   w=R(1)/(R(2)+R(v).exp()+R(-v).exp())
   self.assertGreaterEqual(weight_ceiling(v),w.hi-F(1,10**70))
 def test_gram_original(self):
  for name in ('quasi_separated_n80_i00','one_event_n160_i00'):
   trace,fr,_=validate_original(name);box=max(fr.values(),key=lambda x:x['cap'])['box'];c=trace['certificate']
   a=native_cap(c,box,256);b=upper(c,box);ref,_=independent_bound(c,box,ROOT/'CH40J/source')
   self.assertGreaterEqual(a['gram_upper'],ref)
   self.assertGreaterEqual(b['gram_upper'],ref-F(1,10**65))
   self.assertLess(abs(a['gram_upper']-b['gram_upper']),F(1,10**65))
if __name__=='__main__':unittest.main(verbosity=2)
