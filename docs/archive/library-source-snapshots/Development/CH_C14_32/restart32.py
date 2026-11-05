"""New-interpreter cold recovery: untrusted disk journal is mathematically replayed.

The command never imports persisted MPFR objects, approval flags or receipts.
"""
from __future__ import annotations
import argparse,json,os,sys,time
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D));sys.path.insert(0,str(D.parent/'CH_C14_31'))
from journal32 import ProofJournal
from verifier31 import load_original_case
from prefix31 import project_prefix

def resume(case,path,*,expected_head=None,verify_only=False,discard_uncommitted=False):
    inp,proto,duals,archived=load_original_case(case)
    c63,_=archived(63);c127,receipt127=archived(127)
    def cert(n):return c63 if n==63 else c127 if n==127 else project_prefix(c63 if n<63 else c127,n)
    tick=time.process_time()
    with ProofJournal(path,inp,proto,duals,case_id=case,expected_head_sha256=expected_head) as j:
        initial=j.seq;recovery_fresh=j.recovery_fresh;recovery_cpu=j.recovery_cpu_seconds
        had_pending=len(j._pending)
        discarded=j.discard_pending() if discard_uncommitted else 0
        appended=[]
        if not verify_only:
            for n in (7,15,31,63,95,127):
                # Determine from the exact record height, not a claimed receipt.
                if j.cert is not None and len(j.cert['nodes'])>=n:continue
                appended.append(j.append(cert(n)))
        if not j.cert:raise ValueError('Uninitialized durable proof journal')
        if verify_only and len(j.cert['nodes'])!=127:raise ValueError('Final journal incomplete')
        gap=j.session._last_cap
        if len(j.cert['nodes'])==127 and abs(gap-receipt127['gap_upper_display'])>1e-10:
            raise AssertionError('Recovered bound differs from original CH29 127-node receipt')
        result={'case_id':case,'pid':os.getpid(),'initial_committed_stages':initial,
                'cold_recomputed_bounds':recovery_fresh,'cold_recovery_cpu_seconds':recovery_cpu,
                'uncommitted_pending_found':had_pending,'explicitly_discarded_pending':discarded,
                'newly_appended_stages':[r['nodes'] for r in appended],
                'newly_verified_bounds':sum(r['fresh_nodes'] for r in appended),
                'head_sha256':j.head,'final_nodes':len(j.cert['nodes']),
                'gap_upper_display':gap,'mathematics_reverified_on_restart':True,
                'imported_verified_state':False,'global_certified':False,'production_release':'NO_GO',
                'cpu_seconds':time.process_time()-tick}
        return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True)
    p.add_argument('--journal',required=True,type=Path)
    p.add_argument('--verify-only',action='store_true')
    p.add_argument('--discard-uncommitted',action='store_true')
    p.add_argument('--expected-head')
    a=p.parse_args()
    print(json.dumps(resume(a.case,a.journal,expected_head=a.expected_head,
                            verify_only=a.verify_only,discard_uncommitted=a.discard_uncommitted),
                     sort_keys=True,allow_nan=False))