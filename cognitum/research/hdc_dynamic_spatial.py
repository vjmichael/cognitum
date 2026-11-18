"""CPU research references for compute-on-demand symbols and spatial/sparse pipelines.

ID-VSA (TVLSI 2026) Fig. 5 comparator/toggle interpretation: reset each row,
strict T>V, emit updated toggle. These conventions are explicit experimental
choices, not certified RTL parity. HyperSpace arXiv:2604.15113v2 table 1
FHRR/HRR codebook branch. Sparse AND + learned threshold is an independent
software arm motivated by HyperSPACE ISLPED 2026, not their exact circuit.
"""
from dataclasses import dataclass
import numpy as np
from .hdc_encoders import MAX_ELEMENTS, coherence, CodebookSpec
from .hdc_frontier_encoders import _real, _immutable


def _dim(d):
    if type(d) is not int or not 2 <= d <= 65536: raise ValueError('dimension')


@dataclass(frozen=True)
class VDCToggle:
    dimension: int
    def __post_init__(self):
        _dim(self.dimension)
        if self.dimension & (self.dimension-1): raise ValueError('power of two dimension')
    def atom(self, index):
        d=self.dimension
        if type(index) is not int or not 0<=index<d: raise ValueError('counter range')
        x=np.arange(d,dtype=np.uint32);rev=np.zeros_like(x)
        for _ in range(d.bit_length()-1):
            rev=(rev<<1)|(x&1);x>>=1
        return np.logical_xor.accumulate(rev<index)
    def audit(self, count, start=0):
        if type(count) is not int or type(start) is not int or not 1<=count<=1024 or start<0 or start+count>self.dimension or count*self.dimension>MAX_ELEMENTS:raise ValueError('audit budget')
        return coherence(np.stack([self.atom(i) for i in range(start,start+count)]))


@dataclass(frozen=True)
class SpatialSketch:
    """Single memory, shared continuous position/value phases, optional HRR isometry.

    HRR uses a scaled real inverse FFT transform of the matching
    Hermitian FHRR codes. Explicit endpoints DC and Nyquist fixed to one;
    circular convolution uses ordinary FFT scaling. Half-FHRR stores only
    the nonredundant Hermitian half and weights interior inner products by two.
    No trained decoder; this compression is not applicable to arbitrary FHRR.
    """
    frequencies: np.ndarray  # D/2+1 x (spatial axes + scalar value)
    dimension: int
    backend: str
    memory: np.ndarray
    levels: np.ndarray
    def __post_init__(self):
        _dim(self.dimension);d=self.dimension
        f=_real(self.frequencies,2);v=_real(self.levels,1);m=np.asarray(self.memory)
        if (d%2 or self.backend not in ('fhrr','hrr','half-fhrr') or f.shape[0]!=d//2+1 or not 2<=f.shape[1]<=9
            or np.any(f[[0,-1]]!=0) or len(v)>512 or not np.all(np.diff(v)>0)
            or m.shape!=((d//2+1,) if self.backend=='half-fhrr' else (d,)) or m.dtype!=np.dtype('float64' if self.backend=='hrr' else 'complex128')
            or not np.isfinite(m).all() or not np.linalg.norm(m)>0):raise ValueError('spatial descriptor')
        if self.backend!='hrr' and (m[0].imag!=0 or m[-1 if self.backend=='half-fhrr' else d//2].imag!=0):raise ValueError('nonreal spectrum endpoint')
        if self.backend=='fhrr' and not np.array_equal(m[1:d//2],m[:d//2:-1].conj()):raise ValueError('non-Hermitian spectrum')
        for key,x in [('frequencies',f),('levels',v),('memory',m)]:object.__setattr__(self,key,_immutable(x))
    @staticmethod
    def _phase(f, x, d, backend):
        theta=f@x
        if not np.isfinite(theta).all():raise ValueError('phase overflow')
        half=np.exp(1j*theta)
        if backend=='hrr':return np.fft.irfft(half,n=d)
        if backend=='half-fhrr':return half
        return np.concatenate([half,half[-2:0:-1].conj()])
    @classmethod
    def fit(cls, points, values, levels, dimension, seed, widths, backend='fhrr'):
        p=_real(points,2);v=_real(values,1);l=_real(levels,1);w=_real(widths,1);_dim(dimension)
        if (dimension%2 or not 1<=p.shape[1]<=8 or len(p)!=len(v) or len(w)!=p.shape[1]+1
            or np.any(w<=0) or len(p)*dimension>MAX_ELEMENTS or type(seed) is not int or not 0<=seed<2**64 or backend not in ('fhrr','hrr','half-fhrr')):raise ValueError('spatial inputs')
        f=np.random.default_rng(seed).normal(size=(dimension//2+1,len(w)))/w;f[[0,-1]]=0
        m=np.zeros(dimension//2+1 if backend=='half-fhrr' else dimension,np.float64 if backend=='hrr' else np.complex128)
        for x,y in zip(p,v): m+=cls._phase(f,np.r_[x,y],dimension,backend)
        return cls(f,dimension,backend,m,l)
    def query_vector(self, x):
        p=_real(x,1)
        if len(p)!=self.frequencies.shape[1]-1:raise ValueError('position axes')
        q=self._phase(self.frequencies,np.r_[p,0.],self.dimension,self.backend)
        if self.backend!='hrr':return self.memory*q.conj()
        return np.fft.irfft(np.fft.rfft(self.memory)*np.fft.rfft(q).conj(),n=self.dimension)
    def predict(self, x, cleanup='none', beta=12.):
        if cleanup not in ('none','hopfield','resonator') or not np.isfinite(beta) or not 0<beta<=100:raise ValueError('decoder policy')
        def dot(a,b):
            if self.backend!='half-fhrr':return float(np.vdot(a,b).real)
            return float((a[0].conj()*b[0]+a[-1].conj()*b[-1]).real+2*np.vdot(a[1:-1],b[1:-1]).real)
        def norm(a):return np.sqrt(max(0.,dot(a,a)))
        v=self.query_vector(x); n=norm(v)
        if not n>0:raise ValueError('zero query')
        v=v/n
        # Resident codebook not required. Regenerate per level; count query time.
        def atoms():
            for u in self.levels:
                a=self._phase(self.frequencies,np.r_[np.zeros(self.frequencies.shape[1]-1),u],self.dimension,self.backend)
                yield a/norm(a)
        def scores(y):return np.array([dot(a,y) for a in atoms()])
        def weights(s):
            e=np.exp(beta*(s-s.max()));return e/e.sum()
        s=scores(v)
        if cleanup!='none':
            coeff=weights(s) if cleanup=='hopfield' else s
            c=sum(w*a for w,a in zip(coeff,atoms()));n=norm(c)
            if not n>0:raise ValueError('zero cleanup')
            s=scores(c/n)
        return float(weights(s)@self.levels)
    @property
    def payload_bytes(self):return self.frequencies.nbytes+self.memory.nbytes+self.levels.nbytes+16


@dataclass(frozen=True)
class SparseProjection:
    """Procedural Bernoulli sparse feature projections, AND or XOR comparison.
    Fit quantizer on train counts only; inference retains thresholds and seed.
    """
    dimension:int
    features:int
    seed:int
    density:float
    threshold:np.ndarray
    binding:str='and'
    def __post_init__(self):
        _dim(self.dimension)
        t=_real(self.threshold,1)
        if (type(self.features) is not int or not 1<=self.features<=1024 or len(t)!=self.dimension
            or type(self.seed) is not int or not 0<=self.seed<2**64 or not 0<self.density<1 or self.binding not in ('and','xor')):raise ValueError('sparse descriptor')
        object.__setattr__(self,'threshold',_immutable(t))
    def counts(self,x):
        x=_real(x,2)
        if x.shape[1]!=self.features or len(x)*self.dimension>MAX_ELEMENTS or np.any((x<0)|(x>1)):raise ValueError('input range/budget')
        out=np.zeros((len(x),self.dimension),np.int32)
        for i in range(self.features):
            r=np.random.default_rng(np.random.SeedSequence([self.seed,i]));a=r.random(self.dimension)<self.density;u=r.random(self.dimension)
            lev=x[:,i,None]>u
            out+= (lev&a if self.binding=='and' else lev^a)
        return out
    @classmethod
    def fit(cls,x,dimension,seed,density=.05,binding='and'):
        x=_real(x,2);_dim(dimension)
        proto=cls(dimension,x.shape[1],seed,density,np.zeros(dimension,np.float64),binding)
        return cls(dimension,x.shape[1],seed,density,np.median(proto.counts(x),axis=0),binding)
    def bits(self,x):return self.counts(x)>self.threshold
    @property
    def payload_bytes(self):return self.threshold.nbytes+40

@dataclass(frozen=True)
class NoShiftSymbols:
    """Append-safe position-specific symbols, independent IID control for ID-VSA.

    A fixed injective Cantor mapping avoids remapping existing (symbol,position)
    when the vocabulary grows or n-gram length changes. This is not the VDC RTL.
    """
    dimension:int
    seed:int
    def __post_init__(self):CodebookSpec(self.dimension,self.seed)
    def atom(self,symbol,position):
        if any(type(i) is not int or i<0 or i>=2**20 for i in (symbol,position)):raise ValueError('invalid symbol/position')
        s=symbol+position;i=s*(s+1)//2+position
        if i>=2**20:raise ValueError('index capacity')
        return CodebookSpec(self.dimension,self.seed).bits(1,i)[0]
    def ngram(self,symbols):
        s=tuple(symbols)
        if not 1<=len(s)<=64:raise ValueError('ngram length')
        a=np.zeros(self.dimension,bool)
        for pos,symbol in enumerate(s):a^=self.atom(symbol,pos)
        return a


def vdc_sequence(d,base):
    _dim(d)
    if type(base) is not int or not 2<=base<=65536:raise ValueError('base')
    n=np.arange(d,dtype=np.uint32);v=np.zeros(d,np.float64);f=1./base
    while np.any(n):v+=f*(n%base);n//=base;f/=base
    return v


@dataclass(frozen=True)
class QuasiNormalLevels:
    """ID-VSA QND mean of radix-inverse streams, as in Section III-C.

    Fixed bases 2**1..2**N, N=log2(D), chosen as one explicit convention.
    No claim of normality/independence; use empirical density/coherence audit.
    """
    dimension:int
    slots:int
    def __post_init__(self):
        _dim(self.dimension)
        if self.dimension&(self.dimension-1) or type(self.slots) is not int or not 2<=self.slots<=self.dimension:raise ValueError('QND descriptor')
    def sequence(self):
        return np.mean([vdc_sequence(self.dimension,2**i) for i in range(1,self.dimension.bit_length())],axis=0)
    def level(self,value):
        if not np.isfinite(value) or not 0<=value<=1:raise ValueError('level')
        return self.sequence()<value
    def symbol(self,index):
        if type(index) is not int or not 0<=index<self.slots:raise ValueError('symbol')
        # Explicit fixed-slot QND threshold XOR uniform radix stream. Bounds
        # preserve old vectors; actual source quality must be screened.
        base=2**(1+index%(self.dimension.bit_length()-1))
        return self.level(index/self.slots)^(vdc_sequence(self.dimension,base)<.5)

@dataclass(frozen=True)
class ScreenedSymbols:
    """Bounded admission of regenerable VDC/QND/IID atoms, not a truth store.

    Only accepted indices persist; failed append is atomic. Admission checks
    absolute correlation, catches complements and duplicates. Finite codebook
    exhaustion is explicit, and exact rerendering uses the same descriptor.
    """
    spec: object
    ids: tuple=()
    max_abs: float=.4
    def __post_init__(self):
        if not isinstance(self.spec,(VDCToggle,QuasiNormalLevels,CodebookSpec)) or not 0<=self.max_abs<1 or not np.isfinite(self.max_abs):raise ValueError('screen descriptor')
        if type(self.ids) is not tuple or len(self.ids)>256 or len(self.ids)*self.spec.dimension>MAX_ELEMENTS or len(set(self.ids))!=len(self.ids):raise ValueError('admission budget')
        # Validate restored state, including already admitted pair relations.
        if self.ids:
            a=np.stack([self.atom(i) for i in self.ids])
            if coherence(a)['max_abs']>self.max_abs:raise ValueError('coherence bound')
    def atom(self,i):
        if isinstance(self.spec,VDCToggle):return self.spec.atom(i)
        if isinstance(self.spec,QuasiNormalLevels):return self.spec.symbol(i)
        return self.spec.bits(1,i)[0]
    def append(self,i):
        if i in self.ids or len(self.ids)>=256:raise ValueError('duplicate/full')
        return ScreenedSymbols(self.spec,self.ids+(i,),self.max_abs)
    def payload_bytes(self):
        # Logical indices and fixed descriptor fields; not process RSS.
        return 40+4*len(self.ids)
