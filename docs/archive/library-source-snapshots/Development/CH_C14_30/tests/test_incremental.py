"""CH30 safe incremental replay on *actual* original CH23 zero-event data."""
import copy,json,sys,unittest,hashlib
from pathlib import Path
D=Path(__file__).resolve().parents[1];BASE=D.parent
sys.path.insert(0,str(D));sys.path.insert(0,str(BASE/'CH_C14_29'))
from verifier30 import VerifiedSession,verify_full
from verifier29 import verify as verify29
from solver29 import solve

class IncrementalReplayTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cid='zero_balanced_n80_i00'
  cls.p=json.loads((BASE/'CH_C14_29/frozen_protocol.json').read_text())
  cls.inp=json.loads((BASE/'CH_C14_25/inputs'/f'{cls.cid}.json').read_text())
  cls.duals=json.loads((BASE/'CH_C14_27/frozen_duals.json').read_text())[cls.cid]
  cls.p7={**cls.p,'node_budget_per_case':7}
  cls.p15={**cls.p,'node_budget_per_case':15}
  cls.c7=solve(cls.inp,cls.p7,cls.duals)
  cls.c15=solve(cls.inp,cls.p15,cls.duals)
  assert len(cls.c7['nodes'])==7 and len(cls.c15['nodes'])==15
  cls.r7=verify29(cls.c7,cls.inp,cls.p7,cls.duals)
  cls.r15=verify29(cls.c15,cls.inp,cls.p15,cls.duals)
  cls.verified_seed=VerifiedSession()
  cls.seed_receipt=cls.verified_seed.verify(cls.c7,cls.inp,cls.p7,cls.duals)

 def _session(self):
  sess=VerifiedSession()
  # Test-only fixture derives from the already verified same-process seed.
  # The production-facing session API has no checkpoint import/export.
  sess._state=self.verified_seed._state
  self.assertEqual(self.seed_receipt['ancestor_caps_recomputed'],7)
  return sess
 def test_full_ch29_equivalence_7(self):
  r=verify_full(self.c7,self.inp,self.p7,self.duals)
  self.assertAlmostEqual(r['gap_upper_display'],self.r7['gap_upper_display'],places=12)
 def test_incremental_equivalence_15(self):
  s=self._session()
  inc=s.verify(self.c15,self.inp,self.p15,self.duals)
  self.assertEqual(inc['verified_prefix_nodes_reused'],7)
  self.assertEqual(inc['ancestor_caps_recomputed'],8)
  self.assertEqual(inc['nodes_verified'],15)
  self.assertEqual(inc['replay_status'],self.r15['replay_status'])
  self.assertAlmostEqual(inc['gap_upper_display'],self.r15['gap_upper_display'],places=12)
 def test_mutated_old_node_rejected_and_does_not_poison_session(self):
  s=self._session();bad=copy.deepcopy(self.c15)
  bad['nodes'][0]['bound_mode']='direct' if bad['nodes'][0]['bound_mode']=='coupled' else 'coupled'
  with self.assertRaises(ValueError):s.verify(bad,self.inp,self.p15,self.duals)
  self.assertEqual(s.verify(self.c15,self.inp,self.p15,self.duals)['verified_prefix_nodes_reused'],7)
 def test_mutated_old_box_rejected(self):
  bad=copy.deepcopy(self.c15);bad['nodes'][1]['box'][0][0]='-9.9'
  with self.assertRaises(ValueError):self._session().verify(bad,self.inp,self.p15,self.duals)
 def test_mutated_old_split_rejected(self):
  bad=copy.deepcopy(self.c15);bad['nodes'][0]['split_dim']=2
  with self.assertRaises(ValueError):self._session().verify(bad,self.inp,self.p15,self.duals)
 def test_new_child_corrupted_partition_rejected(self):
  bad=copy.deepcopy(self.c15);bad['nodes'][-1]['box'][0][0]='-9.9'
  with self.assertRaises(ValueError):self._session().verify(bad,self.inp,self.p15,self.duals)
 def test_missing_new_child_rejected(self):
  bad=copy.deepcopy(self.c15);bad['nodes'].pop()
  with self.assertRaises(ValueError):self._session().verify(bad,self.inp,self.p15,self.duals)
 def test_changed_input_rejected(self):
  inp=copy.deepcopy(self.inp);inp['seeds'][0][0]='-3.5'
  with self.assertRaises(ValueError):self._session().verify(self.c15,inp,self.p15,self.duals)
 def test_changed_protocol_precision_rejected(self):
  p={**self.p15,'replay_precision_bits':256}
  with self.assertRaises(ValueError):self._session().verify(self.c15,self.inp,p,self.duals)
 def test_changed_dual_rejected(self):
  q=copy.deepcopy(self.duals);q[0][0][0]='12345'
  with self.assertRaises(ValueError):self._session().verify(self.c15,self.inp,self.p15,q)
 def test_forged_global_certification_rejected(self):
  bad=copy.deepcopy(self.c15);bad['status']='CERTIFIED_BOUNDED_GAP'
  with self.assertRaises(ValueError):self._session().verify(bad,self.inp,self.p15,self.duals)
 def test_parent_cap_display_tampering_not_proof_authority(self):
  bad=copy.deepcopy(self.c15);bad['nodes'][-1]['upper_bound_ceil_display']=-1e90
  r=self._session().verify(bad,self.inp,self.p15,self.duals)
  self.assertAlmostEqual(r['gap_upper_display'],self.r15['gap_upper_display'],places=12)
 def test_serialized_fake_checkpoint_cannot_be_used(self):
  s=self._session()
  self.assertFalse(hasattr(s,'load_checkpoint'))
  self.assertFalse(hasattr(s,'export_checkpoint'))
 def test_premature_truncation_rejected(self):
  bad=copy.deepcopy(self.c7);bad['nodes'].pop()
  with self.assertRaises(ValueError):self._session().verify(bad,self.inp,self.p15,self.duals)
 def test_frozen_ch29_source_and_original_data_unchanged(self):
  proto=self.p
  sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
  inp=BASE/'CH_C14_25/inputs'/f'{self.cid}.json'
  self.assertEqual(sha(inp),proto['original_case_sha256'][self.cid])
  for p,h in proto['solver_source_sha256'].items():self.assertEqual(sha(BASE/'CH_C14_29'/p),h)

if __name__=='__main__':unittest.main()