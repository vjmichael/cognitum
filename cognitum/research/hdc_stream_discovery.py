"""Research-only streaming clustering, count memories and density-distance scoring.
Independent bounded references; not full original-paper reproductions.
"""
import numpy as np
import networkx as nx

_POPCOUNT=np.array([i.bit_count() for i in range(256)],dtype=np.uint8)

MAX_ELEMENTS=8_000_000

def matrix(x, binary=False):
    a=np.asarray(x)
    if a.ndim!=2 or min(a.shape)<1 or a.size>MAX_ELEMENTS or not np.isfinite(a).all():raise ValueError('invalid or excessive matrix')
    if binary and not np.isin(a,[0,1]).all():raise ValueError('expected bits')
    return a.astype(np.uint8 if binary else np.float64,copy=False)

def hamming(x,y):
    x=matrix(x,True);y=matrix(y,True)
    if x.shape[1]!=y.shape[1] or len(x)*len(y)>MAX_ELEMENTS:raise ValueError('distance bound/shape')
    a=x.astype(np.float64);b=y.astype(np.float64)
    return (a.sum(1)[:,None]+b.sum(1)[None,:]-2*a@b.T)/x.shape[1]

def packed_hamming(query,bank,dimension):
    """Byte-packed XOR/popcount; reject nonzero padding and oversized outputs."""
    q=np.asarray(query);b=np.asarray(bank)
    if type(dimension)!=int or dimension<1 or q.ndim!=2 or b.ndim!=2 or min(len(q),len(b))<1 or q.dtype!=np.uint8 or b.dtype!=np.uint8 or q.shape[1]!=b.shape[1] or q.shape[1]!=(dimension+7)//8:raise ValueError('invalid packed shape')
    if len(q)*len(b)*q.shape[1]>MAX_ELEMENTS:raise ValueError('packed distance bound')
    if dimension%8:
        mask=(255 << (dimension%8))&255
        if np.any(q[:,-1]&mask) or np.any(b[:,-1]&mask):raise ValueError('nonzero padding')
    return _POPCOUNT[q[:,None,:]^b[None,:,:]].sum(2)/dimension

class ThermometerProjection:
    def __init__(self,features,projection=64,levels=8,seed=0):
        if min(features,projection,levels)<1 or features*projection>MAX_ELEMENTS or projection*levels>MAX_ELEMENTS:raise ValueError('invalid encoder')
        self.R=np.random.default_rng(seed).normal(size=(features,projection))/np.sqrt(features);self.levels=levels
    def fit(self,x):
        x=matrix(x);self.mean=x.mean(0);self.scale=np.maximum(x.std(0),1e-8)
        y=((x-self.mean)/self.scale)@self.R;self.lo=y.min(0);self.span=np.maximum(y.max(0)-self.lo,1e-8);return self
    def encode(self,x):
        x=matrix(x);p=((x-self.mean)/self.scale)@self.R
        if len(x)*self.R.shape[1]*self.levels>MAX_ELEMENTS:raise ValueError('encoding bound')
        q=np.rint(np.clip((p-self.lo)/self.span,0,1)*self.levels).astype(int)
        return (q[:,:,None]>np.arange(self.levels)).reshape(len(x),-1).astype(np.uint8)
    @property
    def nbytes(self):return sum(a.nbytes for a in (self.R,self.mean,self.scale,self.lo,self.span))

class IDLevel:
    """Progressive independent random flips (not disjoint flips); train-only range."""
    def __init__(self,features,dimension=512,levels=16,seed=0):
        if min(features,dimension,levels)<1 or levels>dimension or (features+levels)*dimension>MAX_ELEMENTS:raise ValueError('invalid encoder')
        rng=np.random.default_rng(seed);self.ids=rng.integers(0,2,(features,dimension),dtype=np.uint8);self.codes=rng.integers(0,2,(levels,dimension),dtype=np.uint8)
        for i in range(1,levels):
            self.codes[i]=self.codes[i-1];self.codes[i,rng.choice(dimension,dimension//levels,replace=False)]^=1
    def fit(self,x):
        x=matrix(x);self.lo=x.min(0);self.span=np.maximum(x.max(0)-self.lo,1e-8);return self
    def encode(self,x):
        x=matrix(x);q=np.minimum((np.clip((x-self.lo)/self.span,0,1)*len(self.codes)).astype(int),len(self.codes)-1)
        if len(x)*self.ids.shape[1]>MAX_ELEMENTS:raise ValueError('encoding bound')
        a=np.zeros((len(x),self.ids.shape[1]),dtype=np.int32)
        for j,key in enumerate(self.ids):a+=self.codes[q[:,j]]^key
        return (a>len(self.ids)/2).astype(np.uint8)
    @property
    def nbytes(self):return sum(a.nbytes for a in (self.ids,self.codes,self.lo,self.span))

class IncrementalLouvain:
    """Frozen majority representatives per bucket; bounded novelty allocation."""
    def __init__(self,k=8,threshold=.25,capacity=128,seed=0):
        if k<1 or capacity<1 or not 0<=threshold<=1:raise ValueError('parameters')
        self.k=k;self.threshold=threshold;self.capacity=capacity;self.seed=seed;self.reps=[];self.buckets=[]
    def fit(self,x,buckets=None):
        x=matrix(x,True);b=np.zeros(len(x),int) if buckets is None else np.asarray(buckets)
        if b.shape!=(len(x),):raise ValueError('bucket shape')
        self.reps=[];self.buckets=[];self.dimension=x.shape[1];labels=np.full(len(x),-1,int)
        for key in np.unique(b):
            idx=np.flatnonzero(b==key);d=hamming(x[idx],x[idx]);g=nx.Graph();g.add_nodes_from(range(len(idx)))
            for i,row in enumerate(d):
                neighbors=[j for j in np.argsort(row,kind='stable') if j!=i][:self.k]
                for j in neighbors:
                    if row[j]<1:g.add_edge(i,int(j),weight=1-float(row[j]))
            groups=nx.community.louvain_communities(g,seed=self.seed) if g.number_of_edges() else [{i} for i in g]
            for c in sorted(groups,key=min):
                if len(self.reps)>=self.capacity:raise ValueError('bootstrap exceeds capacity')
                ids=idx[sorted(c)];labels[ids]=len(self.reps);self.reps.append(np.packbits(x[ids].mean(0)>=.5,bitorder="little"));self.buckets.append(key)
        return labels
    def assign(self,h,bucket=0):
        h=matrix(np.asarray(h)[None],True)[0]
        if len(h)!=self.dimension:raise ValueError("dimension mismatch")
        h=np.packbits(h,bitorder="little");ids=[i for i,b in enumerate(self.buckets) if b==bucket]
        if ids:
            ds=packed_hamming(h[None],np.asarray([self.reps[i] for i in ids]),self.dimension)[0];j=int(ds.argmin())
            if ds[j]<=self.threshold:return ids[j]
        if len(self.reps)>=self.capacity:return -1
        self.reps.append(h.copy());self.buckets.append(bucket);return len(self.reps)-1
    @property
    def nbytes(self):return sum(r.nbytes for r in self.reps)+8*len(self.buckets)

class CountMemory:
    def __init__(self,h,score):
        h=matrix(np.asarray(h)[None],True)[0];
        if not np.isfinite(score):raise ValueError("invalid score")
        self.counts=h.astype(np.uint64);self.n=1;self.total=float(score)
    def distance(self,h):
        h=matrix(np.asarray(h)[None],True)[0]
        if h.shape!=self.counts.shape:raise ValueError("dimension mismatch")
        p=self.counts.astype(float)/self.n
        return float(np.mean(np.where(h,1-p,p)))
    def radius(self):
        p=self.counts.astype(float)/self.n;return float(np.mean(2*p*(1-p)))
    def update(self,h,score):
        h=matrix(np.asarray(h)[None],True)[0]
        if h.shape!=self.counts.shape or self.n>=2**53-1 or not np.isfinite(score) or not np.isfinite(self.total+float(score)):raise ValueError('invalid update')
        self.counts+=h;self.n+=1;self.total+=float(score)
    @property
    def nbytes(self):return self.counts.nbytes+16

class OpenWorld:
    """WaferHDC-inspired two-stage monitor, stable IDs, explicit overflow refusal."""
    def __init__(self,normal,calibration,prototypes=3,neighbors=3,capacity=32,match=.16,recurrence=3,coherence=.18,seed=0):
        a=matrix(normal,True);b=matrix(calibration,True)
        if not 1<=prototypes<=len(a) or not 1<=neighbors<=len(a) or capacity<1 or recurrence<2 or not 0<=match<=1 or not 0<=coherence<=1:raise ValueError('parameters')
        self.ref=a.copy();self.neighbors=neighbors;self.capacity=capacity;self.match=match;self.recurrence=recurrence;self.coherence=coherence;self.mem=[];self.persistent=[]
        p=a[np.random.default_rng(seed).choice(len(a),prototypes,replace=False)].copy()
        for _ in range(15):
            labels=hamming(a,p).argmin(1);q=p.copy()
            for j in range(len(p)):
                if np.any(labels==j):q[j]=(a[labels==j].mean(0)>=.5)
            if np.array_equal(p,q):break
            p=q
        self.prototypes=p;self.threshold=float(np.quantile(self.score(b),.95))
    def score(self,x):
        return np.maximum(hamming(x,self.prototypes).min(1),np.sort(hamming(x,self.ref),axis=1)[:,:self.neighbors].mean(1))
    def observe(self,h):
        score=float(self.score(np.asarray(h)[None])[0])
        if score<=self.threshold:return 0,False,score
        for phase in (True,False):
            ids=[i for i,p in enumerate(self.persistent) if p==phase]
            if ids:
                ds=[self.mem[i].distance(h) for i in ids];j=ids[int(np.argmin(ds))]
                if min(ds)<=self.match:
                    m=self.mem[j];m.update(h,score)
                    if m.n>=self.recurrence and m.radius()<=self.coherence and m.total/m.n>self.threshold:self.persistent[j]=True
                    return j+1,self.persistent[j],score
        if len(self.mem)>=self.capacity:return -1,False,score
        self.mem.append(CountMemory(h,score));self.persistent.append(False);return len(self.mem),False,score
    @property
    def nbytes(self):return self.ref.nbytes+self.prototypes.nbytes+sum(m.nbytes+1 for m in self.mem)

class DensityDistance:
    """Inductive extension of paper's transductive density-distance score.
    Strictly higher density, explicit max-distance fallback and rho floor 1.
    """
    def __init__(self,binary=False):self.binary=binary
    def distances(self,x,y):
        if self.binary:return hamming(x,y)
        x=matrix(x);y=matrix(y)
        if len(x)*len(y)>MAX_ELEMENTS:raise ValueError('distance bound')
        x=x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12);y=y/np.maximum(np.linalg.norm(y,axis=1,keepdims=True),1e-12)
        return np.sqrt(np.maximum(0,(x*x).sum(1)[:,None]+(y*y).sum(1)[None,:]-2*x@y.T))
    def fit(self,x):
        self.ref=matrix(x,self.binary).copy();n=len(self.ref)
        if n<2:raise ValueError('need two references')
        d=self.distances(self.ref,self.ref);self.cutoff=float(np.quantile(d[np.triu_indices(n,1)],.1));np.fill_diagonal(d,np.inf)
        self.rho=(d<self.cutoff).sum(1);return self
    def components(self,x):
        d=self.distances(x,self.ref);rho=(d<self.cutoff).sum(1);higher=self.rho[None,:]>rho[:,None];delta=np.min(np.where(higher,d,np.inf),1);delta=np.where(np.isfinite(delta),delta,d.max(1));return rho,delta
    def score(self,x):
        rho,d=self.components(x);return d/np.maximum(rho,1)
