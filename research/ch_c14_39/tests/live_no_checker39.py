"""Live Linux proof-signing must fail closed when checker UID 1004 is absent."""
import json,os,shutil,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness39 import *
HERE=Path(__file__).resolve().parents[1]

def main(base):
    st=make_root(Path(base));rt=st['root'];procs=[];case='one_event_n80_i00';t=time.monotonic()
    try:
        fixture=rt/'math/code/forged_math_uid.py';shutil.copyfile(HERE/'tests/forged_math_uid.py',fixture)
        os.chown(fixture,MATH_UID,MATH_UID);fixture.chmod(0o600)
        mp=launch(MATH_UID,[fixture,'--socket',st['math_sock'],'--pins',st['math_private']/'frozen_pins.json',
                       '--attestor-uid',ATTESTOR_UID]);procs.append(mp);ready(st['math_sock'],mp)
        at=launch(ATTESTOR_UID,[rt/'attestor/code/attestor39.py',
             '--socket',st['attestor_sock'],'--private',st['attestor_private'],
             '--math-socket',st['math_sock'],'--checker-socket',st['checker_sock'],
             '--math-uid',MATH_UID,'--checker-uid',CHECKER_UID,'--signer-uid',SIGNER_UID],
             groups=f'{ATTESTOR_TO_MATH_GID},{ATTESTOR_TO_CHECKER_GID}');procs.append(at);ready(st['attestor_sock'],at)
        sg=launch(SIGNER_UID,[rt/'signer/code/signer39.py','--socket',st['signer_sock'],
          '--store',st['signer_private'],'--attestor-socket',st['attestor_sock'],
          '--writer-uid',WRITER_UID,'--attestor-uid',ATTESTOR_UID],groups=SIGNER_TO_ATTESTOR_GID)
        procs.append(sg);ready(st['signer_sock'],sg)
        denied=writer_request(st['signer_sock'],{'op':'verify','case_id':case},timeout=15)
        if denied.get('ok') is not False or (st['signer_private']/'HEAD').exists():
            raise AssertionError('Absent checker did not fail closed')
        result={'status':'PASS','checker_running':False,'signed_witness':False,'worker_claimed_success':True,
                'attestor_response':denied,'elapsed_wall_seconds':round(time.monotonic()-t,3)}
        (HERE/'no_checker_results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    finally:
        for p in reversed(procs):stop(p)
        shutil.rmtree(rt,ignore_errors=True)
if __name__=='__main__':main(sys.argv[1])
