"""Bounded CPU research references: typed encoders, stochastic interpolation and
structured capacity. No claim of exact ID-VSA RTL, device acceleration or truth.
Gaussian Polygon: independent selector streams, shared Gaussian level stream;
bilinear MUX selection in the HV domain (TVLSI 2026, Fig. 7, Eq. 1).
"""
from dataclasses import dataclass
from collections import Counter
import itertools
import math
import numpy as np
from scipy.stats import binom
from .hdc_encoders import CodebookSpec, MAX_ELEMENTS, pack
from .hdc_capacity import map_b_gap


def _unit(x):
    if isinstance(x, (bool, np.bool_)) or not np.isscalar(x) or not np.isfinite(x) or not 0 <= x <= 1:
        raise ValueError('unit interval')
    return float(x)

@dataclass(frozen=True)
class OrderedLevels:
    """Explicit nested level/thermometer and rotating circular code policies.
    Level codes change one fixed ordering of coordinates relative to a random
    anchor; thermometer is unipolar; circular is a moving half-active arc.
    Density shares a random threshold ordering, not independent symbols.
    """
    dimension:int
    levels:int
    seed:int
    mode:str='level'
    def __post_init__(self):
        CodebookSpec(self.dimension,self.seed)
        if type(self.levels) is not int or not 2<=self.levels<=self.dimension+1 or self.mode not in ('level','thermometer','circular','density'):
            raise ValueError('level descriptor')
        if self.mode=='circular' and (self.dimension%2 or self.levels>self.dimension):raise ValueError('circular geometry')
    def atom(self,i):
        if type(i) is not int or not 0<=i<self.levels:raise ValueError('level index')
        d=self.dimension;k=(i*d)//(self.levels-1)
        if self.mode=='thermometer':return np.arange(d)<k
        r=np.random.default_rng(self.seed);perm=r.permutation(d)
        if self.mode=='circular':return ((perm-(i*d)//self.levels)%d)<d//2
        mask=perm<k
        if self.mode=='level':return mask^CodebookSpec(d,self.seed).bits(1)[0]
        return mask
    @property
    def logical_bytes(self):return 24 # seed + dimension, level count, policy/version


def structured_sum(records, spec):
    """Directed role/filler records; input order invariant, field order explicit.
    Duplicate records contribute multiplicity; not a graph traversal algorithm.
    """
    rows=tuple(records)
    if not isinstance(spec,CodebookSpec) or not 1<=len(rows)<=4096 or len(rows)*spec.dimension>MAX_ELEMENTS:raise ValueError('record budget')
    def token(role,value):
        if type(value) is not int or not 0<=value<2**18:raise ValueError('symbol range')
        return spec.bits(1,4*value+role)[0]
    out=np.zeros(spec.dimension,np.int32)
    for row in rows:
        if type(row) is not tuple or len(row)!=3:raise ValueError('directed triple')
        a,b,c=row
        bits=token(0,a)^token(1,b)^token(2,c)
        out+=1-2*bits.astype(np.int32)
    return out


def gaussian_level(p, normal_stream):
    """Gaussian-CDF threshold: marginal density p for standard-normal draws."""
    from scipy.special import ndtri
    x=np.asarray(normal_stream)
    if x.dtype!=np.float64 or x.ndim!=1 or not 1<=len(x)<=65536 or not np.isfinite(x).all():raise ValueError('level stream')
    return x<ndtri(_unit(p))


def mux4(corners,sx,sy):
    """Physical four-way selector oracle; no arithmetic average of bit vectors."""
    a=np.asarray(corners);x=np.asarray(sx);y=np.asarray(sy)
    if a.dtype!=bool or a.ndim!=2 or a.shape[0]!=4 or x.dtype!=bool or y.dtype!=bool or x.shape!=y.shape or x.shape!=(a.shape[1],):raise ValueError('mux operands')
    return np.where(y,np.where(x,a[3],a[2]),np.where(x,a[1],a[0]))


def polygon_encode(image, dimension, seed, scale=2, *, block=64):
    """Tile-streamed independent Gaussian-level and uniform-selector streams.
    Explicit clamped last-pixel convention, fixed indexed selector keys. Returns
    integer bundle (not a majority bit vector); batches identical to scalar tile
    order. Shared original intensity stream; coordinate-specific position binding.
    """
    a=np.asarray(image,dtype=np.float64)
    if a.ndim!=2 or not 1<=min(a.shape) or max(a.shape)>32 or not np.isfinite(a).all() or np.any((a<0)|(a>1)):raise ValueError('image')
    spec=CodebookSpec(dimension,seed)
    if type(scale) is not int or not 1<=scale<=4 or type(block) is not int or not 1<=block<=256:raise ValueError('scale/block')
    h,w=a.shape; oh,ow=h*scale,w*scale
    if oh*ow*dimension>MAX_ELEMENTS:raise ValueError('polygon budget')
    normal=np.random.default_rng(np.random.SeedSequence([seed,0x504f4c59])).standard_normal(dimension)
    # Cache per image's shared scalar levels only (counted in the working set).
    from scipy.special import ndtri
    thresholds=ndtri(a);out=np.zeros(dimension,np.int32)
    for start in range(0,oh*ow,block):
        end=min(start+block,oh*ow);pos=np.arange(start,end); yy,xx=np.divmod(pos,ow)
        y,x=yy//scale,xx//scale;dy,dx=(yy%scale)/scale,(xx%scale)/scale
        y1=np.minimum(y+1,h-1);x1=np.minimum(x+1,w-1)
        # Independent per-output selectors, preserving reproducibility under block changes.
        sx=np.stack([np.random.default_rng(np.random.SeedSequence([seed,1,int(i)])).random(dimension)<f for i,f in zip(pos,dx)])
        sy=np.stack([np.random.default_rng(np.random.SeedSequence([seed,2,int(i)])).random(dimension)<f for i,f in zip(pos,dy)])
        chosen=np.where(sy,np.where(sx,thresholds[y1,x1,None],thresholds[y1,x,None]),np.where(sx,thresholds[y,x1,None],thresholds[y,x,None]))
        level=normal[None,:]<chosen
        bits=level^spec.bits(end-start,start)
        out+=len(bits)-2*bits.sum(axis=0,dtype=np.int32)
    return out


def tree_leaf_gaps(tree):
    """Exact correlation for independent IID distinct leaves in odd majority trees.
    Each odd node multiplies path influence by the central-binomial gap. Refuse
    reused symbols; the independent-subtree formula does not cover them.
    """
    gaps={}
    def walk(t,g,depth):
        if depth>16:raise ValueError('tree depth')
        if type(t) is int:
            if not 0<=t<2**20 or t in gaps or len(gaps)>=4096:raise ValueError('non-independent leaves or budget')
            gaps[t]=g;return
        if type(t) is not tuple or not 3<=len(t)<=255 or len(t)%2==0:raise ValueError('odd majority tree')
        f=g*map_b_gap(len(t))
        for c in t:walk(c,f,depth+1)
    walk(tree,1.,0);return gaps


def tree_error(d,gap,threshold=None):
    if type(d) is not int or not 1<=d<=65536 or not 0<gap<=1:raise ValueError('dimension/gap')
    t=gap/2 if threshold is None else threshold
    if not 0<t<gap:raise ValueError('threshold')
    k=math.ceil(d*(1+t)/2)
    return float(binom.cdf(k-1,d,(1+gap)/2)),float(binom.sf(k-1,d,.5))


def distinct_sparse_fp(m,k,n):
    """Exact finite occupancy recurrence for k-distinct positions per symbol.
    P(query subset | occupied R)=choose(R,k)/choose(m,k). No replacement.
    Distinguish from previously implemented with-replacement Bloom oracle.
    """
    if any(type(x) is not int for x in (m,k,n)) or not 2<=m<=512 or not 1<=k<=min(m,32) or not 0<=n<=512 or m*k*n>2_000_000:raise ValueError('occupancy budget')
    denom=math.comb(m,k);p=np.zeros(m+1);p[0]=1
    for _ in range(n):
        q=np.zeros_like(p)
        for r in np.flatnonzero(p):
            for j in range(max(0,k-int(r)),min(k,m-int(r))+1):
                q[r+j]+=p[r]*math.comb(m-int(r),j)*math.comb(int(r),k-j)/denom
        p=q
    return float(sum(p[r]*math.comb(r,k)/denom for r in range(k,m+1)))


def gappy_counts(s,k=3,span=5):
    """Explicit gapped subsequence feature map (bounded span, no hidden fitting).
    PSD linear kernel over counts; not the original authors' optimized kernel.
    """
    if type(s) is not str or not 1<=len(s)<=1024 or type(k) is not int or type(span) is not int or not 1<=k<=span<=8 or k>4:raise ValueError('string geometry')
    c=Counter()
    for i in range(len(s)):
        for tail in itertools.combinations(range(i+1,min(len(s),i+span)),k-1):c[''.join(s[j] for j in (i,*tail))]+=1
    return c


def propagation_counts(adjacency, labels, projections, steps=2, width=.5):
    """Bounded propagation-style graph feature map: row-normalized label
    distributions, shared fixed LSH projections, histogram over time. Dot of
    explicit counts defines a PSD kernel, invariant to simultaneous node relabel.
    No attributed-graph or full original GraKeL propagation claim.
    """
    a=np.asarray(adjacency); y=np.asarray(labels);w=np.asarray(projections,dtype=np.float64)
    if a.dtype!=bool or a.ndim!=2 or a.shape[0]!=a.shape[1] or not 1<=len(a)<=512 or not np.array_equal(a,a.T) or np.any(np.diag(a)) or y.shape!=(len(a),) or y.dtype.kind not in 'iu' or w.ndim!=2 or not 1<=len(w)<=32 or not np.isfinite(w).all() or np.any((y<0)|(y>=w.shape[1])) or type(steps) is not int or not 0<=steps<=8 or not np.isfinite(width) or width<=0:raise ValueError('graph geometry')
    trans=a.astype(np.float64);isolated=~a.any(axis=1);trans[isolated,isolated]=1;trans/=trans.sum(axis=1)[:,None]
    x=np.eye(w.shape[1])[y];c=Counter()
    for t in range(steps+1):
        # shared floor bins per projection; rounding stabilizes exact bin edges.
        bins=np.floor(np.round(x@w.T/width,12)).astype(np.int64)
        c.update((t,j,int(v)) for row in bins for j,v in enumerate(row))
        x=trans@x
    return c


def gappy_pair_counts(s, k=2, gap=2):
    """Gap-collapsed pair of contiguous k-mers, matching NysHD public
    gappypair kernel's gapDifferent=False positive-gap feature semantics.
    k=2 yields length-four features, not arbitrary subsequence counts.
    """
    if type(s) is not str or not 1<=len(s)<=4096 or type(k) is not int or not 1<=k<=4 or type(gap) is not int or not 0<=gap<=16:raise ValueError('gappy pair geometry')
    c=Counter()
    if gap==0:
        c.update(s[i:i+k] for i in range(max(0,len(s)-k+1)))
    else:
        for i in range(max(0,len(s)-2*k+1)):
            for g in range(min(gap,len(s)-i-2*k)+1):
                c[s[i:i+k]+s[i+k+g:i+2*k+g]]+=1
    return c
