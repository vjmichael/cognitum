"""CH29 original-data directed-MPFR monotone cap and fail-closed replay tests."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
D=Path(__file__).resolve().parents[1];BASE=D.parent
sys.path.insert(0,str(D))
for folder in ('CH_C14_24','CH_C14_26','CH_C14_27'):sys.path.insert(0,str(BASE/folder))
from solver29 import solve
from verifier29 import verify
class InheritanceSafety(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=json.loads((D/'frozen_protocol.json').read_text());cls.p={**cls.p,'node_budget_per_case':7}
  cls.cid='zero_balanced_n80_i00'
  cls.inpath=BASE/'CH_C14_25'/'inputs'/(cls.cid+'.json')
  cls.inp=json.loads(cls.inpath.read_text())
  cls.duals=json.loads((BASE/'CH_C14_27'/'frozen_duals.json').read_text())[cls.cid]
  cls.cert=solve(cls.inp,cls.p,cls.duals)
  cls.replayed=verify(cls.cert,cls.inp,cls.p,cls.duals)
 def test_input_and_protocol_hashes(self):
  original=json.loads((D/'frozen_protocol.json').read_text())
  self.assertEqual(hashlib.sha256((D/'frozen_protocol.json').read_bytes()).hexdigest(),(D/'frozen_protocol.sha256').read_text().split()[0])
  self.assertEqual(hashlib.sha256(self.inpath.read_bytes()).hexdigest(),original['original_case_sha256'][self.cid])
  for path,h in original['solver_source_sha256'].items():
   self.assertEqual(hashlib.sha256((D/path).read_bytes()).hexdigest(),h)
 def test_verified_original_case_and_stronger_parent(self):
  self.assertEqual(len(self.cert['nodes']),7)
  self.assertEqual(self.cert['status'],'UNRESOLVED_REFUSE_CERTIFICATION')
  self.assertEqual(self.replayed['replay_status'],'REPLAYED_BUT_UNRESOLVED')
  self.assertGreater(self.cert['counters']['parent_cap_tighter'],0)
  self.assertEqual(self.replayed['ancestor_caps_recomputed'],7)
 def test_monotonic_cap_display(self):
  # Float is only displayed, but monotone at 160-bit MPFR must remain visible.
  for n in self.cert['nodes']:
   if n['parent_id'] is not None:
    p=self.cert['nodes'][n['parent_id']]
    self.assertLessEqual(n['upper_bound_ceil_display'],p['upper_bound_ceil_display'])
 def test_forged_parent_reference_rejected(self):
  x=copy.deepcopy(self.cert);x['nodes'][1]['parent_id']=None
  with self.assertRaises(ValueError):verify(x,self.inp,self.p,self.duals)
 def test_unknown_ancestor_mode_rejected(self):
  x=copy.deepcopy(self.cert);x['nodes'][0]['bound_mode']='stored_cache_only'
  with self.assertRaises(ValueError):verify(x,self.inp,self.p,self.duals)
 def test_false_certification_rejected(self):
  x=copy.deepcopy(self.cert);x['status']='CERTIFIED_BOUNDED_GAP'
  with self.assertRaises(ValueError):verify(x,self.inp,self.p,self.duals)
 def test_forged_partition_rejected(self):
  x=copy.deepcopy(self.cert);x['nodes'][1]['box'][0][0]='-9.5'
  with self.assertRaises(ValueError):verify(x,self.inp,self.p,self.duals)
 def test_fake_display_cap_has_no_effect(self):
  x=copy.deepcopy(self.cert)
  for node in x['nodes']:
   node['upper_bound_ceil_display']=-1e9;node['local_upper_bound_display']=-1e9
  x['gap_upper_display']=-1e9
  replay=verify(x,self.inp,self.p,self.duals)
  self.assertAlmostEqual(replay['gap_upper_display'],self.replayed['gap_upper_display'],places=10)
 def test_infeasible_incumbent_rejected(self):
  x=copy.deepcopy(self.cert);x['incumbent'][0]='9999'
  with self.assertRaises(ValueError):verify(x,self.inp,self.p,self.duals)
 def test_7_node_cpu_cap_keeps_proof_sound(self):
  p={**self.p,'cpu_budget_seconds':0.00001}
  cert=solve(self.inp,p,self.duals)
  replay=verify(cert,self.inp,p,self.duals)
  self.assertLessEqual(len(cert['nodes']),7)
  self.assertEqual(replay['replay_status'],'REPLAYED_BUT_UNRESOLVED')
if __name__=='__main__':unittest.main()
