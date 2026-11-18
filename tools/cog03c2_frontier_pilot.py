"""Fixed split real digits and seeded fixed-set MAP-I theory pilot, CPU only.
Use same kernel and train landmarks; report model arrays, serialized descriptors,
query working buffers and isolated peak process RSS, not just final HV bytes.
"""
import argparse, json, time, math, platform, sys, subprocess
from pathlib import Path
import numpy as np
from cognitum.research.hdc_frontier_encoders import NysHD,StreamedNysHD,GaussianPhase,map_i_membership_bound,intersection_variance
from cognitum.research.hdc_encoders import pack, digest

SEEDS=(52711,52729,52747,52769,52783)

def capacity():
    rows=[]
    for d in (256,1024,4096,8192):
        for n in (8,32,128):
            for seed in SEEDS:
                rng=np.random.default_rng(seed);bank=rng.integers(0,2,size=(256,d),dtype=np.int8).astype(np.int32)*2-1
                a=rng.choice(256,n,replace=False);b=rng.choice(256,n,replace=False)
                y=np.isin(np.arange(256),a);v=bank[a].sum(0,dtype=np.int32);score=bank@v/d
                est=float(v.astype(np.int64)@bank[b].sum(0,dtype=np.int64)/d); truth=len(set(a)&set(b))
                rows.append(dict(d=d,n=n,seed=seed,fn=int(np.sum(y&(score<.5))),fp=int(np.sum(~y&(score>=.5))),queries=256,point_bound=map_i_membership_bound(d,n),union_bound=map_i_membership_bound(d,n,256),intersection=est,truth=truth,variance=intersection_variance(d,n,n,truth)))
    return rows

def rbf(x,z):
    return np.stack([np.exp(-.015*np.square(x-v).sum(axis=1)) for v in z],axis=1)

def digits(arm,seed,dimension=1024):
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    from sklearn.svm import SVC
    import resource
    x,y=load_digits(return_X_y=True);x=x.astype(np.float64)/4
    train,test=train_test_split(np.arange(len(x)),test_size=.25,stratify=y,random_state=seed)
    if arm=='svc':
        t=time.perf_counter();model=SVC(kernel='rbf',gamma=.015,C=1).fit(x[train],y[train]);build=time.perf_counter()-t;t=time.perf_counter();pred=model.predict(x[test]);infer=time.perf_counter()-t
        arrays=sum(v.nbytes for v in vars(model).values() if isinstance(v,np.ndarray))
        return dict(arm=arm,seed=seed,dimension=dimension,correct=int(np.sum(pred==y[test])),n=len(test),build_s=build,infer_s=infer,payload_bytes=arrays,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,split=digest(test),pred=digest(pred))
    lm=np.random.default_rng(seed).choice(train,64,replace=False);z=x[lm].copy()
    t=time.perf_counter();a=rbf(x[train],z);g=rbf(z,z)
    if arm=='stream':enc=StreamedNysHD.fit(g,dimension,seed)
    elif arm=='nystrom':enc=StreamedNysHD.fit(g,dimension,seed)
    else:enc=NysHD.fit(g,dimension,seed)
    if arm=='nystrom':
        a=a@enc.inverse_root;a/=np.linalg.norm(a,axis=1,keepdims=True);encoder_bytes=enc.inverse_root.nbytes
    else:
        def transform(v):
            if arm=='stream':p=enc.packed(v);bits=np.unpackbits(p,axis=1,count=dimension,bitorder='little').astype(bool)
            else:bits=enc.bits(v)
            return 1-2*bits.astype(np.int8)
        a=transform(a);encoder_bytes=enc.nbytes
    c=np.stack([a[y[train]==k].sum(axis=0,dtype=np.float64 if arm=='nystrom' else np.int32) for k in range(10)])
    norm=np.linalg.norm(c,axis=1);build=time.perf_counter()-t;t=time.perf_counter()
    b=rbf(x[test],z)
    if arm=='nystrom':
        b=b@enc.inverse_root;b/=np.linalg.norm(b,axis=1,keepdims=True)
    else:b=transform(b)
    pred=np.argmax((b@c.T)/norm,axis=1);infer=time.perf_counter()-t
    return dict(arm=arm,seed=seed,dimension=dimension,correct=int(np.sum(pred==y[test])),n=len(test),build_s=build,infer_s=infer,payload_bytes=encoder_bytes+z.nbytes+c.nbytes+norm.nbytes+4*10+16,encoder_bytes=encoder_bytes,landmarks_bytes=z.nbytes,centroids_bytes=c.nbytes,norm_bytes=norm.nbytes,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,split=digest(test),pred=digest(pred))

def main():
    p=argparse.ArgumentParser();p.add_argument('--child',choices=['resident','stream','nystrom','svc']);p.add_argument('--seed',type=int);p.add_argument('--dimension',type=int,default=1024);p.add_argument('--out',default='c2-pilot.json');p.add_argument('--quick',action='store_true');a=p.parse_args()
    if a.child:print(json.dumps(digits(a.child,a.seed,a.dimension)));return
    result={'schema':'cognitum.cog03c2.pilot.v1','platform':platform.platform(),'numpy':np.__version__,'capacity':capacity(),'digits':[],'notes':'Linux isolated child RSS includes Python, imports, train/build/query arrays and scratch; portable payload includes explicit numeric model arrays and descriptors for HDC arms, not all interpreter metadata or serialized artifact overhead. SVC counts ndarray state only. NysHD resident vs streamed identical dimension, seed, landmarks and split. No end-to-end host claims.'}
    for seed in SEEDS[:2] if a.quick else SEEDS:
        for arm in ('resident','stream','nystrom','svc'):
            result['digits'].append(json.loads(subprocess.check_output([sys.executable,'-m','tools.cog03c2_frontier_pilot','--child',arm,'--seed',str(seed)],text=True)))
    Path(a.out).write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
