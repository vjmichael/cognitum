"""Bounded diagonal Gaussian tensor-product function algebra; research only.

Exact identities refer to real arithmetic. Float64 evaluations and estimates
are not interval certificates. No production registration or hardware route.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.special import erf

MAX_DIM=8
MAX_TERMS=256
MAX_POINTS=4096
MAX_DEGREE=8
MAX_CONDITION=1e9


def _array(x, ndim, limit):
    a=np.asarray(x)
    if a.ndim!=ndim or np.iscomplexobj(a) or a.size>limit:
        raise ValueError('invalid array')
    a=np.asarray(a,dtype=np.float64)
    if not np.isfinite(a).all() or np.any(np.abs(a)>1e6):
        raise ValueError('nonfinite or excessive input')
    return np.frombuffer(a.tobytes(),dtype=np.float64).reshape(a.shape)


def _scalar(x):
    return float(_array(x,0,1))


def _widths(x,d):
    a=_array(x,1,MAX_DIM)
    if a.shape!=(d,) or not 1<=d<=MAX_DIM or np.any((a<1e-3)|(a>1e3)):
        raise ValueError('invalid widths')
    return a


def _points(x,d,limit=MAX_POINTS):
    a=_array(x,2,limit*MAX_DIM)
    if a.shape[1]!=d or len(a)>limit or not 1<=d<=MAX_DIM:
        raise ValueError('invalid point shape')
    return a


def tensor_kernel(x,y,widths):
    """Product of one-dimensional Gaussian kernels, for row-wise points."""
    ell=_array(widths,1,MAX_DIM);d=len(ell);ell=_widths(ell,d)
    x,y=_points(x,d),_points(y,d,MAX_TERMS)
    return np.prod(np.exp(-.5*((x[:,None,:]-y[None,:,:])/ell)**2),axis=-1)


@dataclass(frozen=True,eq=False)
class Mixture:
    centers:np.ndarray
    weights:np.ndarray
    widths:np.ndarray
    constant:float=0.

    def __post_init__(self):
        c=_array(self.centers,2,MAX_TERMS*MAX_DIM)
        w=_array(self.weights,1,MAX_TERMS)
        s=_array(self.widths,2,MAX_TERMS*MAX_DIM)
        if not 1<=c.shape[1]<=MAX_DIM or len(c)>MAX_TERMS or s.shape!=c.shape or w.shape!=(len(c),) or np.any((s<1e-3)|(s>1e3)):
            raise ValueError('invalid Gaussian mixture')
        for name,val in [('centers',c),('weights',w),('widths',s),('constant',_scalar(self.constant))]:
            object.__setattr__(self,name,val)

    @property
    def dim(self):return self.centers.shape[1]

    @classmethod
    def sections(cls,centers,weights,widths):
        ell=_array(widths,1,MAX_DIM);c=_points(centers,len(ell),MAX_TERMS)
        return cls(c,weights,np.broadcast_to(_widths(ell,len(ell)),c.shape))

    @classmethod
    def const(cls,d,value):
        if type(d)!=int or not 1<=d<=MAX_DIM:raise ValueError('dimension')
        return cls(np.empty((0,d)),np.empty(0),np.empty((0,d)),value)

    def _jet(self,x,order):
        x=_points(x,self.dim)
        n=len(x);d=self.dim
        val=np.full(n,self.constant);grad=np.zeros((n,d));hess=np.zeros((n,d,d))
        for i in range(0,n,64):
            a=x[i:i+64,None,:]-self.centers
            z=a/self.widths
            with np.errstate(under='ignore'):
                t=np.exp(-.5*np.sum(z*z,axis=-1))*self.weights
            val[i:i+64]+=t.sum(axis=1)
            if order:
                g=-a/self.widths**2
                grad[i:i+64]=np.einsum('nt,ntd->nd',t,g)
            if order==2:
                h=np.einsum('nt,ntd,nte->nde',t,g,g)
                h-=np.einsum('nt,td,de->nde',t,1/self.widths**2,np.eye(d))
                hess[i:i+64]=h
        if not all(np.isfinite(v).all() for v in (val,grad,hess)):raise ValueError('calculus overflow')
        return val,grad,hess

    def evaluate(self,x):return self._jet(x,0)[0]
    def gradient(self,x):return self._jet(x,1)[1]
    def hessian(self,x):return self._jet(x,2)[2]
    def laplacian(self,x):return np.trace(self.hessian(x),axis1=1,axis2=2)
    def sup_bound(self):return abs(self.constant)+float(np.sum(np.abs(self.weights)))

    def _same(self,b):
        if not isinstance(b,Mixture) or self.dim!=b.dim:raise ValueError('incompatible dimensions')

    def scale(self,a):
        a=_scalar(a);return Mixture(self.centers,self.weights*a,self.widths,self.constant*a)

    def add(self,b):
        self._same(b)
        if len(self.weights)+len(b.weights)>MAX_TERMS:raise ValueError('term budget')
        return Mixture(np.concatenate((self.centers,b.centers)),np.r_[self.weights,b.weights],np.concatenate((self.widths,b.widths)),self.constant+b.constant)

    def multiply(self,b):
        self._same(b);n,m=len(self.weights),len(b.weights)
        if n*m+(n if b.constant else 0)+(m if self.constant else 0)>MAX_TERMS:raise ValueError('product term budget')
        a,c=self.centers[:,None,:],b.centers[None,:,:]
        u,v=self.widths[:,None,:]**2,b.widths[None,:,:]**2
        den=u+v
        centers=((a*v+c*u)/den).reshape(-1,self.dim)
        widths=np.sqrt(u*v/den).reshape(-1,self.dim)
        w=(self.weights[:,None]*b.weights*np.exp(-.5*np.sum((a-c)**2/den,axis=-1))).ravel()
        f=Mixture(centers,w,widths,self.constant*b.constant)
        if b.constant:f=f.add(Mixture(self.centers,self.weights*b.constant,self.widths))
        if self.constant:f=f.add(Mixture(b.centers,b.weights*self.constant,b.widths))
        return f

    def polynomial(self,coefficients):
        """Horner expansion, coefficients in ascending power order; no truncation."""
        c=_array(coefficients,1,MAX_DEGREE+1)
        if not 1<=len(c)<=MAX_DEGREE+1:raise ValueError('polynomial degree')
        out=Mixture.const(self.dim,c[-1])
        for v in c[-2::-1]:out=out.multiply(self).add(Mixture.const(self.dim,v))
        return out

    def integral(self,lower=None,upper=None):
        """Whole-space or finite axis-aligned box; constant not L1 on R^d."""
        if lower is None and upper is None:
            if self.constant:raise ValueError('nonintegrable constant')
            val=(2*np.pi)**(self.dim/2)*np.dot(self.weights,np.prod(self.widths,axis=1))
        else:
            a,b=_array(lower,1,MAX_DIM),_array(upper,1,MAX_DIM)
            if a.shape!=(self.dim,) or b.shape!=a.shape or np.any(b<a):raise ValueError('invalid box')
            t=np.sqrt(np.pi/2)*self.widths*(erf((b-self.centers)/(np.sqrt(2)*self.widths))-erf((a-self.centers)/(np.sqrt(2)*self.widths)))
            val=np.dot(self.weights,np.prod(t,axis=1))+self.constant*np.prod(b-a)
        if not np.isfinite(val):raise ValueError('integral overflow')
        return float(val)

    def inner(self,b):
        self._same(b)
        if self.constant or b.constant:raise ValueError('constant not qualified in Gaussian RKHS')
        if not len(self.weights) or not len(b.weights):return 0.
        ell=self.widths[0]
        if not np.all(self.widths==ell) or not np.all(b.widths==ell):raise ValueError('different RKHS widths')
        return float(self.weights@tensor_kernel(self.centers,b.centers,ell)@b.weights)

    def norm(self):
        n=self.inner(self)
        if n < -1e-10*max(1.,float(np.sum(np.abs(self.weights)))**2):raise ValueError('negative norm squared')
        return math.sqrt(max(0,n))

    def sin_polynomial(self,degree=7):
        """Uniform real-arithmetic absolute remainder bound on all R^d."""
        if type(degree)!=int or degree not in (1,3,5,7):raise ValueError('unsupported Taylor degree')
        coef=np.zeros(degree+1)
        for k in range(1,degree+1,2):coef[k]=(-1)**((k-1)//2)/math.factorial(k)
        # next even coefficient is zero; Taylor theorem at order degree+1.
        bound=self.sup_bound()**(degree+2)/math.factorial(degree+2)
        return self.polynomial(coef),bound


@dataclass(frozen=True,eq=False)
class Composition:
    """Explicit outer function over inner-function outputs; not a single expansion."""
    outer:Mixture
    inner:tuple

    def __post_init__(self):
        if not isinstance(self.outer,Mixture):raise ValueError('invalid outer')
        v=tuple(self.inner)
        if len(v)!=self.outer.dim or not all(isinstance(f,Mixture) for f in v) or len({f.dim for f in v})!=1:raise ValueError('composition shape')
        object.__setattr__(self,'inner',v)

    def _jet(self,x,order):
        y=np.column_stack([f.evaluate(x) for f in self.inner]);val=self.outer.evaluate(y)
        if not order:return val,None,None
        j=np.stack([f.gradient(x) for f in self.inner],axis=1)
        g=self.outer.gradient(y)
        grad=np.einsum('ni,nid->nd',g,j)
        if order==1:return val,grad,None
        h=np.einsum('nij,nid,nje->nde',self.outer.hessian(y),j,j)
        h+=np.einsum('ni,nide->nde',g,np.stack([f.hessian(x) for f in self.inner],axis=1))
        if not np.isfinite(h).all():raise ValueError('composition overflow')
        return val,grad,h

    def evaluate(self,x):return self._jet(x,0)[0]
    def gradient(self,x):return self._jet(x,1)[1]
    def hessian(self,x):return self._jet(x,2)[2]
    def laplacian(self,x):return np.trace(self.hessian(x),axis1=1,axis2=2)


@dataclass(frozen=True,eq=False)
class TensorInterpolator:
    """Cartesian grid, separable solves; no full Kronecker matrix in fit or power."""
    function:Mixture
    axes:tuple
    factors:tuple
    condition:float

    @classmethod
    def fit(cls,axes,values,widths):
        axes=tuple(_array(a,1,MAX_TERMS) for a in axes);d=len(axes);ell=_widths(widths,d)
        shape=tuple(len(a) for a in axes)
        if not all(1<=n<=MAX_TERMS for n in shape) or math.prod(shape)>MAX_TERMS:raise ValueError('grid budget')
        if any(len(np.unique(a))!=len(a) for a in axes):raise ValueError('duplicate sites')
        y=_array(values,d,MAX_TERMS)
        if y.shape!=shape:raise ValueError('grid shape')
        factors=[];cond=1.;coef=y.copy()
        for k,(a,s) in enumerate(zip(axes,ell)):
            gram=np.exp(-.5*((a[:,None]-a)/s)**2)
            cond*=float(np.linalg.cond(gram))
            if not np.isfinite(cond) or cond>MAX_CONDITION:raise ValueError('ill-conditioned tensor grid')
            l=np.linalg.cholesky(gram);factors.append(_array(l,2,MAX_TERMS**2))
            t=np.moveaxis(coef,k,0);flat=t.reshape(len(a),-1)
            coef=np.moveaxis(np.linalg.solve(l.T,np.linalg.solve(l,flat)).reshape(t.shape),0,k)
        sites=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1).reshape(-1,d)
        return cls(Mixture.sections(sites,coef.ravel(),ell),axes,tuple(factors),cond)

    def power(self,x):
        x=_points(x,self.function.dim);prod=np.ones(len(x));ell=self.function.widths[0]
        for k,(a,l,s) in enumerate(zip(self.axes,self.factors,ell)):
            cross=np.exp(-.5*((x[:,k,None]-a)/s)**2)
            v=np.linalg.solve(l,cross.T);prod*=np.sum(v*v,axis=0)
        p2=1-prod
        if np.min(p2,initial=0)<-1e-7:raise ValueError('negative power squared')
        return np.sqrt(np.maximum(0,p2))

    def error_bound(self,x,target_norm):
        n=_scalar(target_norm)
        if n<0:raise ValueError('invalid externally supplied norm')
        return n*self.power(x)


@dataclass(frozen=True,eq=False)
class TensorFPE:
    """Joint IID Gaussian frequencies; coordinate binding represents addition.

    Kernel similarity estimates the tensor-product kernel, not a tensor product
    of D-sized arrays. Fixed coordinate pairs only for probability bounds.
    """
    omega:np.ndarray
    widths:np.ndarray

    def __post_init__(self):
        w=_array(self.omega,2,65536*MAX_DIM)
        if not 1<=len(w)<=65536:raise ValueError('feature dimension')
        object.__setattr__(self,'omega',w)
        object.__setattr__(self,'widths',_widths(self.widths,w.shape[1]))

    @classmethod
    def random(cls,dimension,widths,seed):
        if type(dimension)!=int or not 1<=dimension<=65536:raise ValueError('feature budget')
        ell=_array(widths,1,MAX_DIM);ell=_widths(ell,len(ell))
        return cls(np.random.default_rng(seed).normal(size=(dimension,len(ell)))/ell,ell)

    def encode(self,x):
        x=_array(x,1,MAX_DIM)
        if x.shape!=self.widths.shape:raise ValueError('coordinate shape')
        return np.exp(1j*(self.omega@x))

    def encode_sections(self,f):
        if not isinstance(f,Mixture) or f.dim!=len(self.widths) or f.constant or not np.all(f.widths==self.widths):raise ValueError('incompatible RKHS sections')
        out=np.zeros(len(self.omega),complex)
        for center,weight in zip(f.centers,f.weights):out+=weight*self.encode(center)
        return np.frombuffer(out.tobytes(),dtype=np.complex128)

    def evaluate(self,c,x):
        return self._decode(c,x,0)

    def gradient(self,c,x):
        return self._decode(c,x,1)

    def hessian(self,c,x):
        return self._decode(c,x,2)

    def _decode(self,c,x,order):
        c=np.asarray(c,dtype=complex);d=len(self.widths)
        if c.shape!=(len(self.omega),) or not np.isfinite(c).all():raise ValueError('invalid coefficient')
        x=_points(x,d);out=np.empty((len(x),)+(d,)*order)
        chunk=max(1,65536//len(c));w=self.omega
        for i in range(0,len(x),chunk):
            phase=np.exp(-1j*(x[i:i+chunk]@w.T))*c
            if order==0:out[i:i+chunk]=phase.real.mean(axis=1)
            elif order==1:out[i:i+chunk]=np.real(-1j*phase@w)/len(c)
            else:out[i:i+chunk]=np.real(-np.einsum('nk,kd,ke->nde',phase,w,w,optimize=True))/len(c)
        if not np.isfinite(out).all():raise ValueError('decode overflow')
        return out

    def finite_pair_bound(self,pairs,alpha):
        if type(pairs)!=int or pairs<=0 or not 0<alpha<1:raise ValueError('confidence request')
        return min(2.,math.sqrt(2*(math.log(2)+math.log(pairs)-math.log(alpha))/len(self.omega)))
