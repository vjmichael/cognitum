"""Actual cross-UID malicious worker replay attack: checker must refuse."""
from __future__ import annotations
import json,shutil,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness39 import *
HERE=Path(__file__).resolve().parents[1]

def main():
    state=make_root(Path(sys.argv[1]));root=state['root'];ps=[]
    case='one_event_n80_i00'; start=time.monotonic()
    try:
        # Fake compromised UID1002 process has no MPFR code and fabricates success.
        fixture=root/'math'/'code'/'forged_math_uid.py'
        shutil.copy2(HERE/'tests'/'forged_math_uid.py',fixture)
        os.chown(fixture,MATH_UID,MATH_UID);fixture.chmod(0o600)
        fake=launch(MATH_UID,[fixture,'--socket',state['math_sock'],
           '--pins',state['math_private']/'frozen_pins.json','--attestor-uid',ATTESTOR_UID]);ps.append(fake)
        ready(state['math_sock'],fake)
        ck=launch(CHECKER_UID,[state['checker_source']/'CH_C14_39/checker39.py',
          '--socket',state['checker_sock'],'--private',state['checker_private'],
          '--source',state['checker_source'],'--proofs',state['checker_proof'],
          '--attestor-uid',ATTESTOR_UID,'--math-uid',MATH_UID,'--workers','1']);ps.append(ck)
        ready(state['checker_sock'],ck)
        at=launch(ATTESTOR_UID,[root/'attestor/code/attestor39.py',
          '--socket',state['attestor_sock'],'--private',state['attestor_private'],
          '--math-socket',state['math_sock'],'--checker-socket',state['checker_sock'],
          '--math-uid',MATH_UID,'--checker-uid',CHECKER_UID,'--signer-uid',SIGNER_UID],
          groups=f'{ATTESTOR_TO_MATH_GID},{ATTESTOR_TO_CHECKER_GID}');ps.append(at)
        ready(state['attestor_sock'],at)
        sg=launch(SIGNER_UID,[root/'signer/code/signer39.py','--socket',state['signer_sock'],
          '--store',state['signer_private'],'--attestor-socket',state['attestor_sock'],
          '--writer-uid',WRITER_UID,'--attestor-uid',ATTESTOR_UID],groups=SIGNER_TO_ATTESTOR_GID);ps.append(sg)
        ready(state['signer_sock'],sg)
        # With the independent checker UNAVAILABLE, attestor must never sign.
        # Here the checker is available but its true MPFR bound differs from the forged report.
        result=writer_request(state['signer_sock'],{'op':'verify','case_id':case},timeout=900)
        if result.get('ok') is not False:raise AssertionError('FORGED MATHEMATICS ACCEPTED')
        if (state['signer_private']/'HEAD').exists():raise AssertionError('Signed witness unexpectedly created')
        info={'status':'PASS','attack':'SYNTACTICALLY_VALID_FALSE_MPFR_ATTESTATION','math_uid':MATH_UID,
              'checker_uid':CHECKER_UID,'signature_created':False,'original_case_id':case,
              'attestor_refusal':result,'elapsed_wall_seconds':round(time.monotonic()-start,3)}
        (HERE/'forgery_results.json').write_text(json.dumps(info,indent=2,sort_keys=True)+'\n')
        print(json.dumps(info,sort_keys=True),flush=True)
    finally:
        for p in reversed(ps):stop(p)
        shutil.rmtree(root,ignore_errors=True)
if __name__=='__main__':main()