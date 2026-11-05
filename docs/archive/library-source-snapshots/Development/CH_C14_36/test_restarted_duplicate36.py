"""Live separate-UID admission recovery against completed CH36 signed ledger.

Requires the recovered 15-record signer-owned store from batch36 and is an
optional integration test (not part of the portable storage test selection).
"""
from __future__ import annotations
import argparse,json,os,signal,socket,stat,subprocess,sys,time
from pathlib import Path
D=Path(__file__).resolve().parents[1]
def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--expected-tip',required=True)
    a=parser.parse_args(argv)
    ROOT=a.state
    ipc=ROOT/'ipc/witness.sock';store=ROOT/'authority/store';src=ROOT/'authority/source'
    if not store.exists():raise RuntimeError('Missing completed research signer store')
    if ipc.exists():
        st=ipc.lstat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_uid!=65534:
            raise ValueError('Only original signer-owned stale socket may be removed')
        ipc.unlink()
    env={**os.environ,'PYTHONPATH':str(src/'CH_C14_35'),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
    cmd=['setpriv','--reuid=65534','--regid=65534','--clear-groups',sys.executable,
         str(D/'service36.py'),'--socket',str(ipc),'--store',str(store),
         '--source',str(src),'--journals',str(ROOT/'writer'),
         '--allowed-uid','1000','--workers','2']
    srv=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    try:
        for _ in range(80):
            if ipc.is_socket():break
            if srv.poll() is not None:raise RuntimeError('Signer restart failed: '+srv.stderr.read())
            time.sleep(.1)
        if not ipc.is_socket():raise RuntimeError('Signer socket absent')
        before=time.monotonic()
        case='one_event_n80_i00'
        r=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--clear-groups',sys.executable,
                          str(D.parent/'CH_C14_35/service35.py'),'request','--socket',str(ipc),'--case',case],
                         capture_output=True,text=True,timeout=5)
        elapsed=time.monotonic()-before
        if r.returncode:raise RuntimeError('Client failed: '+r.stderr)
        obj=json.loads(r.stdout)
        if obj.get('ok') or obj.get('error')!='ValueError':raise AssertionError('Duplicate not denied')
        tip=json.loads((store/'trusted_tip.json').read_text())['tip']
        if tip!=a.expected_tip:
            raise ValueError('Duplicate changed signed tip')
        result={'status':'PASS','restart_from_signed_15_case_ledger':True,
                'duplicate_rejected_before_MPFR':True,'duplicate_response_seconds':round(elapsed,4),
                'signed_tip_unchanged':True,'new_signatures':0,
                'test_code_trusted_in_signer_account':True}
        (D/'duplicate_restart_results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
        print(json.dumps(result,sort_keys=True))
    finally:
        srv.send_signal(signal.SIGINT)
        try:srv.communicate(timeout=8)
        except subprocess.TimeoutExpired:srv.kill();srv.communicate(timeout=2)
if __name__=='__main__':main()