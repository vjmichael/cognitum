"""CPU research references L13-L16. Not production, no hardware performance claim.
THDC and Phase-HDC equations follow primary publications; schedule/encoding choices
are independent (see report). Arrays retained across steps are distinguished from
per-batch temporaries. No implicit network or dependencies beyond CPU torch/numpy.
"""
import math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

MAX=8_000_000

def _dims(features,bins,classes,d):
    if any(type(k) is not int or k<1 for k in (features,bins,classes,d)) or classes<2 or bins<2 or (features+bins+classes)*d>MAX:raise ValueError('shape budget')

def _x(x,features,bins,d):
    x=np.asarray(x)
    if x.ndim!=2 or x.shape[1]!=features or len(x)==0 or x.dtype.kind not in 'iu' or np.any(x<0) or np.any(x>=bins) or x.size*d>MAX:raise ValueError('invalid input or activation budget')
    return torch.from_numpy(x.astype(np.int64,copy=True))

def _y(y,n,c):
    y=np.asarray(y)
    if y.shape!=(n,) or y.dtype.kind not in 'iu' or np.any(y<0) or np.any(y>=c):raise ValueError('invalid labels')
    return torch.from_numpy(y.astype(np.int64,copy=True))

def ste_sign(w):
    hard=torch.where(w>=0,torch.ones_like(w),-torch.ones_like(w))
    return w+(hard-w).detach()

class TrainableItems(nn.Module):
    """THDC-like position/value binding, summation, binary linear readout, STE.
    Mean bundle scaling is an explicit independent conditioning choice.
    """
    def __init__(self,features,bins,classes,d,seed=0,*,learn_items=True):
        super().__init__();_dims(features,bins,classes,d)
        g=torch.Generator().manual_seed(seed);self.shape=features,bins,classes,d
        self.position=nn.Parameter(torch.randn(features,d,generator=g),requires_grad=learn_items)
        self.value=nn.Parameter(torch.randn(bins,d,generator=g),requires_grad=learn_items)
        self.classifier=nn.Parameter(torch.randn(classes,d,generator=g)*.1)
    def forward(self,x):
        f,b,c,d=self.shape;x=_x(x,f,b,d)
        h=(self.position[None,:,:]*self.value[x]).sum(1)/math.sqrt(f*d)
        return h@ste_sign(self.classifier).T
    def logical_inference_bytes(self):
        return 4*(self.position.numel()+self.value.numel())+(self.classifier.numel()+7)//8
    def exported(self):
        return tuple(t.detach().numpy().copy() for t in (self.position,self.value,torch.where(self.classifier>=0,1,-1).to(torch.int8)))

def exported_scores(x,p,v,w):
    f,d=p.shape;x=_x(x,f,len(v),d).numpy()
    return (p[None,:,:]*v[x]).sum(1)/math.sqrt(f*d)@w.T

def notch(q,g,bits,tau):
    q=np.asarray(q);g=np.asarray(g)
    if type(bits)is not int or not 2<=bits<=8 or q.dtype!=np.uint8 or q.shape!=g.shape or q.size>MAX or np.any(q>=2**bits) or not np.isfinite(g).all() or not math.isfinite(tau) or tau<0:raise ValueError('invalid notch input')
    delta=np.where(np.abs(g)>tau,-np.sign(g),0).astype(np.int16)
    return ((q.astype(np.int16)+delta)%(2**bits)).astype(np.uint8)

def phase_logits(x,p,v,w,bits):
    """Continuous extension in index units, modulus of complex class dot / D/T."""
    a=2*math.pi/(2**bits);d=p.shape[1]
    h=torch.exp(1j*a*(p[None,:,:]+v[x])).sum(1)
    z=h@torch.exp(-1j*a*w).T
    return torch.sqrt(z.real.square()+z.imag.square()+1e-12)/(d*.3)

class PhaseMemory:
    """Actual persistent state is uint8 indices; packed bit count is hypothetical.
    Threshold rule has no moments. SGD/Adam controls project one continuous
    optimizer step back to the same grid and do not retain a latent copy.
    """
    def __init__(self,features,bins,classes,d,bits=6,seed=0,*,rule='threshold',tau=3e-5,lr=1.):
        _dims(features,bins,classes,d)
        if type(bits)is not int or not 2<=bits<=8 or rule not in ('threshold','sgd','adam','adam6') or not math.isfinite(tau) or tau<0 or not math.isfinite(lr) or lr<=0:raise ValueError('invalid policy')
        self.shape=features,bins,classes,d;self.bits=bits;self.rule=rule;self.tau=tau;self.lr=lr
        rng=np.random.default_rng(seed);self.tables=tuple(rng.integers(0,2**bits,(n,d),dtype=np.uint8) for n in (features,bins,classes));self.step=0
        self.m=self.v=None
        if rule in ('adam','adam6'):
            self.m=tuple(np.zeros(t.shape,np.float32) for t in self.tables);self.v=tuple(np.zeros_like(t,dtype=np.float32) for t in self.tables)
    def tensors(self,grad=False):return tuple(torch.tensor(q,dtype=torch.float32,requires_grad=grad) for q in self.tables)
    def scores(self,x):
        f,b,c,d=self.shape
        with torch.no_grad():return phase_logits(_x(x,f,b,d),*self.tensors(),self.bits).numpy()
    def update(self,x,y):
        f,b,c,d=self.shape; x=_x(x,f,b,d);y=_y(y,len(x),c);q=self.tensors(True)
        loss=F.cross_entropy(phase_logits(x,*q,self.bits),y);g=tuple(z.detach().numpy() for z in torch.autograd.grad(loss,q))
        if not all(np.isfinite(v).all() for v in g):raise ValueError('nonfinite gradient')
        t=self.step+1;new=[];mm=[];vv=[]
        for i,(a,b) in enumerate(zip(self.tables,g)):
            if self.rule=='threshold':z=notch(a,b,self.bits,self.tau)
            else:
                if self.rule=='sgd':delta=-self.lr*b
                else:
                    m=.9*self.m[i]+.1*b;v=.999*self.v[i]+.001*b*b
                    if self.rule=='adam6':
                        # Independent per-table uniform fake quantization; stored floats
                        # intentionally counted as floats, not claimed packed moments.
                        ms=max(float(np.max(np.abs(m))),1e-20)/31;vs=max(float(v.max()),1e-20)/63
                        m=np.round(m/ms)*ms;v=np.round(v/vs)*vs
                    mm.append(m);vv.append(v);delta=-self.lr*(m/(1-.9**t))/(np.sqrt(v/(1-.999**t))+1e-8)
                z=np.mod(np.rint(a.astype(float)+delta),2**self.bits).astype(np.uint8)
            new.append(z)
        writes=sum(int(np.count_nonzero(a!=b)) for a,b in zip(self.tables,new));self.tables=tuple(new);self.step=t
        if mm:self.m=tuple(mm);self.v=tuple(vv)
        return float(loss.detach()),writes
    def persistent_array_bytes(self):return sum(t.nbytes for t in self.tables)+(sum(t.nbytes for t in (*self.m,*self.v)) if self.m is not None else 0)
    def ideal_grid_bytes(self):return (sum(t.size for t in self.tables)*self.bits+7)//8


def hinge(x,y,w,lam):
    """Zero-bias binary mean hinge + lambda*||w||^2/2; ties use zero subgradient."""
    x=np.asarray(x,dtype=np.float64);y=np.asarray(y);w=np.asarray(w,dtype=np.float64)
    if x.ndim!=2 or not len(x) or x.size>MAX or y.shape!=(len(x),) or np.any(~np.isin(y,[-1,1])) or w.shape!=(x.shape[1],) or not np.isfinite(x).all() or not np.isfinite(w).all() or not math.isfinite(lam) or lam<=0:raise ValueError('bad margin inputs')
    m=1-y*(x@w);bad=m>0
    return float(np.maximum(m,0).mean()+lam*(w@w)/2),lam*w-(x[bad].T@y[bad])/len(x)

def margin_fit(x,y,lam=.01,epochs=100):
    """Independent bounded full-batch subgradient with decreasing step."""
    x=np.asarray(x,dtype=float);w=np.zeros(x.shape[1]);best=w.copy();val=float('inf')
    if type(epochs)is not int or not 1<=epochs<=2000:raise ValueError('epoch budget')
    scale=max(1.,float(np.linalg.norm(x,axis=1).max()))
    for t in range(1,epochs+1):
        loss,g=hinge(x,y,w,lam)
        if loss<val:best=w.copy();val=loss
        w-=g/(scale*math.sqrt(t))
    return best

def channel_bind(x,p,v):
    """Bipolar RGB/other channels; p either shared [pixels,D] or [channels,pixels,D]."""
    x,p,v=map(np.asarray,(x,p,v))
    if x.ndim!=3 or not all(x.shape) or x.dtype.kind not in 'iu' or p.ndim not in (2,3) or v.ndim!=2 or p.shape[-1]!=v.shape[-1] or p.shape[-2]!=x.shape[2] or (p.ndim==3 and p.shape[0]!=x.shape[1]) or np.any(x<0) or np.any(x>=len(v)) or not np.isin(p,[-1,1]).all() or not np.isin(v,[-1,1]).all() or x.size*v.shape[1]>MAX:raise ValueError('invalid channel encoding')
    return (v[x].astype(np.int32)*p).sum(axis=(1,2))

def informative(x,y,w):
    """Train-only P,Q, delta and signed harmonic relevance per class/dimension."""
    x,y,w=map(np.asarray,(x,y,w))
    if x.ndim!=2 or w.ndim!=2 or x.shape[1]!=w.shape[1] or not len(x) or x.size>MAX or y.shape!=(len(x),) or y.dtype.kind not in 'iu' or np.any(y<0) or np.any(y>=len(w)) or len(w)<2 or not np.isin(x,[-1,1]).all() or not np.isin(w,[-1,1]).all():raise ValueError('invalid bipolar evidence')
    p=[];q=[]
    for i,row in enumerate(w):
        same=y==i
        if not same.any() or same.all():raise ValueError('missing class')
        match=x==row;p.append(match[same].mean(0));q.append(match[~same].mean(0))
    p,q=np.array(p),np.array(q);delta=p-q;den=p+1-q
    sh=np.sign(delta)*np.divide(2*p*(1-q),den,out=np.zeros_like(p),where=den>0)
    return p,q,delta,sh

def thermometer(k,q,m):
    k,q=np.asarray(k),np.asarray(q)
    if type(m)is not int or not 1<=m<=128 or k.dtype.kind not in 'iu' or k.shape!=q.shape or k.size*m>MAX or np.any(k<0) or np.any(k>m) or not np.isin(q,[-1,1]).all():raise ValueError('invalid thermometer')
    return q[...,None]*np.where(np.arange(m)<k[...,None],1,-1)

def expanded_dot(x,k,q,m):
    """Exact score of quantized representation, not arbitrary real weights."""
    bits=thermometer(k,q,m);x=np.asarray(x)
    if x.ndim!=2 or bits.ndim!=3 or x.shape[1]!=bits.shape[1] or not np.isin(x,[-1,1]).all() or x.size*m>MAX or len(x)*len(bits)>MAX:raise ValueError('bad input')
    return np.repeat(x,m,axis=1).astype(np.int64)@bits.reshape(len(bits),-1).astype(np.int64).T
