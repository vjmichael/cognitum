"""Bounded real trigonometric VFA algebra, research only.

f(x) = c0 + 2 Re sum_{k=1}^K c[k] exp(ikx), period 2*pi.
Normalized circular convolution multiplies modes; pointwise product convolves
modes. Full-spectrum multiplication does not silently truncate. Residual
bounds are analytic real-arithmetic bounds evaluated in float64, not certified
floating-point enclosures. This is a deterministic companion to random FPE,
not an assertion that random fixed-dimensional hypervectors have closed products.
"""
from dataclasses import dataclass
import math
import numpy as np

MAX_MODE = 1024
MAX_GRID = 16384
MAX_QUERY = 65536


def _real(x):
    if np.ndim(x) != 0 or np.iscomplexobj(x):
        raise ValueError('expected real scalar')
    a = float(x)
    if not math.isfinite(a):
        raise ValueError('nonfinite scalar')
    return a


def _order(k):
    if type(k) is not int or not 0 <= k <= MAX_MODE:
        raise ValueError('mode budget exceeded')
    return k


@dataclass(frozen=True, eq=False)
class Periodic:
    positive: np.ndarray

    def __post_init__(self):
        c = np.asarray(self.positive, dtype=np.complex128)
        if c.ndim != 1 or not 1 <= len(c) <= MAX_MODE + 1:
            raise ValueError('invalid coefficient shape')
        if not np.isfinite(c).all() or c[0].imag != 0:
            raise ValueError('invalid real Fourier coefficients')
        # bytes-backed snapshot: callers cannot re-enable writes.
        object.__setattr__(self, 'positive', np.frombuffer(c.tobytes(), dtype=np.complex128))

    @property
    def order(self):
        return len(self.positive) - 1

    @property
    def full(self):
        return np.r_[self.positive[:0:-1].conj(), self.positive]

    @classmethod
    def constant(cls, value):
        return cls([_real(value)])

    @classmethod
    def from_grid(cls, values, order):
        """Equispaced values at 2*pi*j/N; sample projection, not exact for arbitrary functions."""
        order = _order(order)
        a = np.asarray(values)
        if a.ndim != 1 or not 2*order+1 <= a.size <= MAX_GRID or np.iscomplexobj(a):
            raise ValueError('invalid or undersampled grid')
        a = a.astype(np.float64)
        if not np.isfinite(a).all():
            raise ValueError('nonfinite samples')
        c = np.fft.rfft(a)[:order+1] / len(a)
        c[0] = c[0].real
        return cls(c)

    def evaluate(self, x):
        a = np.asarray(x)
        if np.iscomplexobj(a) or a.size > MAX_QUERY:
            raise ValueError('invalid query')
        a = a.astype(np.float64)
        if not np.isfinite(a).all():
            raise ValueError('nonfinite query')
        out = np.empty(a.size)
        flat = a.ravel()
        k = np.arange(1, self.order+1)
        for i in range(0, a.size, 128):
            out[i:i+128] = self.positive[0].real + 2*(np.exp(1j*np.remainder(flat[i:i+128,None], 2*np.pi)*k) @ self.positive[1:]).real
        if not np.isfinite(out).all():
            raise ValueError('evaluation overflow')
        out = out.reshape(a.shape)
        return out.item() if a.ndim == 0 else out

    def _pad(self, k):
        return np.pad(self.positive, (0,k-self.order))

    def __add__(self, other):
        if not isinstance(other, Periodic): return NotImplemented
        k = max(self.order, other.order)
        return Periodic(self._pad(k) + other._pad(k))

    def __sub__(self, other):
        if not isinstance(other, Periodic): return NotImplemented
        return self + other.scale(-1)

    def scale(self, a):
        return Periodic(self.positive * _real(a))

    def shift(self, a):
        """f(x-a)."""
        return Periodic(self.positive * np.exp(-1j*np.arange(self.order+1)*np.remainder(_real(a),2*np.pi)))

    def multiply(self, other):
        """Pointwise product. Retains every generated frequency or refuses."""
        if not isinstance(other, Periodic): raise TypeError('expected Periodic')
        k = _order(self.order + other.order)
        full = np.convolve(self.full, other.full)
        # Both halves are redundant; DC is mathematically real.
        c = full[k:].copy()
        c[0] = c[0].real
        return Periodic(c)

    def convolve(self, other):
        """(1/2pi) integral_0^2pi f(x-y) g(y) dy."""
        if not isinstance(other, Periodic): raise TypeError('expected Periodic')
        n = min(self.order, other.order)+1
        return Periodic(self.positive[:n] * other.positive[:n])

    def derivative(self, n=1):
        if type(n) is not int or not 0 <= n <= 8:
            raise ValueError('invalid derivative order')
        c = self.positive * (1j*np.arange(self.order+1))**n
        c[0] = c[0].real
        return Periodic(c)

    def antiderivative(self):
        """Zero-mean periodic primitive exists only for zero DC."""
        if self.positive[0] != 0:
            raise ValueError('nonzero mean has no periodic primitive')
        c = self.positive.copy()
        c[1:] /= 1j*np.arange(1,self.order+1)
        return Periodic(c)

    def integral(self, a, b):
        a,b = _real(a),_real(b)
        c = self.positive.copy(); c[0] = 0
        g = Periodic(c).antiderivative()
        return _real(self.positive[0].real*(b-a) + g.evaluate(b)-g.evaluate(a))

    def compose_affine(self, winding, offset=0):
        """f(m*x+b), m integer only; exact retained frequency expansion."""
        if type(winding) is not int or abs(winding)>MAX_MODE:
            raise ValueError('invalid winding')
        b = _real(offset)
        if winding == 0: return Periodic.constant(self.evaluate(b))
        k = _order(abs(winding)*self.order)
        rotated = self.shift(-b).positive
        c = np.zeros(k+1, dtype=complex)
        c[::abs(winding)] = rotated if winding > 0 else rotated.conj()
        return Periodic(c)

    def sup_bound(self):
        return _real(abs(self.positive[0]) + 2*np.sum(np.abs(self.positive[1:])))

    def separation_bound(self):
        """Sufficient, not necessary, lower bound on |f| everywhere."""
        return _real(abs(self.positive[0]) - 2*np.sum(np.abs(self.positive[1:])))

    def truncate(self, order):
        order = _order(order)
        tail = _real(2*np.sum(np.abs(self.positive[order+1:])))
        return Periodic(self.positive[:order+1]), tail

    def parseval_energy(self):
        return _real(abs(self.positive[0])**2 + 2*np.sum(np.abs(self.positive[1:])**2))

    def divide(self, other, *, order, grid, max_error):
        """Approximate pointwise quotient with global coefficient residual check.

        If |g| >= delta > 0, |f/g-q| <= ||f-gq||_inf / delta.
        The triangle bound on residual modes is independent of the fitting grid.
        This is not a directed-rounding interval certificate.
        """
        if not isinstance(other, Periodic): raise TypeError('expected Periodic')
        order = _order(order); _order(order + other.order)
        tol = _real(max_error)
        if tol <= 0 or type(grid) is not int or not max(2*order+1, 2*self.order+1, 2*other.order+1) <= grid <= MAX_GRID:
            raise ValueError('invalid quotient budget')
        delta = other.separation_bound()
        # Guard cancellation and vanishing denominators; conservative refusal.
        if delta <= max(np.finfo(float).tiny, 64*np.finfo(float).eps*other.sup_bound()):
            raise ValueError('denominator not safely separated from zero')
        x = 2*np.pi*np.arange(grid)/grid
        q = Periodic.from_grid(self.evaluate(x)/other.evaluate(x), order)
        residual = (self - other.multiply(q)).sup_bound()
        bound = _real(residual/delta)
        if bound > tol:
            raise ValueError('quotient residual exceeds tolerance')
        return Quotient(q, delta, residual, bound)


@dataclass(frozen=True)
class Quotient:
    function: Periodic
    denominator_lower_bound: float
    residual_upper_bound: float
    error_bound_estimate: float
