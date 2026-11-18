"""Independent SupHDC-inspired real random Fourier feature reference.
No cross-context batching. Explicit slot permutation, signed keys and clean fallback.
"""
import numpy as np

def unit(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-12)
class Shared:
    def __init__(self,features,d,slots,classes,seed,bandwidth=1.):
        if not 1<=slots<=8 or not 2<=classes<=64 or not 1<=features<=4096 or not 1<=d<=65536:raise ValueError('shape bounds')
        self.k,self.c,self.f,self.d=slots,classes,features,d
        rng=np.random.default_rng(seed);self.w=(rng.standard_normal((features,d))*bandwidth).astype(np.float32);self.b=rng.uniform(0,2*np.pi,d).astype(np.float32)
        self.perm=np.stack([rng.permutation(features) for _ in range(slots)]).astype(np.int32);self.sign=rng.choice(np.array([-1,1],np.float32),(slots,features))
    def enc(self,x):return unit(np.cos(x@self.w+self.b))
    def keyed(self,x,k):return x[...,self.perm[k]]*self.sign[k]
    def fit(self,x,y,seed,epochs=2):
        x=np.asarray(x,np.float32);y=np.asarray(y);rng=np.random.default_rng(seed)
        if x.ndim!=2 or x.shape[1]!=self.f or y.shape!=(len(x),) or set(y)!=set(range(self.c)) or len(x)<self.k:raise ValueError('training')
        self.clean=np.stack([unit(np.stack([self.enc(self.keyed(x[y==j],k)).sum(0) for j in range(self.c)])) for k in range(self.k)])
        self.adapt=self.clean.copy();work=self.adapt.copy()
        for epoch in range(epochs):
            ix=rng.permutation(len(x));ix=ix[:len(ix)//self.k*self.k].reshape(-1,self.k)
            for group in ix:
                z=self.enc(sum(self.keyed(x[group[k]],k) for k in range(self.k)))
                for k,t in enumerate(y[group]):
                    s=self.adapt[k]@z;j=int(s.argmax())
                    if j!=t:
                        work[k,t]+=.05*(1-s[t])*z;work[k,j]-=.05*s[j]*z
                        self.adapt[k]=unit(work[k])
        return self
    def predict(self,x,mode='shared',fallback=0.):
        x=np.asarray(x,np.float32)
        if x.ndim!=3 or x.shape[1:]!=(self.k,self.f) or not 0<=fallback<=1 or mode not in ('shared','batch','sequential'):raise ValueError('group input')
        n=len(x);keyed=np.stack([self.keyed(x[:,k],k) for k in range(self.k)],axis=1)
        if mode=='shared':s=np.einsum('nd,kcd->nkc',self.enc(keyed.sum(1)),self.adapt);calls=n
        elif mode=='batch':s=np.einsum('nkd,kcd->nkc',self.enc(keyed.reshape(-1,self.f)).reshape(n,self.k,self.d),self.clean);calls=n*self.k
        else:
            s=np.stack([np.stack([self.clean[k]@self.enc(v[k]) for k in range(self.k)]) for v in keyed]);calls=n*self.k
        pred=s.argmax(2);m=np.sort(s,axis=2);m=m[:,:,-1]-m[:,:,-2]
        if mode=='shared' and fallback:
            i=np.argsort(m.ravel(),kind='stable')[:int(np.ceil(fallback*n*self.k))];rows,slots=np.divmod(i,self.k)
            z=self.enc(keyed[rows,slots]);pred[rows,slots]=np.einsum('nd,ncd->nc',z,self.clean[slots]).argmax(1);calls+=len(i)
        return pred,calls
    @property
    def bytes(self):return sum(a.nbytes for a in (self.w,self.b,self.perm,self.sign,self.clean,self.adapt))
