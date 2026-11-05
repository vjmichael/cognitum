"""CH39 signer-owned V2 witness ledger with embedded attestor-signed replay proof.

A public auditor verifies BOTH Ed25519 layers using independently pinned
public key fingerprints, frozen CH23 policy, and final tip. No MPFR math is
performed in this module or in the signer process.
"""
from __future__ import annotations
import base64, fcntl, os, re, stat
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from protocol39 import (ZERO,HEX64,S_DOMAIN,canonical,objhash,sha,parse,safe_read,
                        sync_dir,atomic,verify_signature,verify_ticket)

RECORD=re.compile(r'([0-9]{8})_([0-9a-f]{64})\.json\Z')

def private_directory(p):
    st=Path(p).lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode & 0o077:
        raise PermissionError('Signer directory must be owner-only under signer UID')

def private_keyfile(p):
    st=Path(p).lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode & 0o077 or st.st_nlink!=1:
        raise PermissionError('Signer key file not private and regular')

def issue_keys(store):
    store=Path(store)
    if store.exists():raise FileExistsError('Refuse reprovision/replace signer identity')
    store.mkdir(mode=0o700,parents=False);(store/'revisions').mkdir(mode=0o700)
    key=Ed25519PrivateKey.generate()
    private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    for name,payload in [('secret.ed25519.pem',private),('public.ed25519.pem',public)]:
        fd=os.open(store/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    sync_dir(store);return {'signer_fingerprint_sha256':sha(public),'public_key_pem':public.decode()}

def audit_chain(root,signer_public,attestor_public,*,signer_fingerprint,attestor_fingerprint,expected_tip,pins):
    """Read-only, public chain audit. External caller MUST pin both keys and tip."""
    if (not HEX64.fullmatch(str(expected_tip)) or sha(signer_public)!=signer_fingerprint or
        sha(attestor_public)!=attestor_fingerprint):raise ValueError('Untrusted external authority identity/tip')
    root=Path(root);head=root/'HEAD'
    if expected_tip==ZERO and not head.exists():return {'tip':ZERO,'length':0,'cases':[],'nonces':[]}
    if not head.exists():raise ValueError('HEAD missing')
    current=parse(safe_read(head));latest=objhash(current)
    if latest!=expected_tip:raise ValueError('Signed ledger rollback/unpinned successor')
    count=0;seen=set();challenges=set();parent_hash=latest;cases=[]
    while True:
        b=verify_signature(current,signer_public,S_DOMAIN)
        req={'version','generation','parent','case_id','signer_fingerprint_sha256',
             'attestor_fingerprint_sha256','policy_sha256','attestor_ticket', 'scientific_release'}
        if set(b)!=req or b['version']!=2 or type(b['generation'])!=int or b['generation']<0:
            raise ValueError('Bad signer witness V2 schema')
        if (b['signer_fingerprint_sha256']!=signer_fingerprint or
            b['attestor_fingerprint_sha256']!=attestor_fingerprint or b['policy_sha256']!=objhash(pins)):
            raise ValueError('Signed record substituted signer/attestor/policy')
        if b['scientific_release']!='NO_GO':raise ValueError('Unsupported scientific claim')
        case=b['case_id']
        if type(case)!=str or case not in pins or case in seen:raise ValueError('Duplicate/unfrozen case')
        vbody=b['attestor_ticket'].get('body') if isinstance(b['attestor_ticket'],dict) else None
        if type(vbody)!=dict:raise ValueError('Attestor ticket body missing')
        nonce=vbody.get('nonce')
        if nonce in challenges:raise ValueError('Duplicate attestor nonce in ledger')
        verify_ticket(b['attestor_ticket'],attestor_public,attestor_fingerprint,objhash(pins),case,nonce,pins)
        challenges.add(nonce);seen.add(case);cases.append(case);count+=1
        f=root/'revisions'/f"{b['generation']:08d}_{parent_hash}.json"
        if parse(safe_read(f))!=current:raise ValueError('Signed revision missing or tampered')
        if b['generation']==0:
            if b['parent']!=ZERO:raise ValueError('Invalid genesis parent')
            break
        prior=b['parent'];p=root/'revisions'/f"{b['generation']-1:08d}_{prior}.json"
        current=parse(safe_read(p))
        if objhash(current)!=prior:raise ValueError('Broken signed parent linkage')
        pb=verify_signature(current,signer_public,S_DOMAIN)
        if pb['generation']!=b['generation']-1:raise ValueError('Generation gap')
        parent_hash=prior
    # Starting from HEAD the sequence must count down to zero.
    if count != (parse(safe_read(head))['body']['generation']+1):raise ValueError('Chain generation mismatch')
    return {'tip':expected_tip,'length':count,'cases':list(reversed(cases)),
            'verified_attestor_tickets':count,'verified_signer_signatures':count,
            'mathematics_rerun_by_public_audit':False,'nonces':sorted(challenges)}

class DualSignerStore:
    def __init__(self,root):
        self.root=Path(root);private_directory(self.root);private_directory(self.root/'revisions')
        private_keyfile(self.root/'secret.ed25519.pem')
        private_keyfile(self.root/'public.ed25519.pem')
        private_keyfile(self.root/'attestor_public.ed25519.pem')
        private_keyfile(self.root/'frozen_pins.json')
        private_keyfile(self.root/'trusted_tip.json')
        self.private=serialization.load_pem_private_key(safe_read(self.root/'secret.ed25519.pem',4096),password=None)
        if not isinstance(self.private,Ed25519PrivateKey):raise ValueError('Wrong signer key')
        self.public=safe_read(self.root/'public.ed25519.pem',4096)
        self.attestor_public=safe_read(self.root/'attestor_public.ed25519.pem',4096)
        self.sf=sha(self.public);self.vf=sha(self.attestor_public)
        self.pins=parse(safe_read(self.root/'frozen_pins.json',65536))
        if not isinstance(self.pins,dict) or len(self.pins)!=15:raise ValueError('Frozen original 15 policy missing')
        self.policy_sha=objhash(self.pins)
    def tip(self):
        tip=parse(safe_read(self.root/'trusted_tip.json',4096))
        if set(tip)!={'tip','signer_fingerprint','attestor_fingerprint','policy_sha256'} or \
           tip['signer_fingerprint']!=self.sf or tip['attestor_fingerprint']!=self.vf or tip['policy_sha256']!=self.policy_sha:
            raise ValueError('Externally pinned identity/policy disagreement')
        return tip['tip']
    def audit(self):return audit_chain(self.root,self.public,self.attestor_public,signer_fingerprint=self.sf,attestor_fingerprint=self.vf,expected_tip=self.tip(),pins=self.pins)
    def publish(self,case,ticket):
        current=self.audit();tip=self.tip()
        if case in current['cases']:raise ValueError('Previously signed case')
        if not isinstance(ticket,dict) or not isinstance(ticket.get('body'),dict):raise ValueError('No signed attestor ticket')
        nonce=ticket['body'].get('nonce')
        if nonce in current['nonces']:raise ValueError('Duplicate attestor nonce; replay refused')
        verify_ticket(ticket,self.attestor_public,self.vf,self.policy_sha,case,nonce,self.pins)
        allnames=list(self.root.iterdir())+list((self.root/'revisions').iterdir())
        if any(p.name.endswith('.pending') for p in allnames):raise ValueError('Interrupted storage publication requires manual reconciliation')
        revisions=list((self.root/'revisions').iterdir())
        if len(revisions)!=current['length'] or any(RECORD.fullmatch(p.name) is None for p in revisions):
            raise ValueError('Orphan/unreachable signed revision; require manual reconciliation')
        body={'version':2,'generation':current['length'],'parent':tip,'case_id':case,
              'signer_fingerprint_sha256':self.sf,'attestor_fingerprint_sha256':self.vf,
              'policy_sha256':self.policy_sha,'attestor_ticket':ticket,'scientific_release':'NO_GO'}
        signature=base64.b64encode(self.private.sign(S_DOMAIN+canonical(body))).decode('ascii')
        rec={'body':body,'signature':signature};raw=canonical(rec)+b'\n';digest=objhash(rec)
        if len(raw)>16384:raise ValueError('Oversized signer record')
        atomic(self.root/'revisions',f'{current["length"]:08d}_{digest}.json',raw)
        atomic(self.root,'HEAD',raw)
        atomic(self.root,'trusted_tip.json',canonical({'tip':digest,'signer_fingerprint':self.sf,
              'attestor_fingerprint':self.vf,'policy_sha256':self.policy_sha})+b'\n')
        return {'tip_sha256':digest,'record':rec,'fingerprint_sha256':self.sf}

def provision_signer(root,attestor_public,pins):
    root=Path(root);info=issue_keys(root)
    policy=canonical(pins)+b'\n'
    for name,content in [('attestor_public.ed25519.pem',attestor_public),('frozen_pins.json',policy),
          ('trusted_tip.json',canonical({'tip':ZERO,'signer_fingerprint':info['signer_fingerprint_sha256'],
                                         'attestor_fingerprint':sha(attestor_public),'policy_sha256':objhash(pins)})+b'\n')]:
        fd=os.open(root/name,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(content);f.flush();os.fsync(f.fileno())
    sync_dir(root)
    return {'signer_fingerprint_sha256':info['signer_fingerprint_sha256'],
            'attestor_fingerprint_sha256':sha(attestor_public),'policy_sha256':objhash(pins)}