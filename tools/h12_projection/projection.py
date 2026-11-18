"""Research-only projection alternatives. Bounded normalized FP32 inputs; no runtime promotion.
Column-block PCG codebook is a NEW reproducible definition, not the old H12 RNG stream.
Packed storage is exact for this codebook. Sparse/structured codebooks are distinct experiments.
"""
from dataclasses import dataclass
import math
import numpy as np

def check(x,f):
    x=np.asarray(x)
    if x.dtype!=np.float32 or x.ndim!=2 or x.shape[1]!=f or not len(x) or not np.isfinite(x).all() or np.max(np.abs(x))>5:raise ValueError('bounded normalized FP32 rows required')
    return x

def rng(seed,block):return np.random.default_rng(np.random.SeedSequence([seed,block]))
def weights(f,n,seed,i):return (2*rng(seed,i).integers(0,2,(f,n),dtype=np.int8)-1)

def stable_bits(x,w,z):
    # +/-1 products are exact in float32. Conservative sequential roundoff bound;
    # near-boundary signs are recomputed from the original float32 terms with fsum.
    u=2**-24; gamma=(2*x.shape[1]*u)/(1-2*x.shape[1]*u)
    l1=np.abs(x.astype(np.float64)).sum(axis=1)
    bound=gamma*l1+np.finfo(np.float32).tiny*x.shape[1]
    bits=z<0; ambiguous=np.argwhere((np.abs(z.astype(np.float64))<=bound[:,None]) & (l1[:,None]>0))
    # Refine in bounded 64-pair blocks. Use fsum only when even the
    # conservative FP64 error bound cannot certify the sign.
    u64=2**-53;g64=(2*x.shape[1]*u64)/(1-2*x.shape[1]*u64)
    for a in range(0,len(ambiguous),64):
        i,j=ambiguous[a:a+64].T
        sums=(x[i].astype(np.float64)*w[:,j].T).sum(axis=1,dtype=np.float64)
        bits[i,j]=sums<0
        for ii,jj in zip(i[np.abs(sums)<=g64*l1[i]],j[np.abs(sums)<=g64*l1[i]]):
            bits[ii,jj]=math.fsum(float(v)*int(b) for v,b in zip(x[ii],w[:,jj]))<0
    return bits

def words(bits):
    a=np.packbits(bits,axis=1,bitorder='little')
    if a.shape[1]%8:a=np.pad(a,((0,0),(0,(-a.shape[1])%8)))
    return np.ascontiguousarray(a).view('<u8')

def unpack(w,d):return np.unpackbits(np.ascontiguousarray(w,dtype='<u8').view(np.uint8),axis=1,bitorder='little',count=d).astype(bool)

@dataclass
class Plan:
    f:int;d:int;seed:int=1201;block:int=256
    def __post_init__(self):
        if not 1<=self.f<=8192 or not 1<=self.d<=65536 or self.block<64 or self.block%64 or self.block>4096 or self.seed<0:raise ValueError('dimensions/block/seed')
    def blocks(self):
        for i,s in enumerate(range(0,self.d,self.block)):yield i,s,min(self.d-s,self.block)
    def dense(self):return np.concatenate([weights(self.f,n,self.seed,i) for i,s,n in self.blocks()],axis=1).astype(np.float32)
    def packed(self):
        result=np.empty(((self.f+7)//8,self.d),dtype=np.uint8)
        for i,s,n in self.blocks():result[:,s:s+n]=np.packbits(weights(self.f,n,self.seed,i)>0,axis=0,bitorder='little')
        return result
    def reference(self,x,w):
        x=check(x,self.f)
        if w.shape!=(self.f,self.d):raise ValueError('dense shape')
        return words(stable_bits(x,w,x@w))
    def encode(self,x,p=None):
        x=check(x,self.f)
        if p is not None and (p.dtype!=np.uint8 or p.shape!=((self.f+7)//8,self.d)):raise ValueError('packed shape')
        result=np.zeros((len(x),(self.d+63)//64),dtype='<u8')
        for i,s,n in self.blocks():
            w=weights(self.f,n,self.seed,i) if p is None else 2*np.unpackbits(p[:,s:s+n],axis=0,count=self.f,bitorder='little').astype(np.int8)-1
            z=x@w.astype(np.float32);b=stable_bits(x,w,z)
            result[:,s//64:s//64+(n+63)//64]=words(b)
        return result

class Sparse:
    def __init__(self,f,d,k,seed):
        if not 1<=k<=f<=8192 or not 1<=d<=65536:raise ValueError('shape')
        self.f,self.d,self.k=f,d,k;r=rng(seed,0);self.indices=np.stack([r.choice(f,k,replace=False) for _ in range(d)]).astype(np.uint16);self.signs=(2*r.integers(0,2,(d,k),dtype=np.int8)-1)
    def encode(self,x,block=256):
        x=check(x,self.f);out=np.zeros((len(x),(self.d+63)//64),dtype='<u8')
        if block%64:raise ValueError('block')
        for s in range(0,self.d,block):
            ids=self.indices[s:s+block];sg=self.signs[s:s+block];a=x[:,ids]*sg; z=a.sum(axis=2,dtype=np.float64);out[:,s//64:s//64+(len(ids)+63)//64]=words(z<0)
        return out

class Hadamard:
    """Signed padded FWHT blocks; not IID projections and not a paper reproduction."""
    def __init__(self,f,d,seed):
        if not 1<=f<=8192 or not 1<=d<=65536:raise ValueError('shape')
        self.f,self.d,self.seed=f,d,seed;self.n=1<<(f-1).bit_length()
    def encode(self,x):
        x=check(x,self.f);out=np.empty((len(x),self.d),dtype=bool)
        for i,s in enumerate(range(0,self.d,self.n)):
            r=rng(self.seed,i);a=np.zeros((len(x),self.n),dtype=np.float64);a[:,:self.f]=x*(2*r.integers(0,2,self.f,dtype=np.int8)-1);h=1
            while h<self.n:
                v=a.reshape(len(x),-1,2*h);l=v[:,:,:h].copy();rr=v[:,:,h:].copy();v[:,:,:h]=l+rr;v[:,:,h:]=l-rr;h*=2
            k=min(self.n,self.d-s);out[:,s:s+k]=a[:,r.permutation(self.n)[:k]]<0
        return words(out)
