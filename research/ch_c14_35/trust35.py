"""CH35 independent proof-witness authority (Linux research prototype).

Trust boundary: this executable, key, evidence source, and signed ledger belong to
an OS account inaccessible to the proof-journal writer. Requests cannot provide
attestations, input paths, digests, or signing keys. The authority independently
replays original CH23 mathematics at 224-bit MPFR before signing anything.

Signatures prove *this authority* attested a scoped, still-unresolved bounded
certificate. They do NOT prove global optimality, prevent compromise of the
signing account, or provide anti-rollback without an independently retained tip.
"""
from __future__ import annotations
import argparse, base64, errno, hashlib, json, os, re, shutil, socket, stat, sys, tempfile, uuid
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

GENESIS = '0'*64
HEX = re.compile(r'^[0-9a-f]{64}$')
REC = re.compile(r'^([0-9]{8})_([0-9a-f]{64})\.json$')
MAX = 32768
DOMAIN = b'Cognitum/CH35/independent-CH23-proof-attestation/v1\x00'


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',', ':'),allow_nan=False,ensure_ascii=True).encode('ascii')

def hashbytes(x): return hashlib.sha256(x).hexdigest()
def shaobj(x): return hashbytes(canonical(x))

def strict(raw):
    if len(raw)>MAX or not raw.endswith(b'\n'): raise ValueError('Missing newline or excessive record size')
    def unique(kv):
        d={}
        for k,v in kv:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    obj=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if canonical(obj)+b'\n' != raw:raise ValueError('Noncanonical JSON')
    return obj

def fsyncdir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def nofollow_read(path,cap=MAX):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size>cap or st.st_nlink!=1:
            raise ValueError('Symlink, hardlink or oversized witness input')
        raw=b''
        while len(raw)<=cap:
            part=os.read(fd,min(65536,cap+1-len(raw)))
            if not part:break
            raw+=part
        if len(raw)>cap:raise ValueError('Excessive witness input size')
        return raw
    finally:os.close(fd)

def atomic(root,name,raw,fail=None,prefix='tmp'):
    temp=root/f'.{prefix}-{uuid.uuid4().hex}.pending'
    fd=os.open(temp,os.O_WRONLY|os.O_EXCL|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as f:
            if fail:fail(prefix+'_write')
            view=memoryview(raw)
            while view:
                n=f.write(view)
                if not n:raise OSError(errno.EIO,'Short write')
                view=view[n:]
            f.flush()
            if fail:fail(prefix+'_fsync')
            os.fsync(f.fileno())
        if fail:fail(prefix+'_rename')
        os.replace(temp,root/name)
        if fail:fail(prefix+'_dirsync')
        fsyncdir(root)
    except BaseException:
        # Keep temp files visible for explicit operator reconciliation.
        raise


def pubkey_fingerprint(pub_pem):return hashbytes(pub_pem)

def signature_ok(record,pub):
    if not isinstance(record,dict) or set(record)!={'body','signature'} or not isinstance(record['body'],dict):raise ValueError('Witness schema mismatch')
    try:pub.verify(base64.b64decode(record['signature'],validate=True),DOMAIN+canonical(record['body']))
    except Exception as e:raise ValueError('Invalid authority signature') from e
    return record['body']


def verify_chain(store, public_pem, *, expected_fingerprint, expected_tip):
    """PUBLIC read-only validation; caller pins both fingerprint and latest tip."""
    store=Path(store)
    if not HEX.fullmatch(str(expected_tip)) or not HEX.fullmatch(str(expected_fingerprint)):
        raise ValueError('External fingerprint and tip are required')
    if pubkey_fingerprint(public_pem)!=expected_fingerprint:raise ValueError('Authority public key substitution')
    pub=serialization.load_pem_public_key(public_pem)
    if not isinstance(pub,Ed25519PublicKey):raise ValueError('Unsupported authority key')
    head=store/'HEAD'; records=store/'revisions'
    if expected_tip==GENESIS and not head.exists():return {'tip':GENESIS,'length':0,'cases':[]}
    if not head.is_file():raise ValueError('Witness HEAD missing')
    newest=strict(nofollow_read(head)); body=signature_ok(newest,pub)
    if shaobj(newest)!=expected_tip:raise ValueError('Anchor rollback or substitution')
    prev=newest;seen=set();cases=[]
    while True:
        b=signature_ok(prev,pub);sha=shaobj(prev)
        fields={'version','generation','parent','case_id','binding_sha256','original_head_sha256','checkpoint_sha256','archive_sha256','nodes','archive_epochs','mpfr_replayed_frames','proof_replayed','scientific_release','verified_source','witness_key_fingerprint'}
        if set(b)!=fields or b['version']!=1 or type(b['generation'])!=int or b['generation']<0:
            raise ValueError('Invalid signed witness schema')
        if b['scientific_release']!='NO_GO' or b['proof_replayed'] is not True or b['nodes']!=127 or b['archive_epochs']!=2 or b['mpfr_replayed_frames']!=6:
            raise ValueError('Invalid mathematical scope or release disposition')
        if b['witness_key_fingerprint']!=expected_fingerprint:raise ValueError('Witness signed with other key identity')
        for k in ('parent','binding_sha256','original_head_sha256','checkpoint_sha256','archive_sha256'):
            if not isinstance(b[k],str) or not HEX.fullmatch(b[k]):raise ValueError('Malformed witness hash')
        if not isinstance(b['case_id'],str) or not b['case_id'] or b['case_id'] in seen:
            raise ValueError('Witness duplicate case or case missing')
        if b['verified_source']!='original_CH23_independent_MPFR_224':raise ValueError('Source identity wrong')
        seen.add(b['case_id']);cases.append(b['case_id'])
        f=records/f"{b['generation']:08d}_{sha}.json"
        if strict(nofollow_read(f))!=prev:raise ValueError('Committed witness revision missing or corrupt')
        if b['generation']==0:
            if b['parent']!=GENESIS:raise ValueError('Witness genesis mismatch')
            break
        fparent=records/f"{b['generation']-1:08d}_{b['parent']}.json"
        par=strict(nofollow_read(fparent))
        if shaobj(par)!=b['parent'] or signature_ok(par,pub)['generation']!=b['generation']-1:
            raise ValueError('Witness parent signature/sequence mismatch')
        prev=par
    # Unreachable records are handled by server admission; this reader asserts
    # only that the externally pinned chain is complete and authentic.
    return {'tip':expected_tip,'length':len(cases),'cases':cases[::-1]}


class WitnessStore:
    """Private local signing store; only the independent OS account may write."""
    def __init__(self,root,*,max_bytes=None):
        self.root=Path(root).resolve();self.revisions=self.root/'revisions'
        if max_bytes is not None and (type(max_bytes)!=int or max_bytes<8192):raise ValueError('Invalid witness quota')
        self.max_bytes=max_bytes
        self._ownership()
    def _ownership(self):
        for p in (self.root,self.revisions):
            st=p.lstat()
            if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or (st.st_mode&0o077):
                raise PermissionError('Witness storage requires private owner-only directory')
        for p in (self.root/'secret.ed25519.pem',self.root/'public.ed25519.pem'):
            st=p.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_nlink!=1 or (st.st_mode&0o077):
                raise PermissionError('Authority keys must be private, owned regular files')
    @staticmethod
    def provision(root):
        root=Path(root)
        if root.exists():raise ValueError('Cannot replace an existing trust authority')
        root.mkdir(mode=0o700,parents=True);(root/'revisions').mkdir(mode=0o700)
        private=Ed25519PrivateKey.generate()
        key=private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public=private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        for name,raw in [('secret.ed25519.pem',key),('public.ed25519.pem',public)]:
            fd=os.open(root/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        fsyncdir(root);fsyncdir(root/'revisions')
        return {'public_key_pem':public.decode(),'fingerprint_sha256':pubkey_fingerprint(public),'initial_tip':GENESIS}
    def _key(self):
        key=serialization.load_pem_private_key(nofollow_read(self.root/'secret.ed25519.pem',4096),password=None)
        if not isinstance(key,Ed25519PrivateKey):raise ValueError('Wrong signer key')
        return key
    def _bytes(self):return sum(p.stat().st_size for d in (self.root,self.revisions) for p in d.iterdir() if p.is_file())
    def _fault(self,stage,inject):
        if inject is None:return
        if inject==(stage,'os_exit'):os._exit(79)
        if isinstance(inject,tuple) and inject[0]==stage:
            raise OSError(inject[1],f'Injected storage fault during {stage}')
    def publish(self,attestation,*,expected_tip,inject=None):
        """Internal only; caller must have computed attestation via independent MPFR.

        Never expose this interface to a writer over IPC. The caller must ensure
        single-authority process admission (service holds exclusive writer lock).
        """
        self._ownership()
        pub=nofollow_read(self.root/'public.ed25519.pem',4096)
        fingerprint=pubkey_fingerprint(pub)
        current=verify_chain(self.root,pub,expected_fingerprint=fingerprint,expected_tip=expected_tip)
        if any(p.name.startswith('.record-') or p.name.startswith('.head-') for d in (self.root,self.revisions) for p in d.iterdir()):
            raise ValueError('Pending witness write; operator recovery required')
        # Reject unreachable/orphan revisions before any new signing.
        revisions=list(self.revisions.iterdir())
        if len(revisions)!=current['length'] or any(not REC.fullmatch(x.name) for x in revisions):
            raise ValueError('Orphan, unknown or missing witness record requires explicit recovery')
        if attestation['case_id'] in current['cases']:raise ValueError('Duplicate case signing forbidden')
        fields={'case_id','binding_sha256','original_head_sha256','checkpoint_sha256','archive_sha256','nodes','archive_epochs','mpfr_replayed_frames','proof_replayed','scientific_release','verified_source'}
        if set(attestation)!=fields:raise ValueError('Unrecognized attestation field')
        body={'version':1,'generation':current['length'],'parent':expected_tip,
              'witness_key_fingerprint':fingerprint,**attestation}
        rec={'body':body,'signature':base64.b64encode(self._key().sign(DOMAIN+canonical(body))).decode()}
        raw=canonical(rec)+b'\n';sha=shaobj(rec)
        if len(raw)>MAX:raise ValueError('Witness record too large')
        if self.max_bytes is not None and self._bytes()+3*len(raw)>self.max_bytes:
            raise OSError(errno.ENOSPC,'Witness quota exhausted before commit')
        name=f"{body['generation']:08d}_{sha}.json";target=self.revisions/name
        if target.exists():raise ValueError('Witness record collision')
        # Durable immutable record first. Never overwrite an existing revision.
        self._fault('record_prewrite',inject)
        atomic(self.revisions,name,raw,lambda step:self._fault(step,inject),prefix='record')
        self._fault('before_head',inject)
        atomic(self.root,'HEAD',raw,lambda step:self._fault(step,inject),prefix='head')
        return {'tip':sha,'record':rec}
    def recover(self,*,external_tip,candidate_tip=None):
        """Read-only recovery assessment; no automatic adoption of a new tip.

        For an interrupted HEAD rename, an operator may separately compare the
        candidate receipt to a *fresh MPFR replay* and explicitly repin it.
        """
        pub=nofollow_read(self.root/'public.ed25519.pem',4096)
        fp=pubkey_fingerprint(pub)
        try:
            return {'state':'EXTERNAL_TIP_VALID','chain':verify_chain(self.root,pub,expected_fingerprint=fp,expected_tip=external_tip)}
        except Exception:
            if candidate_tip is None:raise
            chain=verify_chain(self.root,pub,expected_fingerprint=fp,expected_tip=candidate_tip)
            latest=strict(nofollow_read(self.root/'HEAD'))['body']
            if latest['parent']!=external_tip:raise ValueError('Candidate is not direct successor of externally trusted tip')
            return {'state':'QUARANTINED_UNTIL_INDEPENDENT_REPLAY_AND_EXTERNAL_REPIN','chain':chain}


def witness_original_ch33(case_id,source_root,journals_root,pins):
    """Never accept paths/digests from IPC; only protected configuration."""
    if type(case_id)!=str or case_id not in pins:raise ValueError('Case not frozen in authority policy')
    source_root=Path(source_root).resolve();journals_root=Path(journals_root).resolve()
    # This code is executed with a *sealed* source-root that includes CH29
    # original input/dual SHA checks, not in the journal-writer directory.
    sys.path.insert(0,str(source_root/'CH_C14_31'))
    sys.path.insert(0,str(source_root/'CH_C14_33'))
    from verifier31 import load_original_case
    from compaction33 import CompactProofJournal,ARCHIVE_NAME,RECORD_RE,SNAPSHOT
    inp,proto,duals,archived=load_original_case(case_id)
    expected=pins[case_id]
    for key in ('original_head_sha256','checkpoint_sha256'):
        if key not in expected or not isinstance(expected[key],str) or not HEX.fullmatch(expected[key]):
            raise ValueError('Missing independent frozen proof pin')
    if expected.get('nodes')!=127:raise ValueError('Only original frozen 127-node proof accepted')
    active=journals_root/'active'/case_id
    archives=journals_root/'archives'/case_id
    with tempfile.TemporaryDirectory(prefix='ch35-cold-mpfr-') as td:
        stage=Path(td);(stage/'active').mkdir();(stage/'archives').mkdir()
        # Reopen every file O_NOFOLLOW, then independently verify all hashes
        # of the compacted proofs in the witness-owned temporary directory.
        for p in active.iterdir():
            if p.name in ('checkpoint.json',) or RECORD_RE.fullmatch(p.name):
                raw=nofollow_read(p,8*1024*1024)
                (stage/'active'/p.name).write_bytes(raw)
            elif p.name=='.writer.lock':continue
            else:raise ValueError('Unexpected active proof file')
        for p in archives.iterdir():
            if not ARCHIVE_NAME.fullmatch(p.name):raise ValueError('Unexpected archive file')
            (stage/'archives'/p.name).write_bytes(nofollow_read(p,32*1024*1024))
        if hashbytes(nofollow_read(stage/'active'/'checkpoint.json',8*1024*1024))!=expected['checkpoint_file_sha256']:
            raise ValueError('Checkpoint file bytes disagree with independently frozen manifest')
        with CompactProofJournal(stage/'active',inp,proto,duals,case_id=case_id,
                                 archive_dir=stage/'archives',
                                 expected_head_sha256=expected['original_head_sha256'],
                                 expected_checkpoint_sha256=expected['checkpoint_sha256']) as j:
            if not j.full_mathematical_replay or j.recovery_fresh!=127 or j._covered or j._pending:
                raise ValueError('Independent full 127-node replay or stable journal condition failed')
            history=j.verify_archived_history()
            cp=j._checkpoint['body']
            _,source_receipt=archived(127)
            if len(j.cert['nodes'])!=127 or abs(j.session._last_cap-source_receipt['gap_upper_display'])>1e-10:
                raise ValueError('Original CH29 objective gap differs')
            if history['replayed_frames']!=6 or history['archives']!=2 or cp['stage_nodes']!=127:
                raise ValueError('Original historical archive proof incomplete')
            return {'case_id':case_id,'binding_sha256':j._bound(),
                    'original_head_sha256':j.head,'checkpoint_sha256':j._checkpoint['sha256'],
                    'archive_sha256':cp['archive_sha256'],'nodes':127,'archive_epochs':2,
                    'mpfr_replayed_frames':6,'proof_replayed':True,
                    'scientific_release':'NO_GO','verified_source':'original_CH23_independent_MPFR_224'}


def make_pins(source_root):
    """Operator-side genesis manifest, created from verified original CH33 source.

    After operator inspection, move this file into the signer-only account.
    It must NOT be derived from an untrusted client request at signing time.
    """
    root=Path(source_root)
    heads=json.loads((root/'CH_C14_32/heads.json').read_text())
    cpins=json.loads((root/'CH_C14_33/checkpoint_heads.json').read_text())
    out={}
    for case,tip in sorted(cpins.items()):
        cp=root/'CH_C14_33/active'/case/'checkpoint.json'
        raw=nofollow_read(cp,8*1024*1024)
        out[case]={'original_head_sha256':heads[case],'checkpoint_sha256':tip,
                   'checkpoint_file_sha256':hashbytes(raw),'nodes':127}
    return out
