"""Exact packed CIFAR replay accelerators; offline caches counted separately.
No change to the VisualBank update rule, RNG sequence, or retained model budget.
"""
import numpy as np
from .hdc_uncertain_visual import VisualBank


def distance(a,b,d):
    a=np.asarray(a);b=np.asarray(b)
    if a.dtype!=np.uint8 or b.dtype!=np.uint8 or a.shape[-1]!=(d+7)//8 or b.shape[-1]!=a.shape[-1]:raise ValueError('packed shape')
    x=a^b
    if d%8:x[..., -1]&=np.uint8(255<<(8-d%8)&255)
    return np.bitwise_count(x).sum(axis=-1,dtype=np.int64)


def merge_exact(a,target,d,rng,weights,top_m=3,iterations=2):
    # The source bank is immutable during this routine. All pairwise source
    # distances can be computed once; ties and RNG ordering match consolidate.
    if not 1<=target<=len(a)<=128:raise ValueError('merge bounds')
    w=np.asarray(weights,dtype=np.float64)
    if w.shape!=(len(a),) or not np.isfinite(w).all() or (w<=0).any():raise ValueError('weights')
    pair=distance(a[:,None,:],a[None,:,:],d)
    chosen=[int(rng.integers(len(a)))];ds=pair[:,chosen[0]].astype(float)
    for _ in range(1,target):
        ds[chosen]=-1; candidates=np.argsort(-ds,kind='stable')[:min(top_m,len(a)-len(chosen))]
        j=int(rng.choice(candidates));chosen.append(j);ds=np.minimum(ds,pair[:,j])
    centers=a[chosen].copy();bits=np.unpackbits(a,axis=1,count=d)
    for _ in range(iterations):
        labels=distance(a[:,None,:],centers[None,:,:],d).argmin(1)
        for j in range(target):
            mask=labels==j
            if mask.any():
                vote=w[mask]@bits[mask];half=w[mask].sum()/2;old=np.unpackbits(centers[j],count=d)
                centers[j]=np.packbits(np.where(vote==half,old,vote>half).astype(np.uint8))
    return centers,distance(a[:,None,:],centers[None,:,:],d).argmin(1)


class FastVisualBank(VisualBank):
    def predict(self,q):
        q=np.asarray(q)
        if q.ndim!=1:raise ValueError('query')
        distance(q,q,self.dimension)
        if not self.n:return -1,0.
        s=1-distance(self.bank[:self.n],q,self.dimension)/self.dimension;j=int(s.argmax());return j,float(s[j])
    def observe(self,q):
        q=np.asarray(q);j,s=self.predict(q)
        novel=j<0 or s<max(self.floor,self.mean[j]-self.beta*np.sqrt(self.var[j]))
        if novel and self.n==self.capacity:
            if self.mode=='merge':
                c,lab=merge_exact(self.bank[:self.n],self.capacity-1,self.dimension,self.rng,self.count[:self.n])
                counts=np.bincount(lab,weights=self.count[:self.n],minlength=len(c));self.bank[:len(c)]=c;self.count[:len(c)]=np.maximum(1,counts).astype(np.int64);self.mean[:len(c)]=self.floor;self.var[:len(c)]=.01;self.n=len(c);self.merges+=1
            elif self.mode=='replace':
                k=int(self.count[:self.n].argmin());self.bank[k]=q;self.count[k]=1;self.mean[k]=self.floor;self.var[k]=.01;return j,s,True
            else:novel=False
        if novel:
            k=self.n;self.n+=1;self.bank[k]=q;self.count[k]=1;self.mean[k]=self.floor;self.var[k]=.01
        else:
            delta=s-self.mean[j];self.mean[j]+=self.alpha*delta;self.var[j]=(1-self.alpha)*(self.var[j]+self.alpha*delta*delta)
            mask=np.packbits(self.rng.random(self.dimension)<self.alpha);self.bank[j]=(self.bank[j]&~mask)|(q&mask);self.count[j]+=1
        return j,s,novel


def encode_rows(enc,rows):
    # Bound the scratch tensor to <=8 MiB: rows x features x dimension.
    if not len(rows):raise ValueError('empty rows')
    z=np.asarray(rows);n=max(1,(8<<20)//(enc.features*enc.dimension))
    if z.ndim!=2 or z.shape[1]!=enc.features or z.dtype.kind not in 'iu' or (z<0).any() or (z>=enc.levels).any():raise ValueError('levels')
    out=[]
    for i in range(0,len(z),n):
        a=enc.p[None,:,:]^enc.l[z[i:i+n]]
        votes=np.unpackbits(a,axis=-1,count=enc.dimension).sum(axis=1,dtype=np.uint16)
        out.append(np.packbits(votes.astype(np.uint32)*2>=enc.features,axis=-1))
    return np.concatenate(out)
