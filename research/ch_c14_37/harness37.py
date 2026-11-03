"""Root-operated disposable three-account Linux acceptance against exact CH23.

Source and private authority material are never placed in the distribution.
No public data is called a remote trust anchor. No Windows or power-cut claim.
"""
from __future__ import annotations
import argparse, concurrent.futures, json, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path
from protocol37 import canonical,sha,request,parse
from trust37 import audit_chain,provision_signer
HERE=Path(__file__).resolve().parent
VERIFIER_UID=1002;SIGNER_UID=65534;WRITER_UID=1000;INTEROP_GID=3101
ORIGINAL=Path('/mnt/data/CH37_baseline')

def runas(uid,cmd,*,groups=None,**kw):
    a=['setpriv',f'--reuid={uid}',f'--regid={uid}',
        '--clear-groups' if groups is None else '--groups='+str(groups), *map(str,cmd)]
    return subprocess.run(a,**kw)

def chown_sealed(tree,uid,gid):
    for p in (tree,*tree.rglob('*')):
        if p.is_symlink():raise ValueError('Symlink forbidden in frozen trusted source')
        os.chown(p,uid,gid)
        os.chmod(p,0o700 if p.is_dir() else 0o600)

def copy_to_verifier(source,top):
    vr=top/'verifier';vr.mkdir();os.chown(vr,VERIFIER_UID,VERIFIER_UID);os.chmod(vr,0o700)
    src=vr/'source';shutil.copytree(source,src,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
    local=src/'CH_C14_37';local.mkdir(exist_ok=True)
    for name in ['protocol37.py','trust37.py','verifier37.py']:
        shutil.copy2(HERE/name,local/name)
    # CH35 original replay implementation (unchanged) must be in verifier source.
    original35=HERE.parent/'CH_C14_35'/'trust35.py'
    if original35.exists():shutil.copy2(original35,src/'CH_C14_35'/'trust35.py')
    proof=vr/'proofs';proof.mkdir()
    for typ in ('active','archives'):
        shutil.copytree(source/'CH_C14_33'/typ,proof/typ,
                        ignore=shutil.ignore_patterns('.writer.lock','__pycache__'))
    chown_sealed(src,VERIFIER_UID,VERIFIER_UID);chown_sealed(proof,VERIFIER_UID,VERIFIER_UID)
    return vr,src,proof

def assert_denied(uid,paths,groups=None):
    code='''import json,sys
from pathlib import Path
out=[]
for x in sys.argv[1:]:
 try:Path(x).read_bytes();out.append('READ')
 except PermissionError:out.append('DENIED')
print(json.dumps(out))'''
    r=runas(uid,[sys.executable,'-c',code,*paths],groups=groups,capture_output=True,text=True,timeout=12)
    if r.returncode:raise AssertionError('Privilege probe crashed: '+r.stderr)
    values=json.loads(r.stdout)
    if values!=['DENIED']*len(paths):raise AssertionError('Cross-UID secret accessible: '+repr(values))
    return values

def setup(base):
    if os.geteuid()!=0:raise PermissionError('Real Linux UID acceptance requires root')
    root=Path(tempfile.mkdtemp(prefix='CH37-three-uid-'));os.chmod(root,0o755)
    vr,src,proof=copy_to_verifier(base,root)
    signer=root/'signer';signer.mkdir();os.chown(signer,SIGNER_UID,SIGNER_UID);os.chmod(signer,0o700)
    code=signer/'code';code.mkdir()
    for n in ('protocol37.py','trust37.py','signer37.py'):
        shutil.copy2(HERE/n,code/n)
    chown_sealed(code,SIGNER_UID,SIGNER_UID)
    verifystore=vr/'private'
    cmd='''import json,sys
sys.path.insert(0,sys.argv[1]);from verifier37 import provision_verifier
print(json.dumps(provision_verifier(sys.argv[2],sys.argv[3]),sort_keys=True))'''
    v=runas(VERIFIER_UID,[sys.executable,'-c',cmd,str(src/'CH_C14_37'),str(verifystore),str(src)],capture_output=True,text=True,timeout=30)
    if v.returncode:raise RuntimeError('Verifier provisioning failed: '+v.stderr)
    vp=json.loads(v.stdout)
    # Operator copies ONLY public verifier key and frozen pins. Not verifier secret.
    setupdir=signer/'bootstrap';setupdir.mkdir()
    for f in ('verifier_public.ed25519.pem','frozen_pins.json'):
        shutil.copy2(verifystore/f,setupdir/f)
    chown_sealed(setupdir,SIGNER_UID,SIGNER_UID)
    signerstore=signer/'private'
    code2='''import json,sys
sys.path.insert(0,sys.argv[1]);from trust37 import provision_signer
from protocol37 import parse
from pathlib import Path
r=provision_signer(sys.argv[2],Path(sys.argv[3]).read_bytes(),parse(Path(sys.argv[4]).read_bytes()))
print(json.dumps(r,sort_keys=True))'''
    s=runas(SIGNER_UID,[sys.executable,'-c',code2,str(code),str(signerstore),
                str(setupdir/'verifier_public.ed25519.pem'),str(setupdir/'frozen_pins.json')],capture_output=True,text=True,timeout=25)
    if s.returncode:raise RuntimeError('Signer provisioning failed: '+s.stderr)
    sp=json.loads(s.stdout)
    if sp['verifier_fingerprint_sha256']!=vp['verifier_fingerprint_sha256'] or sp['policy_sha256']!=vp['policy_sha256']:
        raise AssertionError('Independent accounts provisioned with different policy')
    # Same-host group-gated sockets, with peer credentials as second check.
    ipc= root/'ipc';ipc.mkdir();os.chmod(ipc,0o755)
    verifieripc=ipc/'verifier';verifieripc.mkdir();os.chown(verifieripc,VERIFIER_UID,INTEROP_GID);os.chmod(verifieripc,0o2750)
    signeripc=ipc/'signer';signeripc.mkdir();os.chown(signeripc,SIGNER_UID,WRITER_UID);os.chmod(signeripc,0o2750)
    return {'root':root,'verifier':vr,'source':src,'proofs':proof,'signer':signer,
            'verifier_store':verifystore,'signer_store':signerstore,'verifier_sock':verifieripc/'prove.sock',
            'signer_sock':signeripc/'witness.sock','vp':vp,'sp':sp}

def launch(uid,argv,groups=None):
    command=['setpriv',f'--reuid={uid}',f'--regid={uid}',
             '--clear-groups' if groups is None else '--groups='+str(groups),sys.executable,*map(str,argv)]
    return subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                            text=True,start_new_session=True)

def ready(sock,process):
    for _ in range(300):
        if sock.is_socket():return
        if process.poll() is not None:raise RuntimeError('Authority exited early: '+process.stderr.read()[-1200:])
        time.sleep(.1)
    raise RuntimeError('Authority IPC unavailable')

def stop(p):
    if p is None:return
    try:
        if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
        p.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL);p.communicate(timeout=5)

def exercise(base,caseids,results,keep=False):
    st=setup(base);vs=None;ss=None;tick=time.monotonic()
    try:
        vs=launch(VERIFIER_UID,[st['source']/'CH_C14_37'/'verifier37.py',
            '--socket',st['verifier_sock'],'--private',st['verifier_store'],
            '--source',st['source'],'--proofs',st['proofs'],'--signer-uid',str(SIGNER_UID),'--workers','4'])
        ready(st['verifier_sock'],vs)
        ss=launch(SIGNER_UID,[st['signer']/'code'/'signer37.py',
            '--socket',st['signer_sock'],'--store',st['signer_store'],
            '--verifier-socket',st['verifier_sock'],'--writer-uid',str(WRITER_UID),
            '--verifier-uid',str(VERIFIER_UID)],groups=INTEROP_GID)
        ready(st['signer_sock'],ss)
        key_paths=[st['verifier_store']/'verifier_secret.ed25519.pem',
                   st['signer_store']/'secret.ed25519.pem',st['source']/'CH_C14_33'/'checkpoint_heads.json']
        assert_denied(WRITER_UID,key_paths)
        assert_denied(VERIFIER_UID,[key_paths[1]])
        assert_denied(SIGNER_UID,[key_paths[0],key_paths[2]],groups=INTEROP_GID)
        # Signer and verifier identities never share writable credentials.
        blocked=runas(WRITER_UID,[sys.executable,'-c',
                 'import socket,sys;s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[1])',str(st['verifier_sock'])],
                 capture_output=True,text=True,timeout=8)
        if blocked.returncode==0:raise AssertionError('Writer connected to verifier socket')
        extra=request_writer(st['signer_sock'],{'op':'verify','case_id':caseids[0], 'attestation':{'fake':'ok'}})
        if extra.get('ok') is not False:raise AssertionError('Signer accepted injected attestation')
        # Verifier caller cannot invoke signer socket (directory ACL/UID).
        forbidden=runas(VERIFIER_UID,[sys.executable,'-c',
                   'import socket,sys;s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[1])',str(st['signer_sock'])],
                   capture_output=True,text=True,timeout=8)
        if forbidden.returncode==0:raise AssertionError('Verifier can connect directly to signer')
        def do_case(case):
            t=time.monotonic()
            res=request_writer(st['signer_sock'],{'op':'verify','case_id':case},timeout=1200)
            if not res.get('ok'):raise RuntimeError('Signer refused original '+case+': '+str(res))
            item=res['result'];return item,round(time.monotonic()-t,2)
        out=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            for item,secs in p.map(do_case,caseids):
                out.append(item)
                print('PASS',item['case_id'],'uid split verifier',VERIFIER_UID,
                      'signer',SIGNER_UID,'seconds',secs,flush=True)
        out.sort(key=lambda item:item['record']['body']['generation'])
        dupe=request_writer(st['signer_sock'],{'op':'verify','case_id':caseids[0]},timeout=15)
        if dupe.get('ok') is not False:raise AssertionError('Duplicate case signed twice')
        wronguid=runas(VERIFIER_UID,[sys.executable,'-c',
                    'import socket,sys;s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[1])',str(st['signer_sock'])],
                    capture_output=True,text=True,timeout=6)
        if wronguid.returncode==0:raise AssertionError('Verifier bypassed signer ACL')
        import sys as _sys
        _sys.path.insert(0,str(HERE))
        a=st['signer_store'];pin=parse((a/'frozen_pins.json').read_bytes())
        audit=audit_chain(a,(a/'public.ed25519.pem').read_bytes(),(a/'verifier_public.ed25519.pem').read_bytes(),
               signer_fingerprint=st['sp']['signer_fingerprint_sha256'],verifier_fingerprint=st['vp']['verifier_fingerprint_sha256'],
               expected_tip=out[-1]['tip_sha256'],pins=pin)
        if audit['length']!=len(caseids) or set(audit['cases'])!=set(caseids):raise AssertionError('Incomplete signed chain')
        results.parent.mkdir(parents=True,exist_ok=True)
        export=results.parent/'CH37_public_witness'
        export.mkdir(exist_ok=True)
        (export/'revisions').mkdir(exist_ok=True)
        for f in (a/'revisions').iterdir():shutil.copyfile(f,export/'revisions'/f.name)
        for f in ['HEAD','public.ed25519.pem','verifier_public.ed25519.pem','frozen_pins.json']:
            shutil.copyfile(a/f,export/f)
        result={'milestone':'CH-C14-37','status':'PASS','original_CH23_cases_tested':caseids,
               'case_count':len(caseids),'verifier_uid':VERIFIER_UID,'signer_uid':SIGNER_UID,
               'writer_uid':WRITER_UID,'signer_private_key_access_by_verifier':'DENIED',
               'verifier_private_key_access_by_signer':'DENIED','writer_direct_verifier_socket':'DENIED',
               'verifier_direct_signer_socket':'DENIED','writer_injected_ticket':'REJECTED',
               'duplicate':'REFUSED','MPFR_bits':224,'archived_frames_per_case':6,
               'signed_audit':audit,'public_signer_fingerprint':st['sp']['signer_fingerprint_sha256'],
               'public_verifier_fingerprint':st['vp']['verifier_fingerprint_sha256'],
               'frozen_policy_sha256':st['vp']['policy_sha256'],
               'trusted_tip_sha256':out[-1]['tip_sha256'],'records':out,
               'elapsed_wall_seconds':round(time.monotonic()-tick,3),
               'global_optimality_proofs':0,'scientific_release':'NO_GO',
               'off_host_anchor_verified':False,'power_cut_tested':False,'windows_tested':False}
        results.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'status':'PASS','cases':len(caseids),'tip':out[-1]['tip_sha256'],
                          'elapsed_s':result['elapsed_wall_seconds']},sort_keys=True),flush=True)
        return result
    finally:
        stop(ss);stop(vs)
        if not keep:shutil.rmtree(st['root'],ignore_errors=True)
        else:print('PRIVATE TRANSIENT KEYS retained in',st['root'],flush=True)

def request_writer(sock,message,timeout=900):
    code='''import json,socket,sys
sys.path.insert(0,sys.argv[1]);from protocol37 import request
print(json.dumps(request(sys.argv[2],json.loads(sys.argv[3]),timeout=int(sys.argv[4]))))'''
    res=runas(WRITER_UID,[sys.executable,'-c',code,str(HERE),str(sock),json.dumps(message),str(timeout)],
              capture_output=True,text=True,timeout=timeout+5)
    if res.returncode:raise RuntimeError('Writer request exception: '+res.stderr[-1000:])
    return json.loads(res.stdout)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ORIGINAL)
    parser.add_argument('--case',action='append',dest='cases')
    parser.add_argument('--all',action='store_true')
    parser.add_argument('--result',type=Path,default=HERE/'original_results.json')
    parser.add_argument('--keep-state',action='store_true')
    args=parser.parse_args()
    if args.all:cases=sorted(json.loads((args.root/'CH_C14_33/checkpoint_heads.json').read_text()))
    else:cases=args.cases or ['one_event_n80_i00']
    if any(c not in json.loads((args.root/'CH_C14_33/checkpoint_heads.json').read_text()) for c in cases):raise ValueError('Case not original')
    exercise(args.root,cases,args.result,args.keep_state)

if __name__=='__main__':main()
