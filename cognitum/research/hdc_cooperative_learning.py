"""Bounded offline HDC learning references (research only; no network/controller).
Independent mechanisms, not author-code reproductions.
"""
import numpy as np


def bipolar(x):
    return np.where(np.asarray(x)>=0,1,-1).astype(np.int8)


def codebook(n,d,seed):
    if min(n,d)<1 or n*d>2**23:raise ValueError('codebook size')
    return np.random.default_rng(seed).choice(np.array([-1,1],np.int8),size=(n,d))


def unit(x):
    x=np.asarray(x,dtype=np.float64)
    return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-12)


class OfflineQ:
    """Semi-gradient Q learning on fixed behavior replay; terminal bootstrap zero."""
    def __init__(self,features,actions,alpha=.1,gamma=.95):
        f=np.asarray(features,dtype=np.float64)
        if f.ndim!=2 or not np.isfinite(f).all() or actions<1 or not(0<alpha<=1 and 0<=gamma<1):raise ValueError('Q configuration')
        self.f=unit(f);self.w=np.zeros((actions,f.shape[1]));self.alpha=alpha;self.gamma=gamma
    def q(self,s):return self.w@self.f[s]
    def update(self,s,a,r,n,done):
        if not (0<=s<len(self.f) and 0<=n<len(self.f) and 0<=a<len(self.w)) or not np.isfinite(r):raise ValueError('transition')
        err=r+(0 if done else self.gamma*self.q(n).max())-self.q(s)[a]
        self.w[a]+=self.alpha*err*self.f[s];return float(err)
    @property
    def numeric_bytes(self):return self.f.nbytes+self.w.nbytes


def grid_features(side,d,seed):
    x=codebook(side,d,seed);y=codebook(side,d,seed+1)
    return (x[:,None,:]*y[None,:,:]).reshape(side*side,d)


def sums(h,y,classes):
    h=np.asarray(h,dtype=np.float64);y=np.asarray(y)
    if h.ndim!=2 or y.shape!=(len(h),) or not np.issubdtype(y.dtype,np.integer) or np.any((y<0)|(y>=classes)) or not np.isfinite(h).all():raise ValueError('training rows')
    p=np.zeros((classes,h.shape[1]));np.add.at(p,y,h);return p


def scores(h,p):return unit(h)@unit(p).T


def local_update(h,y,global_model,lr=.25,epochs=1):
    p=np.asarray(global_model,dtype=np.float64).copy();h=np.asarray(h,dtype=np.float64);y=np.asarray(y)
    if epochs<1 or lr<=0 or not np.isfinite(p).all():raise ValueError('local configuration')
    for _ in range(epochs):
        for a,b in zip(h,y):
            v=int(np.argmax(scores(a[None,:],p)[0]))
            if v!=b:p[b]+=lr*a;p[v]-=lr*a
    return p-global_model


def aggregate(updates,counts,method='weighted',trim=1,clip=None):
    u=np.asarray(updates,dtype=np.float64);n=np.asarray(counts,dtype=np.float64)
    if u.ndim!=3 or n.shape!=(len(u),) or np.any(n<=0) or not np.isfinite(u).all() or not np.isfinite(n).all():raise ValueError('clients')
    if clip is not None:
        if not np.isfinite(clip) or clip<=0:raise ValueError('clip')
        norms=np.linalg.norm(u.reshape(len(u),-1),axis=1);u=u*np.minimum(1,clip/np.maximum(norms,1e-12))[:,None,None]
    if method=='weighted':return np.average(u,axis=0,weights=n)
    if method=='median':return np.median(u,axis=0)
    if method=='trimmed':
        if trim<1 or 2*trim>=len(u):raise ValueError('trim')
        return np.sort(u,axis=0)[trim:-trim].mean(0)
    raise ValueError('aggregation')


def pack_update(u,flip=0.,seed=0):
    """One bit per coordinate + per-client float32 mean absolute magnitude.
    Communication simulation only; no cryptographic or DP claim.
    """
    u=np.asarray(u,dtype=np.float64)
    if not u.size or not np.isfinite(u).all() or not 0<=flip<=1:raise ValueError('update')
    scale=np.float32(np.mean(np.abs(u)));bits=(u.ravel()>=0)
    if flip:bits^=np.random.default_rng(seed).random(u.size)<flip
    packed=np.packbits(bits,bitorder='little');decoded=(2*np.unpackbits(packed,bitorder='little',count=u.size).astype(np.float64)-1)*scale
    return decoded.reshape(u.shape),packed.nbytes+scale.nbytes


def pseudo_train(h_l,y_l,h_u,classes,margin=.15,rounds=3,limit=64):
    """SemiHD-inspired confidence-gap self-training, no unlabeled labels accepted."""
    if margin<0 or rounds<0 or limit<1:raise ValueError('pseudo config')
    p=sums(h_l,y_l,classes);remaining=np.arange(len(h_u));accepted=[];labels=[]
    for _ in range(rounds):
        if not len(remaining):break
        s=scores(h_u[remaining],p);s[:,np.linalg.norm(p,axis=1)==0]=-np.inf
        if np.count_nonzero(np.linalg.norm(p,axis=1))<2:break
        order=np.argsort(-s,axis=1,kind='stable');gap=s[np.arange(len(s)),order[:,0]]-s[np.arange(len(s)),order[:,1]]
        ix=np.flatnonzero(gap>=margin);ix=ix[np.argsort(-gap[ix],kind='stable')][:limit]
        if not len(ix):break
        ids=remaining[ix];y=order[ix,0];p+=sums(h_u[ids],y,classes);accepted.extend(ids.tolist());labels.extend(y.tolist());remaining=np.delete(remaining,ix)
    return p,np.asarray(accepted,dtype=np.int64),np.asarray(labels,dtype=np.int64)


def multiprototype(h,y,classes,k,seed):
    """SearcHD-inspired class-local binary vector quantization, not paper stochastic training."""
    from sklearn.cluster import KMeans
    p=[];labels=[]
    for c in range(classes):
        x=h[y==c]
        if not len(x):continue
        if k==1:cent=x.mean(0)[None,:]
        else:cent=KMeans(n_clusters=min(k,len(x)),n_init=2,random_state=seed).fit(x).cluster_centers_
        p.extend(bipolar(cent));labels.extend([c]*len(cent))
    return np.asarray(p,dtype=np.int8),np.asarray(labels,dtype=np.int64)


def packed_predict(h,p,labels):
    a=np.packbits(np.asarray(h)>0,axis=1,bitorder='little');b=np.packbits(np.asarray(p)>0,axis=1,bitorder='little')
    lut=np.array([i.bit_count() for i in range(256)],dtype=np.uint8)
    return np.asarray(labels)[np.array([np.argmin(lut[np.bitwise_xor(x,b)].sum(axis=1)) for x in a])]


def stochastic_binary_train(h,y,p,labels,seed,epochs=2,alpha=.25):
    """SearcHD-inspired stochastic attraction to closest true-class binary prototype.
    No claim of exact full SearcHD encoder or published wrong-class update.
    """
    p=p.copy();rng=np.random.default_rng(seed)
    if not 0<=alpha<=1 or epochs<0:raise ValueError('binary update')
    for _ in range(epochs):
        for v,c in zip(h,y):
            ids=np.flatnonzero(labels==c)
            if not len(ids):raise ValueError('missing class prototype')
            dist=np.mean(p[ids]!=v,axis=1);j=ids[dist.argmin()];mask=(p[j]!=v)&(rng.random(len(v))<alpha*float(dist.min()));p[j,mask]=v[mask]
    return p


def task_superpose(models,keys):
    """TP-inspired bind/bundle shared equal-class-count heads; exact linear unbinding plus interference."""
    m=np.asarray(models,dtype=np.float64);k=np.asarray(keys)
    if m.ndim!=3 or k.shape!=(m.shape[0],m.shape[2]) or not np.all(abs(k)==1):raise ValueError('task shape')
    return np.sum(m*k[:,None,:],axis=0)


def task_recover(merged,key):return np.asarray(merged)*np.asarray(key)


def cascade_predict(coarse,fine,threshold):
    """MHD-inspired confidence cascade using separately trained encoders."""
    a=np.asarray(coarse);b=np.asarray(fine)
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]<2:raise ValueError('cascade shape')
    order=np.argsort(-a,axis=1,kind='stable');margin=a[np.arange(len(a)),order[:,0]]-a[np.arange(len(a)),order[:,1]];route=margin<threshold
    return np.where(route,b.argmax(1),order[:,0]),route


def binary_cluster(h,k,seed,iterations=8):
    """HDCluster-inspired Hamming assignment and majority centroid refresh."""
    rng=np.random.default_rng(seed);h=np.asarray(h,dtype=np.int8)
    if h.ndim!=2 or not np.all(abs(h)==1) or not 1<=k<=len(h) or iterations<1:raise ValueError('cluster config')
    p=h[rng.choice(len(h),k,replace=False)].copy();ids=np.arange(k)
    for _ in range(iterations):
        labels=packed_predict(h,p,ids);old=p.copy()
        for j in ids:
            if np.any(labels==j):p[j]=bipolar(h[labels==j].sum(0))
        if np.array_equal(p,old):break
    return p
