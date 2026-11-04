"""Trusted local test supervisor for OS-isolated CH40-M.11 (Linux only).

Must run as host root with CAP_SETUID,CAP_SETGID and unprivileged user+mount+
network namespaces available. The supervisor alone can read both checkpoint DB
and the anchoring authority; neither isolated principal can read the other.
Research-only: not a production daemon or Lu extension.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, pathlib, shutil, signal, sqlite3, subprocess, sys, time
ROOT=pathlib.Path('/mnt/data')
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'CH40M10'))
import m10_durable_auditor as m10
VERIFIER_UID=25221
PRODUCER_UID=25222
ANCHOR_UID=25223
PY=sys.executable

class Refusal(RuntimeError):pass

def write_json(p,obj):
    p=pathlib.Path(p)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')

def mkdir(p,uid,mode=0o700):
    p=pathlib.Path(p);p.mkdir(parents=True,exist_ok=True)
    os.chown(p,uid,uid);os.chmod(p,mode)
    return p

def invoke(uid,sbox,ro,rw,cmd,*,input=None,extra_env=None,timeout=120):
    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ}
    env.update({'CH40M10_WORKSPACE':'/mnt/data','CH40M8_WORKSPACE':'/mnt/data','PYTHONDONTWRITEBYTECODE':'1',
                'PYTHONHASHSEED':'0','HOME':'/tmp','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    env.update(extra_env or {})
    max_as=2048 if uid==VERIFIER_UID else 256
    max_cpu=90 if uid==VERIFIER_UID else 20
    command=['/usr/bin/setpriv','--reuid',str(uid),'--regid',str(uid),'--clear-groups','--no-new-privs',
             '/usr/bin/unshare','-Urnm','--fork',PY,str(HERE/'mount_guard.py'),'--root',str(sbox),'--max-as-mib',str(max_as),'--max-cpu-sec',str(max_cpu)]
    for path in ro:command+=['--ro',str(path)]
    for path in rw:command+=['--rw',str(path)]
    command+=['--',*map(str,cmd)]
    p=subprocess.Popen(command,stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,start_new_session=True)
    try:
        out,err=p.communicate(input,timeout=timeout)
        return subprocess.CompletedProcess(command,p.returncode,out,err)
    except subprocess.TimeoutExpired as exc:
        # Killing only setpriv/unshare leaves an isolated grandchild holding the
        # stdout pipe and may hang communicate forever. Kill the WHOLE session.
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        try:out,err=p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            raise Refusal('unreapable isolated process tree after SIGKILL') from exc
        raise Refusal(f'isolated process group timed out ({timeout}s) rc={p.returncode}: {out[-400:]} {err[-400:]}') from exc

class Lab:
    def __init__(self,path):
        self.path=pathlib.Path(path).resolve()
        self.source=ROOT
        self.public=self.path/'public'
        self.secrets=self.path/'verifier_keys'
        self.anchor=self.path/'anchor_private'
        self.dbdir=self.path/'verifier_state'
        self.inputs=self.path/'producer_journals'
        self.sandbox_ver=self.path/'sandbox_ver'
        self.sandbox_anchor=self.path/'sandbox_anchor'
        self.sandbox_producer=self.path/'sandbox_producer'
        self.meta=self.path/'lab_record.json'
        self.pub=self.public/'verifier-public.key'
        self.priv=self.secrets/'verifier-private.key'
        self.db=self.dbdir/'m11_checkpoint.sqlite'
        self.caseorder=list(m10.CASE_ORDER)
    def setup(self):
        if self.path.exists():raise Refusal('refusing reuse/overwrite of existing lab')
        self.path.mkdir(mode=0o755,parents=True)
        for p,uid,mode in [(self.public,0,0o755),(self.secrets,VERIFIER_UID,0o700),
                           (self.anchor,ANCHOR_UID,0o700),(self.dbdir,VERIFIER_UID,0o700),
                           (self.inputs,PRODUCER_UID,0o755),
                           (self.sandbox_ver,VERIFIER_UID,0o700),
                           (self.sandbox_anchor,ANCHOR_UID,0o700),
                           (self.sandbox_producer,PRODUCER_UID,0o700)]:mkdir(p,uid,mode)
        # Trusted supervisor generates M10 keys; private key stays owned by verifier UID.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
        signer=Ed25519PrivateKey.generate()
        self.priv.write_bytes(signer.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()))
        self.pub.write_bytes(signer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))
        os.chmod(self.priv,0o600);os.chown(self.priv,VERIFIER_UID,VERIFIER_UID)
        os.chmod(self.pub,0o644)
        # Search journals were created by M9; copied byte-for-byte without mutation.
        for x in sorted((ROOT/'CH40M9/full15/journals').glob('*.json')):
            dest=self.inputs/x.name;shutil.copyfile(x,dest)
            os.chown(dest,PRODUCER_UID,PRODUCER_UID);os.chmod(dest,0o644)
        if len(list(self.inputs.glob('*.json')))!=30:raise Refusal('missing original M9 30 journal inputs')
        _,fp=m10.load_public(self.pub)
        man=m10.manifest(self.caseorder,ROOT,fp)
        genesis=m10.digest(b'CH40M10-GENESIS\0'+m10.canonical(man))
        write_json(self.meta,{'protocol':'CH40M11-LAB-V1','cases':self.caseorder,
                'public_sha256':fp,'genesis':genesis,'expected_source_pins':man['trusted_checker_source_pins'],
                'original_pinset_sha256':man['pinset_sha256'],
                'verifier_uid':VERIFIER_UID,'producer_uid':PRODUCER_UID,'anchor_uid':ANCHOR_UID})
        x=self.run_anchor('init',genesis=genesis)
        if x['checkpoint_tip']!=genesis:raise Refusal('anchor initialization failed')
        return x
    def loadmeta(self):return json.loads(self.meta.read_text())
    def ver_ro(self):
        paths=[ROOT/'CH40M10/m10_durable_auditor.py',ROOT/'CH40M8',ROOT/'CH40M5',ROOT/'CH40L2',ROOT/'CH40L',ROOT/'CH40J',ROOT/'CH40K',self.inputs,self.secrets,self.public]
        return paths
    def anchor_ro(self):return [HERE/'anchor_service.py',self.pub]
    def run_verifier(self,*,sign=False,stop_after=0,kill_after=None,expected_tip=None,timeout=150):
        c=[PY,ROOT/'CH40M10/m10_durable_auditor.py','--db',self.db,'--inputs',self.inputs,'--public',self.pub,
           '--stop-after',str(stop_after)]
        if sign:c+=['--private',self.priv]
        if kill_after is not None:c+=['--kill-after-commit',str(kill_after)]
        if expected_tip is not None:c+=['--expected-tip',expected_tip]
        return invoke(VERIFIER_UID,self.sandbox_ver,self.ver_ro(),[self.dbdir],c,timeout=timeout)
    def run_anchor(self,action,*,row=None,genesis=None,extra_env=None):
        c=[PY,HERE/'anchor_service.py',action,'--state',self.anchor]
        if action=='init':c+=['--verifier-public',self.pub,'--genesis',genesis]
        x=invoke(ANCHOR_UID,self.sandbox_anchor,self.anchor_ro(),[self.anchor],c,
                 input=json.dumps(row)+'\n' if row is not None else None,extra_env=extra_env,timeout=40)
        if x.returncode!=0:raise Refusal(f'anchor {action} failed rc={x.returncode}: {x.stderr[-1500:]} {x.stdout[-500:]}')
        found=[line.split('M11_ANCHOR_RESULT ',1)[1] for line in x.stdout.splitlines() if line.startswith('M11_ANCHOR_RESULT ')]
        if len(found)!=1:raise Refusal('missing trusted anchor result')
        return json.loads(found[0])
    def dbrows(self):
        if not self.db.is_file():return []
        with sqlite3.connect(f'file:{self.db}?mode=ro',uri=True) as db:
            rows=db.execute('SELECT idx,case_name,body,body_sha,signature,tip FROM verified ORDER BY idx').fetchall()
        return [dict(idx=i,case_name=c,body_b64=base64.b64encode(body).decode(),body_sha=h,
                     signature_b64=base64.b64encode(sig).decode(),tip=tip) for i,c,body,h,sig,tip in rows]
    def validate_db(self):
        r=self.run_verifier(sign=False,stop_after=0)
        if r.returncode!=0:raise Refusal('trusted verifier rejected recovery DB: '+r.stderr[-900:]+r.stdout[-200:])
        rs=[x.split('RESULT ',1)[1] for x in r.stdout.splitlines() if x.startswith('RESULT ')]
        if len(rs)!=1:raise Refusal('no recovery result')
        result=json.loads(rs[0])
        if result['scientific_release']!='NO_GO':raise Refusal('unexpected scientific status')
        return result
    def reconcile(self):
        # Always validate all signed checkpoints, original trace hashes and input
        # journals using the isolated public-key-only verifier BEFORE reconciling.
        v=self.validate_db()
        anchor=self.run_anchor('status')
        rows=self.dbrows()
        if len(rows)!=v['completed_cases']:raise Refusal('verified row count mismatch')
        if anchor['sequence']>len(rows):raise Refusal('ANCHORED_TIP_AHEAD_OF_CHECKPOINT_DB: rollback detected')
        if anchor['sequence']:
            if anchor['checkpoint_tip']!=rows[anchor['sequence']-1]['tip']:
                raise Refusal('anchored checkpoint tip diverges from signed DB chain')
        else:
            if anchor['checkpoint_tip']!=self.loadmeta()['genesis']:
                raise Refusal('anchor genesis mismatch')
        remaining=[{k:row[k] for k in ('body_b64','body_sha','signature_b64','tip')} for row in rows[anchor['sequence']:]]
        if remaining:
            anchor=self.run_anchor('advance-batch',row=remaining)
        if anchor['checkpoint_tip']!=v['terminal_checkpoint_tip'] or anchor['sequence']!=len(rows):
            raise Refusal('anchor publication incomplete')
        return {'anchored_cases':anchor['sequence'],'anchor_tip':anchor['anchor_tip'],
                'checkpoint_tip':anchor['checkpoint_tip'],'children_checked':v['verified_child_checks']}
    def fresh_one(self,kill_after=None):
        state=self.reconcile()
        if state['anchored_cases']==len(self.caseorder):raise Refusal('already completed')
        r=self.run_verifier(sign=True,stop_after=1,kill_after=kill_after,expected_tip=state['checkpoint_tip'])
        return r


def run_lab(path):
    start=time.monotonic();lab=Lab(path);lab.setup()
    evidence={'protocol':'CH40M11-LIVE-OS-ISOLATION-AND-ANCHOR-V1','scientific_release':'NO_GO',
              'user_namespace':True,'mount_namespace':True,'network_namespace':True,'uid_separation':True,
              'rootless_outer_uid':True,'landlock_available':False,'original_frozen_cases':15}
    one=lab.fresh_one();evidence['first_case_rc']=one.returncode
    if one.returncode!=0:raise Refusal('first isolated M10 audit failed: '+one.stderr[-1200:])
    anchor1=lab.reconcile()
    if anchor1['anchored_cases']!=1:raise Refusal('first external anchor failed')
    crash=lab.fresh_one(kill_after=1)
    evidence['real_sigkill_after_second_sqlite_commit_returncode']=crash.returncode
    if crash.returncode not in (-9,137):raise Refusal('no real SIGKILL after verifier checkpoint: '+crash.stdout[-700:]+crash.stderr[-500:])
    anchored2=lab.reconcile()
    if anchored2['anchored_cases']!=2:raise Refusal('lost valid checkpoint across crash before anchor')
    # Final run intentionally signs remaining 13 cases; trusted coordinator
    # reconciles *all* outstanding authenticated rows in correct order.
    final=lab.run_verifier(sign=True,stop_after=13,expected_tip=anchored2['checkpoint_tip'],timeout=200)
    if final.returncode!=0:raise Refusal('final isolated audit failed: '+final.stderr[-1200:]+final.stdout[-300:])
    done=lab.reconcile()
    if done['anchored_cases']!=15 or done['children_checked']!=296:raise Refusal('15-case proof/anchor coverage incomplete')
    evidence.update({'signed_anchored_cases':done['anchored_cases'],'independently_verified_children':done['children_checked'],
             'checkpoint_tip':done['checkpoint_tip'],'anchor_tip':done['anchor_tip'],
             'wall_seconds':time.monotonic()-start})
    write_json(lab.path/'M11_LIVE_ACCEPTANCE.json',evidence)
    return evidence

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lab',required=True);a=p.parse_args()
    try:print('M11_RESULT '+json.dumps(run_lab(a.lab),sort_keys=True),flush=True)
    except (Refusal,RuntimeError,OSError,ValueError,subprocess.TimeoutExpired) as e:
        print('M11_REFUSED',repr(e),file=sys.stderr,flush=True)
        sys.exit(2)
