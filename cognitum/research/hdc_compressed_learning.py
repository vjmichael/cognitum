"""Bounded compressed classifier references. Research only.
Native ties are not a portable ordering promise; NumPy references use stable ties.
Packed ternary signs preserve zeros, including tied encoder sums.
"""
from __future__ import annotations
import numpy as np
from .hdc_learning import _matrix, _labels, cosine_scores, MAX_ELEMENTS


def ternary(a):
    a=np.asarray(a)
    if a.ndim!=2 or not all(a.shape) or a.size>MAX_ELEMENTS or a.dtype.kind not in 'if' or not np.isin(a,[-1,0,1]).all():
        raise ValueError('bounded ternary matrix required')
    return a.astype(np.int8,copy=False)


def frozen(a):
    return np.frombuffer(a.tobytes(),dtype=a.dtype).reshape(a.shape)


class PackedTernary:
    """Two planes (positive, negative), canonical zero padding and exact dot."""
    def __init__(self, rows):
        v=ternary(rows);self._shape=v.shape
        self._pos=frozen(np.packbits(v>0,axis=1,bitorder='little'))
        self._neg=frozen(np.packbits(v<0,axis=1,bitorder='little'))
    @property
    def shape(self):return self._shape
    @property
    def bytes(self):return self._pos.nbytes+self._neg.nbytes
    def planes(self):return self._pos,self._neg
    def scores(self, probe):
        if not isinstance(probe,PackedTernary) or probe.shape[1]!=self.shape[1] or probe.shape[0]*self.shape[0]>MAX_ELEMENTS:raise ValueError('packed score mismatch')
        p,n=probe.planes();a,b=self.planes();out=np.empty((len(p),len(a)),np.int32)
        # The working set is O(codeword bytes), not Q*C*D.
        for j in range(len(a)):
            for i in range(len(p)):
                same=np.bitwise_count(p[i]&a[j]).sum(dtype=np.int32)+np.bitwise_count(n[i]&b[j]).sum(dtype=np.int32)
                diff=np.bitwise_count(p[i]&b[j]).sum(dtype=np.int32)+np.bitwise_count(n[i]&a[j]).sum(dtype=np.int32)
                out[i,j]=same-diff
        return out
    def decode(self):
        p,n=self.planes();d=self.shape[1]
        return np.unpackbits(p,axis=1,count=d,bitorder='little').astype(np.int8)-np.unpackbits(n,axis=1,count=d,bitorder='little').astype(np.int8)


class PackedLevels:
    """Bipolar feature/level tables, packed at one bit per coordinate.
    Input range fixed to [0,1]. Native float32 nearest-even rounding;
    one feature at a time XOR/accumulate, preserving zero ties.
    """
    def __init__(self, keys, levels):
        k,l=ternary(keys),ternary(levels)
        if k.shape[1]!=l.shape[1] or len(l)<2 or len(k)>32767 or np.any(k==0) or np.any(l==0):raise ValueError('bipolar tables required')
        self.features,self.dimension=k.shape;self.levels=len(l)
        self._keys=frozen(np.packbits(k<0,axis=1,bitorder='little'));self._levels=frozen(np.packbits(l<0,axis=1,bitorder='little'))
    @property
    def bytes(self):return self._keys.nbytes+self._levels.nbytes
    def encode(self,x):
        x=np.asarray(x)
        if x.ndim!=2 or x.dtype!=np.float32 or not len(x) or x.shape[1]!=self.features or x.size>MAX_ELEMENTS or len(x)*self.dimension>MAX_ELEMENTS or not np.isfinite(x).all():raise ValueError('invalid feature matrix')
        idx=np.rint(np.clip(x,0,1)*np.float32(self.levels-1)).astype(np.intp)
        result=np.empty((len(x),self.dimension),np.int8)
        for i,row in enumerate(idx):
            acc=np.zeros(self.dimension,np.int32)
            for j,k in enumerate(row):
                neg=np.unpackbits(self._keys[j]^self._levels[k],count=self.dimension,bitorder='little')
                acc+=1-2*neg.astype(np.int32)
            result[i]=np.sign(acc)
        return result


def fold(rows, keys):
    """CompHD chunk-binding SUM; not sign-fold. Preserve chunk key geometry."""
    a=np.asarray(rows);k=ternary(keys)
    if a.ndim!=2 or a.dtype.kind not in 'if' or not all(a.shape) or a.size>MAX_ELEMENTS or not np.isfinite(a).all() or a.shape[1]!=k.size or np.any(k==0):raise ValueError('invalid CompHD operands')
    r=(a.reshape(len(a),*k.shape)*k).sum(1,dtype=np.float64)
    if not np.isfinite(r).all():raise ValueError('nonfinite fold')
    return r


def prune(w, sparsity, mode='dimension'):
    """Corrected SparseHD contract: fraction REMOVED, stable low-index ties.
    Native 5.8.4 computes the complement and class scatter is not in-place.
    """
    w=_matrix(w,complex_ok=False);c,d=w.shape
    if not np.isfinite(sparsity) or not 0<=sparsity<=1 or mode not in ('dimension','class'):raise ValueError('invalid pruning policy')
    n=round(sparsity*d);out=w.copy()
    if mode=='dimension':out[:,np.argsort(np.ptp(w,axis=0),kind='stable')[:n]]=0
    else:np.put_along_axis(out,np.argsort(np.abs(w),axis=1,kind='stable')[:,:n],0,axis=1)
    return out


class SparseRows:
    """Exact sparse cosine prototype readout, immutable per-row index/value storage."""
    def __init__(self,w):
        w=_matrix(w,complex_ok=False);self.shape=w.shape
        self._idx=[];self._val=[];self._norm=frozen(np.linalg.norm(w.astype(np.float64),axis=1))
        for row in w:
            idx=np.flatnonzero(row).astype(np.uint16 if w.shape[1]<=65536 else np.uint32)
            self._idx.append(frozen(idx));self._val.append(frozen(row[idx]))
        self._idx=tuple(self._idx);self._val=tuple(self._val)
    @property
    def bytes(self):return sum(a.nbytes+b.nbytes for a,b in zip(self._idx,self._val))+self._norm.nbytes+4*(len(self._idx)+1)
    def scores(self,x):
        x=_matrix(x,complex_ok=False)
        if x.shape[1]!=self.shape[1] or len(x)*self.shape[0]>MAX_ELEMENTS:raise ValueError('sparse score mismatch')
        a=x.astype(np.float64);n=np.linalg.norm(a,axis=1);out=np.empty((len(x),self.shape[0]))
        for j,(i,v) in enumerate(zip(self._idx,self._val)):out[:,j]=(a[:,i]@v.astype(np.float64))/np.maximum(n*self._norm[j],1e-8)
        return out


def quant_train(x,y,classes,*,epochs=4,lr=.035,batch=32):
    """Native QuantHD epoch-frozen ternary prediction, float32 counts."""
    x=_matrix(x,complex_ok=False);ternary(x);y=_labels(y,len(x),classes)
    if type(classes) is not int or not 2<=classes<=4096 or classes*x.shape[1]>MAX_ELEMENTS or type(epochs) is not int or not 1<=epochs<=200 or type(batch) is not int or batch<1 or not np.isfinite(lr) or not 0<lr<=1:raise ValueError('invalid quant training budget')
    c=np.zeros((classes,x.shape[1]),x.dtype);np.add.at(c,y,x);w=np.sign(c)
    for _ in range(1,epochs):
        for i in range(0,len(y),batch):
            z=x[i:i+batch];t=y[i:i+batch];p=(z@w.T).argmax(1);bad=p!=t
            np.add.at(c,t[bad],lr*z[bad]);np.add.at(c,p[bad],-lr*z[bad])
        w=np.sign(c)
    return c,w


def lehdc_train(x,y,classes,*,epochs=4,lr=.01,batch=32,weight_decay=.003):
    """Independent preencoded straight-through Adam, no dropout arm.
    Gradients of the ternary forward model copied to real-valued shadow.
    Native ReduceLROnPlateau semantics, no test-data tuning.
    """
    import torch
    a=_matrix(x,complex_ok=False);ternary(a);y=_labels(y,len(a),classes)
    if type(classes) is not int or not 2<=classes<=4096 or classes*a.shape[1]>MAX_ELEMENTS or type(epochs) is not int or not 1<=epochs<=200 or type(batch) is not int or batch<1 or not np.isfinite(lr) or lr<=0 or not np.isfinite(weight_decay) or weight_decay<0:raise ValueError('invalid training budget')
    tx=torch.tensor(a);ty=torch.tensor(y);shadow=torch.nn.Parameter(torch.zeros((classes,a.shape[1]),dtype=tx.dtype));opt=torch.optim.Adam([shadow],lr=lr,weight_decay=weight_decay);scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau(opt,patience=2)
    for _ in range(epochs):
        total=0.
        for i in range(0,len(y),batch):
            w=shadow.detach().sign().requires_grad_();loss=torch.nn.functional.cross_entropy(tx[i:i+batch]@w.T,ty[i:i+batch]);total+=loss.detach().item();opt.zero_grad();loss.backward();shadow.grad=w.grad;opt.step()
        scheduler.step(total)
    return shadow.detach().numpy().copy(),shadow.detach().sign().numpy().copy()


def sparse_train(x,y,classes,*,epochs=4,lr=.035,batch=32,sparsity=.75,mode='dimension'):
    """Mistake-driven batch correction followed by explicit epoch pruning."""
    x=_matrix(x,complex_ok=False);ternary(x);y=_labels(y,len(x),classes)
    if type(classes) is not int or not 2<=classes<=4096 or classes*x.shape[1]>MAX_ELEMENTS or type(epochs) is not int or not 1<=epochs<=200 or type(batch) is not int or batch<1 or not np.isfinite(lr) or not 0<lr<=1:raise ValueError('invalid sparse training budget')
    w=np.zeros((classes,x.shape[1]),x.dtype)
    for _ in range(epochs):
        for i in range(0,len(y),batch):
            z=x[i:i+batch];t=y[i:i+batch];p=cosine_scores(z,w).argmax(1);bad=p!=t
            np.add.at(w,t[bad],lr*z[bad]);np.add.at(w,p[bad],-lr*z[bad])
        w=prune(w,sparsity,mode)
    return w


class PackedFold:
    """CompHD position keys retained as bits; reconstruct one chunk at a time."""
    def __init__(self,keys):
        k=ternary(keys)
        if np.any(k==0):raise ValueError('bipolar chunk keys required')
        self._shape=k.shape;self._bits=frozen(np.packbits(k<0,axis=1,bitorder='little'))
    @property
    def bytes(self):return self._bits.nbytes
    def fold(self,rows):
        a=np.asarray(rows);c,d=self._shape
        if a.ndim!=2 or not all(a.shape) or a.dtype.kind not in 'if' or a.size>MAX_ELEMENTS or a.shape[1]!=c*d or not np.isfinite(a).all():raise ValueError('invalid packed fold input')
        out=np.zeros((len(a),d),np.float64)
        for i,b in enumerate(self._bits):
            signs=1-2*np.unpackbits(b,count=d,bitorder='little').astype(np.int8)
            out+=a[:,i*d:(i+1)*d]*signs
        if not np.isfinite(out).all():raise ValueError('nonfinite packed fold')
        return out
