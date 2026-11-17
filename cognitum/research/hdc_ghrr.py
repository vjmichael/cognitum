"""CPU GHRR research algebra and resident flattened scoring.

Yeung et al., arXiv:2405.09689v2, sec III/IV; Chung et al.,
arXiv:2611.16363v1, sec 2.4-2.6. Independently implemented.
Not an authorized runtime route or an accelerator implementation.
"""
from dataclasses import dataclass
import numpy as np

_MAX_ELEMENTS = 8_388_608

@dataclass(frozen=True)
class GHRRSpec:
    dimension: int
    width: int
    precision: str = 'complex64'

    def __post_init__(self):
        if (type(self.dimension) is not int or not 1 <= self.dimension <= 65536
            or type(self.width) is not int or not 1 <= self.width <= 8
            or self.dimension * self.width**2 > 65536
            or self.precision not in ('complex64', 'complex128')):
            raise ValueError('invalid GHRR dimension, complexity or precision')

    @property
    def family(self): return 'GHRR'
    @property
    def dtype(self): return np.dtype(self.precision)
    @property
    def shape(self): return (self.dimension, self.width, self.width)
    @property
    def scalar_count(self): return self.dimension * self.width**2
    @property
    def nbytes(self): return self.scalar_count * self.dtype.itemsize
    @property
    def unit_tol(self): return 3e-5 if self.precision == 'complex64' else 1e-10

    def checked(self, a):
        a = np.asarray(a)
        if a.shape != self.shape or a.dtype != self.dtype or not np.isfinite(a).all():
            raise ValueError('invalid GHRR shape/dtype/finite operands')
        return a

    def checked_bank(self, a):
        a = np.asarray(a)
        if (a.ndim != 4 or a.shape[1:] != self.shape or a.dtype != self.dtype
            or not 1 <= len(a) <= 4096 or a.size > _MAX_ELEMENTS or not np.isfinite(a).all()):
            raise ValueError('invalid GHRR bank or budget')
        return a

    def identity(self):
        return np.broadcast_to(np.eye(self.width, dtype=self.dtype), self.shape).copy()

    def unitary(self, a):
        a = self.checked(a).astype(np.complex128)
        return bool(np.max(np.abs(a.conj().swapaxes(-1,-2) @ a - np.eye(self.width))) <= self.unit_tol)

    def random_atoms(self, count, seed):
        if (type(count) is not int or not 1 <= count <= 4096
            or count * self.scalar_count > _MAX_ELEMENTS
            or type(seed) is not int or not 0 <= seed < 2**64):
            raise ValueError('invalid atom count/seed/budget')
        r = np.random.default_rng(seed)
        # Complex Gaussian QR with phase correction gives Haar unitary blocks.
        shape = (count, *self.shape)
        q, triangular = np.linalg.qr(r.normal(size=shape) + 1j*r.normal(size=shape))
        diag = np.diagonal(triangular, axis1=-2, axis2=-1)
        if (np.abs(diag)==0).any(): raise ValueError('degenerate QR')
        return self.checked_bank((q * (diag/np.abs(diag))[...,None,:]).astype(self.dtype))

    def bind(self, a, b): return self.checked(self.checked(a) @ self.checked(b))

    def inverse(self, a):
        a = self.checked(a)
        if not self.unitary(a): raise ValueError('adjoint inverse requires unitary blocks')
        return a.conj().swapaxes(-1,-2).copy()

    def unbind(self, role, bound, *, side):
        inv = self.inverse(role)
        if side == 'left': return self.bind(inv, bound)
        if side == 'right': return self.bind(bound, inv)
        raise ValueError('explicit left/right unbind required')

    def bundle(self, rows):
        return self.checked(self.checked_bank(rows).sum(axis=0, dtype=self.dtype))

    def permute(self, a, shift):
        if type(shift) is not int: raise ValueError('invalid shift')
        return np.roll(self.checked(a), shift % self.dimension, axis=0)

    def encode(self, x, theta, q):
        """Q_j diag(exp(i theta_j x)); Q fixed across data points in this map."""
        q = self.checked(q)
        x, theta = np.asarray(x), np.asarray(theta)
        if (x.dtype != np.float64 or x.ndim != 1 or not 1 <= x.size <= 128
            or theta.dtype != np.float64 or theta.shape != (self.dimension,self.width,x.size)
            or theta.size > _MAX_ELEMENTS or not np.isfinite(x).all() or not np.isfinite(theta).all()
            or not self.unitary(q)):
            raise ValueError('invalid encoder inputs')
        angles = theta @ x
        if not np.isfinite(angles).all(): raise ValueError('nonfinite encoder phase')
        return self.checked((q * np.exp(1j*angles)[:,None,:]).astype(self.dtype))

    def flatten(self, a):
        # A view where input layout permits, never an algebraic change of type.
        return np.ascontiguousarray(self.checked(a)).reshape(-1)

    def similarity(self, a, b, *, policy='fixed'):
        """Exact real Frobenius inner product; fixed scale vs cosine are explicit."""
        x, y = self.flatten(a).astype(np.complex128), self.flatten(b).astype(np.complex128)
        num = np.vdot(x,y).real
        if policy == 'fixed': den = self.dimension*self.width
        elif policy == 'cosine':
            den = np.linalg.norm(x)*np.linalg.norm(y)
            if den == 0: raise ValueError('undefined zero cosine')
        else: raise ValueError('unknown similarity policy')
        result = float(num/den)
        if not np.isfinite(result): raise ValueError('nonfinite similarity')
        return result

    def matrix_similarity(self, a, b, *, policy='fixed'):
        # Independent direct matrix trace; intentionally not the fast path.
        a, b = self.checked(a).astype(np.complex128), self.checked(b).astype(np.complex128)
        num = np.trace(a @ b.conj().swapaxes(-1,-2),axis1=-2,axis2=-1).sum().real
        if policy == 'fixed': den = self.dimension*self.width
        elif policy == 'cosine':
            den = np.linalg.norm(a)*np.linalg.norm(b)
            if den == 0: raise ValueError('undefined zero cosine')
        else: raise ValueError('unknown similarity policy')
        result = float(num/den)
        if not np.isfinite(result): raise ValueError('nonfinite similarity')
        return result

class FlatBank:
    """Resident real interleaved bank; copies input, rejects empty/zero cosine.
    Fixed-order IDs are indices only. No fact authority, mutable index or routing.
    Reference float64 or explicit native precision; storage is explicitly accounted.
    """
    def __init__(self, spec, rows, *, policy='fixed', accumulator='reference'):
        if not isinstance(spec,GHRRSpec): raise ValueError('GHRR spec required')
        if policy not in ('fixed','cosine'): raise ValueError('unknown policy')
        if accumulator not in ('reference','native'): raise ValueError('unknown accumulation policy')
        self.spec, self.policy = spec,policy
        self._complex_dtype = np.dtype('complex128') if accumulator=='reference' else spec.dtype
        self._real_dtype = np.dtype('float32') if self._complex_dtype==np.complex64 else np.dtype('float64')
        bank = np.ascontiguousarray(spec.checked_bank(rows), dtype=self._complex_dtype).reshape(len(rows),-1)
        # bytes-backed immutable storage, no shared caller operand alias.
        real = bank.view(self._real_dtype)
        self._real = np.frombuffer(real.tobytes(),self._real_dtype).reshape(real.shape)
        norms = np.linalg.norm(self._real,axis=1) if policy=='cosine' else None
        if norms is not None and ((norms==0).any() or not np.isfinite(norms).all()):
            raise ValueError('undefined or nonfinite bank norm')
        self._norms = None if norms is None else np.frombuffer(norms.tobytes(),self._real_dtype)

    @property
    def nbytes(self):
        return self._real.nbytes + (0 if self._norms is None else self._norms.nbytes)

    def scores(self, query):
        q = self.spec.flatten(query).astype(self._complex_dtype).view(self._real_dtype)
        scores = self._real @ q
        if self.policy == 'fixed': scores /= self.spec.dimension*self.spec.width
        else:
            n = np.linalg.norm(q)
            if n==0 or not np.isfinite(n): raise ValueError('undefined or nonfinite query norm')
            scores /= self._norms*n
        if not np.isfinite(scores).all(): raise ValueError('nonfinite scores')
        return scores

    def topk(self, query, k=1):
        if type(k) is not int or not 1<=k<=len(self._real): raise ValueError('invalid k')
        scores = self.scores(query)
        ids = np.argsort(-scores,kind='stable')[:k]
        return ids,scores[ids]
