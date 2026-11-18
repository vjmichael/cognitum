"""Linux exploratory pilot. Per-arm independent child peak RSS, logical payload cap."""
import argparse,json,math,time,resource,sys,subprocess
import numpy as np
from cognitum.research.hdc_encoders import CodebookSpec,coherence
from cognitum.research.hdc_frontier_encoders import IndexedMAP
from cognitum.research.hdc_dynamic_spatial import VDCToggle,SpatialSketch,SparseProjection,QuasiNormalLevels
from cognitum.research.hdc_capacity import MAPBSet,BloomSketch,map_b_error
SEEDS=(52811,52819,52837,52843,52859)
def sets(arm):
    rows=[]
    for budget in (4096,16384):
      for n in (127,511):
       for seed in SEEDS:
        r=np.random.default_rng(seed);ids=sorted(map(int,r.choice(2**20,n,replace=False)));truth=set(ids)
        yes=list(map(int,r.choice(ids,128,replace=True)));no=[]
        while len(no)<128:
            x=int(r.integers(2**20))
            if x not in truth:no.append(x)
        q=yes+no;r.shuffle(q);actual=np.array([x in truth for x in q])
        start=time.perf_counter();theory=None
        if arm=='exact':
            a=np.array(ids,np.uint32);payload=a.nbytes+16
            def predict(i):
                j=np.searchsorted(a,i);return j<len(a) and a[j]==i
        elif arm=='map-i':
            d=(budget-16-4*n)//2;a=IndexedMAP(d,seed,n)
            for i in ids:a.add(i)
            payload=a.accounting()['payload_bytes'];predict=lambda i:a.score(i)>=.5
        elif arm=='map-b':
            d=min(65536,(budget-24)*8);a=MAPBSet(d,seed,ids);payload=a.payload_bytes;predict=a.contains;theory=map_b_error(d,n)
        else:
            count=arm=='counting';m=min(65536,(budget-32)//2 if count else (budget-32)*8);k=min(16,max(1,round(m/n*math.log(2))))
            a=BloomSketch(m,k,seed,ids,count);payload=a.payload_bytes;predict=a.contains
        build=time.perf_counter()-start;assert payload<=budget
        start=time.perf_counter();p=np.array([predict(i) for i in q],bool);elapsed=time.perf_counter()-start
        batch_s=None
        if arm=='exact':
            t=time.perf_counter();j=np.searchsorted(a,q);batch=(j<len(a))&(a[np.minimum(j,len(a)-1)]==q);batch_s=time.perf_counter()-t;assert np.array_equal(batch,p)
        est=None
        if arm=='counting':
            other=ids[:n//2]+list(range(2**20,2**20+n-n//2));b=BloomSketch(m,k,seed,other,True);est=a.estimate_intersection(b)
        elif arm=='map-i':
            other=ids[:n//2];extra=iter(i for i in range(2**20) if i not in truth);other += [next(extra) for _ in range(n-len(other))];b=IndexedMAP(d,seed,n)
            for i in other:b.add(i)
            est=a.estimate_intersection(b)
        rows.append(dict(arm=arm,budget=budget,n=n,seed=seed,queries=len(q),fp=int((p&~actual).sum()),fn=int((~p&actual).sum()),payload=int(payload),build_s=build,query_s=elapsed,exact_batch_s=batch_s,intersection_estimate=est,intersection_truth=n//2 if est is not None else None,theory=theory))
    return rows

def dynamic():
    rows=[]
    for d in (128,512,1024):
        g=VDCToggle(d)
        for name in ('vdc-toggle','qnd','iid','hadamard'):
            start=time.perf_counter();a=np.stack([g.atom(i) for i in range(64)]) if name=='vdc-toggle' else np.stack([QuasiNormalLevels(d,64).symbol(i) for i in range(64)]) if name=='qnd' else CodebookSpec(d,52811,name).bits(64)
            rows.append(dict(method=name,d=d,n=64,seconds=time.perf_counter()-start,**coherence(a)))
    return rows

def spatial(arm):
    rows=[];x=np.array([(i,j) for i in np.linspace(0,1,5) for j in np.linspace(0,1,5)]);q=np.array([(i,j) for i in np.linspace(.125,.875,4) for j in np.linspace(.125,.875,4)])
    func=lambda p:.5+.25*np.sin(2*np.pi*p[:,0])+.2*np.cos(2*np.pi*p[:,1]);y=func(x);target=func(q);levels=np.linspace(0,1,33);w=np.array([.25,.25,.15])
    for seed in SEEDS:
        start=time.perf_counter()
        if arm in ('hrr','fhrr','half-fhrr'):
            a=SpatialSketch.fit(x,y,levels,512,seed,w,arm);payload=a.payload_bytes;build=time.perf_counter()-start
            start=time.perf_counter();pred=np.array([a.predict(z) for z in q]);elapsed=time.perf_counter()-start
        else:
            payload=x.nbytes+y.nbytes+8;build=time.perf_counter()-start;start=time.perf_counter();k=np.exp(-np.square(q[:,None]-x).sum(-1)/(2*.25**2));pred=k@y/k.sum(1);elapsed=time.perf_counter()-start
        rows.append(dict(arm=arm,seed=seed,n=len(q),mse=float(np.mean((pred-target)**2)),payload=payload,build_s=build,query_s=elapsed,pred=pred.tolist()))
    return rows

def sparse(arm):
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    from sklearn.svm import SVC
    x,y=load_digits(return_X_y=True);x=x/16;a,b,c,d=train_test_split(x,y,test_size=450,random_state=52811,stratify=y);start=time.perf_counter()
    if arm=='svc':
        model=SVC().fit(a,c);payload=sum(z.nbytes for z in [model.support_vectors_,model.dual_coef_,model.intercept_,model.classes_,model.n_support_,model.support_])+8;elapsed=time.perf_counter()-start;start=time.perf_counter();p=model.predict(b);qlat=time.perf_counter()-start;density=None
    else:
        enc=SparseProjection.fit(a,512,52811,.02,arm);counts=enc.counts(a);bits=counts>enc.threshold;hv=1-2*bits.astype(np.int32);protos=np.stack([hv[c==i].sum(0) for i in range(10)]).astype(np.int32);norm=np.maximum(np.linalg.norm(protos,axis=1),1e-12);payload=enc.payload_bytes+protos.nbytes+norm.nbytes+40;elapsed=time.perf_counter()-start;start=time.perf_counter();p=np.argmax((1-2*enc.bits(b).astype(np.int32))@protos.T/norm,axis=1);qlat=time.perf_counter()-start;density=float(counts.sum(dtype=np.int64)/(len(a)*a.shape[1]*enc.dimension))
    return [dict(arm=arm,n=len(d),correct=int((p==d).sum()),payload=payload,build_s=elapsed,query_s=qlat,bound_density=density)]
def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['set','dynamic','spatial','sparse'],required=True);p.add_argument('--arm');p.add_argument('--out');args=p.parse_args();resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));rows=dynamic() if args.mode=='dynamic' else {'set':sets,'spatial':spatial,'sparse':sparse}[args.mode](args.arm);result=dict(mode=args.mode,arm=args.arm,rows=rows,address_space_cap_bytes=512*1024**2,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);s=json.dumps(result,indent=2);open(args.out,'w').write(s+'\n') if args.out else print(s)
if __name__=='__main__':main()
