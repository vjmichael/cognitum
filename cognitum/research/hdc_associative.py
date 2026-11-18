"""Bounded associative research operations, never a canonical memory service.
Kanerva multi-location SDM, classical/DAM/continuous Hopfield references.
Research inputs must be supplied by caller; cleanup returns candidates only.
"""
from dataclasses import dataclass
import numpy as np
from scipy.special import logsumexp
from .hdc_algebra import Spec


def _int(n, lo, hi):
    if type(n) is not int or not lo <= n <= hi:
        raise ValueError('integer outside research limits')
    return n


def _bipolar(a, d):
    a=np.asarray(a)
    if a.shape != (d,) or a.dtype != np.int8 or not np.all((a==1)|(a==-1)):
        raise ValueError('expected int8 bipolar vector')
    return a


@dataclass(frozen=True)
class Candidate:
    index: int
    score: float
    margin: float


class Cleanup:
    """Typed, immutable candidate bank, stable tie rejection and abstention.
    Scores are similarities, not calibrated probabilities or factual evidence.
    """
    def __init__(self, spec: Spec, rows):
        if not isinstance(spec,Spec): raise ValueError('typed spec required')
        a=np.asarray(rows)
        if a.ndim!=2 or not 2<=len(a)<=65536 or a.nbytes>64*1024**2:raise ValueError('bank limits')
        for r in a: spec.checked(r)
        self.spec=spec; self._rows=a.copy(); self._rows.flags.writeable=False

    @property
    def nbytes(self):return self._rows.nbytes

    def scores(self,q):
        q=self.spec.checked(q)
        return np.array([self.spec.similarity(q,r) for r in self._rows],dtype=np.float64)

    def propose(self,q,*,minimum,margin):
        if not np.isfinite([minimum,margin]).all() or not -1<=minimum<=1 or not 0<=margin<=2:raise ValueError('thresholds')
        q=self.spec.checked(q)
        if self.spec.family in ('MAP','HRR','FHRR','VTB') and not q.any():return None
        s=self.scores(q); order=np.argsort(-s,kind='stable'); i,j=map(int,order[:2]); gap=float(s[i]-s[j])
        return Candidate(i,float(s[i]),gap) if s[i]>=minimum and gap>0 and gap>=margin else None



class SparseDistributed:
    """Fixed hard addresses, radius activation, additive distributed counters.
    No clipping: refuse overflow atomically so exact inverse writes are possible.
    Caller must supply original write for subtract; no claim of delete by ID.
    An empty or tied read abstains instead of inventing bipolar bits.
    """
    def __init__(self, addresses, value_dim, radius, *, limit=32767):
        a=np.asarray(addresses)
        if a.ndim!=2 or not 1<=len(a)<=65536 or not 1<=a.shape[1]<=4096 or a.nbytes>64*1024**2 or a.dtype!=np.int8 or not np.all((a==1)|(a==-1)):raise ValueError('hard addresses')
        self.key_dim=a.shape[1];self.value_dim=_int(value_dim,1,4096); self.radius=_int(radius,0,self.key_dim);self.limit=_int(limit,1,32767)
        if len(a)*self.value_dim*2>64*1024**2: raise ValueError('counter budget')
        self._addresses=a.copy();self._addresses.flags.writeable=False;self._counters=np.zeros((len(a),value_dim),np.int16);self._counts=np.zeros(len(a),np.int32)

    @property
    def nbytes(self):return self._addresses.nbytes+self._counters.nbytes+self._counts.nbytes

    def active(self,key):
        q=_bipolar(key,self.key_dim)
        return np.flatnonzero(np.count_nonzero(self._addresses!=q,axis=1)<=self.radius)

    def write(self,key,value,*,subtract=False):
        # A reversible arithmetic primitive, not deletion authorization.
        if type(subtract) is not bool:raise ValueError('subtract flag')
        v=_bipolar(value,self.value_dim);idx=self.active(key)
        if not len(idx):return 0
        sign=-1 if subtract else 1
        counts=self._counts[idx].astype(np.int64)+sign
        nxt=self._counters[idx].astype(np.int32)+sign*v
        if (counts<0).any() or (counts>self.limit).any() or (np.abs(nxt)>self.limit).any() or (np.abs(nxt)>counts[:,None]).any():raise OverflowError('counter limit or invalid subtraction')
        self._counters[idx]=nxt;self._counts[idx]=counts
        return len(idx)

    def raw(self,key):
        idx=self.active(key);return self._counters[idx].sum(axis=0,dtype=np.int64),int(self._counts[idx].sum(dtype=np.int64))

    def read(self,key):
        s,n=self.raw(key)
        return None if n==0 or np.any(s==0) else np.sign(s).astype(np.int8)


def classical_field(patterns,q):
    p=np.asarray(patterns)
    if p.ndim!=2 or not 1<=p.shape[0]<=4096 or not 1<=p.shape[1]<=4096 or p.dtype!=np.int8 or not np.all((p==1)|(p==-1)):raise ValueError('patterns')
    x=_bipolar(q,p.shape[1]).astype(np.int64); p=p.astype(np.int64)
    # (P.T @ P - n I) @ x, without materializing the quadratic matrix.
    return p.T@(p@x)-len(p)*x


def dense_associative_field(patterns,q):
    """Exponential dense associative coordinate-energy difference. Stable LSE.
    Not the continuous Ramsauer update; compare TorchHD modern_hopfield.
    """
    p=np.asarray(patterns)
    if p.ndim!=2 or p.size>4_194_304 or p.dtype!=np.int8 or not len(p) or not p.shape[1] or not np.all((p==1)|(p==-1)):raise ValueError('patterns')
    x=_bipolar(q,p.shape[1]).astype(np.float64); p=p.astype(np.float64)
    base=p@x; without=base[:,None]-p*x
    return logsumexp(without+p,axis=0)-logsumexp(without-p,axis=0)


def continuous_hopfield(patterns,q,beta):
    """Ramsauer softmax update for real rows; no convergence guarantee."""
    p=np.asarray(patterns);q=np.asarray(q)
    if p.dtype.kind not in 'fiu' or q.dtype.kind not in 'fiu' or p.size>4_194_304:raise ValueError('real bounded operands required')
    p=p.astype(np.float64);q=q.astype(np.float64)
    if p.ndim!=2 or not len(p) or p.size>4_194_304 or q.shape!=(p.shape[1],) or not np.isfinite(p).all() or not np.isfinite(q).all() or not np.isfinite(beta) or not 0<beta<=1000:raise ValueError('invalid continuous operands')
    s=beta*(p@q)
    if not np.isfinite(s).all():raise ValueError('score overflow')
    w=np.exp(s-logsumexp(s));out=w@p
    if not np.isfinite(out).all():raise ValueError('output overflow')
    return out


class PhaseWorkingMemory:
    """Bounded FHRR role-value sum; ephemeral research working memory.
    Uses the shared Spec instead of a separate mathematical representation.
    The long-term SDM uses its own typed bipolar input; no implicit cast.
    """
    def __init__(self,dimension,*,capacity=16):
        self.spec=Spec('FHRR',dimension);self.capacity=_int(capacity,1,1024);self._sum=np.zeros(dimension,np.complex64);self.count=0

    def _unit(self,v):
        v=self.spec.checked(v)
        if not np.allclose(np.abs(v),1,rtol=0,atol=2e-6):raise ValueError('unit phase required')
        return v

    @property
    def nbytes(self):return self._sum.nbytes

    def add(self,role,value):
        if self.count>=self.capacity:raise OverflowError('working capacity')
        self._sum+=self.spec.bind(self._unit(role),self._unit(value));self.count+=1

    def cue(self,role):
        if not self.count:return None
        return self.spec.unbind(self._unit(role),self._sum)


class TwoTierRecall:
    """FHRR working cue -> typed phase-address cleanup -> bipolar SDM ->
    typed value cleanup. Both boundaries abstain. Aligned address codebooks
    are an explicit research fixture, not a canonical lookup service.
    """
    def __init__(self, working, phase_addresses, bipolar_addresses, long_term, value_bank):
        if not isinstance(working,PhaseWorkingMemory) or not isinstance(long_term,SparseDistributed):raise ValueError('typed memories required')
        self.working=working;self.long_term=long_term
        self.phase_bank=Cleanup(working.spec,phase_addresses)
        a=np.asarray(bipolar_addresses)
        if len(a)!=len(self.phase_bank._rows):raise ValueError('unaligned codebooks')
        for row in a:_bipolar(row,long_term.key_dim)
        self._addresses=a.copy();self._addresses.flags.writeable=False
        self.value_bank=Cleanup(Spec('MAP',long_term.value_dim),value_bank)

    def propose(self, role, *, minimum=.3, margin=.05):
        q=self.working.cue(role)
        if q is None:return None
        key=self.phase_bank.propose(q,minimum=minimum,margin=margin)
        if key is None:return None
        raw,n=self.long_term.raw(self._addresses[key.index])
        if n==0 or not raw.any():return None
        value=self.value_bank.propose(raw.astype(np.float32),minimum=minimum,margin=margin)
        return (key,value) if value is not None else None
