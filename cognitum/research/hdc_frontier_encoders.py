"""Bounded CPU research: kernel rounding, correlation geometry and MAP-I capacity.

References: Zhao et al., AAAI 2025, doi:10.1609/aaai.v39i21.34442
(Algorithms 1–2); Poduval et al., doi:10.3389/frai.2026.1690492.
Capacity inequalities below are independent elementary Rademacher bounds, not
an implementation of every theorem in Clarkson et al. arXiv:2301.10352.
No automatic routing, persistent facts, or implicit approximate acceptance.
"""
from dataclasses import dataclass
import math
import numpy as np
from .hdc_encoders import MAX_ELEMENTS, CodebookSpec, pack, PackedBank


def _real(a, ndim):
    a = np.asarray(a)
    if a.ndim != ndim or a.dtype != np.float64 or not a.size or a.size > MAX_ELEMENTS or not np.isfinite(a).all():
        raise ValueError('invalid real operand')
    return a


def _immutable(a):
    return np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)


def _factor(gram, dimension, seed, rtol):
    g = _real(gram, 2)
    if (g.shape[0] != g.shape[1] or len(g) > 256 or type(dimension) is not int
        or not 1 <= dimension <= 65536 or dimension*len(g) > MAX_ELEMENTS
        or type(seed) is not int or not 0 <= seed < 2**64
        or not 0 < rtol < 1 or not np.allclose(g, g.T, atol=0, rtol=1e-12)):
        raise ValueError('invalid landmark Gram')
    vals, vecs = np.linalg.eigh(g)
    if vals[-1] <= 0 or vals[0] < -rtol*vals[-1]: raise ValueError('not PSD')
    keep = vals > rtol*vals[-1]
    root = vecs[:, keep]/np.sqrt(vals[keep])
    return root


@dataclass(frozen=True)
class NysHD:
    """Kernel-only encoder. Landmarks selected from training by the caller.

    Store fused hyperplane matrix, not the training Gram or dense codebook.
    Rank truncation is explicit; zero Nyström features are rejected.
    """
    projection: np.ndarray
    inverse_root: np.ndarray
    def __post_init__(self):
        p, r = _real(self.projection, 2), _real(self.inverse_root, 2)
        if p.shape[1] != r.shape[0] or r.shape[1] > r.shape[0] or r.shape[0] > 256:
            raise ValueError('invalid projection shape')
        object.__setattr__(self, 'projection', _immutable(p))
        object.__setattr__(self, 'inverse_root', _immutable(r))

    @classmethod
    def fit(cls, gram, dimension, seed, rtol=1e-10):
        root = _factor(gram, dimension, seed, rtol)
        # Isotropic Gaussian rows have the same signs as unit sphere rows.
        w = np.random.default_rng(seed).normal(size=(dimension, root.shape[1]))
        w /= np.linalg.norm(w, axis=1, keepdims=True)
        return cls(w @ root.T, root)

    def features(self, cross):
        c = _real(cross, 2)
        if c.shape[1] != self.projection.shape[1]: raise ValueError('landmark mismatch')
        f = c @ self.inverse_root
        if not np.isfinite(f).all() or np.any(np.linalg.norm(f, axis=1) <= 1e-14): raise ValueError('degenerate features')
        return f

    def bits(self, cross):
        c = _real(cross, 2)
        if len(c)*len(self.projection) > MAX_ELEMENTS: raise ValueError('output budget')
        self.features(c)
        out = c @ self.projection.T
        if not np.isfinite(out).all(): raise ValueError('projection overflow')
        return out < 0

    @property
    def nbytes(self): return self.projection.nbytes + self.inverse_root.nbytes

    def bank(self, cross): return PackedBank.from_bits(self.bits(cross))

    def scaled_scores(self, bank, cross):
        if bank.dimension != len(self.projection): raise ValueError('dimension mismatch')
        return np.stack([bank.scores(pack(b))* (np.pi/2) for b in self.bits(cross)])


@dataclass(frozen=True)
class GaussianPhase:
    """FPE/RFF with explicitly anisotropic length scales and shared draws."""
    frequencies: np.ndarray
    def __post_init__(self):
        object.__setattr__(self, 'frequencies', _immutable(_real(self.frequencies, 2)))
    @classmethod
    def sample(cls, dimension, widths, seed):
        w = _real(widths, 1)
        if (type(dimension) is not int or not 1 <= dimension <= 65536
            or len(w) > 1024 or dimension*len(w) > MAX_ELEMENTS or np.any(w <= 0)
            or type(seed) is not int or not 0 <= seed < 2**64): raise ValueError('invalid encoder spec')
        return cls(np.random.default_rng(seed).normal(size=(dimension,len(w)))/w)
    def encode(self, points):
        x = _real(points, 2)
        if x.shape[1] != self.frequencies.shape[1] or len(x)*len(self.frequencies)>MAX_ELEMENTS: raise ValueError('phase budget')
        theta = x @ self.frequencies.T
        if not np.isfinite(theta).all(): raise ValueError('phase overflow')
        return np.exp(1j*theta).astype(np.complex64)


def map_i_membership_bound(dimension, cardinality, queries=1):
    """Union bound for fixed sets/queries and IID Rademacher coordinates.

    Score threshold 1/2 on dot(bundle, atom)/D. Conditional on query atom,
    centered score is sum of at most D*n independent signs divided by D.
    One-sided Hoeffding bound exp(-D/(8*n)); conservative for members.
    """
    if any(type(x) is not int or x < 1 for x in (dimension,cardinality,queries)): raise ValueError('positive integer required')
    return min(1., queries*math.exp(-dimension/(8*cardinality)))


def intersection_variance(dimension, n, m, overlap):
    if any(type(x) is not int for x in (dimension,n,m,overlap)) or dimension<1 or min(n,m,overlap)<0 or overlap>min(n,m): raise ValueError('invalid cardinalities')
    return (n*m+overlap*overlap-2*overlap)/dimension


class IndexedMAP:
    """Rematerialized indexed-IID bank; reversible integer sum; not truth store.

    Caller tracks identity/set semantics. Updates validate active-set membership,
    capacity and integer width; unlike packed majority, exact removal is possible.
    """
    def __init__(self, dimension, seed, capacity):
        self.spec = CodebookSpec(dimension, seed)
        if type(capacity) is not int or not 1 <= capacity <= 32767: raise ValueError('capacity')
        self.capacity = capacity
        self._sum = np.zeros(dimension,dtype=np.int16)
        self._ids = set()
    def _atom(self, i):
        return 1-2*self.spec.bits(1,start=i)[0].astype(np.int16)
    def add(self, i):
        a = self._atom(i)
        if i in self._ids or len(self._ids)>=self.capacity: raise ValueError('duplicate/full')
        self._sum += a
        self._ids.add(i)
    def remove(self, i):
        a = self._atom(i)
        if i not in self._ids: raise ValueError('unknown member')
        self._sum -= a
        self._ids.remove(i)
    def score(self, i):
        return int(np.dot(self._sum.astype(np.int64), self._atom(i).astype(np.int64)))/self.spec.dimension
    @property
    def accumulator(self): return _immutable(self._sum)
    def estimate_intersection(self, other):
        if not isinstance(other, IndexedMAP) or other.spec != self.spec: raise ValueError('incompatible codebook')
        return int(np.dot(self._sum.astype(np.int64), other._sum.astype(np.int64)))/self.spec.dimension
    def accounting(self):
        # Logical portable payload, not process RSS. Count IDs explicitly.
        return {'counter_bytes': self._sum.nbytes, 'member_id_bytes': 4*len(self._ids), 'descriptor_bytes': 16,
                'payload_bytes': self._sum.nbytes+4*len(self._ids)+16}


@dataclass(frozen=True)
class StreamedNysHD:
    """Same Gaussian hyperplane rounding, regenerated by blocks instead of resident W.

    Only the eigensystem factor and replay descriptor persist. Packed output is
    filled directly. Fixed block size is a runtime parameter, not a new encoder.
    """
    inverse_root: np.ndarray
    dimension: int
    seed: int
    def __post_init__(self):
        r = _real(self.inverse_root, 2)
        if (not 1 <= r.shape[1] <= r.shape[0] <= 256 or type(self.dimension) is not int
            or not 1 <= self.dimension <= 65536 or type(self.seed) is not int or not 0 <= self.seed < 2**64):
            raise ValueError('stream descriptor')
        object.__setattr__(self,'inverse_root',_immutable(r))
    @classmethod
    def fit(cls, gram, dimension, seed, rtol=1e-10):
        return cls(_factor(gram,dimension,seed,rtol),dimension,seed)
    def packed(self, cross, block=128):
        c = _real(cross,2)
        r = self.inverse_root
        if c.shape[1]!=r.shape[0] or len(c)*self.dimension>MAX_ELEMENTS or type(block) is not int or not 8<=block<=1024 or block%8:
            raise ValueError('stream input/budget')
        f = c@r
        if not np.isfinite(f).all() or np.any(np.linalg.norm(f,axis=1)<=1e-14):raise ValueError('degenerate features')
        out=np.zeros((len(c),(self.dimension+7)//8),np.uint8)
        rng=np.random.default_rng(self.seed)
        for start in range(0,self.dimension,block):
            size=min(block,self.dimension-start)
            w=rng.normal(size=(size,r.shape[1]));w/=np.linalg.norm(w,axis=1,keepdims=True)
            p=w@r.T
            v=c@p.T
            if not np.isfinite(v).all():raise ValueError('projection overflow')
            out[:,start//8:(start+size+7)//8]=np.packbits(v<0,axis=1,bitorder='little')
        return out
    @property
    def nbytes(self):return self.inverse_root.nbytes+16 # dimension/seed descriptor
