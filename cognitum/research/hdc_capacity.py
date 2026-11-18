"""Set membership/intersection references, no authority from approximate scores.
MAP-B uses one-shot sign with odd n; analytical binomial tail for IID atoms.
Bloom uses k independent uniform placements with replacement; Counting Bloom
intersection estimate debiased for known set cardinalities. No delete without
caller custody and actual known member. No universal guarantee from empirical
rates or pseudo-random draws. Sparse OR is Bloom, not a separate magic index.
"""
import math
import numpy as np
from scipy.stats import binom
from .hdc_encoders import CodebookSpec,pack,PackedBank


def map_b_gap(n):
    if type(n) is not int or not 1<=n<=32767 or n%2==0:raise ValueError('odd cardinality required')
    return math.exp(math.lgamma(n)-2*math.lgamma((n+1)/2)-(n-1)*math.log(2))


def map_b_error(d,n,threshold=None):
    if type(d) is not int or not 1<=d<=65536:raise ValueError('dimension')
    g=map_b_gap(n);t=g/2 if threshold is None else threshold
    if not np.isfinite(t) or not 0<t<g:raise ValueError('threshold')
    # score=2*matches/d-1; accept >= t. Round via direct score check.
    k=math.ceil(d*(1+t)/2)
    return float(binom.cdf(k-1,d,(1+g)/2)),float(binom.sf(k-1,d,.5))


def sparse_or_density(m,k,n):
    if any(type(i) is not int for i in (m,k,n)) or m<2 or k<1 or n<0:raise ValueError('invalid parameters')
    return -math.expm1(n*k*math.log1p(-1/m))


class BloomSketch:
    def __init__(self,m,k,seed,ids,counting=False):
        if (type(m) is not int or not 2<=m<=65536 or type(k) is not int or not 1<=k<=64
            or type(seed) is not int or not 0<=seed<2**64 or type(counting) is not bool):raise ValueError('descriptor')
        ids=tuple(ids)
        if len(ids)>65535//k or len(set(ids))!=len(ids):raise ValueError('cardinality/counter limit')
        self.m,self.k,self.seed,self.n,self.counting=m,k,seed,len(ids),counting
        c=np.zeros(m,np.uint16)
        for i in ids:np.add.at(c,self.positions(i),1)
        self.data=c if counting else pack(c>0)
        self.data=np.frombuffer(self.data.tobytes(),self.data.dtype)
    def positions(self,i):
        if type(i) is not int or not 0<=i<2**32:raise ValueError('identifier')
        return np.random.default_rng(np.random.SeedSequence([self.seed,i])).integers(self.m,size=self.k,dtype=np.int64)
    def contains(self,i):
        p=self.positions(i)
        return bool(np.all(self.data[p]>0) if self.counting else np.all((self.data[p//8]>>(p%8))&1))
    def estimate_intersection(self,other):
        if not isinstance(other,BloomSketch) or not self.counting or not other.counting or (self.m,self.k,self.seed)!=(other.m,other.k,other.seed):raise ValueError('incompatible counting sketch')
        # E[dot] = n1*n2*k²/m + overlap*k*(1-1/m).
        cross=int(self.data.astype(np.int64)@other.data.astype(np.int64))
        return (cross-self.n*other.n*self.k**2/self.m)/(self.k*(1-1/self.m))
    @property
    def payload_bytes(self):return self.data.nbytes+32


class MAPBSet:
    def __init__(self,d,seed,ids):
        ids=tuple(ids)
        if len(set(ids))!=len(ids):raise ValueError('duplicates')
        self.gap=map_b_gap(len(ids));self.n=len(ids);self.spec=CodebookSpec(d,seed)
        acc=np.zeros(d,np.int32)
        for i in ids:acc+=1-2*self.spec.bits(1,i)[0].astype(np.int32)
        self.bank=PackedBank.from_bits((acc<0)[None,:])
    def score(self,i):return float(self.bank.scores(pack(self.spec.bits(1,i)[0]))[0])
    def contains(self,i):return self.score(i)>=self.gap/2
    @property
    def payload_bytes(self):return self.bank.nbytes+24


def bloom_exact_fp(m,k,n):
    """Finite occupancy recurrence under IID placements with replacement.

    E[(R/m)**k], R unique occupied slots after n*k draws. Bounded small
    exact-distribution oracle (floating probabilities), not large filter solver.
    """
    if any(type(i) is not int for i in (m,k,n)) or not 2<=m<=4096 or not 1<=k<=64 or n<0 or n*k*m>4_000_000:raise ValueError('occupancy oracle budget')
    p=np.zeros(m+1,np.float64);p[0]=1.;freq=np.arange(m+1)/m
    for _ in range(n*k):
        q=p*freq;q[1:]+=p[:-1]*(1-freq[:-1]);p=q
    return float(p@(freq**k))
