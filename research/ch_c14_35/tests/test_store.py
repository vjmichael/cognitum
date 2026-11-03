"""CH35 signing/store fault tests only; these do not certify MPFR proofs.

Witness claims in this storage suite are fixed identifiers corresponding to an
original CH23 case. No fabricated numerical dataset is passed to a solver.
Only the socket authority is allowed to sign claims in a deployment.
"""
import base64, errno, json, os, signal, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trust35 import (GENESIS, WitnessStore, canonical, hashbytes, pubkey_fingerprint,
                     shaobj, strict, verify_chain)

CASE='one_event_n80_i00'
HEAD='ce92be481fcd868ea18d10eea2f4f54b018a5a107b912019c98e71fea8f92ada'
CP='84429dae20d0315bda2f48a4e82908d515469863a70832ee8d56fc87746232b2'

def att(case=CASE):
    return {'case_id':case,'binding_sha256':'e'*64,
            'original_head_sha256':HEAD,'checkpoint_sha256':CP,
            'archive_sha256':'a'*64,'nodes':127,'archive_epochs':2,
            'mpfr_replayed_frames':6,'proof_replayed':True,
            'scientific_release':'NO_GO','verified_source':'original_CH23_independent_MPFR_224'}

class Storage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'signer'
        provisioned=WitnessStore.provision(self.root)
        self.pub=provisioned['public_key_pem'].encode();self.fp=provisioned['fingerprint_sha256']
        self.s=WitnessStore(self.root)
    def chain(self,tip):return verify_chain(self.root,self.pub,expected_fingerprint=self.fp,expected_tip=tip)
    def commit(self,case=CASE,tip=GENESIS):return self.s.publish(att(case),expected_tip=tip)['tip']
    def test_genesis_and_signed_replay(self):
        one=self.commit();self.assertEqual(self.chain(one)['cases'],[CASE])
        two=self.commit('quasi_separated_n80_i00',one)
        self.assertEqual(self.chain(two)['length'],2)
        self.assertEqual(self.chain(two)['cases'],[CASE,'quasi_separated_n80_i00'])
    def test_public_key_substitution_is_refused(self):
        first=self.commit()
        other=WitnessStore.provision(Path(self.temp.name)/'forger')
        with self.assertRaises(ValueError):verify_chain(self.root,other['public_key_pem'].encode(),expected_fingerprint=self.fp,expected_tip=first)
    def test_signed_body_change_with_matching_file_name_is_refused(self):
        first=self.commit();p=self.root/'HEAD'
        b=json.loads(p.read_text());b['body']['nodes']=128;p.write_bytes(canonical(b)+b'\n')
        with self.assertRaises(ValueError):self.chain(first)
    def test_rollback_detection_uses_external_tip(self):
        first=self.commit();second=self.commit('quasi_separated_n80_i00',first)
        with self.assertRaises(ValueError):self.chain(first)
        self.assertEqual(self.chain(second)['length'],2)
    def test_deleting_parent_refused(self):
        first=self.commit();second=self.commit('rare_1pct_n80_i00',first)
        list((self.root/'revisions').glob('00000000*.json'))[0].unlink()
        with self.assertRaises((ValueError,FileNotFoundError)):self.chain(second)
    def test_duplicate_refused(self):
        first=self.commit()
        with self.assertRaises(ValueError):self.commit(tip=first)
        self.assertEqual(self.chain(first)['length'],1)
    def test_precommit_failures_enospc_eio_edquot_preserve_external_tip(self):
        first=self.commit()
        for stage in ('record_prewrite','record_write','record_fsync','record_rename','record_dirsync',
                      'before_head','head_write','head_fsync','head_rename'):
            for error in (errno.ENOSPC,errno.EIO,errno.EDQUOT):
                # Each trial has an independent signer store to preserve real
                # orphan/pending conditions rather than silently repairing.
                with self.subTest(stage=stage,errno=error):
                    with tempfile.TemporaryDirectory() as t:
                        fresh=Path(t)/'signer';WitnessStore.provision(fresh)
                        local=WitnessStore(fresh)
                        a=local.publish(att(),expected_tip=GENESIS)['tip']
                        with self.assertRaises(OSError) as caught:
                            local.publish(att('rare_1pct_n80_i00'),expected_tip=a,inject=(stage,error))
                        self.assertEqual(caught.exception.errno,error)
                        actual=verify_chain(fresh,(fresh/'public.ed25519.pem').read_bytes(),
                            expected_fingerprint=hashbytes((fresh/'public.ed25519.pem').read_bytes()),expected_tip=a)
                        self.assertEqual(actual['length'],1)
                        if stage == 'record_prewrite':
                            # No file was touched: safe to retry from the pinned prior tip.
                            local.publish(att('zero_balanced_n80_i00'),expected_tip=a)
                        else:
                            with self.assertRaises((ValueError,OSError)):
                                local.publish(att('zero_balanced_n80_i00'),expected_tip=a)
    def test_post_head_rename_crash_quarantines_old_tip(self):
        first=self.commit()
        with self.assertRaises(OSError):
            self.s.publish(att('zero_balanced_n80_i00'),expected_tip=first,inject=('head_dirsync',errno.EIO))
        with self.assertRaises(ValueError):self.chain(first)
        candidate=shaobj(strict((self.root/'HEAD').read_bytes()))
        self.assertEqual(self.s.recover(external_tip=first,candidate_tip=candidate)['state'],
                         'QUARANTINED_UNTIL_INDEPENDENT_REPLAY_AND_EXTERNAL_REPIN')
        with self.assertRaises(ValueError):self.s.publish(att('rare_1pct_n80_i00'),expected_tip=first)
    def test_bad_external_pin_never_autoadopted(self):
        first=self.commit()
        with self.assertRaises(ValueError):self.chain('f'*64)
        self.assertEqual(self.s.recover(external_tip=first)['state'],'EXTERNAL_TIP_VALID')
    def test_quota_failure_no_mutation(self):
        first=self.commit();self.s.max_bytes=self.s._bytes()+20
        with self.assertRaises(OSError) as caught:self.s.publish(att('rare_1pct_n80_i00'),expected_tip=first)
        self.assertEqual(caught.exception.errno,errno.ENOSPC)
        self.assertEqual(self.chain(first)['length'],1)
    def test_symlink_revision_and_head_refused(self):
        first=self.commit();p=self.root/'HEAD';p.unlink();p.symlink_to(self.root/'public.ed25519.pem')
        with self.assertRaises((OSError,ValueError)):self.chain(first)
    def test_actual_kernel_file_size_rejection(self):
        first=self.commit()
        code='''import errno,resource,signal,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]);from trust35 import WitnessStore
root=Path(sys.argv[2]);tip=sys.argv[3]
from tests.test_store import att
signal.signal(signal.SIGXFSZ,signal.SIG_IGN)
resource.setrlimit(resource.RLIMIT_FSIZE,(160,resource.getrlimit(resource.RLIMIT_FSIZE)[1]))
try:WitnessStore(root).publish(att('rare_1pct_n80_i00'),expected_tip=tip)
except OSError as e:
 assert e.errno in (errno.EFBIG,errno.ENOSPC,errno.EDQUOT),e
 print('REAL_KERNEL_WRITE_REJECTION',e.errno)
else:raise AssertionError('Expected genuine file-size write failure')'''
        script=code.replace('from tests.test_store import att',"def att(case):return "+repr(att('rare_1pct_n80_i00')))
        r=subprocess.run([sys.executable,'-c',script,str(Path(__file__).resolve().parents[1]),str(self.root),first],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('REAL_KERNEL_WRITE_REJECTION',r.stdout)
        self.assertEqual(self.chain(first)['length'],1)

if __name__=='__main__':unittest.main()
