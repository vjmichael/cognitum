"""Actual os._exit(79) at five witness-durability boundaries; not power loss.

This is the private signer storage layer only. No mathematical certification is
issued from these test attestations. They are not available through IPC.
"""
from __future__ import annotations
import errno,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trust35 import GENESIS,WitnessStore,hashbytes,shaobj,strict,verify_chain
from test_store import att

class ActualExit(unittest.TestCase):
    def test_hard_exit_before_and_after_head(self):
        events=('record_write','record_fsync','record_rename','record_dirsync','before_head',
                'head_write','head_fsync','head_rename','head_dirsync')
        statuses={}
        for event in events:
            with self.subTest(event=event),tempfile.TemporaryDirectory() as t:
                root=Path(t)/'signer';ident=WitnessStore.provision(root)
                old=WitnessStore(root).publish(att(),expected_tip=GENESIS)['tip']
                script='''import sys
sys.path.insert(0,sys.argv[1]);from trust35 import WitnessStore
from test_store import att
WitnessStore(sys.argv[2]).publish(att('rare_1pct_n80_i00'),expected_tip=sys.argv[3],inject=(sys.argv[4],'os_exit'))'''
                cmd=[sys.executable,'-c',script,str(Path(__file__).resolve().parents[1]),str(root),old,event]
                env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parent)}
                r=subprocess.run(cmd,capture_output=True,text=True,timeout=10,env=env)
                self.assertEqual(r.returncode,79,r.stderr)
                pub=(root/'public.ed25519.pem').read_bytes();fp=ident['fingerprint_sha256']
                if event!='head_dirsync':
                    self.assertEqual(verify_chain(root,pub,expected_fingerprint=fp,expected_tip=old)['length'],1)
                    self.assertEqual(WitnessStore(root).recover(external_tip=old)['state'],'EXTERNAL_TIP_VALID')
                    statuses[event]='PRIOR_TIP_PRESERVED_PENDING_OR_ORPHAN'
                else:
                    with self.assertRaises(ValueError):verify_chain(root,pub,expected_fingerprint=fp,expected_tip=old)
                    candidate=shaobj(strict((root/'HEAD').read_bytes()))
                    self.assertEqual(WitnessStore(root).recover(external_tip=old,candidate_tip=candidate)['state'],
                                     'QUARANTINED_UNTIL_INDEPENDENT_REPLAY_AND_EXTERNAL_REPIN')
                    statuses[event]='QUARANTINED_UNTIL_REPLAY_AND_EXTERNAL_REPIN'
        print('HARD_EXIT_RESULTS '+json.dumps(statuses,sort_keys=True))

if __name__=='__main__':unittest.main()
