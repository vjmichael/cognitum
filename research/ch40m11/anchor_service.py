"""CH40-M.11 independent UID-owned monotonic checkpoint anchor.

A *trusted* coordinator may submit a signed M10 SQLite row over stdin.
The anchor principal cannot read the M10 signing private key or modify its DB.
It verifies Ed25519 M10 signature + checkpoint hash/sequence/previous tip,
then signs a second custody chain, durably replacing an owner-only state file.
It NEVER claims a new mathematical proof. A separate trusted principal and
protected persistence are required; root/host-level attackers are out of scope.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, pathlib, signal, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
from cryptography.exceptions import InvalidSignature

PROTO='CH40M11-OS-SEPARATED-ANCHOR-V1'
DOMAIN=b'CH40M11-ANCHOR-EVENT\x00'
M10DOMAIN=b'CH40M10-VERIFIER\x00'
class Refusal(ValueError):pass

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def sha(x):return hashlib.sha256(x).hexdigest()
def b64(x):return base64.b64encode(x).decode('ascii')
def deb64(x):return base64.b64decode(x,validate=True)

def atomic(path,data):
    # Owner-only directory pre-created by trusted supervisor. No symlinks accepted.
    path=pathlib.Path(path)
    if path.is_symlink():raise Refusal('refuse symlink state')
    fd=os.open(str(path.parent),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        temp=path.with_name('.'+path.name+'.tmp.'+str(os.getpid()))
        f=os.open(str(temp),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(f,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
            if os.environ.get('M11_INJECT_KILL_BEFORE_ANCHOR_RENAME')=='1':
                print('ANCHOR_INJECTING_SIGKILL_BEFORE_RENAME',flush=True)
                os.kill(os.getpid(),signal.SIGKILL)
            os.replace(temp,path)
            os.fsync(fd)
        finally:
            if temp.exists():temp.unlink()
    finally:os.close(fd)

def read_keys(state_dir):
    secret=pathlib.Path(state_dir)/'anchor-private.key';pub=pathlib.Path(state_dir)/'anchor-public.key'
    if secret.stat().st_mode & 0o077:raise Refusal('anchor private key mode not owner-only')
    raw=secret.read_bytes();pb=pub.read_bytes()
    if len(raw)!=32 or len(pb)!=32:raise Refusal('invalid anchor key')
    key=Ed25519PrivateKey.from_private_bytes(raw)
    if key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)!=pb:raise Refusal('anchor keypair mismatch')
    return key,key.public_key()

def check_state(state_dir,pub):
    p=pathlib.Path(state_dir)/'anchor-state.json'
    if p.is_symlink():raise Refusal('anchor state symlink')
    data=p.read_bytes();obj=json.loads(data)
    if canon(obj)!=data:raise Refusal('anchor state noncanonical')
    if obj.get('protocol')!=PROTO or obj.get('anchor_pub_sha256')!=sha(pub.public_bytes(Encoding.Raw,PublicFormat.Raw)):
        raise Refusal('anchor protocol or public identity mismatch')
    verifier_pub=pathlib.Path(obj['verifier_public_path']).read_bytes()
    if len(verifier_pub)!=32 or sha(verifier_pub)!=obj['verifier_pub_sha256']:
        raise Refusal('verifier key fingerprint mismatch')
    entries=obj['entries'];genesis=obj['genesis']
    prev=sha(b'CH40M11-ANCHOR-GENESIS\0'+canon({'genesis':genesis,'verifier_pub_sha256':sha(verifier_pub),'anchor_pub_sha256':obj['anchor_pub_sha256']}))
    prev_checkpoint=genesis
    for idx,entry in enumerate(entries,1):
        e=entry['event'];sig=deb64(entry['signature']);tip=entry['anchor_tip']
        if e.get('sequence')!=idx or e.get('prev_anchor_tip')!=prev or e.get('prev_checkpoint_tip')!=prev_checkpoint:
            raise Refusal('anchor sequence/previous tip mismatch')
        try:pub.verify(sig,DOMAIN+canon(e))
        except InvalidSignature as exc:raise Refusal('forged anchor event') from exc
        calc=sha(canon({'event':e,'signature':entry['signature']}))
        if calc!=tip:raise Refusal('anchor event tip mismatch')
        prev=tip;prev_checkpoint=e['checkpoint_tip']
    if obj.get('anchor_tip')!=prev or obj.get('checkpoint_tip')!=prev_checkpoint or obj.get('count')!=len(entries):
        raise Refusal('anchor state header mismatch')
    return obj

def initialize(state_dir,verifier_public,genesis):
    state_dir=pathlib.Path(state_dir)
    if not state_dir.is_dir() or state_dir.stat().st_mode & 0o077:
        raise Refusal('trusted anchor dir must be owner-only')
    if any(state_dir.iterdir()):raise Refusal('refuse initialized or nonempty anchor dir')
    verifier_public=pathlib.Path(verifier_public)
    ver=verifier_public.read_bytes()
    if len(ver)!=32:raise Refusal('invalid verifier public key')
    if len(genesis)!=64:raise Refusal('invalid genesis')
    key=Ed25519PrivateKey.generate()
    secret=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
    pub=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    for name,data in [('anchor-private.key',secret),('anchor-public.key',pub)]:
        fd=os.open(str(state_dir/name),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
    obj={'protocol':PROTO,'verifier_public_path':str(verifier_public),
         'verifier_pub_sha256':sha(ver),'anchor_pub_sha256':sha(pub),
         'genesis':genesis,'count':0,'entries':[], 'checkpoint_tip':genesis,
         'anchor_tip':sha(b'CH40M11-ANCHOR-GENESIS\0'+canon({'genesis':genesis,'verifier_pub_sha256':sha(ver),'anchor_pub_sha256':sha(pub)}))}
    atomic(state_dir/'anchor-state.json',canon(obj))
    return check_state(state_dir,key.public_key())

def advance(state_dir,row):
    signer,pub=read_keys(state_dir)
    obj=check_state(state_dir,pub)
    if set(row)!={'body_b64','signature_b64','body_sha','tip'}:raise Refusal('invalid checkpoint envelope')
    blob=deb64(row['body_b64']);sig=deb64(row['signature_b64'])
    if sha(blob)!=row['body_sha']:raise Refusal('checkpoint blob hash mismatch')
    body=json.loads(blob)
    if canon(body)!=blob:raise Refusal('checkpoint is not canonical')
    vp=pathlib.Path(obj['verifier_public_path']).read_bytes()
    try:Ed25519PublicKey.from_public_bytes(vp).verify(sig,M10DOMAIN+blob)
    except InvalidSignature as e:raise Refusal('forged verifier checkpoint') from e
    expected_tip=sha(canon({'previous':body['prev_tip'],'body_sha256':row['body_sha'],'signature':row['signature_b64']}))
    if row['tip']!=expected_tip:raise Refusal('checkpoint signature/tip mismatch')
    if (body.get('protocol')!='CH40M10-TRUSTED-VERIFIER-DURABLE-CHECKPOINT-V1' or
        body.get('scientific_release')!='NO_GO' or body.get('sequence')!=obj['count']+1 or
        body.get('prev_tip')!=obj['checkpoint_tip'] or
        body.get('audited_receipt',{}).get('status')!='PASS_RESEARCH_ONLY' or
        body.get('audited_receipt',{}).get('scientific_release')!='NO_GO'):
        raise Refusal('stale, duplicated or invalid mathematical checkpoint')
    if not isinstance(body.get('journal_sha256'),dict) or set(body['journal_sha256'])!={'arb_gram','mpfr_gram'}:
        raise Refusal('missing paired journal identities')
    event={'sequence':obj['count']+1,'case':body['case'],
           'checkpoint_tip':row['tip'],'prev_checkpoint_tip':obj['checkpoint_tip'],
           'prev_anchor_tip':obj['anchor_tip'],'verifier_body_sha256':row['body_sha']}
    event_sig=b64(signer.sign(DOMAIN+canon(event)))
    anchor_tip=sha(canon({'event':event,'signature':event_sig}))
    obj['entries'].append({'event':event,'signature':event_sig,'anchor_tip':anchor_tip})
    obj['count']+=1;obj['checkpoint_tip']=row['tip'];obj['anchor_tip']=anchor_tip
    atomic(pathlib.Path(state_dir)/'anchor-state.json',canon(obj))
    return check_state(state_dir,pub)

def output(obj):
    return {'status':'ANCHORED_RESEARCH_ONLY','scientific_release':'NO_GO',
            'sequence':obj['count'],'checkpoint_tip':obj['checkpoint_tip'],
            'anchor_tip':obj['anchor_tip'],'anchor_public_sha256':obj['anchor_pub_sha256']}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['init','status','advance','advance-batch'])
    p.add_argument('--state',required=True)
    p.add_argument('--verifier-public')
    p.add_argument('--genesis')
    a=p.parse_args()
    try:
        if a.action=='init':obj=initialize(a.state,a.verifier_public,a.genesis)
        elif a.action=='status':_,pub=read_keys(a.state);obj=check_state(a.state,pub)
        elif a.action=='advance':obj=advance(a.state,json.load(sys.stdin))
        else:
            rows=json.load(sys.stdin)
            if not isinstance(rows,list) or not 1<=len(rows)<=15:raise Refusal('bad anchor batch size')
            obj=None
            for row in rows:obj=advance(a.state,row)
        print('M11_ANCHOR_RESULT '+json.dumps(output(obj),sort_keys=True),flush=True)
    except (Refusal,ValueError,KeyError,OSError,TypeError,PermissionError) as e:
        print('M11_ANCHOR_REFUSED '+repr(e),file=sys.stderr,flush=True)
        sys.exit(2)
if __name__=='__main__':main()
