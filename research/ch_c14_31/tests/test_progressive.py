"""CH31 fail-closed progression tests using original CH23 data and CH29 nodes."""
import copy,hashlib,json,subprocess,sys,unittest
from pathlib import Path
D=Path(__file__).resolve().parents[1];BASE=D.parent
sys.path.insert(0,str(D));sys.path.insert(0,str(BASE/'CH_C14_30'))
from prefix31 import project_prefix
from verifier31 import ProgressiveVerifier,load_original_case
from verifier30 import verify_full

class ProgressiveTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cid='zero_balanced_n80_i00';cls.inp,cls.proto,cls.duals,archive=load_original_case(cls.cid)
  cls.c63,cls.rec63=archive(63);cls.c127,cls.rec127=archive(127)
  cls.snapshots={n: (cls.c63 if n==63 else cls.c127 if n==127 else
                    project_prefix(cls.c63 if n<63 else cls.c127,n))
                 for n in (7,15,31,63,95,127)}
  cls.seed=ProgressiveVerifier();cls.r7=cls.seed.verify_stage(cls.snapshots[7],cls.inp,{**cls.proto,'node_budget_per_case':7},cls.duals)
 def cfg(self,n):return {**self.proto,'node_budget_per_case':n}
 def fresh(self):
  # Use the public API; tests never inject precomputed states directly.
  s=ProgressiveVerifier();s.verify_stage(self.snapshots[7],self.inp,self.cfg(7),self.duals);return s
 def test_original_case_hash(self):
  ip=BASE/'CH_C14_25/inputs'/(self.cid+'.json');
  self.assertEqual(hashlib.sha256(ip.read_bytes()).hexdigest(),self.proto['original_case_sha256'][self.cid])
 def test_valid_projection_closed_prefixes(self):
  for n,c in self.snapshots.items():
   self.assertEqual(len(c['nodes']),n)
   for x in c['nodes']:
    if 'children' in x:self.assertTrue(all(k<n for k in x['children']))
 def test_invalid_prefix_sizes(self):
  for n in (0,2,8,64,129,-1,3.14,True):
   with self.subTest(n=n),self.assertRaises(ValueError):project_prefix(self.c127,n)
 def test_full_six_stages(self):
  s=ProgressiveVerifier();last=0;lastgap=float('inf')
  for n in (7,15,31,63,95,127):
   r=s.verify_stage(self.snapshots[n],self.inp,self.cfg(n),self.duals)
   self.assertEqual(r['receipt']['verified_prefix_nodes_reused'],last)
   self.assertEqual(r['receipt']['ancestor_caps_recomputed'],n-last)
   self.assertLessEqual(r['receipt']['gap_upper_display'],lastgap+1e-10)
   last=n;lastgap=r['receipt']['gap_upper_display']
  self.assertAlmostEqual(lastgap,self.rec127['gap_upper_display'],places=10)
 def test_forged_old_node_not_reused(self):
  s=self.fresh();bad=copy.deepcopy(self.snapshots[15]);bad['nodes'][0]['bound_mode']='direct'
  with self.assertRaises(ValueError):s.verify_stage(bad,self.inp,self.cfg(15),self.duals)
  good=s.verify_stage(self.snapshots[15],self.inp,self.cfg(15),self.duals)
  self.assertEqual(good['receipt']['verified_prefix_nodes_reused'],7)
 def test_forged_old_split_not_reused(self):
  s=self.fresh();bad=copy.deepcopy(self.snapshots[15]);bad['nodes'][0]['split_dim']=(bad['nodes'][0]['split_dim']+1)%3
  with self.assertRaises(ValueError):s.verify_stage(bad,self.inp,self.cfg(15),self.duals)
 def test_forged_child_partition(self):
  s=self.fresh();bad=copy.deepcopy(self.snapshots[15]);bad['nodes'][-1]['box'][0][0]='-9.99'
  with self.assertRaises(ValueError):s.verify_stage(bad,self.inp,self.cfg(15),self.duals)
 def test_truncated_cert(self):
  s=self.fresh();bad=copy.deepcopy(self.snapshots[15]);bad['nodes'].pop()
  with self.assertRaises(ValueError):s.verify_stage(bad,self.inp,self.cfg(15),self.duals)
 def test_forged_promotion(self):
  s=self.fresh();bad=copy.deepcopy(self.snapshots[15]);bad['status']='CERTIFIED_BOUNDED_GAP'
  with self.assertRaises(ValueError):s.verify_stage(bad,self.inp,self.cfg(15),self.duals)
 def test_changed_case_or_input_fails(self):
  s=self.fresh();bad=copy.deepcopy(self.inp);bad['seeds'][0][0]='-4.5'
  with self.assertRaises(ValueError):s.verify_stage(self.snapshots[15],bad,self.cfg(15),self.duals)
 def test_changed_dual_fails(self):
  s=self.fresh();q=copy.deepcopy(self.duals);q[0][0][0]='777'
  with self.assertRaises(ValueError):s.verify_stage(self.snapshots[15],self.inp,self.cfg(15),q)
 def test_changed_protocol_fails(self):
  s=self.fresh();p=self.cfg(15);p['replay_precision_bits']=256
  with self.assertRaises(ValueError):s.verify_stage(self.snapshots[15],self.inp,p,self.duals)
 def test_wrong_stage_budget_fails(self):
  s=self.fresh()
  with self.assertRaises(ValueError):s.verify_stage(self.snapshots[15],self.inp,self.cfg(31),self.duals)
 def test_no_regression_to_earlier_stage(self):
  s=self.fresh()
  with self.assertRaises(ValueError):s.verify_stage(self.snapshots[7],self.inp,self.cfg(7),self.duals)
 def test_untrusted_display_not_proof(self):
  s=self.fresh();bad=copy.deepcopy(self.snapshots[15]);bad['nodes'][-1]['upper_bound_ceil_display']=-1e80
  r=s.verify_stage(bad,self.inp,self.cfg(15),self.duals)
  self.assertEqual(r['receipt']['replay_status'],'REPLAYED_BUT_UNRESOLVED')
 def test_no_external_cache_import(self):
  s=ProgressiveVerifier();self.assertFalse(hasattr(s,'import_checkpoint'))
  self.assertFalse(hasattr(s,'load_checkpoint'));self.assertFalse(hasattr(s,'export_checkpoint'))
  self.assertFalse(hasattr(s._session,'load_checkpoint'))
 def test_restart_cli_rejects_cache_flag(self):
  cmd=[sys.executable,str(D/'restart31.py'),'--case',self.cid,'--load-cache','forged.pkl']
  proc=subprocess.run(cmd,check=False,capture_output=True,text=True,timeout=20)
  self.assertNotEqual(proc.returncode,0)
 def test_fresh_interpreter_reverifies_prefix(self):
  cmd=[sys.executable,str(D/'restart31.py'),'--case',self.cid]
  proc=subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=180)
  j=json.loads(proc.stdout)
  self.assertTrue(j['verified']);self.assertFalse(j['imported_cache'])
  self.assertEqual(j['chain'][0]['fresh'],63);self.assertEqual(j['chain'][0]['reused'],0)
  self.assertEqual(j['chain'][1]['fresh'],32);self.assertEqual(j['chain'][2]['fresh'],32)
  self.assertAlmostEqual(j['chain'][-1]['gap_upper_display'],self.rec127['gap_upper_display'],places=10)

if __name__=='__main__':unittest.main()
