"""Kernel-origin ENOSPC on isolated 256 KiB tmpfs; never fill shared mounts."""
import json,subprocess,sys,unittest
from pathlib import Path
D=Path(__file__).resolve().parents[1]
class RealTmpfsFull(unittest.TestCase):
    def test_three_true_kernel_disk_full_boundaries(self):
        results=[]
        for reserve in (0,4096,8192):
            with self.subTest(reserve=reserve):
                p=subprocess.run(['unshare','-Urnm',sys.executable,
                                  str(D/'tests/real_enospc_worker36.py'),
                                  '--reserve',str(reserve)],capture_output=True,text=True,timeout=20)
                self.assertEqual(p.returncode,0,p.stderr+' '+p.stdout)
                obj=json.loads(p.stdout)
                self.assertEqual(obj['status'],'PASS')
                self.assertEqual(obj['real_kernel_errno'],28)
                results.append(obj)
        # We deliberately require coverage of *both* pre-HEAD and post-HEAD
        # failure outcomes, not merely any three ENOSPC exceptions.
        outcomes={r['outcome'] for r in results}
        self.assertEqual(outcomes,{'PREVIOUS_TIP_VALID_PENDING_OR_ORPHAN','NEW_HEAD_QUARANTINED'})
        (D/'real_enospc_results.json').write_text(json.dumps({
            'test':'true Linux kernel ENOSPC in private user+mount namespace',
            'cases':results,'passed':len(results),'hard_power_loss_tested':False,
            'scientific_certifications':0},sort_keys=True,indent=2)+'\n')
if __name__=='__main__':unittest.main()