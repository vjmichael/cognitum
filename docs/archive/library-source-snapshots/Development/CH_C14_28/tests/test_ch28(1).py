"""CH28 original-data bounded-proof, source provenance and adversarial tests."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
D=Path(__file__).resolve().parents[1];BASE=D.parent
for sub in ('CH_C14_24','CH_C14_26','CH_C14_27'):sys.path.insert(0,str(BASE/sub))
sys.path.insert(0,str(D))
from solver28 import solve,bound_by_mode
from verifier28 import verify
from coupled27 import CoupledObjective
from verified_bnb import logistic_model
import mpfr_interval as impl

class CH28Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.proto=json.loads((D/'frozen_protocol.json').read_text())
  cls.cid='zero_balanced_n80_i00'
  cls.data_path=BASE/'CH_C14_25'/'inputs'/f'{cls.cid}.json'
  cls.inp=json.loads(cls.data_path.read_text())
  cls.q=json.loads((BASE/'CH_C14_27'/'frozen_duals.json').read_text())[cls.cid]
  cls.runproto={**cls.proto,'node_budget_per_case':7}
  cls.cert=solve(cls.inp,cls.runproto,cls.q)
  cls.replay=verify(cls.cert,cls.inp,cls.runproto,cls.q)
 def test_protocol_integrity(self):
  self.assertEqual(hashlib.sha256((D/'frozen_protocol.json').read_bytes()).hexdigest(),(D/'frozen_protocol.sha256').read_text().split()[0])
  for filename,digest in self.proto['solver_source_sha256'].items():
   self.assertEqual(hashlib.sha256((D/filename).read_bytes()).hexdigest(),digest)
  for filename,digest in self.proto['dependency_source_sha256'].items():
   self.assertEqual(hashlib.sha256((BASE/filename).read_bytes()).hexdigest(),digest)
  self.assertEqual(hashlib.sha256(self.data_path.read_bytes()).hexdigest(),self.proto['original_case_sha256'][self.cid])
 def test_7node_original_certificate_is_unresolved(self):
  self.assertEqual(len(self.cert['nodes']),7)
  self.assertEqual(self.cert['status'],'UNRESOLVED_REFUSE_CERTIFICATION')
  self.assertEqual(self.replay['replay_status'],'REPLAYED_BUT_UNRESOLVED')
  self.assertEqual(self.cert['counters']['cached_leaf'],self.cert['leaf_count'])
 def test_branch_and_bound_uses_safe_direct_when_uncoupled(self):
  impl.PRECISION=224
  m=CoupledObjective(logistic_model(self.inp['rows']),self.q)
  m.set_tangents(self.inp['seeds'][:1])
  for n in self.cert['nodes']:
   if n['bound_mode']=='direct':
    upper,_=bound_by_mode(m,n['effective_box'],'direct')
    self.assertTrue(upper.hi.as_float() >= n['upper_bound_ceil_display']-1e-8)
 def test_false_global_claim_rejected(self):
  x=copy.deepcopy(self.cert);x['status']='CERTIFIED_BOUNDED_GAP'
  with self.assertRaises(ValueError):verify(x,self.inp,self.runproto,self.q)
 def test_forged_partition_rejected(self):
  x=copy.deepcopy(self.cert);x['nodes'][1]['box'][0][0]='-9.99'
  with self.assertRaises(ValueError):verify(x,self.inp,self.runproto,self.q)
 def test_unknown_upper_method_rejected(self):
  x=copy.deepcopy(self.cert)
  leaf=next(n for n in x['nodes'] if 'children' not in n)
  leaf['bound_mode']='unverified_cache'
  with self.assertRaises(ValueError):verify(x,self.inp,self.runproto,self.q)
 def test_float_upper_display_has_no_authority(self):
  x=copy.deepcopy(self.cert)
  for n in x['nodes']:n['upper_bound_ceil_display']=-100000000
  x['gap_upper_display']=-999999999
  v=verify(x,self.inp,self.runproto,self.q)
  self.assertAlmostEqual(v['gap_upper_display'],self.replay['gap_upper_display'],places=9)
 def test_incumbent_outside_root_rejected(self):
  x=copy.deepcopy(self.cert);x['incumbent'][0]='999'
  with self.assertRaises(ValueError):verify(x,self.inp,self.runproto,self.q)
if __name__=='__main__':unittest.main()