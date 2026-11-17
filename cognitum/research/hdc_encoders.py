"""Research-only typed encoders and compact, immutable query banks.

No general orthogonality claim for quantized QMC and no canonical memory.
Packing is lossless for Boolean vectors; phase8 is explicitly lossy. Actual
accumulator/codebook/workspace storage must be included in memory accounting.
"""
from dataclasses import dataclass
import hashlib
import numpy as np

MAX_ELEMENTS=8_388_608


def _size(d,count):
    if type(d) is not int or type(count) is not int or not 1<=d<=65536 or not 1<=count<=4096 or d*count>MAX_ELEMENTS:
        raise ValueError('invalid dimensions/budget')


@dataclass(frozen=True)
class CodebookSpec:
    dimension:int
    seed:int
    method:str='iid'
    def __post_init__(self):
        _size(self.dimension,1)
        if type(self.seed) is not int or not 0<=self.seed<2**64 or self.method not in ('iid','sobol','halton','hadamard'):
            raise ValueError('bad codebook descriptor')
        if self.method=='hadamard' and self.dimension & (self.dimension-1): raise ValueError('Hadamard dimension must be power of two')
        if self.method in ('sobol','halton') and self.dimension>2048: raise ValueError('QMC dimension budget')

    def bits(self,count,start=0):
        _size(self.dimension,count)
        if type(start) is not int or not 0<=start<=2**20 or start+count>2**20: raise ValueError('index budget')
        if self.method=='iid':
            return np.stack([np.random.Generator(np.random.PCG64(np.random.SeedSequence([self.seed,i]))).integers(0,2,self.dimension,dtype=np.uint8).astype(bool) for i in range(start,start+count)])
        if self.method=='hadamard':
            if start+count>self.dimension: raise ValueError('Hadamard row capacity')
            r=np.random.default_rng(self.seed); perm=r.permutation(self.dimension); signs=r.integers(0,2,self.dimension,dtype=np.uint8).astype(bool)
            return np.array([[(int(i)&int(j)).bit_count()%2 for j in perm] for i in range(start,start+count)],dtype=bool)^signs
        from scipy.stats import qmc
        import warnings
        # SciPy's scrambled codebook is pinned by version in benchmark receipt.
        engine=(qmc.Sobol if self.method=='sobol' else qmc.Halton)(d=self.dimension,scramble=True,seed=self.seed)
        if start: engine.fast_forward(start)
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',message='The balance properties of Sobol')
            return engine.random(count)>=.5


def coherence(bits):
    bits=np.asarray(bits)
    if bits.dtype!=bool or bits.ndim!=2: raise ValueError('Boolean row bank required')
    _size(bits.shape[1],len(bits))
    if len(bits)>1024: raise ValueError('coherence audit pair budget')
    x=1-2*bits.astype(np.int32)
    c=(x@x.T)/bits.shape[1]
    p=c[np.triu_indices(len(x),1)]
    return {'pairs':int(p.size),'duplicates':int(np.count_nonzero(p==1)),'antipodes':int(np.count_nonzero(p==-1)),
            'max_abs':float(np.max(np.abs(p))) if p.size else 0.,'mean_abs':float(np.mean(np.abs(p))) if p.size else 0.}


def screened(spec,count,max_abs):
    if not isinstance(spec,CodebookSpec) or isinstance(max_abs,bool) or not np.isfinite(max_abs) or not 0<=max_abs<1: raise ValueError('invalid coherence ceiling')
    rows=spec.bits(count); audit=coherence(rows)
    if audit['max_abs']>max_abs: raise ValueError(f'codebook coherence bound exceeded: {audit}')
    return rows,audit


def phase_encode(x, frequencies):
    """Continuous FHRR encoding with explicit fixed real frequency matrix."""
    x,w=np.asarray(x),np.asarray(frequencies)
    if (x.dtype!=np.float64 or w.dtype!=np.float64 or x.ndim!=1 or w.ndim!=2
        or not 1<=len(x)<=1024 or w.shape[1]!=len(x) or not np.isfinite(x).all() or not np.isfinite(w).all()): raise ValueError('invalid phase encoder')
    _size(w.shape[0],len(x));theta=w@x
    if not np.isfinite(theta).all(): raise ValueError('phase overflow')
    return np.exp(1j*theta).astype(np.complex64)


def pack(bits):
    a=np.asarray(bits)
    if a.dtype!=bool or a.ndim not in (1,2): raise ValueError('Boolean vectors required')
    _size(a.shape[-1],1 if a.ndim==1 else len(a))
    return np.packbits(a,axis=-1,bitorder='little')


def _packed(a,d,ndim):
    a=np.asarray(a)
    if a.dtype!=np.uint8 or a.ndim!=ndim or a.shape[-1]!=(d+7)//8: raise ValueError('invalid packed layout')
    _size(d,1 if ndim==1 else len(a))
    if d%8 and np.any(a[..., -1] & np.uint8(255^((1<<(d%8))-1))): raise ValueError('noncanonical pad bits')
    return a


_POP=np.array([i.bit_count() for i in range(256)],np.uint8)
_POP.setflags(write=False)

@dataclass(frozen=True)
class PackedBank:
    dimension:int
    packed:np.ndarray
    def __post_init__(self):
        _size(self.dimension,1)
        a=_packed(self.packed,self.dimension,2)
        object.__setattr__(self,'packed',np.frombuffer(a.tobytes(),np.uint8).reshape(a.shape))
    @classmethod
    def from_bits(cls,rows):
        a=np.asarray(rows)
        if a.ndim!=2: raise ValueError('row bank needed')
        return cls(a.shape[1],pack(a))
    @property
    def nbytes(self): return self.packed.nbytes
    def distances(self,query):
        q=_packed(query,self.dimension,1)
        return _POP[self.packed^q].sum(axis=1,dtype=np.int64)
    def scores(self,query): return 1-2*self.distances(query)/self.dimension


def phase8(x):
    a=np.asarray(x)
    if (a.dtype not in (np.dtype('complex64'),np.dtype('complex128')) or a.ndim not in (1,2) or not np.isfinite(a).all()
        or not np.allclose(np.abs(a),1,atol=2e-5,rtol=0)): raise ValueError('phase8 requires unit phases, not additive bundles')
    _size(a.shape[-1],1 if a.ndim==1 else len(a))
    return (np.rint(np.angle(a).astype(np.float64)*(256/(2*np.pi))).astype(np.int64)%256).astype(np.uint8)


def phase8_decode(a):
    a=np.asarray(a)
    if a.dtype!=np.uint8 or a.ndim not in (1,2): raise ValueError('invalid phase8 layout')
    _size(a.shape[-1],1 if a.ndim==1 else len(a))
    return np.exp(2j*np.pi*a.astype(np.float64)/256).astype(np.complex64)

_PHASE_LUT=np.cos(2*np.pi*np.arange(256)/256).astype(np.float32)
_PHASE_LUT.setflags(write=False)

@dataclass(frozen=True)
class PhaseBank:
    codes:np.ndarray
    def __post_init__(self):
        a=np.asarray(self.codes)
        if a.dtype!=np.uint8 or a.ndim!=2: raise ValueError('invalid phase bank')
        _size(a.shape[1],len(a));object.__setattr__(self,'codes',np.frombuffer(a.tobytes(),np.uint8).reshape(a.shape))
    @property
    def nbytes(self): return self.codes.nbytes
    def scores(self,query):
        q=np.asarray(query)
        if q.dtype!=np.uint8 or q.shape!=(self.codes.shape[1],):raise ValueError('invalid phase8 query')
        # uint8 modular subtraction; fixed real phase cosine.
        return _PHASE_LUT[np.subtract(self.codes,q,dtype=np.uint8)].mean(axis=1,dtype=np.float64)


def digest(a):
    a=np.ascontiguousarray(a)
    return hashlib.sha256(a.dtype.str.encode()+str(a.shape).encode()+a.tobytes()).hexdigest()


def nystrom_reference(train, landmark_indices, *, gamma, rtol=1e-10):
    """Bounded RBF Nyström feature map, trained only on supplied train rows.

    This is a conventional kernel reference, not a reproduction of NysHD.
    Explicit train indices are mandatory. Use it as a matched comparison arm.
    """
    a=np.asarray(train);ids=np.asarray(landmark_indices)
    if (a.dtype!=np.float64 or a.ndim!=2 or not np.isfinite(a).all() or not 1<=len(a)<=4096
        or not 1<=a.shape[1]<=1024 or ids.dtype!=np.int64 or ids.ndim!=1
        or not 1<=len(ids)<=256 or len(np.unique(ids))!=len(ids)
        or (ids<0).any() or (ids>=len(a)).any()
        or not np.isfinite(gamma) or gamma<=0 or not 0<rtol<1):raise ValueError('invalid Nyström training inputs')
    z=a[ids].copy()
    def kernel(x,y):
        # Direct differences avoid cancellation in squared distances.
        # Loop across landmarks instead of allocating N x M x features.
        return np.stack([np.exp(-gamma*np.square(x-v).sum(axis=1)) for v in y],axis=1)
    with np.errstate(over='raise',invalid='raise'):
        k=kernel(z,z);vals,vecs=np.linalg.eigh(k)
    keep=vals>rtol*vals[-1]
    if vals[0]<-rtol*vals[-1] or not keep.any():raise ValueError('invalid PSD spectrum')
    inverse_root=vecs[:,keep]/np.sqrt(vals[keep]);z.setflags(write=False);inverse_root.setflags(write=False)
    def transform(x):
        x=np.asarray(x)
        if (x.dtype!=np.float64 or x.ndim!=2 or x.shape[1]!=z.shape[1] or not 1<=len(x)<=4096 or not np.isfinite(x).all()):raise ValueError('invalid Nyström query')
        with np.errstate(over='raise',invalid='raise'):
            out=kernel(x,z)@inverse_root
        if not np.isfinite(out).all():raise ValueError('invalid Nyström result')
        return out
    return transform,{'landmark_bytes':z.nbytes,'factor_bytes':inverse_root.nbytes,'rank':int(keep.sum()),'landmark_digest':digest(z)}
