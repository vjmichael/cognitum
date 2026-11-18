"""Independent E2G closeout mechanisms. Offline research only."""
import struct
import numpy as np
from .hdc_cooperative_learning import codebook, aggregate, unit

LUT=np.array([i.bit_count() for i in range(256)],dtype=np.uint8)

def packed_bits(b):return np.packbits(b,axis=-1,bitorder='little')
def distances(q,p):return LUT[np.bitwise_xor(q,p)].sum(axis=-1,dtype=np.int32)

class RecordEncoder:
    """Correlated level vectors, ID XOR, majority; optional ordered adjacent pair binding."""
    def __init__(self,features,d,levels,seed):
        if not 1<=features<=512 or not 8<=d<=8192 or not 2<=levels<=64:raise ValueError('encoder bounds')
        self.d=d;self.features=features;self.levels=levels
        rng=np.random.default_rng(seed);self.ids=packed_bits(rng.integers(0,2,(features,d),dtype=np.uint8));v=rng.integers(0,2,d,dtype=np.uint8);bank=[v.copy()]
        for _ in range(levels-1):
            v[rng.choice(d,max(1,d//levels),replace=False)]^=1;bank.append(v.copy())
        self.bank=packed_bits(np.array(bank))
    @property
    def numeric_bytes(self):return self.ids.nbytes+self.bank.nbytes
    def encode(self,x,pairs=False):
        x=np.asarray(x,dtype=float)
        if x.shape!=(self.features,) or not np.all(np.isfinite(x)):raise ValueError('record')
        k=np.rint(np.clip(x,0,1)*(self.levels-1)).astype(int)
        counts=np.zeros(self.d,np.int16);prev=None;n=0
        for i,j in enumerate(k):
            b=np.unpackbits(self.ids[i]^self.bank[j],count=self.d,bitorder='little');counts+=b;n+=1
            if pairs and prev is not None:counts+=prev^np.roll(b,1);n+=1
            prev=b
        return packed_bits(counts*2>=n)
    def batch(self,x,pairs=False):return np.stack([self.encode(row,pairs) for row in x])

class PackedSearch:
    """SearcHD class-local random initialization and p=alpha*distance/D substitution.
    RNG generates transient masks; packed state is authoritative. No analog hardware claim.
    """
    def __init__(self,h,y,d,k,seed):
        h=np.asarray(h,dtype=np.uint8);y=np.asarray(y);self.d=int(d);self.rng=np.random.default_rng(seed)
        if h.ndim!=2 or h.shape[1]!=(d+7)//8 or y.shape!=(len(h),) or k<1 or len(h)==0:raise ValueError('prototype shape')
        if d%8 and np.any(h[:,-1]>>(d%8)):raise ValueError('noncanonical padding')
        ids=[]
        for c in np.unique(y):
            selected=np.flatnonzero(y==c)
            ids.extend(self.rng.choice(selected,min(k,len(selected)),replace=False))
        self.p=h[ids].copy();self.labels=y[ids].astype(np.int32)
    @property
    def numeric_bytes(self):return self.p.nbytes+self.labels.nbytes
    def update(self,q,c,alpha,repel=False):
        if not 0<=alpha<=1:raise ValueError('alpha')
        q=np.asarray(q,dtype=np.uint8)
        if q.shape!=(self.p.shape[1],) or (self.d%8 and q[-1]>>(self.d%8)):raise ValueError('query padding')
        ds=distances(q,self.p);ids=np.flatnonzero(self.labels==c)
        if not len(ids):raise ValueError('unknown class')
        j=ids[ds[ids].argmin()];mask=packed_bits(self.rng.random(self.d)<alpha*ds[j]/self.d)
        self.p[j]^=(self.p[j]^q)&mask
        wrong=int(ds.argmin())
        if repel and self.labels[wrong]!=c:
            mask=packed_bits(self.rng.random(self.d)<alpha*(1-ds[wrong]/self.d));self.p[wrong]^=(~(self.p[wrong]^q))&mask
        return int(j)
    def fit(self,h,y,alpha=.5,epochs=1,repel=False):
        for _ in range(epochs):
            for q,c in zip(h,y):self.update(q,c,alpha,repel)
        return self
    def predict(self,h):return np.array([self.labels[distances(q,self.p).argmin()] for q in h])
    def decision(self,q):
        ds=distances(q,self.p);cs=np.unique(self.labels);best=np.array([ds[self.labels==c].min() for c in cs]);o=np.argsort(best,kind='stable');return int(cs[o[0]]),float((best[o[1]]-best[o[0]])/self.d)

class LazyCascade:
    def __init__(self,coarse,fine,coarse_head,fine_head,threshold):self.coarse=coarse;self.fine=fine;self.a=coarse_head;self.b=fine_head;self.threshold=threshold;self.calls=0;self.fine_calls=0
    def predict(self,x):
        out=[]
        for row in x:
            a,g=self.a.decision(self.coarse.encode(row));self.calls+=1
            if g<self.threshold:a,_=self.b.decision(self.fine.encode(row,pairs=True));self.fine_calls+=1
            out.append(a)
        return np.asarray(out)
    @property
    def numeric_bytes(self):return self.coarse.numeric_bytes+self.fine.numeric_bytes+self.a.numeric_bytes+self.b.numeric_bytes

class GridQ:
    """No state-feature cache; exact tabular or normalized generated features."""
    def __init__(self,side,kind,d,seed,actions=4):
        self.side=side;self.kind=kind;self.d=d;self.seed=seed
        if kind=='tabular':self.w=np.zeros((side*side,actions),np.float32);self.keys=None
        else:
            self.w=np.zeros((actions,d),np.float32)
            self.keys=codebook(side*2,d,seed) if kind=='bound' else None
    @property
    def numeric_bytes(self):return self.w.nbytes+(0 if self.keys is None else self.keys.nbytes)+24
    def feature(self,s):
        x,y=divmod(s,self.side)
        if self.kind=='bound':return (self.keys[x]*self.keys[self.side+y]).astype(np.float32)/np.sqrt(self.d)
        if self.kind=='seeded':return codebook(1,self.d,self.seed+s*104729)[0].astype(np.float32)/np.sqrt(self.d)
        if self.kind=='fourier':
            # Deterministic low frequency cosine features (conventional linear Q).
            j=np.arange(self.d);return unit(np.cos(np.pi*((j%int(np.sqrt(self.d)))*x+(j//int(np.sqrt(self.d)))*y)/(self.side-1))).astype(np.float32)
        raise ValueError('feature kind')
    def q(self,s):return self.w[s] if self.kind=='tabular' else self.w@self.feature(s)
    def update(self,s,a,r,n,done,alpha=.18,gamma=.95):
        err=r+(0 if done else gamma*self.q(n).max())-self.q(s)[a]
        if self.kind=='tabular':self.w[s,a]+=alpha*err
        else:self.w[a]+=alpha*err*self.feature(s)
        return float(err)

# Explicit in-memory frame protocol. Header comprises length, client count, scale.
HEADER=struct.Struct('<II f')
def encode_frame(u,count,packed):
    a=np.asarray(u,dtype='<f4').ravel()
    if not len(a) or count<1 or not np.isfinite(a).all():raise ValueError('frame')
    scale=float(np.mean(np.abs(a),dtype=np.float64)) if packed else 0.
    return HEADER.pack(len(a),count,scale)+(packed_bits(a>=0).tobytes() if packed else a.tobytes())
def decode_frame(frame,shape,packed):
    if len(frame)<HEADER.size:raise ValueError('short frame')
    n,count,scale=HEADER.unpack_from(frame);expected=(n+7)//8 if packed else n*4
    if n!=int(np.prod(shape)) or n<1 or count<1 or len(frame)!=HEADER.size+expected or not np.isfinite(scale) or scale<0 or (not packed and scale!=0):raise ValueError('frame shape')
    a=np.frombuffer(frame,offset=HEADER.size,dtype=np.uint8 if packed else '<f4')
    if packed:
        if n%8 and a[-1]>>(n%8):raise ValueError('padding')
        a=(2*np.unpackbits(a,count=n,bitorder='little').astype(np.float32)-1)*scale
    if not np.isfinite(a).all():raise ValueError('frame values')
    return a.reshape(shape),count

def softmax_update(x,y,w,lr=.3,epochs=1):
    """Conventional local softmax SGD; same client examples and rounds."""
    p=w.copy()
    for _ in range(epochs):
        for a,b in zip(x,y):
            s=p@a;s=np.exp(s-s.max());s/=s.sum();s[b]-=1;p-=lr*s[:,None]*a
    return p-w


def hdc_local_update(x,y,w,lr=.3):
    """Float32 class-head updates; no float64 copy of the whole classifier."""
    p=w.copy()
    for a,b in zip(x,y):
        norm=np.sqrt(np.einsum('ij,ij->i',p,p));s=(p@a)/np.maximum(norm,1e-12);v=int(s.argmax())
        if v!=b:p[b]+=lr*a;p[v]-=lr*a
    return p-w
