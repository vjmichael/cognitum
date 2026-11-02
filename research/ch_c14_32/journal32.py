"""CH32 durable hash-linked original CH29 proof extension journal.

Journal bytes are *untrusted*. Committed records use atomic rename+fsync;
restart reconstructs every certificate and verifies every new node at 224-bit
MPFR in a fresh process. JSON/SHA-256 offers accidental-corruption/tamper
EVIDENCE only: protection against an attacker who can rewrite all records
requires an externally pinned chain head (and trustworthy code/runtime).

Research Linux implementation. No untrusted proof-state deserialization.
"""
from __future__ import annotations
import copy, fcntl, hashlib, json, os, re, time, uuid
from pathlib import Path
import sys
D=Path(__file__).resolve().parent
sys.path.insert(0,str(D.parent/'CH_C14_31'))
from verifier31 import ProgressiveVerifier

VERSION=1
RECORD_RE=re.compile(r'^(\d{6})\.json$')
PENDING_RE=re.compile(r'^\.\d{6}-[a-f0-9]{32}\.pending$')
GENESIS='0'*64
MAX_RECORD_BYTES=8*1024*1024


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')


def digest(obj):return hashlib.sha256(canonical(obj)).hexdigest()


def _strict_json(raw):
    def pairlist(xs):
        ret={}
        for k,v in xs:
            if k in ret:raise ValueError('Duplicate journal JSON key')
            ret[k]=v
        return ret
    def no_constant(x):raise ValueError('Non-finite journal numeric constant: '+x)
    return json.loads(raw,object_pairs_hook=pairlist,parse_constant=no_constant)


def _node_stable(node):return {k:v for k,v in node.items() if k not in ('children','split_dim')}


def make_delta(old,new):
    a=old['nodes'];b=new['nodes']
    if len(b)<=len(a) or len(a)%2!=1 or len(b)%2!=1:
        raise ValueError('Extension must add complete binary split pairs')
    promotions=[]
    for i,prior in enumerate(a):
        nxt=b[i]
        if _node_stable(prior)!=_node_stable(nxt):raise ValueError('Historical node data altered')
        if 'children' in prior:
            if prior.get('children')!=nxt.get('children') or prior.get('split_dim')!=nxt.get('split_dim'):
                raise ValueError('Previously committed split mutated')
        elif 'children' in nxt and 'split_dim' in nxt:
            promotions.append({'id':i,'children':copy.deepcopy(nxt['children']), 'split_dim':nxt['split_dim']})
        elif 'children' in nxt or 'split_dim' in nxt or 'split_dim' in prior:
            raise ValueError('Incomplete or altered split')
    if not promotions or (len(b)-len(a))%2 or len(promotions)*2>len(b)-len(a):
        # Newly appended nodes may themselves split within this batch.
        # The independent proof traversal validates every child edge.
        raise ValueError('Invalid new split-pair accounting')
    return {'previous_certificate_sha256':digest(old),
            'promotions':promotions,'append_nodes':copy.deepcopy(b[len(a):]),
            'top_level':{k:copy.deepcopy(v) for k,v in new.items() if k!='nodes'}}


def apply_delta(old,delta):
    if set(delta)!= {'previous_certificate_sha256','promotions','append_nodes','top_level'}:
        raise ValueError('Unknown or missing delta field')
    if delta['previous_certificate_sha256']!=digest(old):
        raise ValueError('Previous certificate mismatch')
    result=copy.deepcopy(old); nodes=result['nodes']
    if not isinstance(delta['promotions'],list) or not isinstance(delta['append_nodes'],list):
        raise ValueError('Invalid delta arrays')
    promoted=set()
    for p in delta['promotions']:
        if set(p)!={'id','children','split_dim'} or type(p['id']) is not int or p['id'] in promoted or not (0<=p['id']<len(nodes)):
            raise ValueError('Malformed promotion')
        old_leaf=nodes[p['id']]
        if 'children' in old_leaf or 'split_dim' in old_leaf:raise ValueError('Previously split node modified')
        old_leaf['children']=copy.deepcopy(p['children'])
        old_leaf['split_dim']=p['split_dim'];promoted.add(p['id'])
    if (not promoted or len(delta['append_nodes'])%2 or
        len(promoted)*2>len(delta['append_nodes'])):
        raise ValueError('Extension split count mismatch')
    nodes.extend(copy.deepcopy(delta['append_nodes']))
    if not isinstance(delta['top_level'],dict) or 'nodes' in delta['top_level']:
        raise ValueError('Invalid certificate metadata')
    for k in list(result):
        if k!='nodes':del result[k]
    result.update(copy.deepcopy(delta['top_level']))
    return result


def _directory_sync(path):
    dfd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(dfd)
    finally:os.close(dfd)


def _write_atomic(path,record,crash_at=None):
    raw=canonical(record)+b'\n'
    if len(raw)>MAX_RECORD_BYTES:raise ValueError('Journal record exceeds limit')
    temp=path.parent/f'.{path.stem}-{uuid.uuid4().hex}.pending'
    fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        if crash_at=='before_rename':raise SimulatedCrash('Crash after pending fsync')
        # Lock must be held by caller; never replace an existing committed entry.
        if path.exists():raise ValueError('Committed journal frame already exists')
        os.rename(temp,path)
        if crash_at=='after_rename':raise SimulatedCrash('Crash after atomic rename')
        _directory_sync(path.parent)
        if crash_at=='after_dir_fsync':raise SimulatedCrash('Crash after durable commit before acknowledgement')
    except BaseException:
        # Leave pending files for explicit crash recovery; do not roll back
        # a committed rename after the application loses its acknowledgement.
        raise

class SimulatedCrash(RuntimeError):pass


def _scan(path):
    if not path.is_dir():raise ValueError('Journal directory missing')
    frames={};pending=[]
    for p in path.iterdir():
        if p.name=='.writer.lock':continue
        if p.is_symlink():raise ValueError('Symlinks in journal forbidden')
        mat=RECORD_RE.fullmatch(p.name)
        if mat:
            seq=int(mat.group(1))
            if seq in frames:raise ValueError('Duplicate frame sequence')
            frames[seq]=p
        elif PENDING_RE.fullmatch(p.name):pending.append(p)
        else:raise ValueError('Unknown journal file: '+p.name)
    if sorted(frames)!=list(range(len(frames))):raise ValueError('Missing, reordered or gapped journal frame')
    return [frames[i] for i in range(len(frames))],pending


def _read_frame(path):
    raw=path.read_bytes()
    if not raw.endswith(b'\n') or len(raw)>MAX_RECORD_BYTES:
        raise ValueError('Torn or oversized committed journal entry')
    entry=_strict_json(raw)
    if not isinstance(entry,dict) or set(entry)!={'body','sha256'}:
        raise ValueError('Malformed journal envelope')
    if not isinstance(entry['sha256'],str) or len(entry['sha256'])!=64 or entry['sha256']!=digest(entry['body']):
        raise ValueError('Journal hash mismatch')
    if raw!=canonical(entry)+b'\n':raise ValueError('Non-canonical journal entry encoding')
    return entry


class ProofJournal:
    """Exclusive per-directory journal writer; no verified state import method."""
    def __init__(self,path,inp,proto,duals,*,case_id,expected_head_sha256=None):
        self.path=Path(path)
        self.inp=inp;self.proto=dict(proto);self.duals=duals;self.case_id=case_id
        if case_id not in self.proto["original_case_sha256"]:
            raise ValueError("Unknown original CH23 case")
        self.expected_head_sha256=expected_head_sha256
        self.session=ProgressiveVerifier()
        self.cert=None;self.head=GENESIS;self.seq=0
        self.recovery_cpu_seconds=0.0;self.recovery_fresh=0
        self._lock_fd=None;self._pending=[];self._poisoned=False
    def __enter__(self):
        self.path.mkdir(parents=True,exist_ok=True)
        self._lock_fd=os.open(self.path/'.writer.lock',os.O_RDWR|os.O_CREAT,0o600)
        fcntl.flock(self._lock_fd,fcntl.LOCK_EX)
        try:self.recover()
        except BaseException:self.__exit__(None,None,None);raise
        return self
    def __exit__(self,*args):
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd,fcntl.LOCK_UN);os.close(self._lock_fd);self._lock_fd=None
    def _bound(self):
        # This value is a binding identifier, never a trusted proof result.
        return digest({'case_id':self.case_id,'case':self.inp['original_CH23_identity'],'inp':self.inp,
                       'proto':{k:v for k,v in self.proto.items() if k!='node_budget_per_case'},
                       'duals':self.duals})
    def recover(self):
        """Cold re-verify EVERY committed frame; ignores pending writes entirely."""
        files,pending=_scan(self.path)
        self._pending=pending
        session=ProgressiveVerifier();prev=None;head=GENESIS;start=time.process_time();fresh=0
        for i,path in enumerate(files):
            entry=_read_frame(path);b=entry['body']
            if set(b)!={'version','seq','prev_sha256','case_id','binding_sha256','stage_nodes','kind','certificate_sha256','payload'}:
                raise ValueError('Journal body schema mismatch')
            if (b['version']!=VERSION or type(b['seq']) is not int or b['seq']!=i or
                b['prev_sha256']!=head or b['case_id']!=self.case_id or
                b['binding_sha256']!=self._bound()):
                raise ValueError('Journal sequence, chain or data binding mismatch')
            if (i==0 and b['kind']!='genesis') or (i>0 and b['kind']!='extension'):
                raise ValueError('Wrong journal frame kind')
            cert=copy.deepcopy(b['payload']) if i==0 else apply_delta(prev,b['payload'])
            if type(b['stage_nodes']) is not int or len(cert['nodes'])!=b['stage_nodes'] or digest(cert)!=b['certificate_sha256']:
                raise ValueError('Certificate payload digest or budget invalid')
            before=session.verify_stage(cert,self.inp,{**self.proto,'node_budget_per_case':len(cert['nodes'])},self.duals)
            if before['receipt']['replay_status']!='REPLAYED_BUT_UNRESOLVED':
                raise ValueError('Unexpected proof certification during cold recovery')
            fresh+=before['receipt']['ancestor_caps_recomputed'];prev=cert;head=entry['sha256']
        if self.expected_head_sha256 is not None and head!=self.expected_head_sha256:
            raise ValueError('Journal head disagrees with externally pinned head')
        self.session=session;self.cert=prev;self.head=head;self.seq=len(files)
        self.recovery_cpu_seconds=time.process_time()-start;self.recovery_fresh=fresh
        return {'stages_verified':len(files),'fresh_bounds':fresh,'recovery_cpu_seconds':self.recovery_cpu_seconds,
                'head_sha256':head,'uncommitted_pending':len(pending),'cached_state_imported':False}
    def discard_pending(self):
        """Explicit repair of orphaned pre-rename writes ONLY, after verified recovery."""
        for p in self._pending:
            if not PENDING_RE.fullmatch(p.name):raise ValueError('Non-pending file')
            p.unlink()
        if self._pending:_directory_sync(self.path)
        n=len(self._pending);self._pending=[];return n
    def append(self,cert,*,crash_at=None):
        if self._poisoned:raise RuntimeError('Writer interrupted; must close and cold-recover before reuse')
        if self._pending:raise ValueError('Uncommitted pending writes require explicit discard')
        if self._lock_fd is None:raise RuntimeError('Writer must hold exclusive lock')
        if self.cert is not None and digest(cert)==digest(self.cert):
            return {'already_committed':True,'head_sha256':self.head,'nodes':len(cert['nodes'])}
        is_genesis=self.cert is None
        payload=copy.deepcopy(cert) if is_genesis else make_delta(self.cert,cert)
        # Original data, protocol, partition, MPFR bounds must all pass BEFORE journal commit.
        candidate_session=self.session
        r=candidate_session.verify_stage(cert,self.inp,{**self.proto,'node_budget_per_case':len(cert['nodes'])},self.duals)
        if r['receipt']['replay_status']!='REPLAYED_BUT_UNRESOLVED':
            raise ValueError('Refuse journal promotion or unverified certificate')
        body={'version':VERSION,'seq':self.seq,'prev_sha256':self.head,
              'case_id':self.case_id,
              'binding_sha256':self._bound(),'stage_nodes':len(cert['nodes']),
              'kind':'genesis' if is_genesis else 'extension','certificate_sha256':digest(cert),'payload':payload}
        entry={'body':body,'sha256':digest(body)}
        try:_write_atomic(self.path/f'{self.seq:06d}.json',entry,crash_at)
        except BaseException:
            self._poisoned=True
            raise
        self.cert=copy.deepcopy(cert);self.head=entry['sha256'];self.seq+=1
        return {'already_committed':False,'head_sha256':self.head,'nodes':len(cert['nodes']),
                'fresh_nodes':r['receipt']['ancestor_caps_recomputed'],'reused_nodes':r['receipt']['verified_prefix_nodes_reused'],
                'verified_gap':r['receipt']['gap_upper_display'],'entry_sha256':entry['sha256']}
