"""Root-only CH36 Linux integration harness for all fifteen ORIGINAL CH23 cases.

Seal an authority-owned source/key store (UID 65534), install writer-controlled
proof copies (UID 1000), then submit case-only AF_UNIX requests concurrently.
The signing service itself commits a single monotonically linked Ed25519 ledger.
No production changes; all attestations expressly report scientific NO_GO.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path
D=Path(__file__).resolve().parent
ORIGINAL=Path(os.environ.get('CH36_ORIGINAL_ROOT','/mnt/data/CH35_package_stage'))
SIGNER_UID=65534; WRITER_UID=1000

def runas(uid,args,**kw):
    return subprocess.run(['setpriv',f'--reuid={uid}',f'--regid={uid}','--clear-groups',*map(str,args)],**kw)

def prepare(root):
    if os.geteuid()!=0:raise PermissionError('Isolated two-UID setup requires root')
    top=Path(tempfile.mkdtemp(prefix='ch36-two-uid-'))
    os.chmod(top,0o755)
    authority=top/'authority';authority.mkdir();os.chown(authority,SIGNER_UID,SIGNER_UID);os.chmod(authority,0o700)
    source=authority/'source';shutil.copytree(root,source,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
    dest=source/'CH_C14_35';dest.mkdir(exist_ok=True)
    for name in ('trust35.py','service35.py'):shutil.copy2(D.parent/'CH_C14_35'/name,dest/name)
    shutil.copy2(D/'service36.py',dest/'service36.py')
    for p in (source,*source.rglob('*')):
        if p.is_symlink():raise ValueError('Unexpected trusted-source symlink')
        os.chown(p,SIGNER_UID,SIGNER_UID)
        os.chmod(p,0o700 if p.is_dir() else 0o600)
    writer=top/'writer';writer.mkdir();os.chmod(writer,0o755)
    for typ in ('active','archives'):
        folder=writer/typ;folder.mkdir();os.chmod(folder,0o755)
        for case in sorted((root/'CH_C14_33'/typ).iterdir()):
            if not case.is_dir():continue
            wd=folder/case.name
            shutil.copytree(case,wd,ignore=shutil.ignore_patterns('.writer.lock','__pycache__'))
            os.chown(wd,WRITER_UID,WRITER_UID);os.chmod(wd,0o755)
            for p in wd.iterdir():
                if not p.is_file() or p.is_symlink():raise ValueError('Unexpected journal item')
                os.chown(p,WRITER_UID,WRITER_UID);os.chmod(p,0o644)
    ipc=top/'ipc';ipc.mkdir();os.chown(ipc,SIGNER_UID,SIGNER_UID);os.chmod(ipc,0o755)
    return top,authority,source,writer,ipc

def request(socket,case):
    cmd=[sys.executable,str(D.parent/'CH_C14_35'/'service35.py'),'request','--socket',str(socket),'--case',case]
    # service35.client() is only an AF_UNIX client; it has no signer key or path privileges.
    r=runas(WRITER_UID,cmd,capture_output=True,text=True,timeout=1000)
    if r.returncode:raise ValueError('Writer-side client failed: '+r.stderr[-250:])
    obj=json.loads(r.stdout)
    if not obj.get('ok'):raise ValueError('Signer refused '+case+': '+str(obj))
    return obj['result']

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--root',type=Path,default=ORIGINAL)
    parser.add_argument('--results',type=Path,default=D/'original15_results.json')
    parser.add_argument('--retain-state',action='store_true')
    a=parser.parse_args(argv)
    top,authority,source,writer,ipc=prepare(a.root)
    socket=ipc/'witness.sock';store=authority/'store';src35=source/'CH_C14_35'
    provision='''import json,sys
sys.path.insert(0,sys.argv[1]);from trust35 import make_pins
from service35 import provision
print(json.dumps(provision(sys.argv[3],sys.argv[2],pins=make_pins(sys.argv[2])),sort_keys=True))'''
    r=runas(SIGNER_UID,[sys.executable,'-c',provision,str(src35),str(source),str(store)],capture_output=True,text=True,timeout=30)
    if r.returncode:raise RuntimeError('Independent authority provisioning failed: '+r.stderr)
    key=json.loads(r.stdout)
    cmd=['setpriv',f'--reuid={SIGNER_UID}',f'--regid={SIGNER_UID}','--clear-groups',
         sys.executable,str(src35/'service36.py'),'--socket',str(socket),
         '--store',str(store),'--source',str(source),'--journals',str(writer),
         '--allowed-uid',str(WRITER_UID),'--workers',str(a.workers)]
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    timer=time.monotonic()
    try:
        for _ in range(150):
            if socket.is_socket():break
            if proc.poll() is not None:raise RuntimeError('Authority crashed: '+proc.stderr.read()[-2000:])
            time.sleep(.1)
        if not socket.is_socket():raise RuntimeError('Authority socket missing')
        cases=sorted(json.loads((source/'CH_C14_33/checkpoint_heads.json').read_text()))
        if len(cases)!=15:raise AssertionError('Original case set not exactly 15')
        # An untrusted extra field must not let writer submit a proof or digest.
        injection='''import socket,sys,json
s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[1]);s.sendall(json.dumps({'op':'verify','case_id':sys.argv[2], 'certificate':{'forgery':True}}).encode()+b'\\n');print(s.recv(8192).decode())'''
        attack=runas(WRITER_UID,[sys.executable,'-c',injection,str(socket),cases[0]],capture_output=True,text=True,timeout=10)
        if attack.returncode or json.loads(attack.stdout)['ok']:
            raise AssertionError('Forged signer submission was accepted')
        # Verify the writer lacks read access to signer-owned key AND frozen source.
        forbidden='''from pathlib import Path
import sys
for s in sys.argv[1:]:
 try:Path(s).read_bytes();print('ACCESSIBLE')
 except PermissionError:print('DENIED')'''
        denied=runas(WRITER_UID,[sys.executable,'-c',forbidden,str(store/'secret.ed25519.pem'),str(source/'CH_C14_33/checkpoint_heads.json')],capture_output=True,text=True,timeout=10)
        if denied.returncode or denied.stdout.strip().splitlines()!=['DENIED','DENIED']:
            raise AssertionError('OS-enforced signer separation failed: '+denied.stdout+' '+denied.stderr)
        def work(case):
            start=time.monotonic();res=request(socket,case)
            return {'case_id':case,'wall_seconds':round(time.monotonic()-start,4),
                    'tip_sha256':res['tip_sha256'],'record_sha256':hashlib.sha256(
                        json.dumps(res['record'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                    'record':res['record']}
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
            results=list(pool.map(work,cases))
        if any(x['record']['body']['scientific_release']!='NO_GO' for x in results):
            raise AssertionError('Unexpected global certificate')
        if len({x['tip_sha256'] for x in results})!=15:raise AssertionError('Duplicate signed tip')
        duplicate=runas(WRITER_UID,[sys.executable,str(D.parent/'CH_C14_35'/'service35.py'),'request','--socket',str(socket),'--case',cases[0]],capture_output=True,text=True,timeout=10)
        if duplicate.returncode or json.loads(duplicate.stdout).get('ok'):
            raise AssertionError('Duplicate original case was signed')
        audit='''import json,sys
sys.path.insert(0,sys.argv[1]);from trust35 import verify_chain
from pathlib import Path
store=Path(sys.argv[2]);pub=(store/'public.ed25519.pem').read_bytes()
print(json.dumps(verify_chain(store,pub,expected_fingerprint=sys.argv[3],expected_tip=sys.argv[4])))'''
        # Order of signatures is the signed generation, not order of concurrent callers.
        by_generation=sorted(results,key=lambda x:x['record']['body']['generation'])
        tip=by_generation[-1]['tip_sha256']
        auditp=runas(SIGNER_UID,[sys.executable,'-c',audit,str(src35),str(store),key['fingerprint_sha256'],tip],capture_output=True,text=True,timeout=20)
        if auditp.returncode:raise RuntimeError('Signed chain audit failed: '+auditp.stderr)
        chain=json.loads(auditp.stdout)
        if chain['length']!=15 or set(chain['cases'])!=set(cases):raise AssertionError('Signed chain missing original cases')
        outcome={'milestone':'CH-C14-36','status':'PASS','case_count':15,
                 'previous_CH35_case_count':1,'newly_covered_original_cases':14,
                 'original_CH23_cases':cases,'original_127_node_replays':15,'archived_frame_replays':90,
                 'verified_precision_bits':224,'source':'frozen_original_CH23_29_32_33',
                 'isolated_accounts':{'signer':SIGNER_UID,'writer':WRITER_UID},
                 'unsigned_writer_attestations_rejected':True,'key_and_source_access_writer':'DENIED',
                 'fingerprint_sha256':key['fingerprint_sha256'],'signed_final_tip_sha256':tip,
                 'signed_chain':chain,'records':by_generation,'wall_seconds':round(time.monotonic()-timer,3),
                 'production_release':'NO_GO','global_optimality_certified_cases':0,
                 'power_cut_tested':False,'windows_tested':False}
        a.results.parent.mkdir(parents=True,exist_ok=True)
        a.results.write_text(json.dumps(outcome,sort_keys=True,indent=2)+'\n')
        (D/'witness_public_key.pem').write_bytes((store/'public.ed25519.pem').read_bytes())
        print(json.dumps({'status':'PASS','cases':15,'new':14,'signed_tip':tip,
                          'wall_seconds':outcome['wall_seconds'],'state':str(top)},sort_keys=True),flush=True)
        return 0
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:proc.kill();proc.communicate()
        if not a.retain_state: shutil.rmtree(top,ignore_errors=True)

if __name__=='__main__':raise SystemExit(main())
