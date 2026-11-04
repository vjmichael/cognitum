"""No optional solver dependencies or frozen scientific fixtures required.
Checks the adapter's import safety and fail-closed primitives, NOT numerical acceptance.
"""
from __future__ import annotations
import ast,sys,unittest
from pathlib import Path
from fractions import Fraction as F
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'source'))

class OfflineContracts(unittest.TestCase):
 def test_all_source_files_parse_as_python(self):
  files=list((R/'source').glob('*.py'))
  self.assertGreaterEqual(len(files),8)
  for file in files:ast.parse(file.read_text(),filename=file.name)
 def test_exact_dyadic_endpoint_without_flint(self):
  from flint_arb_backend import dyadic
  class Endpoint:
   def __init__(self,m,e):self.m,self.e=m,e
   def man_exp(self):return self.m,self.e
  self.assertEqual(dyadic(Endpoint(7,-3)),F(7,8))
  self.assertEqual(dyadic(Endpoint(-9,4)),F(-144,1))
 def test_ibex_generator_rejects_nonfinite_constant(self):
  from ibex_model import assert_decimal_string
  for s in ('NaN','Infinity','-Infinity'):
   with self.assertRaises(ValueError):assert_decimal_string(s)
 def test_flint_missing_not_silently_approximated(self):
  # Only import the optional wrapper; ensure missing native import never returns an approximate value.
  from flint_arb_backend import arb_point,BackendUnavailable
  try:
   import flint
  except ImportError:
   with self.assertRaises(BackendUnavailable):arb_point(None,None)

if __name__=='__main__':unittest.main()

