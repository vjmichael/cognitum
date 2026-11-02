"""Additional CH27 proof-boundary and source-freeze tests using original CH23 fixtures."""
import json,hashlib,sys,copy,unittest
from pathlib import Path
from decimal import Decimal
D=Path(__file__).resolve().parents[1];BASE=D.parent
sys.path.insert(0,str(D));sys.path.insert(0,str(BASE/'CH_C14_24'))
from coupled27 import CoupledObjective
from interval_newton27 import contract,replay_check
from verified_bnb import logistic_model
from mpfr_interval import Interval as I
P=json.loads((D/'frozen_protocol.json').read_text());Q=json.loads((D/'frozen_duals.json').read_text())

class AdditionalProofTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cid='zero_balanced_n80_i00'
  cls.ref=json.loads((BASE/'CH_C14_25'/'inputs'/f'{cid}.json').read_text())
  cls.m=CoupledObjective(logistic_model(cls.ref['rows']),Q[cid])
 def test_pinned_sources_untouched(self):
  for path,digest in P['source_sha256'].items():
   self.assertEqual(hashlib.sha256((D/path).read_bytes()).hexdigest(),digest)
  for path,digest in P['dependency_sha256'].items():
   self.assertEqual(hashlib.sha256((BASE/path).read_bytes()).hexdigest(),digest)
  self.assertEqual(hashlib.sha256((D/'frozen_duals.json').read_bytes()).hexdigest(),P['dual_matrices_sha256'])
 def test_forged_newton_matrix_cannot_justify_saved_shrink(self):
  s=self.ref['seeds'][0]
  box=[[str(Decimal(v)-Decimal('.001')),str(Decimal(v)+Decimal('.001'))] for v in s]
  receipt=contract(self.m,box,self.ref['bounds']);self.assertEqual(receipt['status'],'CONTRACTED')
  counterfeit=copy.deepcopy(receipt)
  counterfeit['C']=[['0','0','0'],['0','0','0'],['0','0','0']]
  with self.assertRaises(ValueError):replay_check(self.m,box,self.ref['bounds'],counterfeit)
 def test_excluded_original_interior_region_is_rechecked(self):
  box=[['-8','-7.9'],['0','0.01'],['0','0.01']]
  r=contract(self.m,box,self.ref['bounds'])
  self.assertEqual(r['status'],'NO_STATIONARY')
  self.assertTrue(replay_check(self.m,box,self.ref['bounds'],r))
 def test_global_root_boundary_always_preserved(self):
  for box in [self.ref['bounds'],[['-10','-9.5'],['-1','1'],['-1','1']],
              [['-5','-4'],['-5','-4'],['0','0.1']]]:
   self.assertEqual(contract(self.m,box,self.ref['bounds'])['status'],'NOT_INTERIOR')

if __name__=='__main__':unittest.main()
