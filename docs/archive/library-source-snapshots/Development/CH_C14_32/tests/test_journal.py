"""CH32 crash-consistency, replay and tamper tests on original CH23 data."""
import copy, hashlib, json, shutil, sys, tempfile, unittest
from pathlib import Path
D=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(D),str(D.parent/'CH_C14_31')]
from journal32 import ProofJournal, SimulatedCrash, apply_delta, canonical, digest, make_delta
from verifier31 import load_original_case
from prefix31 import project_prefix

class JournalTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cid='zero_balanced_n80_i00'
  cls.inp,cls.proto,cls.duals,arc=load_original_case(cls.cid)
  c63,_=arc(63)
  cls.c7=project_prefix(c63,7)
  cls.c15=project_prefix(c63,15)
  cls.c31=project_prefix(c63,31)
  cls.template=tempfile.TemporaryDirectory()
  with ProofJournal(Path(cls.template.name)/'original',cls.inp,cls.proto,cls.duals,case_id=cls.cid) as j:
   cls.head7=j.append(cls.c7)['head_sha256']
   cls.head15=j.append(cls.c15)['head_sha256']
 @classmethod
 def tearDownClass(cls):cls.template.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'j'
  shutil.copytree(Path(self.template.name)/'original',self.path)
 def tearDown(self):self.tmp.cleanup()
 def open(self,**kw):return ProofJournal(self.path,self.inp,self.proto,self.duals,case_id=self.cid,**kw)
 def getframe(self,i):return self.path/f'{i:06d}.json'
 def loadframe(self,i):return json.loads(self.getframe(i).read_text())
 def saveframe(self,i,e):self.getframe(i).write_bytes(canonical(e)+b'\n')
 def test_two_stage_durable_recovery(self):
  with self.open() as j:
   self.assertEqual((j.seq,j.recovery_fresh),(2,15));self.assertEqual(j.head,self.head15)
   self.assertEqual(j.cert,self.c15)
 def test_delta_exact_original_case(self):
  d=make_delta(self.c15,self.c31);self.assertEqual(apply_delta(self.c15,d),self.c31)
  self.assertEqual(len(d['append_nodes']),16)
 def test_continue_after_replay(self):
  with self.open() as j:
   res=j.append(self.c31);self.assertEqual(res['fresh_nodes'],16);self.assertEqual(res['reused_nodes'],15)
  with self.open() as j:self.assertEqual(j.seq,3);self.assertEqual(j.recovery_fresh,31)
 def test_no_cached_mpfr_import(self):
  with self.open() as j:self.assertFalse(hasattr(j,'import_verified_cache'))
 def test_no_unknown_journal_files(self):
  (self.path/'000001.bak').write_text('bad')
  with self.assertRaises(ValueError),self.open():pass
 def test_missing_frame(self):
  self.getframe(0).rename(self.path/'000009.json')
  with self.assertRaises(ValueError),self.open():pass
 def test_hash_tamper(self):
  e=self.loadframe(1);e['body']['stage_nodes']=13;self.saveframe(1,e)
  with self.assertRaises(ValueError),self.open():pass
 def test_valid_envelope_but_false_mathematics(self):
  e=self.loadframe(0)
  e['body']['payload']['nodes'][0]['box'][0][0]='-11'
  e['body']['certificate_sha256']=digest(e['body']['payload']);e['sha256']=digest(e['body']);self.saveframe(0,e)
  with self.assertRaises(ValueError),self.open():pass
 def test_chain_rewrite(self):
  e=self.loadframe(1);e['body']['prev_sha256']='c'*64;e['sha256']=digest(e['body']);self.saveframe(1,e)
  with self.assertRaises(ValueError),self.open():pass
 def test_external_head_pin(self):
  with self.open(expected_head_sha256=self.head15):pass
  self.getframe(1).unlink()
  with self.assertRaises(ValueError),self.open(expected_head_sha256=self.head15):pass
 def test_duplicate_json_key(self):
  p=self.getframe(1);raw=p.read_text();p.write_text(raw.replace('"sha256":','"sha256":"fake","sha256":',1))
  with self.assertRaises(ValueError),self.open():pass
 def test_truncated_committed_record(self):
  p=self.getframe(1);p.write_bytes(p.read_bytes()[:80])
  with self.assertRaises(ValueError),self.open():pass
 def test_bad_proof_does_not_advance(self):
  with self.open() as j:
   b=copy.deepcopy(self.c31);b['nodes'][0]['box'][0][0]='-500'
   with self.assertRaises(ValueError):j.append(b)
   self.assertEqual(j.seq,2)
  with self.open() as j:self.assertEqual(j.seq,2)
 def test_restart_after_pending_fsync(self):
  with self.open() as j:
   with self.assertRaises(SimulatedCrash):j.append(self.c31,crash_at='before_rename')
   with self.assertRaises(RuntimeError):j.append(self.c31)
  with self.open() as j:
   self.assertEqual((j.seq,j.recovery_fresh,len(j._pending)),(2,15,1))
   with self.assertRaises(ValueError):j.append(self.c31)
   self.assertEqual(j.discard_pending(),1)
   self.assertEqual(j.append(self.c31)['nodes'],31)
  with self.open() as j:self.assertEqual(j.recovery_fresh,31)
 def test_restart_after_rename_before_fsync(self):
  with self.open() as j:
   with self.assertRaises(SimulatedCrash):j.append(self.c31,crash_at='after_rename')
  with self.open() as j:
   self.assertEqual((j.seq,j.recovery_fresh),(3,31))
   self.assertTrue(j.append(self.c31)['already_committed'])
 def test_restart_after_fsync_before_ack(self):
  with self.open() as j:
   with self.assertRaises(SimulatedCrash):j.append(self.c31,crash_at='after_dir_fsync')
  with self.open() as j:
   self.assertEqual(j.recovery_fresh,31)
   self.assertTrue(j.append(self.c31)['already_committed'])
 def test_mismatched_original_data(self):
  bad=copy.deepcopy(self.inp);bad['seeds'][0][0]='-4.23423'
  with self.assertRaises(ValueError),ProofJournal(self.path,bad,self.proto,self.duals,case_id=self.cid):pass
 def test_wrong_case(self):
  other='one_event_n80_i00'
  with self.assertRaises(ValueError),ProofJournal(self.path,self.inp,self.proto,self.duals,case_id=other):pass
 def test_unsupported_semantic_extension(self):
  bad=copy.deepcopy(self.c31);bad['status']='CERTIFIED_BOUNDED_GAP'
  with self.open() as j:
   with self.assertRaises(ValueError):j.append(bad)
 def test_final_leaf_meta_cannot_change(self):
  bad=copy.deepcopy(self.c31);bad['nodes'][0]['upper_method']='invented'
  with self.assertRaises(ValueError):make_delta(self.c15,bad)

if __name__=='__main__':unittest.main()