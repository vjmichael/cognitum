"""Bounded independent E2B extensions; CPU references, no production routing.
Actual packed state is counted; transient unpacking and autograd are separate.
"""
import numpy as np
import torch
from torch.nn import functional as F
from .hdc_frontier_learning import PhaseMemory, phase_logits, _x, _y, informative, channel_bind, MAX


def pack6(x):
    x=np.asarray(x)
    if x.dtype!=np.uint8 or not x.size or x.size>MAX or np.any(x>63):raise ValueError('invalid six-bit array')
    return np.packbits(((x.reshape(-1,1)>>np.arange(6,dtype=np.uint8))&1).ravel(),bitorder='little')


def unpack6(p,shape):
    n=int(np.prod(shape));p=np.asarray(p)
    if not 0<n<=MAX or p.dtype!=np.uint8 or p.shape!=((6*n+7)//8,):raise ValueError('invalid packed payload')
    if 6*n%8 and int(p[-1])>>(6*n%8):raise ValueError('noncanonical padding')
    return (np.unpackbits(p,count=6*n,bitorder='little').reshape(n,6)@np.array([1,2,4,8,16,32],np.uint8)).reshape(shape)


def quantize_moments(m,v):
    if not np.isfinite(m).all() or not np.isfinite(v).all() or np.any(v<0):raise ValueError('invalid moments')
    ms=np.float32(max(float(np.max(np.abs(m))),1e-20)/31);vs=np.float32(max(float(v.max()),1e-20)/63)
    a=np.clip(np.rint(m/ms),-31,31).astype(np.int16);b=np.clip(np.rint(v/vs),0,63).astype(np.uint8)
    return (a+31).astype(np.uint8),b,ms,vs


class PackedPhaseAdam(PhaseMemory):
    """Actual six-bit signed-offset/unsigned moments with float32 scales.
    Pack grid as well. Compare against explicit dense identical quantizer control.
    No latent floating weights or moment arrays retained in packed arm.
    """
    def __init__(self,*args,packed=True,**kwargs):
        if kwargs.pop('bits',6)!=6 or 'rule' in kwargs:raise ValueError('six-bit Adam only')
        super().__init__(*args,bits=6,rule='threshold',**kwargs);self.packed=packed
        self.shapes=tuple(t.shape for t in self.tables)
        self.scales=tuple((np.float32(1),np.float32(1)) for _ in self.tables)
        zero=tuple(np.zeros(s,np.uint8) for s in self.shapes)
        self.mc=tuple(self._store(z+31) for z in zero);self.vc=tuple(self._store(z) for z in zero)
        self.tables=tuple(self._store(t) for t in self.tables)
    def _store(self,a):return pack6(a) if self.packed else a.copy()
    def _read(self,a,s):return unpack6(a,s) if self.packed else a.copy()
    def codes(self):return tuple(self._read(a,s) for a,s in zip(self.tables,self.shapes))
    def tensors(self,grad=False):return tuple(torch.tensor(q,dtype=torch.float32,requires_grad=grad) for q in self.codes())
    def update(self,x,y):
        f,b,c,d=self.shape;x=_x(x,f,b,d);y=_y(y,len(x),c);q=self.tensors(True)
        loss=F.cross_entropy(phase_logits(x,*q,6),y);grads=tuple(g.detach().numpy() for g in torch.autograd.grad(loss,q));t=self.step+1
        new=[];mm=[];vv=[];ss=[];writes=0
        for i,(a,g,s) in enumerate(zip(self.codes(),grads,self.shapes)):
            ms,vs=self.scales[i];m=(self._read(self.mc[i],s).astype(np.float32)-31)*ms;v=self._read(self.vc[i],s).astype(np.float32)*vs
            mc,vc,ms,vs=quantize_moments(.9*m+.1*g,.999*v+.001*g*g)
            m=(mc.astype(np.float32)-31)*ms;v=vc.astype(np.float32)*vs
            delta=-self.lr*(m/(1-.9**t))/(np.sqrt(v/(1-.999**t))+1e-8)
            z=np.mod(np.rint(a.astype(float)+delta),64).astype(np.uint8);writes+=int(np.count_nonzero(a!=z))
            new.append(self._store(z));mm.append(self._store(mc));vv.append(self._store(vc));ss.append((ms,vs))
        self.tables=tuple(new);self.mc=tuple(mm);self.vc=tuple(vv);self.scales=tuple(ss);self.step=t
        return float(loss.detach()),writes
    def persistent_array_bytes(self):return sum(a.nbytes for a in (*self.tables,*self.mc,*self.vc))+8*len(self.shapes)
    def ideal_grid_bytes(self):return sum((6*np.prod(s)+7)//8 for s in self.shapes).item()


def class_union(x,y,w,threshold):
    """Independent per-class positive relevance threshold and exact union.
    Train-only selection; empty union refuses rather than silently changing gate.
    """
    if not np.isfinite(threshold) or not 0<=threshold<=1:raise ValueError('threshold')
    _,_,delta,sh=informative(x,y,w);m=(delta>threshold)|(sh>threshold)
    return m,np.flatnonzero(m.any(0))


def packed_expanded_dot(x,k,q,m):
    """Actual packed thermometer readout, streaming classwise XOR/popcount.
    Per-row padding is ignored through the original logical length.
    """
    from .hdc_frontier_learning import thermometer
    x=np.asarray(x);w=thermometer(k,q,m)
    if x.ndim!=2 or w.ndim!=3 or x.shape[1]!=w.shape[1] or not np.isin(x,[-1,1]).all() or x.size*m>MAX or len(x)*len(w)>MAX:raise ValueError('bad inputs')
    p=np.packbits(np.repeat(x<0,m,axis=1),axis=1,bitorder='little');b=np.packbits(w.reshape(len(w),-1)<0,axis=1,bitorder='little');out=np.empty((len(x),len(b)),np.int64);n=x.shape[1]*m
    for j,v in enumerate(b):out[:,j]=n-2*np.bitwise_count(p^v).sum(1,dtype=np.int64)
    return out,b.nbytes
