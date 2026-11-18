"""D1C bounded research memory; no registered route or canonical authority.
Packed SDM activation; signed symmetric Hopfield sketch (not a recurrent net);
HRR select/project candidates, with independent current-snapshot checks.
"""
from dataclasses import dataclass
import hashlib, json, math
import numpy as np
from .hdc_associative import SparseDistributed, _bipolar, _int
from .hdc_encoders import PackedBank, pack, CodebookSpec
from .hdc_algebra import Spec

class PackedSDM(SparseDistributed):
    """Standalone research backend. Not interchangeable with D1B lifecycle,
    whose checkpoint uses explicit hard addresses. Same counters and writes.
    """
    def __init__(self, addresses, value_dim, radius, *, limit=32767):
        super().__init__(addresses,value_dim,radius,limit=limit)
        self._bank=PackedBank.from_bits(self._addresses<0)
        del self._addresses
    @property
    def nbytes(self): return self._bank.nbytes+self._counters.nbytes+self._counts.nbytes
    def active(self,key):
        q=_bipolar(key,self.key_dim)
        return np.flatnonzero(self._bank.distances(pack(q<0))<=self.radius)

class SignedHopfieldSketch:
    """Clarkson/Ubaru/Yang signed outer-product sketch, triangular int32.
    Atom signs and independent coefficient sign regenerated from domain-separated
    indexed seeds. Frobenius inner product divided by d**2 is unbiased under
    independent coefficient signs. Not a guarantee for every fixed seed.
    No deletion authority or retained set. Input IDs must be unique.
    """
    def __init__(self,dimension,seed,ids):
        self.d=_int(dimension,2,1024); self.seed=_int(seed,0,2**63-1)
        ids=tuple(ids)
        if len(ids)>4096 or len(set(ids))!=len(ids): raise ValueError('set budget or duplicate')
        self.n=len(ids); tri=np.triu_indices(self.d,1)
        self._diag=0; a=np.zeros(len(tri[0]),np.int32)
        for i in ids:
            v,s=self.atom(i); self._diag+=s; a+=s*v[tri[0]]*v[tri[1]]
        self.data=np.frombuffer(a.tobytes(),np.int32)
    def atom(self,i):
        _int(i,0,2**20-1)
        v=1-2*CodebookSpec(self.d,self.seed).bits(1,i)[0].astype(np.int32)
        sign=1-2*int(np.random.default_rng(np.random.SeedSequence([self.seed,i,0x48504d])).integers(2))
        return v,sign
    @property
    def payload_bytes(self): return self.data.nbytes+32 # logical descriptor; triangle indices are temporary
    def dense(self):
        tri=np.triu_indices(self.d,1); a=np.full((self.d,self.d),self._diag,np.int32); a[tri]=self.data; a[(tri[1],tri[0])]=self.data
        return a
    def intersection(self,other):
        if not isinstance(other,SignedHopfieldSketch) or (self.d,self.seed)!=(other.d,other.seed):raise ValueError('incompatible sketch')
        return (2*int(self.data.astype(np.int64)@other.data.astype(np.int64))+self.d*self._diag*other._diag)/self.d**2
    def score(self,i):
        v,s=self.atom(i); tri=np.triu_indices(self.d,1)
        return s*(2*int(self.data.astype(np.int64)@(v[tri[0]]*v[tri[1]]).astype(np.int64))+self.d*self._diag)/self.d**2
    def contains(self,i): return self.score(i)>=.5

def _token(value):
    # SQL experiment limited to integers, case-sensitive strings and NULL.
    if value is None:return ['null']
    if type(value) is int and -(2**63)<=value<2**63:return ['int',value]
    if type(value) is str and len(value)<=128:return ['text',value]
    raise ValueError('unsupported cell')

def _atom(d, seed, domain, value):
    raw=json.dumps([seed,domain,_token(value)],ensure_ascii=True,separators=(',',':')).encode()
    rng=np.random.default_rng(int.from_bytes(hashlib.sha256(raw).digest()[:16],'big'))
    x=rng.normal(size=d);return (x/np.linalg.norm(x)).astype(np.float32)

def _table(rows,width):
    rows=tuple(tuple(r) for r in rows)
    if not 1<=len(rows)<=4096 or any(len(r)!=width for r in rows):raise ValueError('table shape')
    for r in rows:
        for v in r:_token(v)
    return rows

def _digest(rows):
    return hashlib.sha256(json.dumps(rows,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()

def _predicates(predicates,width):
    p=tuple(predicates)
    if not 1<=len(p)<=width:raise ValueError('predicate count')
    for j,op,v in p:
        _int(j,0,width-1);_token(v)
        if op not in ('=','!=','IS NULL','IS NOT NULL') or (op.startswith('IS ') and v is not None) or (op in ('=','!=') and v is None):raise ValueError('predicate')
    if len({j for j,_,_ in p})!=len(p):raise ValueError('duplicate predicate column')
    return p

def matches(row,p):
    for j,op,v in p:
        x=row[j]
        if op=='IS NULL':ok=x is None
        elif op=='IS NOT NULL':ok=x is not None
        else:ok=x is not None and ((x==v) if op=='=' else (x!=v))
        if not ok:return False
    return True

@dataclass(frozen=True)
class TableProposal:
    snapshot:str
    revision:int
    digest:str
    ids:tuple[int,...]

class HRRTable:
    """Normalized role/value convolutions. Per-column predicate scoring allows
    conjunctions of equality, inequality and NULL tests; independent extension,
    not exact reproduction of the paper's summed-query thresholds. Row indices
    are positional in a single supplied snapshot; duplicates stay distinct.
    No canonical storage. Approximate selection can omit matching rows.
    """
    def __init__(self,rows,dimension,seed,snapshot,revision):
        self.spec=Spec('HRR',_int(dimension,32,4096));self.seed=_int(seed,0,2**63-1)
        if type(snapshot) is not str or not 1<=len(snapshot)<=80:raise ValueError('snapshot')
        self.snapshot=snapshot;self.revision=_int(revision,1,2**63-1)
        rows=tuple(rows)
        if not rows:raise ValueError('empty table')
        self.width=_int(len(rows[0]),1,20);rows=_table(rows,self.width)
        if len(rows)*dimension>4_194_304:raise ValueError('index budget')
        self.digest=_digest(rows)
        self._roles=np.stack([_atom(dimension,seed,'role',j) for j in range(self.width)])
        self._roles.flags.writeable=False
        self._rows=np.stack([self.encode(r) for r in rows]);self._rows.flags.writeable=False
    def pair(self,j,v):return self.spec.bind(self._roles[j],_atom(self.spec.dimension,self.seed,'cell',v))
    def encode(self,row):
        t=self.spec.bundle(np.stack([self.pair(j,v) for j,v in enumerate(row)]));n=np.linalg.norm(t)
        if n==0:raise ValueError('degenerate row')
        return t/n
    @property
    def payload_bytes(self):return self._roles.nbytes+self._rows.nbytes+len(self.digest)+len(self.snapshot.encode())+32
    def propose(self,predicates):
        p=_predicates(predicates,self.width);mask=np.ones(len(self._rows),bool)
        # Midpoint between asymptotic matching and nonmatching single-pair
        # means, fixed before experiment, no tuning on ground truth.
        cutoff=.5/math.sqrt(self.width)
        for j,op,v in p:
            q=self.pair(j,v);scores=self._rows@(q/np.linalg.norm(q))
            if op in ('=','IS NULL'):mask &= scores>=cutoff
            else:mask &= scores<cutoff
            if op=='!=':
                z=self.pair(j,None);mask &= self._rows@(z/np.linalg.norm(z))<cutoff
        return TableProposal(self.snapshot,self.revision,self.digest,tuple(map(int,np.flatnonzero(mask))))
    def project_candidates(self,row_id,column,values):
        _int(row_id,0,len(self._rows)-1);_int(column,0,self.width-1)
        v=tuple(values)
        if not 1<=len(v)<=4096 or len({json.dumps(_token(x)) for x in v})!=len(v):raise ValueError('projection vocabulary')
        q=self.spec.unbind(self._roles[column],self._rows[row_id]);scores=[self.spec.similarity(q,_atom(self.spec.dimension,self.seed,'cell',x)) for x in v]
        return v[int(np.argmax(scores))]

    def verify(self,proposal,predicates,columns,*,canonical_rows,current_snapshot,current_revision,complete=False):
        """Independent exact filtering/projection from supplied current rows.
        Caller must be host-authorized; no authorization inferred here. With
        complete=True explicitly scan all rows (not an HDC speed claim).
        Returns positional row IDs plus projection to preserve SQL duplicates.
        """
        if type(complete) is not bool or not isinstance(proposal,TableProposal):raise ValueError('proposal')
        if (current_snapshot,current_revision)!=(self.snapshot,self.revision) or (proposal.snapshot,proposal.revision,proposal.digest)!=(self.snapshot,self.revision,self.digest):raise ValueError('STALE_TABLE')
        rows=_table(canonical_rows,self.width)
        if _digest(rows)!=self.digest:raise ValueError('STALE_TABLE_CONTENT')
        p=_predicates(predicates,self.width);cols=tuple(columns)
        if not 1<=len(cols)<=self.width or any(type(j) is not int or not 0<=j<self.width for j in cols):raise ValueError('columns')
        if tuple(sorted(set(proposal.ids)))!=proposal.ids or any(type(i) is not int or not 0<=i<len(rows) for i in proposal.ids):raise ValueError('invalid proposal IDs')
        ids=range(len(rows)) if complete else proposal.ids
        return tuple((i,tuple(rows[i][j] for j in cols)) for i in ids if matches(rows[i],p))
