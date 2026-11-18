"""Research-only bounded extensions; no canonical routing or author parity claim."""
import numpy as np
from .hdc_stream_discovery import (IncrementalLouvain, DensityDistance, OpenWorld,
                                  matrix, packed_hamming, hamming, MAX_ELEMENTS)

class CalibratedLouvain(IncrementalLouvain):
    """Frozen bootstrap prototypes; calibrate on separate unlabeled known stream.

    Novel allocation does not mutate the thresholds or old representatives.
    """
    def fit(self,x,buckets=None):
        self.thresholds={}
        return super().fit(x,buckets)
    def calibrate(self,x,buckets=None,quantile=.95):
        x=matrix(x,True); b=np.zeros(len(x),int) if buckets is None else np.asarray(buckets)
        if x.shape[1]!=self.dimension or b.shape!=(len(x),) or not 0<=quantile<=1:raise ValueError('calibration parameters')
        thresholds={}
        for key in np.unique(b):
            ids=[i for i,k in enumerate(self.buckets) if k==key]
            if not ids:raise ValueError('unseen calibration bucket')
            d=packed_hamming(np.packbits(x[b==key],axis=1,bitorder='little'),np.asarray([self.reps[i] for i in ids]),self.dimension)
            thresholds[key]=float(np.quantile(d.min(1),quantile,method='higher'))
        self.thresholds=thresholds
        return self
    def assign(self,h,bucket=0):
        # avoid mutating base threshold, including on a failed call
        h=matrix(np.asarray(h)[None],True)[0]
        if len(h)!=self.dimension:raise ValueError('dimension mismatch')
        p=np.packbits(h,bitorder='little');ids=[i for i,b in enumerate(self.buckets) if b==bucket]
        if ids:
            ds=packed_hamming(p[None],np.asarray([self.reps[i] for i in ids]),self.dimension)[0];i=int(ds.argmin())
            if ds[i]<=self.thresholds.get(bucket,self.threshold):return ids[i]
        if len(self.reps)>=self.capacity:return -1
        self.reps.append(p);self.buckets.append(bucket);return len(self.reps)-1
    @property
    def nbytes(self):return super().nbytes+16*len(self.thresholds)

class PackedDensity(DensityDistance):
    """Same scores as binary DensityDistance; store exact bit-packed bank.
    Training still uses a dense distance matrix; storage is not peak RAM.
    """
    def __init__(self):super().__init__(True)
    def fit(self,x):
        x=matrix(x,True);super().fit(x);self.dimension=x.shape[1];self.ref=np.packbits(self.ref,axis=1,bitorder='little');return self
    def components(self,x):
        x=matrix(x,True)
        if x.shape[1]!=self.dimension:raise ValueError('dimension mismatch')
        # bound XOR tensor in blocks; reference density remains fixed
        width=self.ref.shape[1];batch=max(1,MAX_ELEMENTS//(len(self.ref)*width));parts=[]
        for start in range(0,len(x),batch):
            q=np.packbits(x[start:start+batch],axis=1,bitorder='little');d=packed_hamming(q,self.ref,self.dimension)
            rho=(d<self.cutoff).sum(1);delta=np.min(np.where(self.rho[None,:]>rho[:,None],d,np.inf),1);delta=np.where(np.isfinite(delta),delta,d.max(1));parts.append((rho,delta))
        return np.concatenate([p[0] for p in parts]),np.concatenate([p[1] for p in parts])
    @property
    def nbytes(self):return self.ref.nbytes+self.rho.nbytes+16

class BoundedCount:
    """Exact counts until bounded aging; after aging these are effective counts.
    Round proportional count rescaling at the cap, scale score sum consistently. No raw examples stored.
    """
    def __init__(self,h,score,limit):
        self.counts=np.asarray(h,dtype=np.uint16).copy();self.n=1;self.total=float(score);self.limit=limit
    def distance(self,h):
        p=self.counts.astype(float)/self.n;return float(np.mean(np.where(h,1-p,p)))
    def radius(self):
        p=self.counts.astype(float)/self.n;return float(np.mean(2*p*(1-p)))
    def update(self,h,score):
        if self.n==self.limit:
            n=self.n//2;self.counts=((self.counts.astype(np.uint64)*n+self.n//2)//self.n).astype(np.uint16);self.total*=n/self.n;self.n=n
        self.counts+=h.astype(np.uint16);self.n+=1;self.total+=float(score)

class BoundedWorld:
    """Packed normal-bank and bounded count memories; monotonic identity IDs.
    Expiry is checked only when novelty exhausts capacity. 'temporary' protects
    established clusters, 'lru' permits forgetting any dormant cluster.
    """
    def __init__(self,normal,calibration,*,capacity=8,policy='refuse',idle=40,limit=256,match=.13,coherence=.18,recurrence=3,seed=0):
        if policy not in ('refuse','temporary','lru') or type(capacity)!=int or capacity<1 or type(idle)!=int or idle<1 or type(limit)!=int or not 4<=limit<=65535 or not 2<=recurrence<=limit//2 or not 0<=match<=1 or not 0<=coherence<=1:raise ValueError('parameters')
        # reuse only bootstrap normal fitter, release dense state
        orig=OpenWorld(normal,calibration,capacity=capacity,match=match,coherence=coherence,recurrence=recurrence,seed=seed)
        self.dimension=orig.ref.shape[1];self.ref=np.packbits(orig.ref,axis=1,bitorder='little');self.prototypes=np.packbits(orig.prototypes,axis=1,bitorder='little');self.neighbors=orig.neighbors;self.threshold=orig.threshold
        self.capacity=capacity;self.policy=policy;self.idle=idle;self.limit=limit;self.match=match;self.coherence=coherence;self.recurrence=recurrence;self.slots={};self.sequence=0;self.next_id=1;self.evictions=0
    def score(self,h):
        p=np.packbits(h[None],axis=1,bitorder='little');a=packed_hamming(p,self.prototypes,self.dimension)[0];b=packed_hamming(p,self.ref,self.dimension)[0];return float(max(a.min(),np.sort(b)[:self.neighbors].mean()))
    def observe(self,h):
        h=matrix(np.asarray(h)[None],True)[0]
        if len(h)!=self.dimension:raise ValueError('dimension mismatch')
        score=self.score(h);self.sequence+=1
        if score<=self.threshold:return 0,False,score
        for phase in (True,False):
            keys=[k for k,(_,persistent,_) in self.slots.items() if persistent==phase]
            if keys:
                ds=[self.slots[k][0].distance(h) for k in keys];j=int(np.argmin(ds));k=keys[j]
                if ds[j]<=self.match:
                    m,p,_=self.slots[k];m.update(h,score);p=p or (m.n>=self.recurrence and m.radius()<=self.coherence and m.total/m.n>self.threshold);self.slots[k]=(m,p,self.sequence);return k,p,score
        if len(self.slots)==self.capacity:
            eligible=[k for k,(_,p,last) in self.slots.items() if self.policy!='refuse' and (self.policy=='lru' or not p) and self.sequence-last>=self.idle]
            if not eligible:return -1,False,score
            del self.slots[min(eligible,key=lambda k:(self.slots[k][2],k))];self.evictions+=1
        k=self.next_id;self.next_id+=1;self.slots[k]=(BoundedCount(h,score,self.limit),False,self.sequence);return k,False,score
    @property
    def nbytes(self):return self.ref.nbytes+self.prototypes.nbytes+64+sum(m.counts.nbytes+40 for m,_,_ in self.slots.values())
