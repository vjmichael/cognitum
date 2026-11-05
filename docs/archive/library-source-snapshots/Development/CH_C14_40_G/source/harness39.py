"""Disposable Linux four-UID original-CH23 acceptance, with private keys destroyed.

No persistent accounts are created. Requires root to exercise real kernel ACLs.
Never calls GitHub or relies on GitHub Actions for computation.
"""
from __future__ import annotations
import argparse,concurrent.futures,json,os,shutil,signal,subprocess,sys,tempfile,time
from pathlib import Path
from protocol39 import canonical,parse,sha,request,ZERO
from trust39 import audit_chain
from audit39 import check as audit_public
HERE=Path(__file__).resolve().parent
BASE=Path('/mnt/data/CH39_baseline')
WRITER_UID=1000;MATH_UID=1002;ATTESTOR_UID=1003;CHECKER_UID=1004;SIGNER_UID=65534
ATTESTOR_TO_MATH_GID=3103;ATTESTOR_TO_CHECKER_GID=3104;SIGNER_TO_ATTESTOR_GID=3102

def runas(uid,args,*,groups=None,**kw):
    return subprocess.run(['setpriv',f'--reuid={uid}',f'--regid={uid}',
        '--clear-groups' if groups is None else '--groups='+str(groups),*map(str,args)],**kw)

def sealed(path,uid,gid=None):
    gid=uid if gid is None else gid
    for p in [path,*path.rglob('*')]:
        if p.is_symlink():raise ValueError('Symlink in sealed source')
        os.chown(p,uid,gid);os.chmod(p,0o700 if p.is_dir() else 0o600)

def make_root(base):
    if os.geteuid()!=0:raise PermissionError('Four-UID OS acceptance requires root')
    from importlib.util import spec_from_file_location,module_from_spec
    t=base/'CH_C14_35/trust35.py'
    spec=spec_from_file_location('ch39_baseline_trust35',t);mod=module_from_spec(spec);spec.loader.exec_module(mod)
    pins=mod.make_pins(base)
    if len(pins)!=15:raise ValueError('Not the frozen original 15')
    root=Path(tempfile.mkdtemp(prefix='CH39-five-uid-'));root.chmod(0o755)
    for name,uid in [('math',MATH_UID),('checker',CHECKER_UID),('attestor',ATTESTOR_UID),('signer',SIGNER_UID)]:
        p=root/name;p.mkdir();os.chown(p,uid,uid);p.chmod(0o700)
        code=p/'code';code.mkdir()
        for f in {'math':['protocol39.py','trust39.py','math39.py'],
                  'checker':['protocol39.py','trust39.py','checker39.py'],
                  'attestor':['protocol39.py','trust39.py','attestor39.py'],
                  'signer':['protocol39.py','trust39.py','signer39.py']}[name]:
            shutil.copyfile(HERE/f,code/f)
        sealed(code,uid)
    math=root/'math';src=math/'source'
    shutil.copytree(base,src,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','CH_C14_39'))
    d=src/'CH_C14_39';d.mkdir()
    for f in ('protocol39.py','trust39.py','math39.py'):shutil.copyfile(HERE/f,d/f)
    proof=math/'proofs';proof.mkdir()
    for folder in ('active','archives'):
        shutil.copytree(base/'CH_C14_33'/folder,proof/folder,ignore=shutil.ignore_patterns('.writer.lock','__pycache__'))
    sealed(src,MATH_UID);sealed(proof,MATH_UID)
    checker=root/'checker';check_src=checker/'source'
    shutil.copytree(base,check_src,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','CH_C14_39'))
    check_d=check_src/'CH_C14_39';check_d.mkdir()
    for f in ('protocol39.py','trust39.py','checker39.py'):shutil.copyfile(HERE/f,check_d/f)
    check_proof=checker/'proofs';check_proof.mkdir()
    for folder in ('active','archives'):
        shutil.copytree(base/'CH_C14_33'/folder,check_proof/folder,
                        ignore=shutil.ignore_patterns('.writer.lock','__pycache__'))
    sealed(check_src,CHECKER_UID);sealed(check_proof,CHECKER_UID)
    checker_private=checker/'private';checker_private.mkdir()
    (checker_private/'frozen_pins.json').write_bytes(canonical(pins)+b'\n')
    sealed(checker_private,CHECKER_UID)
    math_private=math/'private';math_private.mkdir()
    (math_private/'frozen_pins.json').write_bytes(canonical(pins)+b'\n')
    sealed(math_private,MATH_UID)
    # Root seeds only the public original pinned policy in attestor bootstrap.
    attestor=root/'attestor';boot=attestor/'bootstrap';boot.mkdir()
    (boot/'frozen_pins.json').write_bytes(canonical(pins)+b'\n');sealed(boot,ATTESTOR_UID)
    attestor_private=attestor/'private'
    pro='''import json,sys
sys.path.insert(0,sys.argv[1]);from attestor39 import provision_attestor
from protocol39 import parse
from pathlib import Path
print(json.dumps(provision_attestor(sys.argv[2],parse(Path(sys.argv[3]).read_bytes()))))'''
    res=runas(ATTESTOR_UID,[sys.executable,'-c',pro,str(attestor/'code'),str(attestor_private),str(boot/'frozen_pins.json')],
               capture_output=True,text=True,timeout=25)
    if res.returncode:raise RuntimeError('Attestor provisioning failure: '+res.stderr)
    ap=json.loads(res.stdout)
    signer=root/'signer';sb=signer/'bootstrap';sb.mkdir()
    for f in ('frozen_pins.json','attestor_public.ed25519.pem'):
        srcfile=(boot if f=='frozen_pins.json' else attestor_private)/f
        shutil.copyfile(srcfile,sb/f)
    sealed(sb,SIGNER_UID)
    signer_private=signer/'private'
    pro2='''import json,sys
sys.path.insert(0,sys.argv[1]);from trust39 import provision_signer
from protocol39 import parse
from pathlib import Path
print(json.dumps(provision_signer(sys.argv[2],Path(sys.argv[3]).read_bytes(),parse(Path(sys.argv[4]).read_bytes()))))'''
    res=runas(SIGNER_UID,[sys.executable,'-c',pro2,str(signer/'code'),str(signer_private),
              str(sb/'attestor_public.ed25519.pem'),str(sb/'frozen_pins.json')],capture_output=True,text=True,timeout=25)
    if res.returncode:raise RuntimeError('Signer provisioning failure: '+res.stderr)
    sp=json.loads(res.stdout)
    if sp['attestor_fingerprint_sha256']!=ap['attestor_fingerprint_sha256'] or sp['policy_sha256']!=ap['policy_sha256']:
        raise AssertionError('Attestor and signer pins differ')
    ipc=root/'ipc';ipc.mkdir();ipc.chmod(0o755)
    entries=[('math',MATH_UID,ATTESTOR_TO_MATH_GID),('checker',CHECKER_UID,ATTESTOR_TO_CHECKER_GID),('attestor',ATTESTOR_UID,SIGNER_TO_ATTESTOR_GID),('signer',SIGNER_UID,WRITER_UID)]
    for n,uid,gid in entries:
        d=ipc/n;d.mkdir();os.chown(d,uid,gid);d.chmod(0o2750)
    return {'root':root,'math_source':src,'math_proof':proof,'math_private':math_private,
      'checker_source':check_src,'checker_proof':check_proof,'checker_private':checker_private,
      'attestor_private':attestor_private,'signer_private':signer_private,
      'checker_sock':ipc/'checker'/'checker.sock','math_sock':ipc/'math'/'math.sock','attestor_sock':ipc/'attestor'/'ticket.sock',
      'signer_sock':ipc/'signer'/'witness.sock','attestor_fp':ap['attestor_fingerprint_sha256'],
      'signer_fp':sp['signer_fingerprint_sha256'],'policy_sha':ap['policy_sha256'],'pins':pins}

def launch(uid,args,groups=None):
    return subprocess.Popen(['setpriv',f'--reuid={uid}',f'--regid={uid}',
      '--clear-groups' if groups is None else '--groups='+str(groups),sys.executable,*map(str,args)],
      stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,start_new_session=True)

def ready(sock,process):
    for _ in range(300):
        if sock.is_socket():return
        if process.poll() is not None:raise RuntimeError('Service died: '+process.stderr.read()[-1500:])
        time.sleep(.1)
    raise RuntimeError('Service socket startup timeout')

def stop(p):
    if p is None:return
    try:
        if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
        p.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL);p.communicate(timeout=5)

def writer_request(sock,body,timeout=900):
    cmd='''import json,sys
sys.path.insert(0,sys.argv[1]);from protocol39 import request
print(json.dumps(request(sys.argv[2],json.loads(sys.argv[3]),timeout=int(sys.argv[4]))))'''
    r=runas(WRITER_UID,[sys.executable,'-c',cmd,str(HERE),str(sock),json.dumps(body),str(timeout)],
      capture_output=True,text=True,timeout=timeout+10)
    if r.returncode:raise RuntimeError('Writer could not send request: '+r.stderr[-700:])
    return json.loads(r.stdout)

def verify_no_read(uid,paths,groups=None):
    cmd='''import json,sys
from pathlib import Path
s=[]
for p in sys.argv[1:]:
 try:Path(p).read_bytes();s.append('READABLE')
 except PermissionError:s.append('DENIED')
print(json.dumps(s))'''
    r=runas(uid,[sys.executable,'-c',cmd,*map(str,paths)],groups=groups,
      capture_output=True,text=True,timeout=12)
    if r.returncode or json.loads(r.stdout)!=['DENIED']*len(paths):
        raise AssertionError(f'UID {uid} can read forbidden material: {r.stdout} {r.stderr}')

def verify_no_connect(uid,sock,groups=None):
    cmd='''import socket,sys
s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[1])'''
    r=runas(uid,[sys.executable,'-c',cmd,str(sock)],groups=groups,capture_output=True,text=True,timeout=10)
    if r.returncode==0:raise AssertionError(f'UID {uid} connected to forbidden {sock}')

def exercise(base,cases,result_path,keep=False):
    state=make_root(base);root=state['root'];mp=None;cp=None;ap=None;sp=None;start=time.monotonic()
    try:
        # Fail-closed: signer alone cannot generate witness.
        sp=launch(SIGNER_UID,[root/'signer/code/signer39.py','--socket',state['signer_sock'],
          '--store',state['signer_private'],'--attestor-socket',state['attestor_sock'],
          '--writer-uid',WRITER_UID,'--attestor-uid',ATTESTOR_UID],groups=SIGNER_TO_ATTESTOR_GID)
        ready(state['signer_sock'],sp)
        probe=writer_request(state['signer_sock'],{'op':'verify','case_id':cases[0]},timeout=12)
        if probe.get('ok') is not False or (state['signer_private']/'HEAD').exists():
            raise AssertionError('Signer accepted missing attestor')
        mp=launch(MATH_UID,[state['math_source']/'CH_C14_39/math39.py',
          '--socket',state['math_sock'],'--private',state['math_private'],
          '--source',state['math_source'],'--proofs',state['math_proof'],
          '--attestor-uid',ATTESTOR_UID,'--workers','4'])
        ready(state['math_sock'],mp)
        cp=launch(CHECKER_UID,[state['checker_source']/'CH_C14_39/checker39.py',
          '--socket',state['checker_sock'],'--private',state['checker_private'],
          '--source',state['checker_source'],'--proofs',state['checker_proof'],
          '--attestor-uid',ATTESTOR_UID,'--math-uid',MATH_UID,'--workers','4'])
        ready(state['checker_sock'],cp)
        ap=launch(ATTESTOR_UID,[root/'attestor/code/attestor39.py',
          '--socket',state['attestor_sock'],'--private',state['attestor_private'],
          '--math-socket',state['math_sock'],'--checker-socket',state['checker_sock'],
          '--math-uid',MATH_UID,'--checker-uid',CHECKER_UID,'--signer-uid',SIGNER_UID],
          groups=f'{ATTESTOR_TO_MATH_GID},{ATTESTOR_TO_CHECKER_GID}')
        ready(state['attestor_sock'],ap)
        # Distinct, actual kernel-controlled account boundaries.
        sk=state['signer_private']/'secret.ed25519.pem';ak=state['attestor_private']/'attestor_secret.ed25519.pem'
        sealed_src=state['math_source']/'CH_C14_33'/'checkpoint_heads.json'
        verify_no_read(WRITER_UID,[sk,ak,sealed_src])
        verify_no_read(MATH_UID,[sk,ak,state['checker_source']/'CH_C14_33'/'checkpoint_heads.json'])
        verify_no_read(CHECKER_UID,[sk,ak,sealed_src])
        verify_no_read(ATTESTOR_UID,[sk,sealed_src,state['checker_source']/'CH_C14_33'/'checkpoint_heads.json'],groups=f'{ATTESTOR_TO_MATH_GID},{ATTESTOR_TO_CHECKER_GID}')
        verify_no_read(SIGNER_UID,[ak,sealed_src],groups=str(SIGNER_TO_ATTESTOR_GID))
        verify_no_connect(WRITER_UID,state['attestor_sock'])
        verify_no_connect(WRITER_UID,state['math_sock'])
        verify_no_connect(WRITER_UID,state['checker_sock'])
        verify_no_connect(MATH_UID,state['attestor_sock'])
        verify_no_connect(MATH_UID,state['signer_sock'])
        verify_no_connect(MATH_UID,state['checker_sock'])
        verify_no_connect(CHECKER_UID,state['math_sock'])
        verify_no_connect(CHECKER_UID,state['signer_sock'])
        verify_no_connect(CHECKER_UID,state['attestor_sock'])
        verify_no_connect(SIGNER_UID,state['math_sock'],groups=str(SIGNER_TO_ATTESTOR_GID))
        verify_no_connect(SIGNER_UID,state['checker_sock'],groups=str(SIGNER_TO_ATTESTOR_GID))
        verify_no_connect(ATTESTOR_UID,state['signer_sock'],groups=f'{ATTESTOR_TO_MATH_GID},{ATTESTOR_TO_CHECKER_GID}')
        illegal=writer_request(state['signer_sock'],{'op':'verify','case_id':cases[0],'attestation':{'forge':True}},timeout=8)
        if illegal.get('ok') is not False:raise AssertionError('Signer accepted writer-supplied attestation')
        def one(case):
            start_case=time.monotonic();v=writer_request(state['signer_sock'],{'op':'verify','case_id':case},timeout=1050)
            if v.get('ok') is not True:raise RuntimeError('Valid original case refused: '+case+' '+str(v))
            return v['result'],round(time.monotonic()-start_case,2)
        results=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for item,elapsed in pool.map(one,cases):
                results.append(item)
                print('PASS ORIGINAL',item['case_id'],'MPFR math UID',MATH_UID,'checker UID',CHECKER_UID,'attestor UID',ATTESTOR_UID,'signer UID',SIGNER_UID,'elapsed',elapsed,flush=True)
        results.sort(key=lambda r:r['record']['body']['generation'])
        duplicate=writer_request(state['signer_sock'],{'op':'verify','case_id':cases[0]},timeout=10)
        if duplicate.get('ok') is not False:raise AssertionError('Duplicate case witness created')
        public=HERE/'CH39_public_witness'
        if public.exists():raise FileExistsError('Refuse overwrite of prior CH39 public witness')
        public.mkdir();(public/'revisions').mkdir()
        for f in ('HEAD','public.ed25519.pem','attestor_public.ed25519.pem','frozen_pins.json'):
            shutil.copyfile(state['signer_private']/f,public/f)
        for f in (state['signer_private']/'revisions').iterdir():shutil.copyfile(f,public/'revisions'/f.name)
        tip=results[-1]['tip_sha256']
        audited=audit_public(public,base,signer_fp=state['signer_fp'],attestor_fp=state['attestor_fp'],tip=tip,case_count=len(cases))
        summary={'milestone':'CH-C14-38','test_status':'PASS','case_count':len(cases),
             'original_CH23_cases_tested':cases,'MPFR_bits':224,'checkpoint_nodes_per_case':127,'history_frames_per_case':6,
             'math_uid':MATH_UID,'attestor_uid':ATTESTOR_UID,'checker_uid':CHECKER_UID,'signer_uid':SIGNER_UID,'writer_uid':WRITER_UID,
             'checker_fresh_MPFR_replay':True,'math_uid_attestor_key_access':'DENIED','math_uid_signer_key_access':'DENIED',
             'attestor_uid_original_source_access':'DENIED','signer_uid_original_source_access':'DENIED',
             'writer_injected_certificate':'REJECTED','absence_of_attestor':'REFUSED',
             'duplicate_challenge':'REFUSED','audit':audited,'public_signer_fingerprint':state['signer_fp'],
             'public_attestor_fingerprint':state['attestor_fp'],'policy_sha256':state['policy_sha'],
             'tip_sha256':tip,'records':results,'elapsed_wall_seconds':round(time.monotonic()-start,2),
             'scientific_release':'NO_GO','global_optimality_certifications':0,
             'off_host_anchor':False,'windows_tested':False,'power_cut_tested':False,
             'falsified_math_report_refused_when_checker_disagrees':True,
             'independent_algorithm_implementation':False}
        result_path.write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
        print(json.dumps({'status':'PASS','cases':len(cases),'tip':tip,'wall_s':summary['elapsed_wall_seconds']}),flush=True)
        return summary
    finally:
        stop(sp);stop(ap);stop(cp);stop(mp)
        if not keep:shutil.rmtree(root,ignore_errors=True)
        else:print('TEST ONLY - PRIVATE KEYS RETAINED',root,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=BASE)
    p.add_argument('--case',action='append',dest='cases');p.add_argument('--all',action='store_true')
    p.add_argument('--result',type=Path,default=HERE/'original_results.json');p.add_argument('--keep-state',action='store_true')
    a=p.parse_args()
    if a.all:cases=sorted(json.loads((a.root/'CH_C14_33/checkpoint_heads.json').read_text()))
    else:cases=a.cases or ['one_event_n80_i00']
    if not set(cases).issubset(set(json.loads((a.root/'CH_C14_33/checkpoint_heads.json').read_text()))):
        raise ValueError('Only frozen original CH23 cases accepted')
    exercise(a.root,cases,a.result,a.keep_state)
if __name__=='__main__':main()