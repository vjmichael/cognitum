"""Research-only label-conditional uncertainty and bounded visual discovery.
Independent HDUQ-HAR/ImageHD-inspired CPU references; no production routing.
"""
import numpy as np
from dataclasses import dataclass


def finite(x, ndim):
    a=np.asarray(x,dtype=np.float64)
    if a.ndim!=ndim or not a.size or not np.isfinite(a).all(): raise ValueError('invalid finite input')
    return a


def bipolar(x, ndim):
    a=np.asarray(x)
    if a.ndim!=ndim or not a.size or not np.isin(a,[-1,1]).all(): raise ValueError('bipolar input required')
    return a.astype(np.int8)


def scores(windows, prototypes):
    """Candidate-specific distance, rival gap and within-window vote dispersion.
    windows: N x grams x D; prototypes: C x D. Label-independent inputs.
    """
    w=bipolar(windows,3); p=bipolar(prototypes,2)
    if w.shape[2]!=p.shape[1] or len(p)<2: raise ValueError('shape/classes')
    votes=w.astype(np.float64)@p.T/p.shape[1]
    s=votes.mean(axis=1)
    rivals=np.stack([np.max(np.delete(s,j,axis=1),axis=1) for j in range(len(p))],axis=1)
    return np.stack([(1-s)/2,(1+rivals-s)/3,votes.std(axis=1)/2],axis=-1)


def nonconformity(signals, weights=(1.,1.,1.)):
    a=finite(signals,3); w=finite(weights,1)
    if a.shape[-1]!=3 or w.shape!=(3,) or (w<0).any() or w.sum()==0: raise ValueError('weights')
    return a@ (w/w.sum())


class Mondrian:
    """Split conformal; group-max option treats groups as exchangeable units.
    Calibration scores only; no fitting or score tuning on calibration/test.
    Missing classes get infinite cutoff (conservative, not informative).
    """
    def __init__(self, alpha=.1):
        if not np.isfinite(alpha) or not 0<alpha<1: raise ValueError('alpha')
        self.alpha=float(alpha)
    def fit(self, s, y, groups=None):
        s=finite(s,2); y=np.asarray(y)
        if y.shape!=(len(s),) or y.dtype.kind not in 'iu' or (y<0).any() or (y>=s.shape[1]).any(): raise ValueError('labels')
        g=None if groups is None else np.asarray(groups)
        if g is not None and g.shape!=y.shape: raise ValueError('groups')
        cut=[]; counts=[]
        for k in range(s.shape[1]):
            a=s[y==k,k]
            if g is not None:
                gs=g[y==k]; a=np.array([a[gs==q].max() for q in np.unique(gs)])
            n=len(a); rank=int(np.ceil((n+1)*(1-self.alpha)))
            cut.append(np.sort(a)[rank-1] if 1<=rank<=n else np.inf); counts.append(n)
        self.cutoffs=np.array(cut); self.counts=np.array(counts,dtype=np.int64); return self
    def predict(self,s):
        a=finite(s,2)
        if a.shape[1]!=len(self.cutoffs): raise ValueError('class count')
        return a<=self.cutoffs

class LevelEncoder:
    """Fixed binary position/ordered-level XOR and majority. Packed tables."""
    def __init__(self, features, dimension, levels=16, seed=0):
        if not (1<=features<=4096 and 8<=dimension<=16384 and 2<=levels<=256 and features*dimension<=8_000_000): raise ValueError('bounds')
        self.features=features; self.dimension=dimension; self.levels=levels
        rng=np.random.default_rng(seed); p=rng.integers(0,2,(features,dimension),dtype=np.uint8)
        start=rng.integers(0,2,dimension,dtype=np.uint8); order=rng.permutation(dimension); ls=[]
        for i in range(levels):
            a=start.copy(); a[order[:round(i*dimension/2/(levels-1))]]^=1; ls.append(a)
        self.p=np.packbits(p,axis=1); self.l=np.packbits(np.array(ls),axis=1)
    @property
    def numeric_bytes(self): return self.p.nbytes+self.l.nbytes
    def encode(self,x):
        x=np.asarray(x)
        if x.shape!=(self.features,) or x.dtype.kind not in 'iu' or (x<0).any() or (x>=self.levels).any(): raise ValueError('quantized levels')
        bound=np.bitwise_xor(self.p,self.l[x]); votes=np.unpackbits(bound,axis=1,count=self.dimension).sum(axis=0)
        return np.packbits((votes*2>=self.features).astype(np.uint8))


def hamming(a,b,dimension):
    a=np.asarray(a); b=np.asarray(b)
    if a.dtype!=np.uint8 or b.dtype!=np.uint8 or a.shape[-1]!=(dimension+7)//8 or b.shape[-1]!=a.shape[-1]: raise ValueError('packed shape')
    return np.unpackbits(a^b,axis=-1,count=dimension).sum(axis=-1)


def consolidate(bank,target,dimension,rng,top_m=3,iterations=2,weights=None):
    """Top-M farthest seeding + fixed binary majority refinement.
    Return packed centroids and source assignments. Empty groups are reseeded
    from an existing centroid, and ties preserve current center bits.
    """
    a=np.asarray(bank)
    if a.ndim!=2 or not 1<=target<=len(a)<=1024 or not 1<=top_m<=1024 or not 0<=iterations<=32: raise ValueError('merge bounds')
    hamming(a,a,dimension)
    w=np.ones(len(a)) if weights is None else finite(weights,1)
    if w.shape!=(len(a),) or (w<=0).any(): raise ValueError('weights')
    chosen=[int(rng.integers(len(a)))]; distance=hamming(a,a[chosen[0]],dimension).astype(float)
    for _ in range(1,target):
        distance[chosen]=-1; candidates=np.argsort(-distance,kind='stable')[:min(top_m,len(a)-len(chosen))]
        j=int(rng.choice(candidates)); chosen.append(j); distance=np.minimum(distance,hamming(a,a[j],dimension))
    centers=a[chosen].copy(); bits=np.unpackbits(a,axis=1,count=dimension)
    for _ in range(iterations):
        labels=np.argmin(hamming(a[:,None,:],centers[None,:,:],dimension),axis=1)
        for j in range(target):
            mask=labels==j
            if mask.any():
                vote=w[mask]@bits[mask]; half=w[mask].sum()/2; old=np.unpackbits(centers[j],count=dimension)
                centers[j]=np.packbits(np.where(vote==half,old,vote>half).astype(np.uint8))
    labels=np.argmin(hamming(a[:,None,:],centers[None,:,:],dimension),axis=1)
    return centers,labels


class VisualBank:
    """Unsupervised single pass; preallocated packed bank + bounded scalar state.
    At capacity, merge before inserting, not periodic overshoot. Running binary
    update uses stochastic bit replacement, an explicit alternative to the
    paper's underspecified two-HV majority tie convention.
    """
    def __init__(self,dimension,capacity,seed=0,beta=2.,alpha=.1,novelty_floor=.60,mode='merge'):
        if not 8<=dimension<=16384 or not 2<=capacity<=128 or not 0<alpha<=1 or not 0<=beta<=10 or not 0<=novelty_floor<=1 or mode not in ('merge','replace','fixed'): raise ValueError('bank bounds')
        self.dimension=dimension; self.capacity=capacity; self.rng=np.random.default_rng(seed); self.beta=beta; self.alpha=alpha; self.floor=novelty_floor; self.mode=mode
        self.bank=np.zeros((capacity,(dimension+7)//8),np.uint8); self.mean=np.zeros(capacity); self.var=np.zeros(capacity); self.count=np.zeros(capacity,np.int64); self.n=0; self.merges=0
    @property
    def numeric_bytes(self): return self.bank.nbytes+self.mean.nbytes+self.var.nbytes+self.count.nbytes
    def predict(self,q):
        q=np.asarray(q)
        hamming(q,q,self.dimension)
        if q.ndim!=1: raise ValueError('query')
        if not self.n: return -1,0.
        s=1-hamming(self.bank[:self.n],q,self.dimension)/self.dimension; j=int(s.argmax()); return j,float(s[j])
    def observe(self,q):
        q=np.asarray(q); j,s=self.predict(q)
        novel=j<0 or s<max(self.floor,self.mean[j]-self.beta*np.sqrt(self.var[j]))
        if novel and self.n==self.capacity:
            if self.mode=='merge':
                c,lab=consolidate(self.bank[:self.n],self.capacity-1,self.dimension,self.rng,weights=self.count[:self.n]);
                counts=np.bincount(lab,weights=self.count[:self.n],minlength=len(c)); self.bank[:len(c)]=c; self.count[:len(c)]=np.maximum(1,counts).astype(np.int64); self.mean[:len(c)]=self.floor; self.var[:len(c)]=.01; self.n=len(c); self.merges+=1
            elif self.mode=='replace':
                k=int(self.count[:self.n].argmin()); self.bank[k]=q; self.count[k]=1; self.mean[k]=self.floor; self.var[k]=.01; return j,s,True
            else: novel=False
        if novel:
            k=self.n; self.n+=1; self.bank[k]=q; self.count[k]=1; self.mean[k]=self.floor; self.var[k]=.01
        else:
            # EMA statistics and stochastic bounded binary bundling.
            delta=s-self.mean[j]; self.mean[j]+=self.alpha*delta; self.var[j]=(1-self.alpha)*(self.var[j]+self.alpha*delta*delta)
            mask=np.packbits(self.rng.random(self.dimension)<self.alpha); self.bank[j]=(self.bank[j]&~mask)|(q&mask); self.count[j]+=1
        return j,s,novel
