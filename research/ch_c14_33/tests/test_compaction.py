"""CH33 safety regression suite on the ORIGINAL CH23 frozen case only."""
from __future__ import annotations
import copy,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
D=Path(__file__).resolve().parents[1]; ROOT=D.parent
sys.path[:0]=[str(D),str(ROOT/'CH_C14_31')]
from compaction33 import CompactProofJournal, SimulatedCrash, _read_envelope,canonical,digest
from verifier31 import load_original_case

class TestCompaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cid='zero_balanced_n80_i00'
        cls.inp,cls.proto,cls.duals,arc=load_original_case(cls.cid)
        cls.source=ROOT/'CH_C14_32/journals'/cls.cid
        cls.original_head=json.loads((ROOT/'CH_C14_32/heads.json').read_text())[cls.cid]
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.journal=self.root/'active';self.archives=self.root/'archives'
        self.journal.mkdir()
        self.copy_source(0)
    def tearDown(self):self.temp.cleanup()
    def copy_source(self,i):shutil.copy2(self.source/f'{i:06d}.json',self.journal/f'{i:06d}.json')
    def open(self,**kw):return CompactProofJournal(self.journal,self.inp,self.proto,self.duals,case_id=self.cid,archive_dir=self.archives,**kw)
    def first(self,**kw):
        with self.open() as j:return j.compact(**kw)
    def test_first_compaction_saves_space(self):
        original=sum(x.stat().st_size for x in self.journal.glob('*.json'))
        info=self.first()
        self.assertLess(info['active_bytes'],original)
        self.assertEqual(info['covered_files_removed'],1)
        self.assertFalse(list(self.journal.glob('[0-9]*.json')))
        with self.open(expected_checkpoint_sha256=info['checkpoint_sha256']) as j:
            self.assertEqual(j.recovery_fresh,7)
            self.assertTrue(j.full_mathematical_replay)
            self.assertEqual(j.verify_archive_chain_metadata()['archive_epochs'],1)
    def test_compacted_history_replay_two_epochs(self):
        a=self.first();self.copy_source(1)
        with self.open(expected_checkpoint_sha256=a['checkpoint_sha256']) as j:
            self.assertEqual(j.recovery_fresh,15)
            b=j.compact()
        with self.open(expected_checkpoint_sha256=b['checkpoint_sha256']) as j:
            self.assertEqual(j.recovery_fresh,15)
            full=j.verify_archived_history()
            self.assertEqual((full['archives'],full['replayed_frames']),(2,2))
    def test_compaction_cannot_reuse_saved_proof_state(self):
        a=self.first()
        with self.open() as j:
            self.assertFalse(hasattr(j,'import_verified_cache'))
            self.assertEqual(j.recovery_fresh,7)
    def test_pending_before_rename_requires_discard(self):
        with self.open() as j:
            with self.assertRaises(SimulatedCrash):j.compact(crash_at='before_snapshot_rename')
        with self.open() as j:
            self.assertEqual(j.seq,1)
            self.assertIsNone(j._checkpoint)
            self.assertEqual(len(j._pending),1)
            with self.assertRaises(ValueError):j.compact()
            self.assertEqual(j.discard_pending(),1)
            self.assertEqual(j.compact()['compacted_frames'],1)
    def test_after_fsync_requires_explicit_prune(self):
        with self.open() as j:
            with self.assertRaises(SimulatedCrash):j.compact(crash_at='after_snapshot_fsync')
        with self.open() as j:
            self.assertEqual(len(j._covered),1)
            self.copy_source(1)
            with self.assertRaises(ValueError):j.append({'nodes':[]})
            self.assertEqual(j.cleanup_covered(),1)
            self.assertTrue(j.verify_archive_chain_metadata()['hash_chain_complete'])
    def test_during_prune_recovers_remaining(self):
        self.copy_source(1)
        with self.open() as j:
            with self.assertRaises(SimulatedCrash):j.compact(crash_at='during_prune')
        with self.open() as j:
            self.assertEqual(len(j._covered),1)
            self.assertEqual(j.cleanup_covered(),1)
            self.assertEqual(j.recovery_fresh,15)
    def test_covered_frame_tamper_fails(self):
        with self.open() as j:
            with self.assertRaises(SimulatedCrash):j.compact(crash_at='after_snapshot_fsync')
        p=self.journal/'000000.json';p.write_bytes(b'corrupt')
        with self.assertRaises(ValueError),self.open():pass
    def test_missing_archive_fails(self):
        a=self.first();list(self.archives.glob('*.zlib'))[0].unlink()
        with self.assertRaises(ValueError),self.open():pass
    def test_archive_corruption_fails(self):
        self.first();p=list(self.archives.glob('*.zlib'))[0]
        data=p.read_bytes();p.write_bytes(data[:-4]+b'abcd')
        with self.assertRaises(ValueError),self.open():pass
    def test_recomputed_checkpoint_hash_is_not_proof(self):
        self.first();p=self.journal/'checkpoint.json';env=json.loads(p.read_text())
        env['body']['compressed_certificate']='eJwLcnR1BgADLwEB'
        env['sha256']=digest(env['body']);p.write_bytes(canonical(env)+b'\n')
        with self.assertRaises(Exception),self.open():pass
    def test_external_checkpoint_pin_detects_rewrite(self):
        info=self.first()
        with self.open(expected_checkpoint_sha256=info['checkpoint_sha256']):pass
        cp=self.journal/'checkpoint.json';env=json.loads(cp.read_text())
        env['body']['stage_nodes']=14;env['sha256']=digest(env['body'])
        cp.write_bytes(canonical(env)+b'\n')
        with self.assertRaises(ValueError),self.open(expected_checkpoint_sha256=info['checkpoint_sha256']):pass
    def test_missing_prior_archive_invalidates_chain(self):
        self.first();self.copy_source(1)
        with self.open() as j:info=j.compact()
        files=sorted(self.archives.glob('*.zlib'));self.assertEqual(len(files),2)
        files[0].unlink()
        with self.assertRaises(ValueError),self.open():pass
    def test_active_bytes_budget_proactive_compact(self):
        from prefix31 import project_prefix
        _,_,_,archive=load_original_case(self.cid)
        c63,_=archive(63);c31=project_prefix(c63,31)
        self.copy_source(1)
        with self.open(max_active_bytes=42000) as j:
            self.assertGreater(j._active_bytes(),30000)
            self.assertIsNone(j._checkpoint)
            result=j.append(c31)
            self.assertEqual(result['nodes'],31)
            self.assertIsNotNone(j._checkpoint)
            self.assertLessEqual(j._active_bytes(),42000)
            self.assertEqual(j._checkpoint['body']['stage_nodes'],15)
        with self.open(max_active_bytes=42000) as j:
            self.assertEqual(j.recovery_fresh,31)
            self.assertLessEqual(j._active_bytes(),42000)
    def test_invalid_active_budget_rejected(self):
        with self.assertRaises(ValueError):self.open(max_active_bytes=100)
    def test_unknown_file_rejected(self):
        self.first();(self.journal/'fake.json').write_text('evil')
        with self.assertRaises(ValueError),self.open():pass
    def test_wrong_original_input_rejected(self):
        self.first();bad=copy.deepcopy(self.inp);bad['seeds'][0][0]='0.999999'
        with self.assertRaises(ValueError),CompactProofJournal(self.journal,bad,self.proto,self.duals,case_id=self.cid,archive_dir=self.archives):pass

if __name__=='__main__':unittest.main()
