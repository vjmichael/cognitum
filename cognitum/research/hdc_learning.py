"""Bounded research learning references, independent of production routing.

Batch semantics are explicit: predictions are evaluated on the pre-batch
state, then all class contributions are accumulated. For online single-example
semantics supply batch size one. No score is a calibrated probability.
"""
from __future__ import annotations
import math
import numpy as np

MAX_ELEMENTS = 8_000_000


def _matrix(a, *, complex_ok=True):
    a = np.asarray(a)
    allowed = (np.float32, np.float64, np.complex64, np.complex128) if complex_ok else (np.float32, np.float64)
    if a.ndim != 2 or not all(a.shape) or a.size > MAX_ELEMENTS or a.dtype.type not in allowed or not np.isfinite(a).all():
        raise ValueError('invalid bounded finite matrix')
    return a


def _labels(y, n, c):
    y = np.asarray(y)
    if y.shape != (n,) or y.dtype.kind not in 'iu' or np.any(y < 0) or np.any(y >= c):
        raise ValueError('invalid class labels')
    return y.astype(np.intp, copy=False)


def cosine_scores(x, w):
    x, w = _matrix(x), _matrix(w)
    if x.shape[1] != w.shape[1] or x.dtype != w.dtype or x.shape[0]*w.shape[0] > MAX_ELEMENTS:
        raise ValueError('incompatible score matrices')
    # Accumulate in at least float64; real part of Hermitian product for FHRR.
    a = x.astype(np.complex128 if np.iscomplexobj(x) else np.float64)
    b = w.astype(a.dtype)
    with np.errstate(over='raise', invalid='raise'):
        den = np.linalg.norm(a, axis=1)[:,None]*np.linalg.norm(b, axis=1)[None,:]
        dot = (a @ b.conj().T).real
        result = dot / np.maximum(den, 1e-8)
    if not np.isfinite(result).all():
        raise ValueError('nonfinite scores')
    return np.clip(result, -1, 1)


class Prototype:
    """Vanilla, fixed-rate mistake correction, cosine-weighted online, and
    margin-violation correction (independent reference, not RefineHD replication)."""
    def __init__(self, classes, dimensions, dtype=np.float32):
        if type(classes) is not int or type(dimensions) is not int or not 2 <= classes <= 4096 or not 1 <= dimensions <= 65536 or classes*dimensions > MAX_ELEMENTS:
            raise ValueError('invalid prototype shape')
        self._w = _matrix(np.zeros((classes, dimensions), dtype=dtype))
        self.updates = 0

    @property
    def weights(self):
        return self._w.copy()

    def scores(self, x):
        return cosine_scores(x, self._w)

    def update(self, x, y, *, rule='vanilla', lr=1., margin=.1):
        x = _matrix(x)
        c, d = self._w.shape
        if x.shape[1] != d or x.dtype != self._w.dtype:
            raise ValueError('encoding mismatch')
        y = _labels(y, len(x), c)
        if rule not in ('vanilla','adapt','online','margin') or not math.isfinite(lr) or not 0 < lr <= 100 or not math.isfinite(margin) or not 0 <= margin <= 2:
            raise ValueError('invalid learning policy')
        w = self._w.copy()
        if rule == 'vanilla':
            with np.errstate(over='raise',invalid='raise'):
                np.add.at(w, y, lr*x)
            count = len(x)
        else:
            s = self.scores(x)
            p = np.argmax(s, axis=1)
            if rule == 'margin':
                other=s.copy();other[np.arange(len(y)),y]=-np.inf
                p=np.argmax(other,axis=1)
                use=s[np.arange(len(y)),y]-s[np.arange(len(y)),p]<margin
            else:
                use=p!=y
            q=x[use]; t=y[use]; f=p[use]; scores=s[use]; ix=np.arange(len(q))
            a=1-scores[ix,t] if rule=='online' else np.ones(len(q))
            b=scores[ix,f]-1 if rule=='online' else -np.ones(len(q))
            with np.errstate(over='raise',invalid='raise'):
                np.add.at(w,t,(lr*a[:,None]*q).astype(w.dtype))
                np.add.at(w,f,(lr*b[:,None]*q).astype(w.dtype))
            count=len(q)
        if not np.isfinite(w).all():
            raise ValueError('nonfinite update')
        self._w=w; self.updates+=count
        return count

    def reset_dimensions(self, indices):
        i=np.asarray(indices)
        if i.ndim!=1 or not len(i) or i.dtype.kind not in 'iu' or np.any(i<0) or np.any(i>=self._w.shape[1]) or len(np.unique(i))!=len(i):
            raise ValueError('invalid reset indices')
        self._w[:,i]=0

    def predict(self,x,*,min_score=-1.,min_margin=0.):
        if not math.isfinite(min_score) or not -1<=min_score<=1 or not math.isfinite(min_margin) or not 0<=min_margin<=2:
            raise ValueError('invalid abstention thresholds')
        x=_matrix(x);s=self.scores(x);p=s.argmax(1);ix=np.arange(len(s));best=s[ix,p];s[ix,p]=-np.inf;gap=best-s.max(1)
        accept=(best>=min_score)&(gap>min_margin)&(np.linalg.norm(x,axis=1)>0)&(np.linalg.norm(self._w[p],axis=1)>0)
        return np.where(accept,p,-1)


class RandomFeatures:
    """Explicit sinusoid, linear projection and unit-phase encoders.

    Parameters may be imported from a native initialized encoder for matched
    controls; replacement uses assignment, not in-place ops on advanced-index
    temporaries. FHRR phases are an independent learning experiment.
    """
    def __init__(self, projection, bias=None, *, kind='sinusoid'):
        w=_matrix(projection,complex_ok=False)
        if kind not in ('sinusoid','linear','phase'):
            raise ValueError('unknown encoder kind')
        b=np.zeros(w.shape[0],w.dtype) if bias is None else np.asarray(bias)
        if b.shape!=(len(w),) or b.dtype!=w.dtype or not np.isfinite(b).all():raise ValueError('invalid bias')
        self._w=w.copy();self._b=b.copy();self.kind=kind

    @classmethod
    def seeded(cls, features, dimensions, seed, *, kind='sinusoid', dtype=np.float32):
        if type(features) is not int or type(dimensions) is not int or min(features,dimensions)<1 or features*dimensions>MAX_ELEMENTS:
            raise ValueError('encoder shape budget')
        r=np.random.default_rng(seed);w=r.normal(size=(dimensions,features)).astype(dtype)
        w/=np.maximum(np.linalg.norm(w,axis=1,keepdims=True),1e-12)
        b=r.uniform(0,2*np.pi,dimensions).astype(dtype)
        return cls(w,b,kind=kind)

    def state(self):
        return self._w.copy(),self._b.copy()

    def encode(self,x):
        x=_matrix(x,complex_ok=False)
        if x.shape[1]!=self._w.shape[1] or x.dtype!=self._w.dtype or len(x)*len(self._w)>MAX_ELEMENTS:
            raise ValueError('encoder input mismatch')
        with np.errstate(over='raise',invalid='raise'):
            p=x@self._w.T
            if self.kind=='linear':out=p
            elif self.kind=='phase':out=np.exp(1j*(p+self._b))
            else:out=np.cos(p+self._b)*np.sin(p)
        return _matrix(out)

    def regenerate(self,indices,rng,model):
        i=np.asarray(indices)
        if not isinstance(model,Prototype) or model.weights.shape[1]!=len(self._w) or model.weights.dtype!=self.encode(np.zeros((1,self._w.shape[1]),self._w.dtype)).dtype:
            raise ValueError('incompatible prototype')
        if i.ndim!=1 or not len(i) or i.dtype.kind not in 'iu' or np.any(i<0) or np.any(i>=len(self._w)) or len(np.unique(i))!=len(i):raise ValueError('invalid regeneration indices')
        w=rng.normal(size=(len(i),self._w.shape[1])).astype(self._w.dtype)
        b=rng.uniform(0,2*np.pi,len(i)).astype(self._b.dtype)
        if not np.isfinite(w).all() or not np.isfinite(b).all():raise ValueError('invalid regenerated parameters')
        model.reset_dimensions(i);self._w[i]=w;self._b[i]=b


def normalized_prototypes(w):
    w=_matrix(w);return w/np.maximum(np.linalg.norm(w,axis=1,keepdims=True),1e-12)


def neural_regeneration_scores(w):
    """Variance across L2-normalized class prototypes, sample variance."""
    w=_matrix(w,complex_ok=False)
    if len(w)<2:raise ValueError('at least two classes')
    return np.var(normalized_prototypes(w),axis=0,ddof=1)


def dist_regeneration_scores(x,y,w,*,alpha=.5,beta=1.,theta=.25):
    """DistHD partial/complete misclassification distance contributions.
    Stable low-index ties are explicit; compare native only on untied scores.
    All-correct batches return a vector of zeros, not a scalar."""
    x,w=_matrix(x,complex_ok=False),_matrix(w,complex_ok=False)
    if len(w)<2 or not all(math.isfinite(z) and z>=0 for z in (alpha,beta,theta)):
        raise ValueError('invalid DistHD inputs')
    y=_labels(y,len(x),len(w));s=cosine_scores(x,w)
    p=np.argsort(-s,axis=1,kind='stable')[:,:2];bad=p[:,0]!=y;x=x[bad];y=y[bad];p=p[bad];w=normalized_prototypes(w)
    first=np.abs(w[p[:,0]]-x);second=np.abs(w[p[:,1]]-x);target=np.abs(w[y]-x);partial=p[:,1]==y
    return .5*np.sum(beta*first[partial]-alpha*target[partial],axis=0)+np.sum(beta*first[~partial]+theta*second[~partial]-alpha*target[~partial],axis=0)


def density_ridge(x,y,classes,alpha=1.,*,cutoff="native_rank"):
    """TorchHD intRVFL readout equation: variance-scaled diagonal ridge,
    not conventional alpha*I. Real encoded operands, sample variance.
    native_rank uses PyTorch default relative cutoff D*eps(input_dtype)
    with float64 accumulation; full_rank uses NumPy default 1e-15.
    Neither policy guarantees bitwise native predictions."""
    x=_matrix(x,complex_ok=False)
    if type(classes) is not int or not 2<=classes<=4096 or len(x)<2 or x.shape[1]>2048 or classes*x.shape[1]>MAX_ELEMENTS or len(x)*classes>MAX_ELEMENTS or not math.isfinite(alpha) or alpha<0:raise ValueError('ridge budget')
    if cutoff not in ('native_rank','full_rank'):raise ValueError('invalid pseudoinverse cutoff')
    y=_labels(y,len(x),classes);a=x.astype(np.float64);t=np.eye(classes)[y]
    gram=a.T@a+alpha*np.diag(a.var(0,ddof=1))
    rcond=x.shape[1]*np.finfo(x.dtype).eps if cutoff=='native_rank' else 1e-15
    w=(t.T@a@np.linalg.pinv(gram,rcond=rcond)).astype(x.dtype)
    if not np.isfinite(w).all():raise ValueError('nonfinite readout')
    return w
