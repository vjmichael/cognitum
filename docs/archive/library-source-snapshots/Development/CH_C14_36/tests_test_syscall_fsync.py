"""CH36 errno propagation through Linux libc fsync, not Python monkey-patching.

These tests intentionally use storage-layer-only specimen attestations (NO_GO).
They do NOT claim any new mathematical certification or physical disk fullness.
"""
from __future__ import annotations
import errno,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
CH36=Path(__file__).resolve().parents[1]
CH35=CH36.parent/'CH_C14_35'
sys.path.insert(0,str(CH35))
from trust35 import GENESIS,WitnessStore,atomic,canonical,hashbytes,shaobj,strict,verify_chain

LIB=CH36/'fsync_fault36.so'

def sample(case):
    # Synthetic METADATA only, not original scientific proof or verifier input.
    return {'case_id':case,'binding_sha256':'e'*64,
            'original_head_sha256':'a'*64,'checkpoint_sha256':'b'*64,
            'archive_sha256':'c'*64,'nodes':127,'archive_epochs':2,
            'mpfr_replayed_frames':6,'proof_replayed':True,
            'scientific_release':'NO_GO','verified_source':'original_CH23_independent_MPFR_224'}

class SyscallDurability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name!='posix' or not Path('/proc/self/fd').is_dir():
            raise unittest.SkipTest('Linux /proc required')
        compile=subprocess.run(['gcc','-shared','-fPIC','-O2','-Wall','-Wextra','-o',str(LIB),
                                str(CH36/'fsync_fault36.c'),'-ldl'],capture_output=True,text=True)
        if compile.returncode:raise RuntimeError('Fault injector compiler failed: '+compile.stderr)
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(prefix='ch36-fsync-');self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)/'store'
        self.ident=WitnessStore.provision(self.root)
        self.key=self.ident['public_key_pem'].encode();self.fp=self.ident['fingerprint_sha256']
        first=WitnessStore(self.root).publish(sample('original_ch23_first'),expected_tip=GENESIS)
        self.old=first['tip']
        atomic(self.root,'trusted_tip.json',canonical({'tip':self.old,'fingerprint':self.fp})+b'\n',prefix='tip')
    def old_valid(self):
        return verify_chain(self.root,self.key,expected_fingerprint=self.fp,expected_tip=self.old)
    def test_fsync_raised_real_errno_at_file_and_directory(self):
        stages=[('record_file','prefix:.record-','old'),
                ('record_directory','exact:'+str(self.root/'revisions'),'old'),
                ('head_file','prefix:.head-','old'),
                ('head_directory','exact:'+str(self.root),'quarantine'),
                ('tip_file','prefix:.tip-','quarantine')]
        statuses={}
        code='''import sys
sys.path.insert(0,sys.argv[1])
from trust35 import WitnessStore,atomic,canonical
from pathlib import Path
r=Path(sys.argv[2]);tip=sys.argv[3]
att={'case_id':'original_ch23_second','binding_sha256':'e'*64,'original_head_sha256':'a'*64,'checkpoint_sha256':'b'*64,'archive_sha256':'c'*64,'nodes':127,'archive_epochs':2,'mpfr_replayed_frames':6,'proof_replayed':True,'scientific_release':'NO_GO','verified_source':'original_CH23_independent_MPFR_224'}
try:
 res=WitnessStore(r).publish(att,expected_tip=tip)
 atomic(r,'trusted_tip.json',canonical({'tip':res['tip'],'fingerprint':sys.argv[4]})+b'\\n',prefix='tip')
except OSError as e:
 print('FSYNC_FAIL',e.errno,flush=True)
else:
 raise AssertionError('Expected injected libc fsync failure')'''
        # The code string contains a Python escaped newline, not an actual newline.
        for stage,target,expected in stages:
            for er in (errno.ENOSPC,errno.EIO,errno.EDQUOT):
                with self.subTest(stage=stage,errno=er),tempfile.TemporaryDirectory() as temp:
                    # An independent clone per fault preserves each failure artifact.
                    import shutil
                    replica=Path(temp)/'store';shutil.copytree(self.root,replica)
                    actual_target=target.replace(str(self.root),str(replica))
                    env={**os.environ,'LD_PRELOAD':str(LIB),
                         'CH36_FSYNC_TARGET':actual_target,'CH36_FSYNC_ERRNO':str(er)}
                    p=subprocess.run([sys.executable,'-c',code,str(CH35),str(replica),self.old,self.fp],
                                     env=env,capture_output=True,text=True,timeout=20)
                    self.assertEqual(p.returncode,0,p.stderr+' '+p.stdout)
                    self.assertIn('FSYNC_FAIL '+str(er),p.stdout)
                    trusted=json.loads((replica/'trusted_tip.json').read_text())
                    self.assertEqual(trusted['tip'],self.old)
                    signer=WitnessStore(replica)
                    if expected=='old':
                        self.assertEqual(verify_chain(replica,self.key,expected_fingerprint=self.fp,
                                                     expected_tip=self.old)['length'],1)
                        if stage=='record_file':
                            self.assertTrue(list((replica/'revisions').glob('.record-*.pending')))
                        else:
                            self.assertGreater(len(list((replica/'revisions').iterdir())),1)
                        with self.assertRaises((ValueError,OSError)):
                            signer.publish(sample('third'),expected_tip=self.old)
                    else:
                        with self.assertRaises(ValueError):
                            verify_chain(replica,self.key,expected_fingerprint=self.fp,
                                         expected_tip=self.old)
                        candidate=shaobj(strict((replica/'HEAD').read_bytes()))
                        self.assertEqual(signer.recover(external_tip=self.old,candidate_tip=candidate)['state'],
                            'QUARANTINED_UNTIL_INDEPENDENT_REPLAY_AND_EXTERNAL_REPIN')
                        with self.assertRaises(ValueError):
                            signer.publish(sample('third'),expected_tip=self.old)
                    statuses[stage+'_'+str(er)]=expected
        self.assertEqual(len(statuses),15)
        (CH36/'syscall_fsync_results.json').write_text(json.dumps({'cases':15,'passed':len(statuses),
            'simulated_errno':{'ENOSPC':errno.ENOSPC,'EIO':errno.EIO,'EDQUOT':errno.EDQUOT},
            'injection':'LD_PRELOAD intercept of libc fsync on actual active file descriptor',
            'real_filesystem_full':False,'faults':statuses},sort_keys=True,indent=2)+'\n')

if __name__=='__main__':unittest.main()