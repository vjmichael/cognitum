"""Research-only Gaussian RKHS and FPE. Bounds are real-arithmetic estimates, not intervals."""
from dataclasses import dataclass
import math
import numpy as np

MAX_TERMS = 256
MAX_POINTS = 16384
MAX_FEATURES = 65536


def array(x, limit=MAX_POINTS):
    a = np.asarray(x)
    if np.iscomplexobj(a) or a.ndim != 1 or not 1 <= a.size <= limit:
        raise ValueError('invalid real vector')
    a = np.asarray(a, dtype=np.float64)
    if not np.isfinite(a).all() or np.any(np.abs(a) > 1e6):
        raise ValueError('nonfinite or out of range')
    return np.frombuffer(a.tobytes(), dtype=np.float64)


def length(x):
    if np.ndim(x) != 0 or np.iscomplexobj(x):
        raise ValueError('invalid length')
    x = float(x)
    if not 1e-3 <= x <= 1e3:
        raise ValueError('invalid length')
    return x


def kernel(x, y, ell):
    x, y, ell = array(x), array(y, MAX_TERMS), length(ell)
    return np.exp(-0.5*((x[:, None]-y)/ell)**2)


@dataclass(frozen=True, eq=False)
class Gaussian:
    centers: np.ndarray
    weights: np.ndarray
    widths: np.ndarray

    def __post_init__(self):
        c, w, s = (array(v, MAX_TERMS) for v in (self.centers, self.weights, self.widths))
        if not len(c) == len(w) == len(s) or np.any((s < 1e-3) | (s > 1e3)):
            raise ValueError('invalid Gaussian terms')
        for name, value in zip(('centers','weights','widths'), (c,w,s)):
            object.__setattr__(self, name, value)

    @classmethod
    def sections(cls, centers, weights, ell):
        return cls(centers, weights, np.full(np.size(centers), length(ell)))

    def evaluate(self, x):
        x = array(x)
        return np.exp(-0.5*((x[:, None]-self.centers)/self.widths)**2) @ self.weights

    def derivative(self, x):
        x = array(x)
        d = (x[:, None]-self.centers)/self.widths
        return (-d/self.widths*np.exp(-0.5*d*d)) @ self.weights

    def integral(self):
        return float(np.sqrt(2*np.pi)*self.weights @ self.widths)

    def scale(self, value):
        if np.ndim(value) or np.iscomplexobj(value) or not math.isfinite(float(value)):
            raise ValueError('invalid scale')
        return Gaussian(self.centers, self.weights*value, self.widths)

    def add(self, other):
        if len(self.centers)+len(other.centers)>MAX_TERMS:
            raise ValueError('term budget')
        return Gaussian(*(np.r_[getattr(self,k),getattr(other,k)] for k in ('centers','weights','widths')))

    def multiply(self, other):
        if len(self.centers)*len(other.centers)>MAX_TERMS:
            raise ValueError('term budget')
        a,b = self.centers[:,None],other.centers
        u,v = self.widths[:,None]**2,other.widths**2
        den = u+v
        c = (a*v+b*u)/den
        w = self.weights[:,None]*other.weights*np.exp(-0.5*(a-b)**2/den)
        return Gaussian(c.ravel(),w.ravel(),np.sqrt(u*v/den).ravel())

    def inner(self, other):
        ell = self.widths[0]
        if not np.all(self.widths == ell) or not np.all(other.widths == ell):
            raise ValueError('different RKHS section widths')
        return float(self.weights @ kernel(self.centers,other.centers,ell) @ other.weights)

    def norm(self):
        n = self.inner(self)
        if n < -1e-10*max(1.,float(np.sum(np.abs(self.weights)))**2):
            raise ValueError('negative squared norm')
        return math.sqrt(max(0.,n))


@dataclass(frozen=True, eq=False)
class Interpolator:
    function: Gaussian
    cholesky: np.ndarray
    condition: float

    @classmethod
    def fit(cls, x, y, ell):
        x,y,ell = array(x,MAX_TERMS),array(y,MAX_TERMS),length(ell)
        if x.shape != y.shape or len(np.unique(x))!=len(x):
            raise ValueError('duplicate sites or shape mismatch')
        k = kernel(x,x,ell)
        cond = float(np.linalg.cond(k))
        if not np.isfinite(cond) or cond > 1e9:
            raise ValueError('ill-conditioned interpolation')
        l = np.linalg.cholesky(k)
        a = np.linalg.solve(l.T,np.linalg.solve(l,y))
        return cls(Gaussian.sections(x,a,ell),np.frombuffer(l.tobytes(),dtype=float).reshape(l.shape),cond)

    def power(self, x):
        k = kernel(x,self.function.centers,self.function.widths[0])
        v = np.linalg.solve(self.cholesky,k.T)
        p2 = 1-np.sum(v*v,axis=0)
        if np.min(p2)<-1e-7:
            raise ValueError('negative power squared')
        return np.sqrt(np.maximum(0,p2))

    def error_bound(self, x, target_norm):
        if not math.isfinite(target_norm) or target_norm<0:
            raise ValueError('invalid supplied norm')
        # Norm is externally supplied, not inferred from sample labels.
        return target_norm*self.power(x)


@dataclass(frozen=True, eq=False)
class FPE:
    omega: np.ndarray
    ell: float

    def __post_init__(self):
        object.__setattr__(self,'omega',array(self.omega,MAX_FEATURES))
        object.__setattr__(self,'ell',length(self.ell))

    @classmethod
    def random(cls, dimension, ell, seed):
        if type(dimension) is not int or not 1<=dimension<=MAX_FEATURES:
            raise ValueError('dimension budget')
        ell=length(ell)
        return cls(np.random.default_rng(seed).normal(0,1/ell,dimension),ell)

    def similarity(self, differences):
        d=array(differences); out=np.empty(len(d))
        for i in range(0,len(d),max(1,262144//len(self.omega))):
            n=max(1,262144//len(self.omega))
            out[i:i+n]=np.cos(d[i:i+n,None]*self.omega).mean(axis=1)
        return out

    def encode_sections(self, f):
        if not np.all(f.widths==self.ell):
            raise ValueError('incompatible Gaussian width')
        c=np.zeros(len(self.omega),complex)
        for a,w in zip(f.centers,f.weights):
            c+=w*np.exp(1j*a*self.omega)
        return np.frombuffer(c.tobytes(),dtype=np.complex128)

    def evaluate(self, coeff, x):
        c=np.asarray(coeff,dtype=complex); x=array(x)
        if c.shape!=self.omega.shape or not np.isfinite(c).all():
            raise ValueError('invalid features')
        out=np.empty(len(x)); n=max(1,262144//len(c))
        for i in range(0,len(x),n):
            out[i:i+n]=(np.exp(-1j*x[i:i+n,None]*self.omega)@c).real/len(c)
        return out

    def finite_pair_bound(self, pairs, alpha):
        """Hoeffding union bound: IID Gaussian frequencies and fixed pairs only."""
        if type(pairs) is not int or pairs<=0 or not 0<alpha<1:
            raise ValueError('invalid confidence request')
        return min(2.,math.sqrt(2*(math.log(2)+math.log(pairs)-math.log(alpha))/len(self.omega)))
