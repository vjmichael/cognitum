"""Bounded, independent encoder tuning and packed RegHD prediction references."""
import numpy as np
from .hdc_learning import _matrix, MAX_ELEMENTS
from .hdc_regression import Encoder, _targets

class ScaledEncoder(Encoder):
    def __init__(self,features,dim,seed=0,kind='reghd',scale=1.):
        super().__init__(features,dim,seed,kind)
        if not np.isfinite(scale) or scale<=0:raise ValueError('scale')
        self.w*=scale
    def encode(self,x):
        x=_matrix(x,complex_ok=False)
        if x.shape[1]!=self.w.shape[0]:raise ValueError('shape')
        batch=max(1,MAX_ELEMENTS//self.w.shape[1])
        if len(x)*self.w.shape[1]>MAX_ELEMENTS:raise ValueError('output limit')
        return np.concatenate([super(ScaledEncoder,self).encode(x[i:i+batch]) for i in range(0,len(x),batch)])

class PackedRegHD:
    """Exact binary signs, optional per-head calibrated gains. No hidden float weights."""
    def __init__(self,c,w,threshold=0.):
        c=_matrix(c,complex_ok=False);w=_matrix(w,complex_ok=False)
        if c.shape!=w.shape or not np.isfinite(threshold):raise ValueError('shape or threshold')
        self.dim=c.shape[1];self.threshold=float(threshold)
        self.c=np.packbits(c>=threshold,axis=1,bitorder='little');self.w=np.packbits(w>=threshold,axis=1,bitorder='little');self.gain=np.ones(c.shape[0]);self.bias=0.
    def _components(self,h):
        h=_matrix(h,complex_ok=False)
        if h.shape[1]!=self.dim:raise ValueError('shape')
        b=np.packbits(h>=self.threshold,axis=1,bitorder='little')
        lut=np.array([int(i).bit_count() for i in range(256)],dtype=np.int32)
        def dot(p):
            if len(b)*len(p)*b.shape[1]>MAX_ELEMENTS:raise ValueError('packed score bounds')
            return self.dim-2*lut[np.bitwise_xor(b[:,None,:],p[None,:,:])].sum(2)
        s=dot(self.c)/self.dim;q=np.exp(s-s.max(1,keepdims=True));q/=q.sum(1,keepdims=True)
        return q*dot(self.w)
    def calibrate(self,h,y,alpha=1.):
        a=self._components(h);y=_targets(y,len(a))
        if not np.isfinite(alpha) or alpha<=0:raise ValueError('alpha')
        m=a.mean(0);v=a-m;gain=np.linalg.solve(v.T@v+alpha*np.eye(v.shape[1]),v.T@(y-y.mean()))
        self.gain=gain;self.bias=float(y.mean()-m@gain);return self
    def predict(self,h):return self._components(h)@self.gain+self.bias
    @property
    def nbytes(self):return self.c.nbytes+self.w.nbytes+self.gain.nbytes+16

class StreamingRidge:
    """Primal sufficient statistics with scalar-row encoding; intercept fitted.

    Budget accounts for encoder arrays, conservative explicit NumPy numeric
    workspace (including duplicate covariance for solve), excludes BLAS internals.
    Input data is external shared dataset custody, not counted in model budget.
    """
    def __init__(self,encoder,alpha,budget):
        if not np.isfinite(alpha) or alpha<=0 or type(budget) is not int or budget<1:raise ValueError('settings')
        self.encoder=encoder;self.alpha=alpha;self.budget=budget;d=encoder.w.shape[1]
        self.numeric_bound=encoder.nbytes+8*(4*d*d+16*d+16)
        if self.numeric_bound>budget:raise ValueError('budget')
    def fit(self,x,y):
        x=_matrix(x,complex_ok=False);y=_targets(y,len(x));d=self.encoder.w.shape[1];s=np.zeros(d);sy=np.zeros(d);g=np.zeros((d,d));my=float(y.mean())
        for v,t in zip(x,y):
            h=self.encoder.encode(v[None,:])[0];s+=h;sy+=h*(t-my);g+=np.outer(h,h)
        mu=s/len(x);g-=np.outer(s,mu);g.flat[::d+1]+=self.alpha;w=np.linalg.solve(g,sy)
        self.w=w;self.bias=float(my-mu@w);return self
    def predict(self,x):
        x=_matrix(x,complex_ok=False);return np.array([float(self.encoder.encode(v[None,:])[0]@self.w+self.bias) for v in x])
    @property
    def nbytes(self):return self.encoder.nbytes+self.w.nbytes+8
