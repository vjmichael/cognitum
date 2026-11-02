"""CH27 original-data mathematical and fail-closed regression tests."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
from decimal import Decimal
D=Path(__file__).resolve().parents[1];ROOT=D.parent;C=ROOT/'CH_C14_25'
sys.path.insert(0,str(D))
from coupled27 import CoupledObjective,is_spd_exact
from interval_newton27 import contract,replay_check,interior
from verified_bnb import logistic_model
from mpfr_interval import Interval as I,MP
from solver27 import solve
from verifier27 import verify
P=json.loads((D/'frozen_protocol.json').read_text())
Qs=json.loads((D/'frozen_duals.json').read_text())

class CH27Regression(unittest.TestCase):
 def _load(self,id):return json.loads((C/'inputs'/f'{id}.json').read_text())
 def test_cohort_uses_all_original_15_digest_matches(self):
  self.assertEqual(len(P['case_input_sha256']),15)
  for cid,digest in P['case_input_sha256'].items():
   self.assertEqual(hashlib.sha256((C/'inputs'/f'{cid}.json').read_bytes()).hexdigest(),digest)
   self.assertTrue(all(is_spd_exact(q) for q in Qs[cid]))
 def test_indefinite_or_asymmetric_dual_refused(self):
  self.assertFalse(is_spd_exact([['1','2'],['2','1']]))
  self.assertFalse(is_spd_exact([['1','0.1'],['0','1']]))
  p=self._load('zero_balanced_n80_i00')
  with self.assertRaises(ValueError):CoupledObjective(logistic_model(p['rows']),[[['1','0','0'],['0','-1','0'],['0','0','1']]])
 def test_coupled_root_bounds_original_feasible_points(self):
  for cid in ['zero_balanced_n80_i00','rare_5pct_n80_i00','quasi_separated_n160_i00','zero_imbalanced_n160_i05']:
   p=self._load(cid)
   m=CoupledObjective(logistic_model(p['rows']),Qs[cid]);m.set_tangents(p['seeds'][:1])
   root=m.coupled_upper(p['bounds'])
   for s in p['seeds']:
    f=m.objective([I(z) for z in s])[0]
    self.assertGreaterEqual(root.cmp(f.lo),0)
 def test_newton_contracts_original_narrow_root_and_replays(self):
  p=self._load('zero_balanced_n80_i00');m=CoupledObjective(logistic_model(p['rows']),Qs['zero_balanced_n80_i00'])
  seed=p['seeds'][0]
  box=[[str(Decimal(s)-Decimal('.001')),str(Decimal(s)+Decimal('.001'))] for s in seed]
  r=contract(m,box,p['bounds'])
  self.assertEqual(r['status'],'CONTRACTED');self.assertLess(r['volume_ratio_display'],1)
  self.assertTrue(replay_check(m,box,p['bounds'],r))
  bad=copy.deepcopy(r);bad['box'][0][0]=box[0][1]
  with self.assertRaises(ValueError):replay_check(m,box,p['bounds'],bad)
 def test_boundary_not_prunable(self):
  p=self._load('zero_balanced_n80_i00');m=CoupledObjective(logistic_model(p['rows']),Qs['zero_balanced_n80_i00'])
  self.assertEqual(contract(m,p['bounds'],p['bounds'])['status'],'NOT_INTERIOR')
 def test_verified_partition_and_fake_certification(self):
  p=self._load('zero_balanced_n80_i00');q=Qs['zero_balanced_n80_i00']
  protocol=dict(P,node_budget_per_case=3,max_newton_evaluations_per_case=0)
  cert=solve(p,protocol,q)
  r=verify(cert,p,protocol,q)
  self.assertEqual(r['replay_status'],'REPLAYED_BUT_UNRESOLVED')
  f=copy.deepcopy(cert);f['status']='CERTIFIED_BOUNDED_GAP'
  with self.assertRaisesRegex(ValueError,'not proven'):verify(f,p,protocol,q)
  f=copy.deepcopy(cert);f['nodes'][1]['box'][0][0]='-9.999'
  with self.assertRaisesRegex(ValueError,'Partition'):verify(f,p,protocol,q)
  f=copy.deepcopy(cert);f['dual_matrices'][0][0][0]='-1'
  with self.assertRaisesRegex(ValueError,'dual'):verify(f,p,protocol,q)

if __name__=='__main__':unittest.main()
