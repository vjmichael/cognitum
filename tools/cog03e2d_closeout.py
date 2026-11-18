"""Fixed-seed train/calibration/test controls. Numeric retained payload caps only."""
import argparse,json,time
from pathlib import Path
import numpy as np
from sklearn.datasets import make_blobs,load_wine,load_breast_cancer,load_digits
from sklearn.metrics import adjusted_rand_score,normalized_mutual_info_score,roc_auc_score,average_precision_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.neighbors import LocalOutlierFactor,NearestNeighbors
from sklearn.covariance import LedoitWolf
from cognitum.research.hdc_stream_discovery import ThermometerProjection, IDLevel, IncrementalLouvain, DensityDistance, hamming
from cognitum.research.hdc_discovery_closeout import CalibratedLouvain, PackedDensity, BoundedWorld
from tools.cog03e2d_pilot import synthetic


def cluster(seed,quick):
    r=np.random.default_rng(seed);x,y=make_blobs(n_samples=300 if quick else 600,centers=4,n_features=8,cluster_std=1.5,random_state=seed)
    known=r.permutation(np.flatnonzero(y!=3));n=len(known)//3;train=known[:n];cal=known[n:2*n];test=r.permutation(np.r_[known[2*n:],np.flatnonzero(y==3)])
    w,z=load_wine(return_X_y=True);i=r.permutation(len(w));a=len(w)//3
    rows=[]
    for dataset,x,y,tr,ca,te in [('novel_blobs',x,y,train,cal,test),('wine',w,z,i[:a],i[a:2*a],i[2*a:])]:
        enc=ThermometerProjection(x.shape[1],64,8,seed).fit(x[tr]);h,c,t=[enc.encode(x[q]) for q in (tr,ca,te)]
        for order in ('random','reverse'):
            ids=np.arange(len(te)) if order=='random' else np.arange(len(te))[::-1]
            for quantile in (None,.90,.95,.99):
                m=CalibratedLouvain(k=8,capacity=128,threshold=.13,seed=seed);boot=m.fit(h)
                if quantile is not None:m.calibrate(c,quantile=quantile)
                start=time.perf_counter();p=np.asarray([m.assign(t[j]) for j in ids]);seconds=time.perf_counter()-start;truth=y[te[ids]]
                rows.append(dict(dataset=dataset,seed=seed,order=order,quantile=quantile,threshold=m.thresholds.get(0,.13),ari=adjusted_rand_score(truth,p),nmi=normalized_mutual_info_score(truth,p),clusters=len(set(p)-{-1}),bootstrap=len(set(boot)),refused=int((p<0).sum()),n=len(p),numeric_bytes=m.nbytes+enc.nbytes,seconds=seconds))
    return rows


def drift(seed,quick):
    # Controlled already-encoded binary input, not a wafer dataset. Labels used only in metrics.
    r=np.random.default_rng(seed);dim=512;codes=np.zeros((7,dim),np.uint8);codes[1:]=r.integers(0,2,(6,dim),dtype=np.uint8)
    def make(mode,n):return codes[mode]^(r.random((n,dim))<.025).astype(np.uint8)
    a,c=make(0,40),make(0,30);n=12 if quick else 30
    phases=[(0,1,2),(0,3,4),(0,5,6),(0,1,2)]
    stream=[];labels=[];phaseids=[]
    for phase, modes in enumerate(phases):
        v=np.vstack([make(k,n) for k in modes]);y=np.repeat(modes,n);i=r.permutation(len(y));stream.extend(v[i]);labels.extend(y[i]);phaseids.extend([phase]*len(i))
    stream=np.asarray(stream);y=np.asarray(labels);phaseids=np.asarray(phaseids);rows=[]
    for budget in (6*1024,10*1024):
        # exact logical arrays + declared scalar metadata; fixed common bank and dim.
        cap=(budget-((40+3)*64+64))//(2*dim+40)
        for policy in ('refuse','temporary','lru'):
            m=BoundedWorld(a,c,capacity=cap,policy=policy,idle=n,limit=32,match=.12,coherence=.18,seed=seed);pred=[];persistent=[];peak=m.nbytes
            start=time.perf_counter()
            for h in stream:
                k,p,_=m.observe(h);pred.append(k);persistent.append(p);peak=max(peak,m.nbytes);assert peak<=budget
            duration=time.perf_counter()-start;p=np.asarray(pred);flag=np.asarray(persistent);anomaly=y!=0;old=np.isin(y,[1,2])&(phaseids==3);novel=(phaseids==2)&anomaly
            # Freeze a map from first phase solely for retrospective evaluation. Never fed back to model.
            identities={k:(int(np.bincount(p[(phaseids==0)&(y==k)&(p>0)]).argmax()) if np.any((phaseids==0)&(y==k)&(p>0)) else -2) for k in (1,2)}
            hit=np.asarray([v==identities.get(int(k),-2) and v>0 for v,k in zip(p,y)])
            rows.append(dict(seed=seed,budget=budget,policy=policy,capacity=cap,peak_numeric_bytes=peak,n=len(y),evictions=m.evictions,assignment_coverage=float((p[anomaly]>0).mean()),promotion_coverage=float(flag[anomaly].mean()),old_identity_retention=float(hit[old].mean()),late_novel_coverage=float((p[novel]>0).mean()),fpr=float((p[~anomaly]!=0).mean()),tpr=float((p[anomaly]!=0).mean()),ari=adjusted_rand_score(y[anomaly],p[anomaly]),seconds=duration))
    return rows


def split_real(seed,ds,quick):
    r=np.random.default_rng(seed)
    if ds=='breast_cancer':
        x,y=load_breast_cancer(return_X_y=True);normal=x[y==1];bad=x[y==0]
    else:
        x,y=load_digits(return_X_y=True);normal=x[y==0];bad=x[y!=0]
    normal=normal[r.permutation(len(normal))];bad=bad[r.permutation(len(bad))];n=len(normal)//2;m=len(normal)//5
    a,c,t=normal[:n],normal[n:n+m],normal[n+m:];bad=bad[:len(t)]
    if quick:a,c,t,bad=a[:40],c[:20],t[:20],bad[:20]
    return a,c,np.vstack([t,bad]),np.r_[np.zeros(len(t)),np.ones(len(bad))]


def anomaly(seed,quick):
    rows=[]
    for dataset,split in [('synthetic',synthetic(seed,quick)),('breast_cancer',split_real(seed,'breast_cancer',quick)),('digits_zero',split_real(seed,'digits_zero',quick))]:
        a,c,t,truth=split;scaler=StandardScaler().fit(a);a,c,t=[scaler.transform(x) for x in (a,c,t)];scale_bytes=sum(getattr(scaler,k).nbytes for k in ('mean_','scale_','var_'))
        # lower-dimensional ID bank to fit at least two rows even with all 64 input features
        enc=IDLevel(a.shape[1],256,16,seed).fit(a);ha=enc.encode(a);hc=enc.encode(c);ht=enc.encode(t)
        for budget in (32*1024,64*1024):
            order=np.random.default_rng(seed).permutation(len(a))
            for arm in ('hd_dense','hd_packed','raw_density','knn','lof','isolation_forest','ocsvm','shrinkage_covariance'):
                start=time.perf_counter();n=len(a);cap=True
                if arm in ('hd_dense','hd_packed'):
                    width=256 if arm=='hd_dense' else 32;overhead=enc.nbytes+scale_bytes+16;n=min(n,(budget-overhead)//(width+8));assert n>=2
                    m=(DensityDistance(True) if arm=='hd_dense' else PackedDensity()).fit(ha[order[:n]]);fn=m.score;cal,test=hc,ht;payload=overhead+m.ref.nbytes+m.rho.nbytes
                    if arm=='hd_packed':
                        oracle=DensityDistance(True).fit(ha[order[:n]]);assert np.array_equal(fn(ht),oracle.score(ht))
                elif arm in ('raw_density','knn'):
                    n=min(n,(budget-scale_bytes-16)//(8*a.shape[1]+8));assert n>=2
                    if arm=='raw_density':m=DensityDistance().fit(a[order[:n]]);fn=m.score;payload=scale_bytes+16+m.ref.nbytes+m.rho.nbytes
                    else:
                        m=NearestNeighbors(n_neighbors=min(5,n),algorithm='brute').fit(a[order[:n]]);fn=lambda v:m.kneighbors(v)[0].mean(1);payload=scale_bytes+m._fit_X.nbytes+16
                    cal,test=c,t
                else:
                    # full-training conventional comparisons, NOT claimed within matched caps
                    if budget!=32*1024:continue
                    cap=False;payload=None;cal,test=c,t
                    if arm=='lof':m=LocalOutlierFactor(n_neighbors=min(20,n-1),novelty=True).fit(a);fn=lambda v:-m.score_samples(v)
                    elif arm=='isolation_forest':m=IsolationForest(n_estimators=100,random_state=seed,n_jobs=1).fit(a);fn=lambda v:-m.score_samples(v)
                    elif arm=='ocsvm':m=OneClassSVM(nu=.05).fit(a);fn=lambda v:-m.decision_function(v)
                    else:m=LedoitWolf().fit(a);fn=m.mahalanobis
                fit=time.perf_counter()-start;threshold=float(np.quantile(fn(cal),.95));start=time.perf_counter();scores=fn(test);seconds=time.perf_counter()-start;flags=scores>threshold
                assert np.isfinite(scores).all() and (not cap or payload<=budget)
                rows.append(dict(dataset=dataset,seed=seed,arm=arm,budget=budget if cap else None,n_train=n,n_test=len(t),numeric_bytes=payload,roc_auc=roc_auc_score(truth,scores),pr_auc=average_precision_score(truth,scores),fpr=float(flags[truth==0].mean()),tpr=float(flags[truth==1].mean()),fit_seconds=fit,score_seconds=seconds,score_time_scope='preencoded input' if arm.startswith('hd_') else 'prestandardized input'))
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out',required=True);args=p.parse_args();r=dict(scope='independent software references; train/calibration/test disjoint; numeric retained array budgets include encoder/scaler and declared metadata, exclude allocators/training scratch; general conventional arms unmatched; not full author datasets or physical timings',clustering=[],drift=[],anomaly=[])
    for s in ([701] if args.quick else [701,709,719]):
        r['clustering']+=cluster(s,args.quick);r['drift']+=drift(s,args.quick);r['anomaly']+=anomaly(s,args.quick)
    Path(args.out).write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
