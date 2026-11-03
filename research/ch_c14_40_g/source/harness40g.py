"""Live five-UID CH40-G acceptance; root-only Linux disposable research lab.

Reuses original CH39 signer/trust/protocol/MPFR replay implementations in a
CH40G research domain, adds complete independent original-producer bound proof
under UID1004 and protected trace/source policy inside signer + attestor.
Source ZIP and all 15 producer traces are frozen, never modified in place.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,pathlib,shutil,signal,subprocess,sys,time,zipfile,traceback,threading
from pathlib import Path
from harness39 import make_root,runas,launch,ready,stop,writer_request,verify_no_read,verify_no_connect,sealed
from harness39 import WRITER_UID,MATH_UID,CHECKER_UID,ATTESTOR_UID,SIGNER_UID
from harness39 import ATTESTOR_TO_MATH_GID,ATTESTOR_TO_CHECKER_GID,SIGNER_TO_ATTESTOR_GID
from protocol39 import ZERO,canonical,objhash,parse,verify_signature,S_DOMAIN,V_DOMAIN
from caps_policy40g import ORIGINAL_ARCHIVE_SHA256,PINNED
from trust39 import audit_chain
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CASE='one_event_n80_i00'
ARCHIVE=ROOT/'assets'/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
TRACE_FILE=ROOT/'assets'/(CASE+'_127_original_mpfr_trace.json')

def prepare(original_root=ROOT/'baseline',archive=ARCHIVE,trace=TRACE_FILE):
    if os.geteuid()!=0:raise PermissionError('Five-UID CH40G experiment requires real Linux UID isolation')
    if hashlib.sha256(Path(archive).read_bytes()).hexdigest()!=ORIGINAL_ARCHIVE_SHA256:
        raise ValueError('Frozen CH39 original archive tampered')
    if hashlib.sha256(Path(trace).read_bytes()).hexdigest()!=PINNED[CASE]['trace_sha256']:
        raise ValueError('Frozen CH40F producer trace tampered')
    state=make_root(original_root);root=state['root']
    for name,uid in [('math',MATH_UID),('checker',CHECKER_UID),('attestor',ATTESTOR_UID),('signer',SIGNER_UID)]:
        code=root/name/'code'
        for filename in (['protocol39.py']+(['caps_policy40g.py'] if name in ('checker','attestor','signer') else [])):
            shutil.copyfile(HERE/filename,code/filename)
        if name=='checker':
            for filename in ('checker40g.py','checker39.py','research_receipt40f.py','verify_trace40e.py','rational_kernel40d.py'):
                shutil.copyfile(HERE/filename,code/filename)
        elif name=='attestor':
            for filename in ('attestor40g.py','attestor39.py'):
                shutil.copyfile(HERE/filename,code/filename)
        elif name=='signer':shutil.copyfile(HERE/'signer39.py',code/'signer39.py')
        elif name=='math':
            # CH39 original worker mathematical implementation unchanged.
            shutil.copyfile(HERE/'math39.py',code/'math39.py')
            shutil.copyfile(HERE/'fake_math40g.py',code/'fake_math40g.py')
        sealed(code,uid)
    for role,uid in [('math',MATH_UID),('checker',CHECKER_UID)]:
        d=state[role+'_source']/'CH_C14_39'
        shutil.copyfile(HERE/'protocol39.py',d/'protocol39.py')
        if role=='checker':
            shutil.copyfile(HERE/'caps_policy40g.py',d/'caps_policy40g.py')
            shutil.copyfile(HERE/'checker40g.py',d/'checker40g.py')
            shutil.copyfile(HERE/'research_receipt40f.py',d/'research_receipt40f.py')
            shutil.copyfile(HERE/'verify_trace40e.py',d/'verify_trace40e.py')
            shutil.copyfile(HERE/'rational_kernel40d.py',d/'rational_kernel40d.py')
        sealed(d,uid)
    cp=root/'checker'
    traces=cp/'caps_traces';traces.mkdir()
    shutil.copyfile(trace,traces/trace.name);sealed(traces,CHECKER_UID)
    source=cp/'caps_source';source.mkdir()
    shutil.copyfile(archive,source/archive.name);sealed(source,CHECKER_UID)
    state['caps_trace']=traces/trace.name;state['caps_archive']=source/archive.name
    state['caps_trace_dir']=traces
    return state

def launch_signer(s):
    root=s['root'];p=launch(SIGNER_UID,[root/'signer/code/signer39.py','--socket',s['signer_sock'],
          '--store',s['signer_private'],'--attestor-socket',s['attestor_sock'],
          '--writer-uid',WRITER_UID,'--attestor-uid',ATTESTOR_UID],groups=SIGNER_TO_ATTESTOR_GID)
    ready(s['signer_sock'],p);return p

def launch_attestor(s):
    p=launch(ATTESTOR_UID,[s['root']/'attestor/code/attestor40g.py','--socket',s['attestor_sock'],
           '--private',s['attestor_private'],'--math-socket',s['math_sock'],
           '--checker-socket',s['checker_sock'],'--math-uid',MATH_UID,
           '--checker-uid',CHECKER_UID,'--signer-uid',SIGNER_UID],
           groups=f'{ATTESTOR_TO_MATH_GID},{ATTESTOR_TO_CHECKER_GID}')
    ready(s['attestor_sock'],p);return p

def launch_checker(s):
    p=launch(CHECKER_UID,[s['checker_source']/'CH_C14_39/checker40g.py','--socket',s['checker_sock'],
         '--private',s['checker_private'],'--source',s['checker_source'],'--proofs',s['checker_proof'],
         '--archive',s['caps_archive'],'--traces',s['caps_trace_dir'],
         '--attestor-uid',ATTESTOR_UID,'--math-uid',MATH_UID,'--workers','1'])
    ready(s['checker_sock'],p);return p

def launch_math(s):
    p=launch(MATH_UID,[s['math_source']/'CH_C14_39/math39.py','--socket',s['math_sock'],
         '--private',s['math_private'],'--source',s['math_source'],'--proofs',s['math_proof'],
         '--attestor-uid',ATTESTOR_UID,'--workers','1'])
    ready(s['math_sock'],p);return p

def launch_fake(s,corrupt=False):
    p=launch(MATH_UID,[s['root']/'math/code/fake_math40g.py','--socket',s['math_sock'],
         '--attestation',s['root']/'math/private/public_attestation.json','--attestor-uid',ATTESTOR_UID,
         *(['--corrupt'] if corrupt else [])])
    ready(s['math_sock'],p);return p

def extract_public_attestation(s,original_zip):
    with zipfile.ZipFile(original_zip) as z:
        found=[]
        for name in z.namelist():
            if name.startswith('CH_C14_39/CH39_public_witness/revisions/'):
                rec=json.loads(z.read(name))
                if rec['body']['case_id']==CASE:
                    found.append(rec['body']['attestor_ticket']['body']['attestation'])
        if len(found)!=1:raise ValueError('Missing archived original attestation')
    path=s['root']/'math/private/public_attestation.json';path.write_bytes(canonical(found[0])+b'\n')
    sealed(path.parent,MATH_UID)
    return path

def all_acl_denials(s):
    a=s['attestor_private']/'attestor_secret.ed25519.pem'
    key=s['signer_private']/'secret.ed25519.pem'
    proof=s['caps_trace'];orig=s['caps_archive']
    verify_no_read(WRITER_UID,[a,key,orig,proof]);verify_no_read(MATH_UID,[a,key,orig,proof])
    verify_no_read(ATTESTOR_UID,[key,orig,proof],groups=f'{ATTESTOR_TO_MATH_GID},{ATTESTOR_TO_CHECKER_GID}')
    verify_no_read(SIGNER_UID,[a,orig,proof],groups=str(SIGNER_TO_ATTESTOR_GID))
    verify_no_read(CHECKER_UID,[a,key])
    for uid,socks,groups in [
        (WRITER_UID,[s['math_sock'],s['checker_sock'],s['attestor_sock']],None),
        (MATH_UID,[s['checker_sock'],s['signer_sock'],s['attestor_sock']],None),
        (CHECKER_UID,[s['math_sock'],s['signer_sock'],s['attestor_sock']],None),
        (SIGNER_UID,[s['math_sock'],s['checker_sock']],str(SIGNER_TO_ATTESTOR_GID))]:
        for sock in socks:verify_no_connect(uid,sock,groups=groups)

def export_public(s,report_root):
    report_root.mkdir(parents=True,exist_ok=False)
    public=report_root/'public';public.mkdir();(public/'revisions').mkdir()
    for f in ('HEAD','public.ed25519.pem','attestor_public.ed25519.pem','frozen_pins.json'):
        shutil.copyfile(s['signer_private']/f,public/f)
    for f in (s['signer_private']/'revisions').iterdir():shutil.copyfile(f,public/'revisions'/f.name)
    tip=json.loads((s['signer_private']/'trusted_tip.json').read_text())['tip']
    audited=audit_chain(public,(public/'public.ed25519.pem').read_bytes(),
      (public/'attestor_public.ed25519.pem').read_bytes(),
      signer_fingerprint=s['signer_fp'],attestor_fingerprint=s['attestor_fp'],
      expected_tip=tip,pins=s['pins'])
    return tip,audited

def run(mode,keep_state=False):
    results=ROOT/'results';results.mkdir(exist_ok=True)
    state=prepare();root=state['root'];sp=ap=cp=mp=None;checks={};started=time.monotonic()
    try:
        extract_public_attestation(state,ARCHIVE)
        # The real CH39 signer store and real private-key-per-UID layout are reused.
        sp=launch_signer(state)
        missing=writer_request(state['signer_sock'],{'op':'verify','case_id':CASE},timeout=12)
        if missing.get('ok') is not False or (state['signer_private']/'HEAD').exists():
            raise AssertionError('Signer published without attestor')
        checks['signer_without_attestor']='REFUSED_NO_LEDGER'
        if mode=='valid':
            mp=launch_math(state);cp=launch_checker(state);ap=launch_attestor(state)
            all_acl_denials(state);checks['real_kernel_uid_acl_and_peer_denials']='PASS'
            illegal=writer_request(state['signer_sock'],{'op':'verify','case_id':CASE,'fabricated_report':'true'},timeout=10)
            if illegal.get('ok') is not False:raise AssertionError('Writer bypassed signer schema')
            checks['writer_submitted_worker_report']='REFUSED'
            print('CH40G LIVE: original CH39 224-bit MPFR + separate CH40F 160-bit producer-cap replay begun',flush=True)
            res=writer_request(state['signer_sock'],{'op':'verify','case_id':CASE},timeout=900)
            if res.get('ok') is not True:raise AssertionError('Valid original case was refused: '+str(res))
            record=res['result']['record'];b=record['body']['attestor_ticket']['body']
            if b['caps_receipt']['unsupported_caps']!=0 or b['caps_receipt']['node_count']!=127 or \
               b['caps_receipt']['global_optimality_certified'] is not False:
                raise AssertionError('Signed research cap receipt wrong')
            checks['CH39_224bit_historical_6frame_replay']='PASS'
            checks['CH40F_160bit_independent_real_producer_cap_replay']='PASS'
            checks['attestor_uid1003_research_only_signed_receipt']='PASS'
            checks['signer_uid65534_signed_chain']='PASS'
            duplicate=writer_request(state['signer_sock'],{'op':'verify','case_id':CASE},timeout=10)
            if duplicate.get('ok') is not False:raise AssertionError('Duplicate case signed')
            checks['duplicate_signing_attempt']='REFUSED'
            tip,public=export_public(state,results/'CH40G_live_valid')
            if public['length']!=1:raise AssertionError('Invalid research witness length')
            checks['independent_public_dual_signature_chain_audit']='PASS'
            # CH39 historical signatures must NOT accept CH40G research-domain keys.
            src=ROOT/'assets/historical_protocol39.py'
            from importlib.util import spec_from_file_location,module_from_spec
            spec=spec_from_file_location('original_CH39_signature_domain',src);mod=module_from_spec(spec);spec.loader.exec_module(mod)
            try:mod.verify_signature(record,(results/'CH40G_live_valid/public/public.ed25519.pem').read_bytes(),mod.S_DOMAIN)
            except ValueError:checks['CH39_signature_domain_downgrade']='REFUSED'
            else:raise AssertionError('CH40G research signature cross-verifies as CH39!')
            # Clean restart of the signer recovers the same trusted committed tip.
            stop(sp);sp=None
            state['signer_sock'].unlink(missing_ok=True)
            sp=launch_signer(state)
            d=writer_request(state['signer_sock'],{'op':'verify','case_id':CASE},timeout=10)
            if d.get('ok') is not False:raise AssertionError('Restart forgot durable signed case')
            checks['signed_chain_survives_signer_restart']='PASS'
            detail={'record':record,'tip':tip,'public_audit':public}
        elif mode in ('missing-checker','tampered-trace','forged-worker','interrupted-checker'):
            mp=launch_fake(state,corrupt=mode=='forged-worker')
            if mode!='missing-checker':cp=launch_checker(state)
            if mode=='tampered-trace':
                with state['caps_trace'].open('ab') as f:f.write(b'CORRUPTED_AFTER_PIN\n')
            ap=launch_attestor(state)
            if mode=='interrupted-checker':
                assert cp is not None
                def kill_during_math():
                    time.sleep(3)
                    stop(cp)
                threading.Thread(target=kill_during_math,daemon=True).start()
            checks['actual_uid_authenticated_services_started']='PASS'
            print('CH40G LIVE ADVERSE',mode,'request',flush=True)
            res=writer_request(state['signer_sock'],{'op':'verify','case_id':CASE},timeout=900)
            if res.get('ok') is not False:raise AssertionError('Malicious test obtained signed witness: '+str(res))
            if (state['signer_private']/'HEAD').exists() or list((state['signer_private']/'revisions').iterdir()):
                raise AssertionError('Negative test left signed revision')
            checks['attack_refused_no_signature']='PASS'
            detail={'denial':res,'attack':mode}
        else:raise ValueError('Unknown mode')
        result={'milestone':'CH40G','mode':mode,'outcome':'PASS','checks':checks,
            'source_pin_sha256':ORIGINAL_ARCHIVE_SHA256,'original_case':CASE,
            'uid_identity':{'writer':WRITER_UID,'math':MATH_UID,'checker':CHECKER_UID,
                            'attestor':ATTESTOR_UID,'signer':SIGNER_UID},
            'kernel_so_peercred_enforced':True,'source_trace_sha256':PINNED[CASE]['trace_sha256'],
            'separate_research_signature_domain':True,'scientific_release':'NO_GO',
            'production_admission':False,'global_optimality_certified':False,
            'wall_seconds':round(time.monotonic()-started,3), 'detail':detail}
        dest=results/('CH40G_'+mode.replace('-','_')+'_results.json')
        dest.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
        print('CH40G',mode,'PASS',json.dumps({'checks':checks,'elapsed_s':result['wall_seconds']},sort_keys=True),flush=True)
        return result
    finally:
        for p in (sp,ap,cp,mp):stop(p)
        if not keep_state:shutil.rmtree(root,ignore_errors=True)
        else:print('SECURITY DEBUG ONLY: temporary private keys retained at',root,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['valid','missing-checker','tampered-trace','forged-worker','interrupted-checker'],default='valid')
    p.add_argument('--keep-state',action='store_true');a=p.parse_args()
    run(a.mode,a.keep_state)
