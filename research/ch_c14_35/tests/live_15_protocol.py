"""One genuine CH23 replay by an isolated Linux signer process.

The test actually runs signer UID 65534 and writer UID 1000. Source code, trusted
frozen inputs and the private signing key are in a signer-only directory.
The writer owns only an externally readable/modifiable journal copy and IPC.
"""
from pathlib import Path
import argparse, hashlib, json, os, pwd, shutil, signal, subprocess, sys, tempfile, time

ROOT=Path(os.environ.get('CH35_REPRO_ROOT', Path(__file__).resolve().parents[2]))
if not (ROOT/'CH_C14_33').is_dir() and Path('/mnt/data/CH34_repro').is_dir():
    ROOT=Path('/mnt/data/CH34_repro')
CH35=Path(__file__).resolve().parents[1]
SIGNER_UID=65534; WRITER_UID=1000


def runas(uid,args,**kw):
    return subprocess.run(['setpriv',f'--reuid={uid}',f'--regid={uid}','--clear-groups']+list(args),**kw)


def make():
    top=Path(tempfile.mkdtemp(prefix='ch35-trust-separation-'))
    os.chmod(top,0o755)
    sealed=top/'signer' ;sealed.mkdir()
    os.chown(sealed,SIGNER_UID,SIGNER_UID);os.chmod(sealed,0o700)
    src=sealed/'source'
    shutil.copytree(ROOT,src,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
    dest=src/'CH_C14_35';dest.mkdir()
    for name in ('trust35.py','service35.py'):
        shutil.copy2(CH35/name,dest/name)
    for p in [src,*src.rglob('*')]:
        if p.is_symlink():raise ValueError('Trusted source may not be symlinked')
        os.chown(p,SIGNER_UID,SIGNER_UID)
        if p.is_dir():os.chmod(p,0o700)
        else:os.chmod(p,0o600)
    ipc=top/'ipc';ipc.mkdir();os.chown(ipc,SIGNER_UID,SIGNER_UID);os.chmod(ipc,0o755)
    writer=top/'writer';writer.mkdir();os.chmod(writer,0o755)
    case='one_event_n80_i00'
    for typ in ('active','archives'):
        d=writer/typ;d.mkdir();os.chmod(d,0o755)
        case_dir=d/case;shutil.copytree(ROOT/'CH_C14_33'/typ/case,case_dir)
        os.chown(case_dir,WRITER_UID,WRITER_UID);os.chmod(case_dir,0o755)
        for p in case_dir.iterdir():
            os.chown(p,WRITER_UID,WRITER_UID);os.chmod(p,0o644)
    return top,sealed,src,ipc,writer,case


def one_request(socket_path,case):
    code='''import json,socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(800);s.connect(sys.argv[1]);s.sendall(json.dumps({'op':'verify','case_id':sys.argv[2]}).encode()+b'\\n')
raw=b''
while not raw.endswith(b'\\n'):
 c=s.recv(65536)
 if not c:break
 raw+=c
print(raw.decode())'''
    # Replace escaped literal sequence with one Python escaped newline in code.
    code=code.replace("b'\\\\n'", "b'\\n'")
    r=runas(WRITER_UID,[sys.executable,'-c',code,str(socket_path),case],capture_output=True,text=True,timeout=700)
    if r.returncode:raise RuntimeError(f'Client failure rc={r.returncode}: {r.stderr}')
    return json.loads(r.stdout)


def main():
    top,sealed,src,ipc,writer,case=make()
    signer=src/'CH_C14_35'
    socket_path=ipc/'proof.sock'
    store=sealed/'store'
    code='''import json,sys
sys.path.insert(0,sys.argv[1])
from trust35 import make_pins
from service35 import provision
pins=make_pins(sys.argv[2]);print(json.dumps(provision(sys.argv[3],sys.argv[2],pins=pins),sort_keys=True))'''
    proc=runas(SIGNER_UID,[sys.executable,'-c',code,str(signer),str(src),str(store)],capture_output=True,text=True,timeout=30)
    if proc.returncode:raise RuntimeError('Signer provisioning failed: '+proc.stderr)
    identity=json.loads(proc.stdout)
    cmd=['setpriv',f'--reuid={SIGNER_UID}',f'--regid={SIGNER_UID}','--clear-groups',
         sys.executable,str(signer/'service35.py'),'serve','--socket',str(socket_path),
         '--store',str(store),'--source',str(src),'--journals',str(writer),'--allowed-uid',str(WRITER_UID)]
    server=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        for _ in range(100):
            if socket_path.exists():break
            if server.poll() is not None:raise RuntimeError('Witness exited: '+server.stderr.read())
            time.sleep(.1)
        if not socket_path.exists():raise RuntimeError('Witness socket not created')
        access='''from pathlib import Path
import sys
for p in sys.argv[1:]:
 try:p2=Path(p);p2.read_bytes();print('WRITER_READ_KEY_UNEXPECTED')
 except (PermissionError,FileNotFoundError):print('KEY_ACCESS_DENIED')
try:Path(sys.argv[1]).write_text('forged');print('WRITER_WRITE_UNEXPECTED')
except PermissionError:print('KEY_MODIFY_DENIED')'''
        deny=runas(WRITER_UID,[sys.executable,'-c',access,str(store/'secret.ed25519.pem'),str(src/'CH_C14_29/frozen_protocol.json')],capture_output=True,text=True,timeout=10)
        if deny.returncode or deny.stdout.count('KEY_ACCESS_DENIED')!=2 or 'KEY_MODIFY_DENIED' not in deny.stdout:
            raise AssertionError('OS trust-domain separation failed: '+deny.stdout+'\n'+deny.stderr)
        cp=writer/'active'/case/'checkpoint.json'
        raw=cp.read_bytes();cp.write_bytes(raw[:-1]+b'X')
        tampered=one_request(socket_path,case)
        if tampered['ok']:raise AssertionError('Authority signed corrupted original checkpoint')
        cp.write_bytes(raw)
        started=time.time()
        signed=one_request(socket_path,case)
        elapsed=time.time()-started
        if not signed['ok']:raise AssertionError('Original independent MPFR verification failed: '+str(signed))
        second=one_request(socket_path,case)
        if second['ok']:raise AssertionError('Duplicate signed original case')
        # Writer cannot alter key, signed revisions or the protected tip.
        deny2='''from pathlib import Path
import sys
for p in sys.argv[1:]:
 try:Path(p).write_bytes(b'garbage');print('WRITE_SUCCEEDED')
 except PermissionError:print('WRITE_DENIED')'''
        q=runas(WRITER_UID,[sys.executable,'-c',deny2,str(store/'trusted_tip.json'),str(store/'HEAD'),str(store/'revisions')],capture_output=True,text=True,timeout=10)
        if q.stdout.count('WRITE_DENIED')!=3 or q.returncode:
            raise AssertionError('Authority writer-side isolation failed: '+q.stdout+' '+q.stderr)
        validation='''import json,sys
sys.path.insert(0,sys.argv[1]);from trust35 import verify_chain
from pathlib import Path
store=Path(sys.argv[2]);tip=sys.argv[3];pub=(store/'public.ed25519.pem').read_bytes();fp=sys.argv[4]
print(json.dumps(verify_chain(store,pub,expected_fingerprint=fp,expected_tip=tip)))'''
        tip=signed['result']['tip_sha256']
        report=runas(SIGNER_UID,[sys.executable,'-c',validation,str(signer),str(store),tip,identity['fingerprint_sha256']],capture_output=True,text=True,timeout=10)
        if report.returncode:raise RuntimeError('Public signed replay failed: '+report.stderr)
        (CH35/'witness_public_key.pem').write_bytes((store/'public.ed25519.pem').read_bytes())
        results={'status':'PASS','case':case,'source':'original_CH23','independent_user_ids':{'signer':SIGNER_UID,'journal_writer':WRITER_UID},
                 'key_read_and_write_denied':True,'sealed_frozen_inputs_unreadable_to_writer':True,
                 'tampered_journal_denied':tampered,'signed_original':signed['result'],'second_sign_refused':second,
                 'verified_chain':json.loads(report.stdout),'mpfr_end_to_end_wall_seconds':elapsed,
                 'root':str(top),'power_loss_tested':False,'windows_tested':False,'global_certificate':False}
        (CH35/'independent_process_results.json').write_text(json.dumps(results,sort_keys=True,indent=2)+'\n')
        print(json.dumps({'status':'PASS','case':case,'tip':tip,'writer_key_access':'DENIED','original_math_replayed':True,'wall_seconds':elapsed,'root':str(top)},sort_keys=True))
        return 0
    finally:
        server.terminate()
        try:server.communicate(timeout=10)
        except subprocess.TimeoutExpired:server.kill();server.communicate()

if __name__=='__main__':raise SystemExit(main())
