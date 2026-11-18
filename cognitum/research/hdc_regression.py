"""Bounded continuous HDC research, no production routing.
Associative target prototypes, normalized online LMS and ridge on identical
RegHD-style features. Ridge gains are not attributed to HDC alone.
"""
import numpy as np
from .hdc_learning import _matrix, MAX_ELEMENTS

class Encoder:
    def __init__(self, features, dim, seed=0, kind='reghd'):
        if type(features) is not int or type(dim) is not int or min(features,dim)<1 or features*dim>MAX_ELEMENTS or kind not in ('reghd','rff'):
            raise ValueError('encoder bounds')
        rng=np.random.default_rng(seed); self.w=rng.normal(size=(features,dim));self.b=rng.uniform(0,2*np.pi,dim);self.kind=kind
    def encode(self,x):
        x=_matrix(x,complex_ok=False)
        if x.shape[1]!=self.w.shape[0] or x.shape[0]*self.w.shape[1]>MAX_ELEMENTS:raise ValueError('encoding bounds')
        z=x@self.w
        return np.cos(z+self.b)*np.sin(z) if self.kind=='reghd' else np.sqrt(2/self.w.shape[1])*np.cos(z+self.b)
    @property
    def nbytes(self):return self.w.nbytes+self.b.nbytes

def _targets(y,n):
    y=np.asarray(y,dtype=float)
    if y.shape!=(n,) or not np.all(np.isfinite(y)):raise ValueError('invalid targets')
    return y

def _cosine(x,p):
    return (x@p.T)/np.maximum(np.linalg.norm(x,axis=1)[:,None]*np.linalg.norm(p,axis=1),1e-12)

class Regression:
    def __init__(self,kind,*,alpha=1.,epochs=10,rate=.5,bins=8):
        if kind not in ('associative','lms','ridge') or not np.isfinite(alpha) or alpha<=0 or not 0<rate<=1 or type(epochs) is not int or not 1<=epochs<=1000 or type(bins) is not int or not 2<=bins<=256:raise ValueError('invalid settings')
        self.kind=kind;self.alpha=alpha;self.epochs=epochs;self.rate=rate;self.bins=bins
    def fit(self,h,y):
        h=_matrix(h,complex_ok=False);y=_targets(y,len(h));self.mean=float(y.mean()); yc=y-self.mean
        if self.kind=='associative':
            # target quantiles computed only on training data; duplicates collapsed
            cuts=np.unique(np.quantile(y,np.linspace(0,1,self.bins+1)[1:-1]));idx=np.searchsorted(cuts,y)
            groups=np.unique(idx);self.p=np.stack([h[idx==i].mean(0) for i in groups]);self.values=np.array([y[idx==i].mean() for i in groups]);
        elif self.kind=='lms':
            self.w=np.zeros(h.shape[1]);
            for _ in range(self.epochs):
                for v,t in zip(h,yc):self.w+=self.rate*(t-v@self.w)*v/max(v@v,1e-12)
        else:
            n,d=h.shape
            if min(n,d)**2>MAX_ELEMENTS:raise ValueError('solver bounds')
            self.w=(np.linalg.solve(h.T@h+self.alpha*np.eye(d),h.T@yc) if d<=n else h.T@np.linalg.solve(h@h.T+self.alpha*np.eye(n),yc))
        return self
    def predict(self,h):
        h=_matrix(h,complex_ok=False)
        if self.kind=='associative':
            s=8*_cosine(h,self.p);s-=s.max(1,keepdims=True);s=np.exp(s);return (s@self.values)/s.sum(1)
        return self.mean+h@self.w
    @property
    def nbytes(self):return 8+(self.p.nbytes+self.values.nbytes if self.kind=='associative' else self.w.nbytes)

def split_conformal(y,p,alpha=.1):
    p=np.asarray(p,dtype=float);y=_targets(y,len(p))
    if p.ndim!=1 or not np.isfinite(p).all() or not 0<alpha<1:raise ValueError('invalid calibration')
    k=int(np.ceil((len(y)+1)*(1-alpha)))
    return float(np.sort(np.abs(y-p))[k-1]) if k<=len(y) else float('inf')

def mixture_reference(h,y,initial,epochs,rate):
    """Independent RegHD-style fit on shared exact encoded operands and initial clusters."""
    h=_matrix(h,complex_ok=False);y=_targets(y,len(h));c=_matrix(initial,complex_ok=False).copy()
    if c.shape[1]!=h.shape[1] or not np.all(np.abs(c)==1) or not 0<rate<=1 or not 1<=epochs<=1000:raise ValueError('invalid mixture')
    w=np.zeros_like(c);b=c.copy()
    for _ in range(epochs):
        for v,t in zip(h,y):
            q=np.exp(b@np.where(v>=0,1.,-1.)/len(v));q/=q.sum()
            delta=t-q@(w@v);w+=rate*delta*q[:,None]*v
            j=np.argmax(q);c[j]+=(1-q[j])*v
        b=np.where(c>=0,1.,-1.)
    return c,w

def mixture_predict(h,c,w):
    h=_matrix(h,complex_ok=False);c=_matrix(c,complex_ok=False);w=_matrix(w,complex_ok=False)
    if c.shape!=w.shape or h.shape[1]!=c.shape[1]:raise ValueError('shape mismatch')
    s=np.where(h>=0,1.,-1.)@np.where(c>=0,1.,-1.).T/h.shape[1];q=np.exp(s-s.max(1,keepdims=True));q/=q.sum(1,keepdims=True)
    return np.sum(q*(h@w.T),axis=1)

class FisherSelector:
    """Independent train-only univariate ranking, not hdlib stepwise parity."""
    def __init__(self,k):
        if type(k) is not int or k<1:raise ValueError('feature count')
        self.k=k
    def fit(self,x,y):
        x=_matrix(x,complex_ok=False);y=np.asarray(y)
        if y.shape!=(len(x),) or y.dtype.kind not in 'iu' or self.k>x.shape[1]:raise ValueError('invalid labels or feature count')
        labels=np.unique(y)
        if len(labels)<2 or len(labels)>=len(x):raise ValueError('class count')
        m=x.mean(0);between=np.zeros(x.shape[1]);within=between.copy()
        for label in labels:
            g=x[y==label];mu=g.mean(0);between+=len(g)*(mu-m)**2;within+=np.sum((g-mu)**2,axis=0)
        self.scores=np.divide(between,within,out=np.where(between>0,np.inf,0.),where=within>0)
        self.indices=np.lexsort((np.arange(len(between)),-self.scores))[:self.k];self.features=x.shape[1];return self
    def transform(self,x):
        x=_matrix(x,complex_ok=False)
        if x.shape[1]!=self.features:raise ValueError('feature mismatch')
        return x[:,self.indices]
