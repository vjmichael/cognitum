"""Default-off bounded D2B research. Scores produce proposals, not facts.
GSBC factorizer: Hersche et al., DOI 10.3233/NAI-240713, equations 1,3-10.
GraphHD-inspired tied-rank encoding; ARC-inspired finite object DSL.
"""
from dataclasses import dataclass
from itertools import product, islice
from math import prod
import numpy as np
from .hdc_resonator_frontier import CoupledResonator, _bounded_int
from .hdc_algebra import Spec


def correlated_banks(spec, roles, count, fraction, seed):
    """Share a fixed prototype coordinate mask within each role, not across roles."""
    _bounded_int(roles,2,8); _bounded_int(count,2,256); _bounded_int(seed,0,2**64-1)
    if not isinstance(spec,Spec) or spec.family not in ('MAP','FHRR') or spec.dimension>4096 or roles*count*spec.dimension*spec.dtype.itemsize>32*1024**2 or not np.isfinite(fraction) or not 0<=fraction<=1:
        raise ValueError('correlation controls')
    rng=np.random.default_rng(seed);banks=[]
    for _ in range(roles):
        if spec.family=='MAP': b=rng.choice([-1,1],(count,spec.dimension)).astype(spec.dtype)
        else: b=np.exp(1j*rng.uniform(-np.pi,np.pi,(count,spec.dimension))).astype(spec.dtype)
        mask=rng.permutation(spec.dimension)[:round(fraction*spec.dimension)]
        b[:,mask]=b[0,mask];banks.append(b)
    return tuple(banks)


def coordinate_beam(engine, q, *, width=8, sweeps=6, seed=0, minimum=.5):
    """Multi-start coordinate beam; no claim of global optimality."""
    _bounded_int(width,1,32);_bounded_int(sweeps,1,32);_bounded_int(seed,0,2**64-1)
    q=engine.spec.checked(q);n=len(engine.banks)
    if not np.isfinite(minimum) or not 0<=minimum<=1 or width*sweeps*sum(b.size for b in engine.banks)>100_000_000:raise ValueError('beam budget')
    if not q.any():return None,0
    rng=np.random.default_rng(seed);beam={tuple(int(rng.integers(len(b))) for b in engine.banks) for _ in range(width)};evaluations=0
    for _ in range(sweeps):
        for role,b in enumerate(engine.banks):
            proposals=set()
            for ids in beam:
                cue=q.copy()
                for j,k in enumerate(ids):
                    if j!=role:cue*=engine.banks[j][k].conj()
                s=engine.scores(role,cue);evaluations+=len(b)
                for k in np.argsort(-s,kind='stable')[:width]:proposals.add(ids[:role]+(int(k),)+ids[role+1:])
            beam=set(sorted(proposals,key=lambda x:(-engine.spec.similarity(q,engine.compose(x)),x))[:width]);evaluations+=len(proposals)
    ranked=sorted((engine.spec.similarity(q,engine.compose(x)),x) for x in beam);evaluations+=len(beam)
    score,ids=ranked[-1]
    return (ids if score>=minimum and (len(ranked)==1 or score-ranked[-2][0]>1e-7) else None),evaluations


def peel(engine, q, count, *, method='iterative', minimum=.35, seed=0):
    """Matching pursuit on superpositions. Abstain on duplicate or low-score tuple.
    Returned tuples are candidates; residual can expose incomplete explanations.
    """
    _bounded_int(count,1,8);_bounded_int(seed,0,2**64-9)
    if method not in ('iterative','exhaustive') or not np.isfinite(minimum) or not 0<=minimum<=1:raise ValueError('peel controls')
    r=engine.spec.checked(q).copy();ids=[];work=0
    if np.max(np.abs(r))>8:raise ValueError('bounded mixture')
    for k in range(count):
        if np.linalg.norm(r)<1e-6:break
        result=(engine.decode(r,rule='relu',project=False,restarts=3,steps=25,seed=seed+k,minimum=minimum) if method=='iterative' else engine.exhaustive(r))
        work+=result.projections
        if result.ids is None or result.score<minimum or result.ids in ids:break
        v=engine.compose(result.ids);weight=float(np.vdot(v,r).real/np.vdot(v,v).real)
        if weight<=0:break
        new=r-weight*v
        if np.linalg.norm(new)>=np.linalg.norm(r):break
        ids.append(result.ids)
        mat=np.stack([engine.compose(i) for i in ids],axis=1)
        target=engine.spec.checked(q)
        weights=np.linalg.lstsq(np.concatenate([mat.real,mat.imag]),np.concatenate([target.real,target.imag]),rcond=None)[0]
        if (weights<=0).any():ids.pop();break
        r=(target-mat@weights).astype(engine.spec.dtype)
    return tuple(ids),float(np.linalg.norm(r)),work


def gsbc_correlate(a,b):
    """Independent real circular correlations; normalized blocks remain PMFs."""
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64)
    if a.shape!=b.shape or a.ndim!=2 or a.size>16384 or not all(np.isfinite(x).all() and (x>=0).all() and np.allclose(x.sum(1),1) for x in (a,b)):raise ValueError('block PMFs')
    x=np.fft.irfft(np.fft.rfft(a,axis=1)*np.fft.rfft(b,axis=1).conj(),n=a.shape[1],axis=1)
    x=np.maximum(x,0);return x/x.sum(1,keepdims=True)

@dataclass(frozen=True)
class SparseResult:
    ids: tuple|None
    status: str
    searches: int
    sweeps: int
    score: float

class BlockFactorizer:
    """Binary SBC atoms stored as integer positions; GSBC estimates are dense PMFs."""
    def __init__(self,banks,length):
        self.length=_bounded_int(length,2,1024)
        if not 2<=len(banks)<=6:raise ValueError('factor count')
        self.banks=[];bcount=None
        for bank in banks:
            b=np.asarray(bank)
            if b.ndim!=2 or b.dtype.kind not in 'iu' or not 2<=len(b)<=4096 or not 2<=b.shape[1]<=256 or (b<0).any() or (b>=length).any() or (bcount is not None and b.shape[1]!=bcount):raise ValueError('block bank')
            bcount=b.shape[1];b=b.astype(np.uint16);b.flags.writeable=False;self.banks.append(b)
        self.banks=tuple(self.banks);self.blocks=bcount
        if self.blocks*length>16384:raise ValueError('block dimension budget')
    @property
    def nbytes(self):return sum(b.nbytes for b in self.banks)
    def positions(self,ids):
        if len(ids)!=len(self.banks):raise ValueError('factor count')
        for i,b in zip(ids,self.banks):
            if isinstance(i,(bool,np.bool_)) or not isinstance(i,(int,np.integer)) or not 0<=i<len(b):raise ValueError('factor index')
        return np.sum([b[i].astype(np.int64) for b,i in zip(self.banks,ids)],axis=0)%self.length
    def encode(self,ids):return np.eye(self.length)[self.positions(ids)]
    def _bundle(self,b,w):
        x=np.zeros((self.blocks,self.length));np.add.at(x,(np.broadcast_to(np.arange(self.blocks),b.shape),b),np.broadcast_to(w[:,None],b.shape));return x/w.sum()
    def _query(self,q):
        q=np.asarray(q,dtype=np.float64)
        if q.shape!=(self.blocks,self.length) or not np.isfinite(q).all() or (q<0).any() or not np.allclose(q.sum(1),1):raise ValueError('query PMF')
        return q
    def _scores(self,q,b,metric):
        v=q[np.arange(self.blocks),b]
        return v.min(1) if metric=='linf' else v.mean(1)
    def decode(self,q,*,threshold=.01,detection=.5,sampling=2,steps=100,seed=0,metric='linf'):
        q=self._query(q);_bounded_int(steps,1,1000);_bounded_int(seed,0,2**64-1)
        if metric not in ('linf','dot') or not np.isfinite([threshold,detection]).all() or not 0<=threshold<=1 or not 0<detection<=1:raise ValueError('BCF controls')
        _bounded_int(sampling,1,min(map(len,self.banks)))
        cell=prod(map(len,self.banks));per=sum(map(len,self.banks));limit=min(steps,cell//per)
        if limit*per*self.blocks>100_000_000:raise ValueError('BCF compute budget')
        rng=np.random.default_rng(seed);states=[self._bundle(b,np.ones(len(b))) for b in self.banks];best=0.
        for k in range(limit):
            nxt=[];ids=[];conf=[];ties=[]
            for i,b in enumerate(self.banks):
                cue=q
                for j,state in enumerate(states):
                    if j!=i:cue=gsbc_correlate(cue,state)
                a=self._scores(cue,b,metric);top=int(np.argmax(a));ids.append(top);conf.append(a[top]);ties.append(np.count_nonzero(np.isclose(a,a[top],atol=1e-10,rtol=0))!=1)
                w=np.where(a>=threshold,a,0.)
                if not w.any():w[rng.choice(len(b),sampling,replace=False)]=1/sampling
                nxt.append(self._bundle(b,w))
            score=1-float(np.max(np.abs(q-self.encode(ids))));best=max(best,score)
            if not any(ties) and min(conf)>=detection and score>=detection:
                return SparseResult(tuple(ids),'detected',per*(k+1),k+1,score)
            states=nxt
        return SparseResult(None,'budget',per*limit,limit,best)
    def exhaustive(self,q,max_candidates=65536):
        q=self._query(q);_bounded_int(max_candidates,1,65536);n=prod(map(len,self.banks))
        if n>max_candidates or n*self.blocks>16_777_216:raise ValueError('cartesian budget')
        it=product(*(range(len(b)) for b in self.banks));best=-1.;winner=None;ties=0
        while batch:=list(islice(it,256)):
            ids=np.array(batch);p=sum(b[ids[:,i]].astype(np.int64) for i,b in enumerate(self.banks))%self.length
            a=self._scores(q,p,'linf')
            for idx,s in enumerate(a):
                if s>best+1e-10:best=float(s);winner=batch[idx];ties=1
                elif abs(s-best)<=1e-10:ties+=1
        return SparseResult(winner if ties==1 else None,'exhaustive' if ties==1 else 'ambiguous',n,0,best)


def graph_rank_features(adjacency, *, centrality='pagerank'):
    """Tie-aware GraphHD variant: equal centralities share a rank, no ID tie leak."""
    a=np.asarray(adjacency)
    if a.ndim!=2 or a.shape[0]!=a.shape[1] or not 1<=len(a)<=256 or not np.isin(a,[0,1]).all() or not np.array_equal(a,a.T) or np.diag(a).any():raise ValueError('simple undirected graph')
    n=len(a);degree=a.sum(1);p=np.full(n,1/n)
    if centrality=='pagerank':
        transition=np.divide(a,degree[:,None],out=np.full((n,n),1/n),where=degree[:,None]!=0)
        for _ in range(100):
            new=.15/n+.85*(p@transition)
            if np.max(abs(new-p))<1e-12:break
            p=new
        vals=np.round(new,10)
    elif centrality=='degree':vals=degree
    else:raise ValueError('centrality')
    ranks={v:i for i,v in enumerate(sorted(set(vals),reverse=True))};r=[ranks[v] for v in vals];counts={}
    for i,j in zip(*np.triu(a,1).nonzero()):
        k=tuple(sorted((r[i],r[j])));counts[k]=counts.get(k,0)+1
    return counts


def rank_hv(features, dimension, seed):
    """Domain separated rank atoms and bound endpoint counts using MAP."""
    _bounded_int(dimension,16,8192);_bounded_int(seed,0,2**64-1)
    if len(features)>32640 or any(type(n) is not int or n<=0 for n in features.values()) or sum(features.values())>32640:raise ValueError('rank feature budget')
    x=np.zeros(dimension,np.int32);atoms={}
    for (i,j),n in sorted(features.items()):
        if not 0<=i<=j<256 or type(n) is not int or not 0<n<=32640:raise ValueError('rank feature')
        for k in (i,j):
            if k not in atoms:atoms[k]=np.random.default_rng(np.random.SeedSequence([seed,k])).choice([-1,1],dimension).astype(np.int32)
        # domain-separate second endpoint, avoiding collapse of self-rank pairs
        x+=n*atoms[i]*np.roll(atoms[j],1)
    return x


OPS=('shift_left','shift_right','reverse','recolor')
def execute_program(scene,program):
    """Finite object DSL: 1D non-overlapping (position,color) objects on 16 cells."""
    scene=tuple(scene);program=tuple(program)
    if not 1<=len(scene)<=16 or not 1<=len(program)<=3 or any(op not in OPS for op in program) or len({p for p,c in scene})!=len(scene) or any(type(p) is not int or type(c) is not int or not 0<=p<16 or not 1<=c<=3 for p,c in scene):raise ValueError('scene/program')
    for op in program:
        if op=='shift_left':scene=tuple((p-1,c) for p,c in scene)
        elif op=='shift_right':scene=tuple((p+1,c) for p,c in scene)
        elif op=='reverse':scene=tuple((15-p,c) for p,c in scene)
        else:scene=tuple((p,c%3+1) for p,c in scene)
        if any(not 0<=p<16 for p,c in scene):return None
    return tuple(sorted(scene))


def synthesize(examples, *, spec=None, depth=2, budget=20, seed=0):
    """Rank same finite program universe with VSA or deterministic order;
    exact train-example checking only; held-out execution is separate.
    """
    _bounded_int(depth,1,3);_bounded_int(budget,1,84);_bounded_int(seed,0,2**64-1)
    if not 1<=len(examples)<=16:raise ValueError('examples')
    # Validate both examples before ranker allocates its banks.
    for x,y in examples:execute_program(x,('recolor',));execute_program(y,('recolor',))
    programs=[p for d in range(1,depth+1) for p in product(OPS,repeat=d)]
    if spec is not None:
        if not isinstance(spec,Spec) or spec.family!='FHRR':raise ValueError('FHRR scene ranker')
        rng=np.random.default_rng(seed);pos=np.exp(1j*rng.uniform(-np.pi,np.pi,(16,spec.dimension))).astype(spec.dtype);color=np.exp(1j*rng.uniform(-np.pi,np.pi,(3,spec.dimension))).astype(spec.dtype)
        def enc(s):return sum((spec.bind(pos[p],color[c-1]) for p,c in s),np.zeros(spec.dimension,spec.dtype))
        targets=[enc(y) for _,y in examples]
        def rank(p):
            pred=[execute_program(x,p) for x,_ in examples]
            if any(x is None for x in pred):return -2.
            return sum(spec.similarity(enc(a),b) for a,b in zip(pred,targets))/len(examples)
        programs=sorted(programs,key=lambda p:(-rank(p),len(p),p))
    for i,p in enumerate(programs[:budget],1):
        if all(execute_program(x,p)==tuple(sorted(y)) for x,y in examples):return p,i,len(programs) if spec is not None else 0
    return None,min(budget,len(programs)),len(programs) if spec is not None else 0

class GraphFingerprintIndex:
    """Collision-resolved graph *feature* identity, not graph isomorphism.
    Dynamic storage and exact feature comparison; zero-bit fingerprint is a
    deliberately colliding valid control. No authorization or canonical store.
    """
    def __init__(self,dimension=128,seed=0,bits=16):
        self.dimension=_bounded_int(dimension,16,8192); self.seed=_bounded_int(seed,0,2**64-1);self.bits=_bounded_int(bits,0,min(64,dimension));self.rows={};self.buckets={}
    def _key(self,features):
        v=rank_hv(features,self.dimension,self.seed);return np.packbits(v[:self.bits]>=0).tobytes(),tuple(sorted(features.items()))
    def insert(self,identity,features):
        if not isinstance(identity,str) or not 0<len(identity)<=128 or identity in self.rows or len(self.rows)>=4096:raise ValueError('index identity/budget')
        h,f=self._key(features);self.rows[identity]=(h,f);self.buckets.setdefault(h,set()).add(identity)
    def remove(self,identity):
        h,_=self.rows.pop(identity);self.buckets[h].remove(identity)
        if not self.buckets[h]:del self.buckets[h]
    def lookup(self,features):
        h,f=self._key(features);return tuple(sorted(i for i in self.buckets.get(h,()) if self.rows[i][1]==f))


def transfer_rule(engine, path_relations, consequent, train_starts, *, min_support=2):
    """Derive observed 2-hop implication with exact training witnesses only.
    A witnessed rule is a hypothesis, never a universal assertion. An entirely
    separate current graph is required for validation, even for a known rule.
    """
    _bounded_int(min_support,1,4096)
    if len(path_relations)!=2 or consequent not in engine.relations or any(x not in engine.relations for x in path_relations) or len(train_starts)>4096:raise ValueError('rule controls')
    positives=[];opportunities=0
    for s in sorted(set(train_starts)):
        direct={e.target:e for e in engine.adj.get(s,()) if e.relation==consequent}
        for e in engine.adj.get(s,()):
            if e.relation!=path_relations[0]:continue
            for f in engine.adj.get(e.target,()):
                if f.relation!=path_relations[1]:continue
                opportunities+=1
                if opportunities>4096:raise OverflowError('rule budget')
                if f.target in direct:positives.append((s,e.witness,f.witness,direct[f.target].witness))
    support=len({x[0] for x in positives})
    if support<min_support or len(positives)!=opportunities:return None
    return tuple(positives)


def verified_rule_paths(engine, start, antecedent, consequent, *, current_snapshot, canonical_edges, k=64):
    """HDC ranking then exact path+consequent check; incomplete rank budget explicit."""
    if current_snapshot!=engine.snapshot:raise ValueError('stale snapshot')
    if len(antecedent)!=2 or consequent not in engine.relations:raise ValueError('rule controls')
    from .hdc_resonator_frontier import Edge
    canonical=tuple(islice(canonical_edges,4097))
    if len(canonical)>4096 or any(not isinstance(e,Edge) for e in canonical) or len({e.witness for e in canonical})!=len(canonical):raise ValueError('canonical witness budget')
    direct={e.target:e.witness for e in canonical if e.source==start and e.relation==consequent}
    result=[]
    for _,path in engine.candidates(start,engine.encode(antecedent),2,k=k):
        v=engine.verify(path,start=start,relations=antecedent,current_snapshot=current_snapshot,canonical_edges=canonical)
        if v is not None and v[0] in direct:result.append((v[0],v[1],direct[v[0]]))
    return tuple(result)


def exact_equal_pair(engine,q,*,max_pairs=65536,tolerance=1e-5):
    """Independent bounded joint oracle for two equal-weight, distinct atoms.
    Unlike greedy cleanup, this handles a tie between both correct factors.
    Returns no answer for equal residuals or residual above absolute tolerance.
    """
    from itertools import combinations
    q=engine.spec.checked(q);_bounded_int(max_pairs,1,65536)
    if not np.isfinite(tolerance) or not 0<=tolerance<=1:raise ValueError('tolerance')
    n=prod(map(len,engine.banks));pairs=n*(n-1)//2
    if pairs>max_pairs or pairs*engine.spec.dimension>50_000_000:raise ValueError('joint oracle budget')
    candidates=list(product(*(range(len(b)) for b in engine.banks)))
    atoms=np.stack([engine.compose(ids) for ids in candidates]);best=np.inf;winner=None;ties=0
    for i,j in combinations(range(n),2):
        residual=float(np.linalg.norm(q-atoms[i]-atoms[j]))
        if residual<best-1e-6:best=residual;winner=(candidates[i],candidates[j]);ties=1
        elif abs(residual-best)<=1e-6:ties+=1
    return (winner if ties==1 and best<=tolerance else None),best,pairs
