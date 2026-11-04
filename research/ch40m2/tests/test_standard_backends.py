from __future__ import annotations
import json,os,sys,unittest
from pathlib import Path
try:
 import numpy as np
 import scipy
except ImportError:
 raise unittest.SkipTest('CH40M research-only SciPy/NumPy dependencies unavailable; base Cognitum remains stdlib-first')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'source'))
from frozen40m2 import load_cases, float_objective, validated_candidate
from model_equivalence import explicit_firth_float
from flint_arb_backend import dyadic, BackendUnavailable, compare_point
from ibex_model import ibex_text,write_model,probe_ibex
from ipopt_backend import run_ipopt
from scip_backend import run_scip
TRACES=Path(os.environ.get('CH40M_TRACES','/mnt/data/CH40K/traces')); PINS=Path(os.environ.get('CH40M_PINS','/mnt/data/CH40K/CH40K_ACCEPTANCE.json'))
REF=Path(os.environ.get('CH40M_REFERENCE_DIR','/mnt/data/CH40J/source'))

class AdoptionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not TRACES.is_dir() or not PINS.is_file():raise unittest.SkipTest('Frozen original CH40K raw traces unavailable; never substitute synthetic fixtures')
  cls.cases=load_cases(TRACES,PINS)
 def test_all_exact_original_pins(self):
  self.assertEqual(len(self.cases),15)
  self.assertEqual(len({v.source_sha256 for v in self.cases}),15)
 def test_all_float_objectives_evaluable(self):
  for c in self.cases:
   self.assertTrue(validated_candidate(c,c.incumbent))
   self.assertTrue(np.isfinite(float_objective(c,c.incumbent)))
 def test_generator_15_models(self):
  for c in self.cases:
   txt=ibex_text(c)
   self.assertIn('Minimize',txt)
   self.assertEqual(txt.count('function W'),len(c.certificate['model']['rows']))
   self.assertEqual(txt.count('function L'),len(c.certificate['model']['rows']))
   self.assertIn('Constraints',txt)
   self.assertIn('ln(',txt)
 def test_no_false_global_certificates(self):
  c=self.cases[0]
  self.assertEqual(run_ipopt(c).get('global_certificate',False),False)
  self.assertEqual(run_scip(c).get('global_certificate',False),False)
 def test_flint_fail_closed_or_crosschecked(self):
  c=self.cases[0]
  try:
   result=compare_point(c,c.incumbent,REF)
   self.assertTrue(result['overlap_independent_rational'])
  except BackendUnavailable:
   pass
 def test_explicit_firth_matches_numpy_structure(self):
  for c in self.cases:
   val=explicit_firth_float(c.certificate,c.incumbent)
   self.assertAlmostEqual(val,float_objective(c,c.incumbent),places=8)
 def test_changed_data_refusal(self):
  import tempfile
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp);(f/'traces').mkdir()
   for i,c in enumerate(self.cases):
    p=TRACES/(c.name+'_127_original_mpfr_trace.json')
    (f/'traces'/p.name).symlink_to(p)
   altered=f/'traces'/(self.cases[0].name+'_127_original_mpfr_trace.json')
   altered.unlink();altered.write_bytes((TRACES/altered.name).read_bytes()+b'\n')
   with self.assertRaises(ValueError):load_cases(f/'traces',PINS)

if __name__=='__main__':unittest.main()

