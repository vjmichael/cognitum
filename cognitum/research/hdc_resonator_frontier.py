"""Bounded recurrent algebra research; proposals never establish factual truth.
Frady/Kent 2020; nonlinear cleanup DOI 10.3389/frai.2026.1793314.
Uses shared MAP/FHRR units, simultaneous or sequential coupled updates.
"""
from dataclasses import dataclass
from itertools import product
import hashlib
from math import prod
import numpy as np
from .hdc_algebra import Spec
from .hdc_ghrr import GHRRSpec
from .hdc_associative import classical_field, continuous_hopfield

RULES=('sign','softmax','relu','polynomial')

def _bounded_int(n,lo,hi):
    if type(n) is not int or not lo<=n<=hi: raise ValueError('bounded integer required')
    return n

def _project(spec,x):
    if spec.family=='MAP': return np.where(x>=0,1,-1).astype(spec.dtype)
    mag=np.abs(x)
    return np.divide(x,mag,out=np.ones_like(x),where=mag>1e-12).astype(spec.dtype)

def cleanup_weights(a,rule,*,beta=20.,degree=2):
    a=np.asarray(a,dtype=np.float64)
    if a.ndim!=1 or not len(a) or not np.isfinite(a).all() or rule not in RULES or not np.isfinite(beta) or not 0<beta<=1000 or type(degree) is not int or not 1<=degree<=8:raise ValueError('cleanup parameters')
    if rule=='sign': return a
    if rule=='softmax': w=np.exp(beta*(a-a.max()))
    else:
        w=np.maximum(a,0.)
        if w.max()>0:w=w/w.max()
        if rule=='polynomial':w=w**degree
    return w/w.sum() if w.sum()>0 else np.full(len(w),1/len(w))

@dataclass(frozen=True)
class FactorResult:
    ids: tuple[int,...]|None
    status: str
    score: float
    sweeps: int
    projections: int
    attempts: int
    decoded_ids: tuple[int,...]|None = None

class CoupledResonator:
    def __init__(self,spec,banks):
        if not isinstance(spec,Spec) or spec.family not in ('MAP','FHRR') or spec.dimension>4096 or not 2<=len(banks)<=8:raise ValueError('MAP/FHRR and 2..8 roles required')
        self.spec=spec;self.banks=[]
        for bank in banks:
            x=np.asarray(bank)
            if x.ndim!=2 or not 2<=len(x)<=4096 or x.shape[1]!=spec.dimension or x.dtype!=spec.dtype or not np.isfinite(x).all() or not np.allclose(np.abs(x),1,rtol=0,atol=2e-6):raise ValueError('unit bank required')
            x=x.copy();x.flags.writeable=False;self.banks.append(x)
        if sum(b.nbytes for b in self.banks)>32*1024**2:raise ValueError('bank budget')
        self.banks=tuple(self.banks)
    @property
    def nbytes(self):return sum(b.nbytes for b in self.banks)
    def compose(self,ids):
        if len(ids)!=len(self.banks):raise ValueError('roles')
        x=np.ones(self.spec.dimension,self.spec.dtype)
        for i,b in zip(ids,self.banks):
            if isinstance(i,(bool,np.bool_)) or not isinstance(i,(int,np.integer)) or not 0<=i<len(b):raise ValueError('factor index')
            x=self.spec.bind(x,b[i])
        return x
    def scores(self,i,q):return (self.banks[i].conj()@q).real/self.spec.dimension
    def sweep(self,query,states,*,rule='sign',project=True,beta=20.,degree=2,asynchronous=True):
        q=self.spec.checked(query)
        if len(states)!=len(self.banks) or np.max(np.abs(q))>16 or type(project) is not bool or type(asynchronous) is not bool:raise ValueError('sweep controls')
        cleanup_weights([0.],rule,beta=beta,degree=degree)
        old=[self.spec.checked(x).copy() for x in states]
        if any(np.max(np.abs(x))>1.00001 for x in old):raise ValueError('bounded state amplitude')
        states=list(old);new=[]
        for i,b in enumerate(self.banks):
            source=states if asynchronous else old
            cue=q.copy()
            for j,x in enumerate(source):
                if j!=i:cue*=x.conj()
            a=(b.conj()@cue)/self.spec.dimension
            w=a if rule=='sign' else cleanup_weights(a.real,rule,beta=beta,degree=degree)
            x=(w@b).astype(self.spec.dtype)
            if project:x=_project(self.spec,x)
            elif rule=='sign':
                norm=np.max(np.abs(x));x=x/norm if norm else x
            if asynchronous:states[i]=x
            else:new.append(x)
        return tuple(states if asynchronous else new)
    def decode(self,query,*,rule='sign',project=None,steps=40,restarts=1,seed=0,beta=20.,degree=2,asynchronous=True,minimum=.5,initial=None):
        q=self.spec.checked(query); steps=_bounded_int(steps,1,250);restarts=_bounded_int(restarts,1,32);_bounded_int(seed,0,2**64-1)
        if np.max(np.abs(q))>16 or steps*restarts*sum(b.size for b in self.banks)>500_000_000:raise ValueError('compute/query budget')
        if rule not in RULES or type(asynchronous) is not bool or not np.isfinite(minimum) or not -1<=minimum<=1:raise ValueError('controls')
        if project is None:project=rule in ('sign','softmax')
        if type(project) is not bool:raise ValueError('projection flag')
        cleanup_weights([0.],rule,beta=beta,degree=degree)
        if not q.any():return FactorResult(None,'zero',0.,0,0,0)
        if initial is not None:self.compose(initial)
        rng=np.random.default_rng(seed);best=None;n=len(self.banks);total=0;projections=0
        for attempt in range(restarts):
            if attempt==0 and initial is not None: states=[b[i].copy() for b,i in zip(self.banks,initial)]
            elif attempt==0:states=[_project(self.spec,b.sum(axis=0)) if project else b.mean(axis=0) for b in self.banks]
            else:states=[b[rng.integers(len(b))].copy() for b in self.banks]
            status='budget';ids=None;seen=set()
            for _ in range(steps):
                total+=1;old=[x.copy() for x in states]
                states=list(self.sweep(q,states,rule=rule,project=project,beta=beta,degree=degree,asynchronous=asynchronous))
                projections+=n
                scores=[self.scores(i,x) for i,x in enumerate(states)]
                ids=tuple(int(np.argmax(s)) for s in scores)
                tied=any(np.count_nonzero(np.isclose(s,s.max(),rtol=0,atol=1e-7))>1 for s in scores)
                fixed=all(np.allclose(a,b,rtol=0,atol=1e-6) for a,b in zip(old,states))
                if fixed:status='ambiguous' if tied else 'fixed';break
                # exact state repeat detection, not just decoded ID repeat
                key=hashlib.sha256(b''.join(x.tobytes() for x in states)).digest()
                if key in seen:status='cycle';break
                seen.add(key)
            score=self.spec.similarity(q,self.compose(ids))
            candidate=FactorResult(ids if status=='fixed' and score>=minimum else None,status,score,total,projections,attempt+1,ids)
            if best is None or (candidate.ids is not None,score)>(best.ids is not None,best.score):best=candidate
            if candidate.ids is not None and score>=1-1e-6:break
        return FactorResult(best.ids,best.status,best.score,total,projections,attempt+1,best.decoded_ids)
    def exhaustive(self,q,*,max_candidates=65536):
        q=self.spec.checked(q); _bounded_int(max_candidates,1,65536)
        count=prod(map(len,self.banks))
        if count>max_candidates:raise ValueError('exhaustive budget')
        if not q.any():return FactorResult(None,'zero',0.,0,0,0)
        if np.max(np.abs(q))>16 or count*self.spec.dimension>100_000_000:raise ValueError('exhaustive compute/query budget')
        # streamed Cartesian products, exact shared coordinate score, bounded tiles
        best=-np.inf;ids=None;ties=0;norm=np.linalg.norm(q.astype(np.complex128))*np.sqrt(self.spec.dimension)
        from itertools import islice
        it=product(*(range(len(b)) for b in self.banks))
        while batch:=list(islice(it, max(1,min(256,1_048_576//self.spec.dimension)))):
            idx=np.asarray(batch);x=np.ones((len(batch),self.spec.dimension),self.spec.dtype)
            for i,b in enumerate(self.banks):x*=b[idx[:,i]]
            scores=(x.conj()@q).real/norm
            for j,s in enumerate(scores):
                if s>best+1e-7:best=float(s);ids=batch[j];ties=1
                elif abs(s-best)<=1e-7:ties+=1
        return FactorResult(ids if ties==1 else None,'exhaustive' if ties==1 else 'ambiguous',best,0,count,1,ids if ties==1 else None)

@dataclass(frozen=True)
class HopfieldResult:
    state: np.ndarray
    status: str
    sweeps: int
    energies: tuple[float,...]

def iterate_classical(patterns,q,*,steps=30):
    p=np.asarray(patterns);x=np.asarray(q).copy();_bounded_int(steps,1,250)
    classical_field(p,x) # validate accepted shared reference
    if p.size>1_048_576 or p.size*steps>100_000_000:raise ValueError('iteration budget')
    p=p.astype(np.int64);x=x.astype(np.int64);n=len(p);s=p@x
    energy=lambda:float(-.5*(s@s-n*len(x)))
    energies=[energy()]
    for k in range(steps):
        changed=False
        for i in range(len(x)):
            f=int(p[:,i]@s-n*x[i]);v=1 if f>0 else -1 if f<0 else x[i]
            if v!=x[i]:s+=p[:,i]*(v-x[i]);x[i]=v;changed=True
        energies.append(energy())
        if not changed:return HopfieldResult(x.astype(np.int8),'fixed',k+1,tuple(energies))
    return HopfieldResult(x.astype(np.int8),'budget',steps,tuple(energies))

def iterate_continuous(patterns,q,*,beta=8.,steps=30,tolerance=1e-8):
    _bounded_int(steps,1,250)
    if not np.isfinite(tolerance) or not 0<tolerance<=.01:raise ValueError('tolerance')
    p=np.asarray(patterns);q=np.asarray(q)
    if q.dtype.kind not in 'fiu' or p.dtype.kind not in 'fiu':raise ValueError('real operands required')
    x=q.astype(np.float64).copy()
    if p.size*steps>100_000_000 or not np.isfinite(p).all() or np.max(np.abs(p),initial=0)>16 or np.max(np.abs(x),initial=0)>16:raise ValueError('iteration budget')
    continuous_hopfield(p,x,beta)
    def energy(x):return float(.5*(x@x)-np.logaddexp.reduce(beta*(p@x))/beta)
    es=[energy(x)]
    for k in range(steps):
        y=continuous_hopfield(p,x,beta);es.append(energy(y))
        if np.linalg.norm(y-x)<=tolerance:return HopfieldResult(y,'fixed',k+1,tuple(es))
        x=y
    return HopfieldResult(x,'budget',steps,tuple(es))

@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str
    witness: str

class OrderedPaths:
    """Bounded candidate path ranking; exact current directed witness required.
    No LLM, graph authorization, fact inference, or persistence implied.
    """
    def __init__(self,spec,relations,edges,snapshot):
        if not isinstance(spec,(Spec,GHRRSpec)) or (isinstance(spec,Spec) and spec.family!='FHRR') or not isinstance(snapshot,str) or not snapshot or len(snapshot)>128:raise ValueError('typed path spec and snapshot')
        if not 1<=len(relations)<=256 or len(edges)>4096 or sum(np.asarray(v).nbytes for v in relations.values())>16*1024**2:raise ValueError('graph budget')
        self.spec=spec;self.snapshot=snapshot;self.relations={}
        for name,v in relations.items():
            if not isinstance(name,str) or not name:raise ValueError('relation name')
            v=spec.checked(v).copy()
            if isinstance(spec,GHRRSpec):
                if not spec.unitary(v):raise ValueError('unitary relation')
            elif not np.allclose(abs(v),1,atol=2e-6):raise ValueError('unit phase relation')
            v.flags.writeable=False;self.relations[name]=v
        self.edges=tuple(edges);self.adj={};seen=set()
        for e in self.edges:
            if not isinstance(e,Edge) or e.relation not in self.relations or not all(isinstance(x,str) and 0<len(x)<=128 for x in (e.source,e.target,e.witness)) or e.witness in seen:raise ValueError('invalid edge')
            seen.add(e.witness);self.adj.setdefault(e.source,[]).append(e)
    def encode(self,relations):
        if not 1<=len(relations)<=6:raise ValueError('path length')
        x=self.spec.identity() if isinstance(self.spec,GHRRSpec) else np.ones(self.spec.dimension,self.spec.dtype)
        for i,r in enumerate(relations):
            v=self.relations[r];x=self.spec.bind(x,v if isinstance(self.spec,GHRRSpec) else self.spec.permute(v,i))
        return x
    def candidates(self,start,q,depth,*,k=8,max_paths=4096):
        _bounded_int(depth,1,6);_bounded_int(k,1,64);_bounded_int(max_paths,1,4096);self.spec.checked(q)
        frontier=[(start,())]
        for _ in range(depth):
            nxt=[]
            for node,path in frontier:
                for e in self.adj.get(node,[]):
                    if len(nxt)>=max_paths:raise OverflowError('path enumeration budget')
                    nxt.append((e.target,path+(e,)))
            frontier=nxt
        ranked=[]
        for node,path in frontier:
            score=self.spec.similarity(q,self.encode([e.relation for e in path]));ranked.append((score,path))
        return tuple(sorted(ranked,key=lambda x:(-x[0],tuple(e.witness for e in x[1])))[:k])
    def verify(self,path,*,start,relations,current_snapshot,canonical_edges):
        if current_snapshot!=self.snapshot:raise ValueError('stale snapshot')
        if not path or len(path)!=len(relations) or len(path)>6:return None
        by_id={}
        for i,e in enumerate(canonical_edges):
            if i>=4096 or not isinstance(e,Edge) or e.witness in by_id:raise ValueError('canonical edge budget/duplicate')
            by_id[e.witness]=e
        node=start
        for e,r in zip(path,relations):
            if not isinstance(e,Edge) or by_id.get(e.witness)!=e or e.source!=node or e.relation!=r:return None
            node=e.target
        return node,tuple(e.witness for e in path)
