"""Independent research prototype: random Fourier quadrature, not production HDC.
Convention F(w)=integral f(x) exp(iwx) dx; f(x)=Re integral F(w)exp(-iwx)dw/(2pi).
Uniform spectral samples on [-B,B]; decoder uses B/pi. Finite random quadrature.
No claim of an exact arbitrary-function algebra or fixed-point hardware equivalence.
"""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True, eq=False)
class Basis:
    omega: np.ndarray
    bandwidth: float
    def __post_init__(self):
        w=np.array(self.omega,dtype=np.float64,copy=True)
        b=float(self.bandwidth)
        if w.ndim!=1 or not 1<=w.size<=65536 or not np.isfinite(b) or b<=0 or not np.isfinite(w).all() or np.any(np.abs(w)>b):
            raise ValueError('invalid spectral basis')
        w=np.frombuffer(w.tobytes(),dtype=np.float64)
        object.__setattr__(self,'omega',w); object.__setattr__(self,'bandwidth',b)
    @classmethod
    def random(cls, dimension, bandwidth, seed):
        if type(dimension) is not int or not 1<=dimension<=65536 or not np.isfinite(bandwidth) or bandwidth<=0:
            raise ValueError('invalid dimension/bandwidth')
        return cls(np.random.default_rng(seed).uniform(-bandwidth,bandwidth,dimension),bandwidth)
    def encode(self,x):
        x=float(x)
        if not np.isfinite(x): raise ValueError('nonfinite coordinate')
        return np.exp(1j*self.omega*x)
    def from_samples(self, x, y):
        """Trapezoidal Fourier transform of sampled function; finite-domain truncation."""
        x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float)
        if x.ndim!=1 or not 2<=x.size<=16384 or y.shape!=x.shape or not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(np.diff(x)<=0): raise ValueError('invalid sample grid')
        dx=np.diff(x); weights=np.r_[dx[0]/2,(dx[:-1]+dx[1:])/2,dx[-1]/2]
        c=np.empty(self.omega.size,dtype=complex)
        for i in range(0,len(c),256):
            c[i:i+256]=np.exp(1j*self.omega[i:i+256,None]*x)@(weights*y)
        return Function(self,c)

@dataclass(frozen=True, eq=False)
class Function:
    basis: Basis
    coeff: np.ndarray
    def __post_init__(self):
        c=np.array(self.coeff,dtype=np.complex128,copy=True)
        if c.shape!=self.basis.omega.shape or not np.isfinite(c).all(): raise ValueError('invalid coefficients')
        c=np.frombuffer(c.tobytes(),dtype=np.complex128); object.__setattr__(self,'coeff',c)
    def evaluate(self,x):
        x=np.asarray(x,dtype=float)
        if x.size>65536 or not np.isfinite(x).all(): raise ValueError('invalid coordinate')
        out=np.empty(x.size)
        flat=x.ravel(); w=self.basis.omega
        for i in range(0,len(flat),128):
            out[i:i+128]=(np.exp(-1j*flat[i:i+128,None]*w)@self.coeff).real*(self.basis.bandwidth/(np.pi*len(w)))
        if not np.isfinite(out).all(): raise ValueError('evaluation overflow')
        out=out.reshape(x.shape)
        return out.item() if x.ndim==0 else out
    def _same(self, other):
        if not isinstance(other,Function) or self.basis.bandwidth!=other.basis.bandwidth or not np.array_equal(self.basis.omega,other.basis.omega): raise ValueError('incompatible bases')
    def __add__(self,other):
        self._same(other); return Function(self.basis,self.coeff+other.coeff)
    def __sub__(self,other):
        self._same(other); return Function(self.basis,self.coeff-other.coeff)
    def scale(self,a):
        a=float(a)
        if not np.isfinite(a): raise ValueError('nonfinite scale')
        return Function(self.basis,self.coeff*a)
    def translate(self,a):
        return Function(self.basis,self.coeff*self.basis.encode(a))
    def convolve(self,other):
        self._same(other); return Function(self.basis,self.coeff*other.coeff)
    def derivative(self):
        return Function(self.basis,-1j*self.basis.omega*self.coeff)
