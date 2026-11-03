"""CH32 hard-exit process crash tests on *original* CH23 data.

Runs separate Linux Python processes that call os._exit(79) at the injected
before-rename / after-dir-fsync commit boundaries. On recovery, the proof is
recomputed from scratch at 224-bit MPFR; no persisted verification state.
"""
import json,os,subprocess,sys,tempfile,time
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path[:0]=[str(D),str(D.parent/'CH_C14_31')]
from journal32 import ProofJournal,SimulatedCrash
from verifier31 import load_original_case
from prefix31 import project_prefix


def run():
    cid='zero_balanced_n80_i00'
    inp,proto,duals,archive=load_original_case(cid);c63,_=archive(63)
    c7=project_prefix(c63,7);c15=project_prefix(c63,15)
    out=[]
    for mode in ('before_rename','after_dir_fsync'):
        with tempfile.TemporaryDirectory(prefix='ch32-exit-') as tmp:
            target=Path(tmp)/'journal'
            with ProofJournal(target,inp,proto,duals,case_id=cid) as j:j.append(c7)
            child_code=f'''import os,sys
sys.path[:0]={repr([str(D),str(D.parent/'CH_C14_31')])}
from journal32 import ProofJournal,SimulatedCrash
from verifier31 import load_original_case
from prefix31 import project_prefix
cid={cid!r};inp,p,d,arc=load_original_case(cid);c,_=arc(63)
with ProofJournal({str(target)!r},inp,p,d,case_id=cid) as j:
    try:j.append(project_prefix(c,15),crash_at={mode!r})
    except SimulatedCrash:os._exit(79)
os._exit(78)
'''
            p=subprocess.run([sys.executable,'-c',child_code],capture_output=True,text=True,timeout=90)
            if p.returncode!=79:raise AssertionError('Expected abrupt child termination '+str((mode,p.returncode,p.stderr)))
            with ProofJournal(target,inp,proto,duals,case_id=cid) as j:
                expected=7 if mode=='before_rename' else 15
                if j.recovery_fresh!=expected:raise AssertionError('Incorrect durable commit boundary')
                if mode=='before_rename':
                    if j.discard_pending()!=1:raise AssertionError('Pre-rename temporary write missing')
                    j.append(c15)
                else:
                    if not j.append(c15)['already_committed']:raise AssertionError('Duplicate committed extension')
            with ProofJournal(target,inp,proto,duals,case_id=cid) as j:
                if j.recovery_fresh!=15 or len(j.cert['nodes'])!=15:
                    raise AssertionError('Mathematical restart recheck failed')
                out.append({'mode':mode,'child_exit_code':p.returncode,
                            'fresh_rechecked_before_recovery':expected,
                            'final_cold_rechecked_nodes':j.recovery_fresh,
                            'head_sha256':j.head,'accepted':True})
    (D/'hard_exit_results.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print('CH32 ACTUAL PROCESS EXIT PASS',json.dumps(out))
if __name__=='__main__':run()
