"""Independent duration and packed temporal research. No production routing."""
import numpy as np
from .hdc_temporal import CategoricalHMM, LDN, PackedPrototype, _obs


def duration_hmm(model, minimum):
    """Explicit minimum dwell via age expansion; geometric tail thereafter.
    No hidden-label knowledge or fitted duration distribution assumed.
    """
    if not isinstance(minimum,(int,np.integer)) or not 1<=minimum<=8:raise ValueError('minimum dwell 1..8')
    k=len(model.initial);d=int(minimum);p=np.zeros(k*d);p[::d]=model.initial
    a=np.zeros((k*d,k*d));b=np.repeat(model.emission,d,axis=0)
    for i in range(k):
        for age in range(d-1):a[i*d+age,i*d+age+1]=1
        for j in range(k):a[i*d+d-1,j*d+(d-1 if i==j else 0)]=model.transition[i,j]
    return CategoricalHMM(p,a,b)


def duration_tokens(seq,alphabet,edges=(1,2,4,8)):
    """Run tokens encode observed symbol and capped dwell bin, not hidden state."""
    a=_obs(seq,alphabet);edges=np.asarray(edges)
    if edges.ndim!=1 or len(edges)==0 or np.any(edges<1) or np.any(np.diff(edges)<=0):raise ValueError('invalid duration edges')
    cuts=np.r_[0,np.flatnonzero(a[1:]!=a[:-1])+1,len(a)]
    return a[cuts[:-1]]*(len(edges)+1)+np.searchsorted(edges,np.diff(cuts),side='left')


def adaptive_summary(sequence,order=4,theta=.3,normalized=False):
    """Known complete-window duration control; not causal unknown-length mode."""
    x=np.asarray(sequence,dtype=float)
    if x.ndim!=2 or not len(x) or not np.isfinite(x).all():raise ValueError('nonempty finite matrix')
    l=LDN(order,theta,1/len(x) if normalized else 1/64,x.shape[1]);mean=np.zeros_like(l.state);m2=mean.copy()
    for i,u in enumerate(x,1):
        z=l.step(u);delta=z-mean;mean+=delta/i;m2+=delta*(z-mean)
    return np.r_[l.state.ravel(),mean.ravel(),np.sqrt(np.maximum(m2/len(x),0)).ravel()]


def batched_summary(x,order=4,theta=.6,dt=.02):
    """Time-major recurrence for a bounded batch of separately reset windows."""
    x=np.asarray(x,dtype=float)
    if x.ndim!=3 or not 1<=len(x)<=64 or not x.shape[1] or not np.isfinite(x).all():raise ValueError('batch limit or bad samples')
    l=LDN(order,theta,dt,x.shape[2]);z=np.zeros((len(x),order,x.shape[2]));mean=z.copy();m2=z.copy()
    for i in range(x.shape[1]):
        z=l.Ad@z+l.Bd[None,:,None]*x[:,i,None,:];delta=z-mean;mean+=delta/(i+1);m2+=delta*(z-mean)
    return np.concatenate([a.reshape(len(x),-1) for a in (z,mean,np.sqrt(np.maximum(m2/x.shape[1],0)))],axis=1)


class SeededPackedHead:
    """Fixed projection regenerated from a seed in small blocks. Training uses
    bounded batches; numeric model size excludes draw scratch and NumPy RNG internals.
    """
    def __init__(self,dimension,seed,block=64):
        if not isinstance(dimension,int) or not 8<=dimension<=16384 or not 1<=block<=256:raise ValueError('dimensions')
        self.dimension=dimension;self.seed=int(seed);self.block=block
    def encode(self,z):
        z=np.asarray(z,dtype=np.float64)
        if z.ndim!=2 or len(z)>64 or z.shape[1]!=len(self.mean) or not np.isfinite(z).all():raise ValueError('bounded feature batch')
        r=np.random.default_rng(self.seed);v=(z-self.mean)/self.scale;out=np.empty((len(v),self.dimension),bool)
        for j in range(0,self.dimension,self.block):
            w=min(self.dimension-j,self.block);out[:,j:j+w]=(v@r.standard_normal((w,v.shape[1])).T)>=0
        return out
    def fit(self,x,y):
        x=np.asarray(x,dtype=float);y=np.asarray(y);self.labels=np.unique(y)
        if x.ndim!=2 or len(x)!=len(y) or not len(x) or not np.isfinite(x).all():raise ValueError('fit shape')
        self.mean=x.mean(0);self.scale=np.maximum(x.std(0),1e-8);counts=np.zeros((len(self.labels),self.dimension),np.int64)
        for j in range(0,len(x),64):
            z=self.encode(x[j:j+64]).astype(np.int64)*2-1
            for i,c in enumerate(self.labels):counts[i]+=z[y[j:j+64]==c].sum(0)
        self.head=PackedPrototype(counts);return self
    def predict(self,x):
        x=np.asarray(x,dtype=float);out=[]
        for j in range(0,len(x),64):
            z=self.encode(x[j:j+64]);q=np.packbits(z,axis=1,bitorder='little');d=np.bitwise_count(q[:,None,:]^self.head.bits[None,:,:]).sum(2);out.extend(self.labels[d.argmin(1)])
        return np.asarray(out,dtype=self.labels.dtype)
    @property
    def numeric_bytes(self):return self.mean.nbytes+self.scale.nbytes+self.labels.nbytes+self.head.numeric_bytes+24
